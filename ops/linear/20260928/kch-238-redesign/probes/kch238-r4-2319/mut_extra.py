import subprocess, sys, os

T = sys.argv[1]
F = f"{T}/loan_manager/application/agent/tokeniser.py"
orig = open(F).read()

# Cycle-2 code was restructured enough that mut2.py's original string
# patterns for N3/N4/N8/N10/N16/N17 no longer appear verbatim (reported as
# "PATTERN 0" against the final code). These are the SAME properties,
# re-expressed as exact-match mutations against the CURRENT source.
M = {
    "N3' year context always true (old rule)": (
        "        and _is_year_context(text, start, end)\n",
        "        and True\n",
    ),
    "N4' 'of' re-added to year-context words": (
        '_YEAR_CONTEXT_WORDS = frozenset({"in", "since", "until", "till", "by", "year", "fy"})',
        '_YEAR_CONTEXT_WORDS = frozenset({"in", "since", "until", "till", "by", "year", "fy", "of"})',
    ),
    "N8' unit 'l' removed": (
        '_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|l|k|thousands?|hundreds?"',
        '_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|k|thousands?|hundreds?"',
    ),
    "N10' unclassified int/float/Decimal does not raise": (
        "        if isinstance(value, (int, float, Decimal)):\n            raise PlaintextLeakError(\n"
        "                f\"unclassified key carries a numeric value {value!r} -- add it to \"",
        "        if isinstance(value, (int, float, Decimal)) and False:\n            raise PlaintextLeakError(\n"
        "                f\"unclassified key carries a numeric value {value!r} -- add it to \"",
    ),
    "N16' TOKEN_RE widened to 3+ digits": (
        'TOKEN_RE = re.compile(r"\\b(?:[BDGQ][0-9]{3}|AMOUNT_[0-9]+)\\b")',
        'TOKEN_RE = re.compile(r"\\b(?:[BDGQ][0-9]{3,}|AMOUNT_[0-9]+)\\b")',
    ),
    "N17' leading punctuation no longer excluded from word spans": (
        "        if not _is_word_char(text[i]):\n            i += 1\n            continue\n",
        "        if False:\n            i += 1\n            continue\n",
    ),
}

tests = [
    "tests/unit/application/agent/test_tokeniser.py",
    "tests/unit/application/agent/test_tokeniser_egress.py",
]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", QT_QPA_PLATFORM="offscreen")

try:
    for name, (a, b) in M.items():
        if orig.count(a) != 1:
            print("PATTERN", orig.count(a), name)
            continue
        open(F, "w").write(orig.replace(a, b))
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", *tests],
            cwd=T,
            env=env,
            capture_output=True,
            text=True,
        )
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        fail = [l for l in lines if l.startswith("FAILED")]
        print(
            ("KILLED  " if r.returncode else "SURVIVED"),
            name,
            "|",
            (fail[0][:110] if fail else lines[-1][:90]),
        )
finally:
    open(F, "w").write(orig)
