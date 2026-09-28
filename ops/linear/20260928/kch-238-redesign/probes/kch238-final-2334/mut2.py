import subprocess, sys, os
T=sys.argv[1]; F=f"{T}/loan_manager/application/agent/tokeniser.py"
orig=open(F).read()
M={
# --- the 11 cycle-1 survivors, re-expressed on the new code
"O1 scrub names shortest-first": ("key=len, reverse=True):\n            text = _value_boundary_pattern","key=len, reverse=False):\n            text = _value_boundary_pattern"),
"O2 guard money scans whole body": ("    for key, leaf in _walk_keyed_leaves(messages):\n        if key in _OPAQUE_ID_KEYS:\n            continue\n        if isinstance(leaf, str):\n            if MONEY_RE","    for key, leaf in _walk_keyed_leaves(body):\n        if key in _OPAQUE_ID_KEYS:\n            continue\n        if isinstance(leaf, str):\n            if MONEY_RE"),
"O3 candidate kind ignores field": ('kind = NAME_KEYS.get(candidate.get("field"))','kind = TokenKind.BORROWER if candidate.get("field") else None'),
"O4 rehydrate Q returns token": ("                return format_inr(key)\n            return str(key)","                return format_inr(key)\n            return token if kind is TokenKind.MENTION else str(key)"),
"O5 depositor_group own ns": ('"depositor_group": TokenKind.GROUP,\n}\n\n# review1 m6','"depositor_group": TokenKind.DEPOSITOR,\n}\n\n# review1 m6'),
"O6 HALF_EVEN token_for": ("key = Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)","key = Decimal(value).quantize(_TWO_PLACES)"),
"O7 no NOISE skip pass3": ("if not only_exact and first_core.lower() in NOISE_TOKENS:","if False:"),
"O8 scrub drops _pass_amounts": ("        text = self._scrub_issued_amounts(text)\n        text = self._pass_amounts(text)\n        return text","        text = self._scrub_issued_amounts(text)\n        return text"),
"O9 scrub issued amounts skipped": ("        for key, token in amount_entries:","        for key, token in amount_entries[:0]:"),
"O10 window cap 2": ("max_n = self._max_entity_words()","max_n = min(2, self._max_entity_words())"),
"O11 AMOUNT_KEYS drop principal/interest": ('{"total_amount", "exposure", "total_exposure", "principal", "interest"}','{"total_amount", "exposure", "total_exposure"}'),
# --- NEW properties introduced by cycle 1
"N1 possessive not stripped": ("if possessive and len(core) > len(possessive.group(0)):","if False:"),
"N2 ingress typed-token rejection removed": ("        found = TOKEN_RE.search(text)\n        if found:","        found = TOKEN_RE.search(text)\n        if False:"),
"N3 year context always true (old rule)": ("            and _is_year_context(text, start, end)\n","            and True\n"),
"N4 'of' dropped from year words": ('{"in", "since", "until", "till", "by", "year", "fy", "of"}','{"in", "since", "until", "till", "by", "year", "fy"}'),
"N5 month-name following ignored": ("    return bool(following and following.lower() in _MONTH_NAMES)","    return False"),
"N6 old trailing lookahead": ('_NO_TRAILING_WORD = r"(?![\\w-]|[.,]\\d)"','_NO_TRAILING_WORD = r"(?![\\w.,/-])"'),
"N7 MONEY_RE loses suffix": ('+ r"|(?<![\\w.,/-])\\d{5,}(?:\\.\\d+)?" + _MONEY_SUFFIX + _NO_TRAILING_WORD','+ r"|(?<![\\w.,/-])\\d{5,}(?:\\.\\d+)?" + _NO_TRAILING_WORD'),
"N8 unit 'l' removed": ('_UNIT_WORD = r"(?:lakhs?|lacs?|crores?|cr|l|k)"','_UNIT_WORD = r"(?:lakhs?|lacs?|crores?|cr|k)"'),
"N9 loan(s) exclusion re-added": ('_EXCLUDE_FOLLOWING_WORDS = frozenset({"month", "months", "day", "days"})','_EXCLUDE_FOLLOWING_WORDS = frozenset({"month", "months", "day", "days", "loan", "loans"})'),
"N10 unclassified int no raise": ("        if isinstance(value, (int, Decimal)):\n            raise","        if isinstance(value, (int, Decimal)) and False:\n            raise"),
"N11 unclassified numeric str no raise": ("        if isinstance(value, str) and parse_amount(value) is not None:","        if False:"),
"N12 field-kind check no-op": ("        expected = _FIELD_EXPECTED_KINDS.get(field)\n","        expected = None\n"),
"N13 guard months exemption removed": ("            if key in _NON_AMOUNT_NUMERIC_KEYS:\n                continue","            if False:\n                continue"),
"N14 guard name scan whole body": ("        for key, leaf in _walk_keyed_leaves(messages):\n            if key in _OPAQUE_ID_KEYS:\n                continue\n            if isinstance(leaf, str) and pattern","        for key, leaf in _walk_keyed_leaves(body):\n            if key in _OPAQUE_ID_KEYS:\n                continue\n            if isinstance(leaf, str) and pattern"),
"N15 guard opaque-id skip removed (money)": ("    for key, leaf in _walk_keyed_leaves(messages):\n        if key in _OPAQUE_ID_KEYS:\n            continue\n        if isinstance(leaf, str):","    for key, leaf in _walk_keyed_leaves(messages):\n        if isinstance(leaf, str):"),
"N16 TOKEN_RE widened to 3+": (r'TOKEN_RE = re.compile(r"\b(?:[BDGQ]\d{3}|AMOUNT_\d+)\b")',r'TOKEN_RE = re.compile(r"\b(?:[BDGQ]\d{3,}|AMOUNT_\d+)\b")'),
"N17 leading edge punct not stripped": ("    while start < end and not (window_text[start].isalnum() or window_text[start] == \"&\"):\n        start += 1\n",""),
"N18 name cache disabled": ("        pattern = self._name_pattern_cache.get(name)\n","        pattern = None\n"),
"N19 max_entity_words fixed 3": ("        longest = 1\n","        return 3\n        longest = 1\n"),
"N20 year window 1900-2099 -> 2000-2099": ("_YEAR_MIN, _YEAR_MAX = 1900, 2099","_YEAR_MIN, _YEAR_MAX = 2000, 2099"),
}
tests=["tests/unit/application/agent/test_tokeniser.py","tests/unit/application/agent/test_tokeniser_egress.py"]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",QT_QPA_PLATFORM="offscreen")
try:
  for name,(a,b) in M.items():
    if orig.count(a)!=1: print("PATTERN",orig.count(a),name); continue
    open(F,"w").write(orig.replace(a,b))
    r=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","-x",*tests],cwd=T,env=env,capture_output=True,text=True)
    lines=[l for l in r.stdout.splitlines() if l.strip()]
    fail=[l for l in lines if l.startswith("FAILED")]
    print(("KILLED  " if r.returncode else "SURVIVED"),name,"|",(fail[0][:110] if fail else lines[-1][:90]))
finally:
  open(F,"w").write(orig)
