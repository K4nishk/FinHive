"""KCH-234 regression: settings_tab.py used to write `self._settings` back
verbatim. If the initial load ever failed -- corrupt JSON, invalid UTF-8, a
non-object top level, or read while another tab wrote mid-write --
`self._settings` was `{}`, and the very next colour or theme change
overwrote data/settings.json with just `{"theme": ..., "custom_colours":
...}`, silently deleting the `llm` block (and anything else) a human never
touched.

`SettingsTab.__init__` builds a full PySide6 widget tree, which this test
must not do (`QT_QPA_PLATFORM=offscreen` makes it possible but slow and
unnecessary here). `SettingsTab.__new__(SettingsTab)` constructs an instance
without running `__init__` (`object.__new__` is refused by shiboken for a
QWidget subclass: "not safe, use SettingsTab.__new__()"), so
`_load_settings`/`_save_settings` -- plain methods that only touch
`self._settings`, `self._custom_colours`, `self._custom_colours_loaded`,
`self._main_window` and the module-level `SETTINGS_FILE` -- can be exercised
directly.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from loan_manager.presentation.tabs import settings_tab as settings_tab_module
from loan_manager.presentation.tabs.settings_tab import SettingsTab


def _bare_tab() -> SettingsTab:
    tab = SettingsTab.__new__(SettingsTab)
    tab._main_window = None
    return tab


class _StatusRecorder:
    """Stands in for `_main_window`: records every `show_status()` call so a
    test can see whether a later call overwrote an earlier one."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def show_status(self, message: str) -> None:
        self.messages.append(message)


def _llm_block(model: str) -> dict:
    return {
        "base_url": "https://openrouter.ai/api/v1",
        "model": model,
        "api_key_env": "OPENROUTER_API_KEY",
        "temperature": 0.1,
        "max_steps": 6,
        "timeout_s": 60,
    }


def test_corrupt_settings_file_is_not_overwritten(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{not valid json")
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._load_settings()
    assert tab._settings == {}

    tab._custom_colours = {"Active": {"background": "#00ff00"}}
    tab._save_settings()

    # the file on disk is untouched -- still not valid JSON, still the exact
    # bytes it started with. A successful (over)write would have replaced it
    # with valid JSON lacking every key this test never set.
    assert settings_file.read_text() == "{not valid json"


def test_invalid_utf8_settings_file_is_not_overwritten(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    original_bytes = b"\xff\xfe\x00bad-utf8-not-json"
    settings_file.write_bytes(original_bytes)
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._load_settings()  # must not raise
    assert tab._settings == {}

    tab._custom_colours = {"Active": {"background": "#00ff00"}}
    tab._save_settings()  # must not raise, must not overwrite

    assert settings_file.read_bytes() == original_bytes


def test_non_dict_json_settings_file_is_not_overwritten(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("[]")
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._load_settings()  # valid JSON, but not an object -- must not raise
    assert tab._settings == {}

    tab._custom_colours = {"Active": {"background": "#00ff00"}}
    tab._save_settings()  # must not raise, must not overwrite

    assert settings_file.read_text() == "[]"


def test_save_preserves_llm_block(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "theme": "dark", "custom_colours": {}, "llm": _llm_block("model-v1"),
    }))
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._load_settings()

    # The file changes on disk AFTER this tab's own load -- e.g. an app
    # restart rewrote data/settings.json's llm block. `self._settings` still
    # holds the OLD block; a verbatim write of it would clobber the new one
    # with data this tab never saw change. Read-modify-write must re-read
    # the file at save time and touch only theme/custom_colours, so the
    # current on-disk llm block survives untouched.
    settings_file.write_text(json.dumps({
        "theme": "dark", "custom_colours": {}, "llm": _llm_block("model-v2"),
    }))

    tab._settings["theme"] = "light"
    tab._custom_colours = {"Overdue": {"background": "#ff0000"}}
    tab._save_settings()

    on_disk = json.loads(settings_file.read_text())
    assert on_disk["theme"] == "light"
    assert on_disk["custom_colours"] == {"Overdue": {"background": "#ff0000"}}
    assert on_disk["llm"]["model"] == "model-v2"
    assert on_disk["llm"]["api_key_env"] == "OPENROUTER_API_KEY"


def test_failed_initial_load_does_not_wipe_current_on_disk_colours(tmp_path, monkeypatch) -> None:
    """KCH-234 review round 1, item 11: a tab whose very first load failed
    never actually saw real custom_colours -- its self._custom_colours is
    just __init__'s empty default, not an edit. If something else (another
    tab, a hand fix) repairs the file with real colours before this tab
    saves, a save must not clobber them with the empty default."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{not valid json")
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._load_settings()
    tab._custom_colours = {}  # this tab's own, never-loaded default

    # The file gets repaired with REAL colours this tab never saw.
    settings_file.write_text(json.dumps({
        "theme": "dark",
        "custom_colours": {"Active": {"background": "#00ff00"}},
    }))

    tab._settings["theme"] = "light"
    tab._save_settings()

    on_disk = json.loads(settings_file.read_text())
    assert on_disk["theme"] == "light"
    assert on_disk["custom_colours"] == {"Active": {"background": "#00ff00"}}


def test_missing_file_pick_colour_is_persisted(tmp_path, monkeypatch) -> None:
    """KCH-234 review round 2, item 1 (MAJOR): a fresh install / deleted
    settings.json used to leave `_custom_colours_loaded=False` forever, so
    every `_pick_colour` save wrote `{"theme": ...}` with no `custom_colours`
    key at all -- the very first colour a new user ever picks was silently
    dropped and gone on restart. `_load_settings` on a missing file is now a
    legitimate "loaded, nothing there yet" state, and `_pick_colour`'s save
    merges the edited status into whatever is freshly on disk."""
    settings_file = tmp_path / "settings.json"
    assert not settings_file.exists()
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._custom_colours = {}  # __init__'s own default, set before _load_settings()
    tab._load_settings()
    assert tab._custom_colours_loaded is True

    tab._custom_colours["Active"] = {"background": "#00ff00", "text": "#000000", "bold": True}
    tab._save_settings(edited_colour="Active")

    on_disk = json.loads(settings_file.read_text())
    assert on_disk["custom_colours"]["Active"]["background"] == "#00ff00"


def test_failed_load_then_repaired_file_pick_colour_is_persisted_and_others_kept(
    tmp_path, monkeypatch
) -> None:
    """KCH-234 review round 2, item 1 (MAJOR): the same loss also happened
    after a load that failed outright (corrupt JSON) and was later repaired
    by something else before this tab ever reloaded -- `_custom_colours_loaded`
    stayed False from the failed load, so the picked colour was still
    dropped, and it was also at risk of clobbering the OTHER colours the
    repair had put on disk. The merge-into-freshly-re-read-disk fix in
    `_save_settings` must both persist the new pick and keep the pre-existing
    on-disk colour."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{not valid json")
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._load_settings()
    assert tab._custom_colours_loaded is False
    tab._custom_colours = {}  # this tab's own, never-loaded default

    # Repaired by something else, with a colour this tab never saw.
    settings_file.write_text(json.dumps({
        "theme": "dark",
        "custom_colours": {"Overdue": {"background": "#ff0000"}},
    }))

    tab._custom_colours["Active"] = {"background": "#00ff00", "text": "#000000", "bold": True}
    tab._save_settings(edited_colour="Active")

    on_disk = json.loads(settings_file.read_text())
    assert on_disk["custom_colours"]["Active"]["background"] == "#00ff00"
    assert on_disk["custom_colours"]["Overdue"]["background"] == "#ff0000"


def test_pick_colour_wires_edited_colour_into_save(tmp_path, monkeypatch) -> None:
    """KCH-234 fix cycle 3: `_pick_colour` must call
    `self._save_settings(edited_colour=status)`, not a bare
    `self._save_settings()` -- the `edited_colour` kwarg is what makes
    `_save_settings` merge this pick into whatever `custom_colours` is
    freshly re-read from disk (see `_save_settings`'s own docstring), rather
    than gating on this tab's own (here: never-loaded) `_custom_colours_loaded`
    view. Drives the real `_pick_colour` method, with only
    `QColorDialog.getColor` monkeypatched, instead of calling
    `_save_settings(edited_colour=...)` directly as the other tests here do.

    Fail-first: change `_pick_colour`'s call to a bare `self._save_settings()`
    and this fails, because with `_custom_colours_loaded=False` the bare call
    takes `_save_settings`'s `else` branch (leaves on-disk `custom_colours`
    untouched) instead of the `edited_colour is not None` branch -- so
    `on_disk["custom_colours"]` never gains "Active" at all, only keeps the
    pre-existing "Overdue"."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{not valid json")
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._custom_colours = {}
    tab._load_settings()
    assert tab._custom_colours_loaded is False  # this tab never saw real colours

    # Repaired by something else, with a colour this tab never saw.
    settings_file.write_text(json.dumps({
        "theme": "dark",
        "custom_colours": {"Overdue": {"background": "#ff0000"}},
    }))

    tab._theme = SimpleNamespace(
        get_status_colour=lambda status: {
            "background": "#000000", "text": "#ffffff", "bold": True,
        }
    )
    tab._colour_buttons = {}
    tab._theme_combo = SimpleNamespace(currentText=lambda: "dark")
    fake_colour = SimpleNamespace(isValid=lambda: True, name=lambda: "#00ff00")
    monkeypatch.setattr(
        settings_tab_module.QColorDialog, "getColor", lambda *args, **kwargs: fake_colour
    )

    tab._pick_colour("Active")

    on_disk = json.loads(settings_file.read_text())
    assert on_disk["custom_colours"]["Active"]["background"] == "#00ff00"
    assert on_disk["custom_colours"]["Overdue"]["background"] == "#ff0000"


def test_apply_theme_does_not_overwrite_a_refused_save_status(tmp_path, monkeypatch) -> None:
    """KCH-234 review round 2, item 5 (minor): `_on_apply_theme` used to call
    `show_status("Theme changed to ...")` unconditionally, even when
    `_save_settings()` had just refused to write and already posted
    "Settings not saved: ...". The refusal message must be the last word."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("[]")  # valid JSON, not an object -- save refused
    monkeypatch.setattr(settings_tab_module, "SETTINGS_FILE", settings_file)

    tab = _bare_tab()
    tab._settings = {"theme": "dark"}
    tab._custom_colours = {}
    tab._custom_colours_loaded = False
    tab._theme_combo = SimpleNamespace(currentText=lambda: "light")
    recorder = _StatusRecorder()
    tab._main_window = recorder

    tab._on_apply_theme()

    assert recorder.messages == ["Settings not saved: existing settings file is unreadable."]
    assert "Theme changed to light." not in recorder.messages
