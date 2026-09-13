"""CLI entry point: ``python -m finhive.db.migrate``.

Thin wrapper so the launcher scripts
(run_local_mac.sh, run_local_windows.bat) can invoke
the migration runner as
``python -m finhive.db.migrate`` -- the module name is
the verb (what you do), while ``finhive.db.migrations``
is the noun (the library).
"""

from __future__ import annotations

from finhive.db.migrations import main

if __name__ == "__main__":
    raise SystemExit(main())
