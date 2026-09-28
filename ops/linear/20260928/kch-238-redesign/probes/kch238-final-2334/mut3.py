import subprocess, sys, os
T=sys.argv[1]; F=f"{T}/loan_manager/application/agent/tokeniser.py"
orig=open(F).read()
M={
"C1 NM4 combining marks not word chars": ('return ch.isalnum() or ch == "_" or unicodedata.category(ch)[0] == "M"','return ch.isalnum() or ch == "_"'),
"C2 NB2 in-word apostrophe not kept": ("            if ch in _APOSTROPHES and i + 1 < n and _is_word_char(text[i + 1]):","            if False:"),
"C3 curly apostrophe fold disabled": ('    return text.replace(_CURLY_APOSTROPHE, "\'")','    return text'),
"C4 NB1 currency/unit-marked never recognised": ("    return bool(_CURRENCY_PREFIX_RE.match(matched_text)) or bool(\n        _CURRENCY_OR_UNIT_SUFFIX_RE.search(matched_text)\n    )","    return False"),
"C5 NB1 suffix-only marks ignored (prefix only)": ("    return bool(_CURRENCY_PREFIX_RE.match(matched_text)) or bool(\n        _CURRENCY_OR_UNIT_SUFFIX_RE.search(matched_text)\n    )","    return bool(_CURRENCY_PREFIX_RE.match(matched_text))"),
"C6 ingress 'suffixed' branch removed": ('    r"|(?P<suffixed>(?<![\\w.,/-])\\d+(?:\\.\\d+)?" + _MANDATORY_MONEY_SUFFIX + r")",','    r"",'),
"C7 guard MONEY_RE suffixed branch removed": ('    + r"|(?<![\\w.,/-])\\d+(?:\\.\\d+)?" + _MANDATORY_MONEY_SUFFIX,','    + r"",'),
"C8 NM5 thousand/hundred units removed": ('_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|l|k|thousands?|hundreds?"','_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|l|k"'),
"C9 NM5 hundred only removed": ('_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|l|k|thousands?|hundreds?"','_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|l|k|thousands?"'),
"C10 NM1 _tokenise_free numeric no raise": ("        if isinstance(value, (int, float, Decimal)):\n            raise PlaintextLeakError(\n                f\"a free-text","        if isinstance(value, (int, float, Decimal)) and False:\n            raise PlaintextLeakError(\n                f\"a free-text"),
"C11 NM1 float exempt everywhere": ("isinstance(value, (int, float, Decimal))","isinstance(value, (int, Decimal))"),
"C12 NM2 budget off-by-one (>1000)": ("if kind is not TokenKind.AMOUNT and n > 999:","if kind is not TokenKind.AMOUNT and n > 1000:"),
"C13 NM2 budget check removed": ("if kind is not TokenKind.AMOUNT and n > 999:","if False:"),
"C14 TOKEN_RE back to \\d": ('TOKEN_RE = re.compile(r"\\b(?:[BDGQ][0-9]{3}|AMOUNT_[0-9]+)\\b")','TOKEN_RE = re.compile(r"\\b(?:[BDGQ]\\d{3}|AMOUNT_\\d+)\\b")'),
"C15 NM3 money-shape gate always True": ('    if "," in rendering:\n        return True\n','    return True\n'),
"C16 NM3 money-shape threshold 3 digits": ("    return len(str(integer_part)) >= 4","    return len(str(integer_part)) >= 3"),
"C17 NM3 guard rendering lookbehind back to (?<!\\w)": ('re.compile(rf"(?<![\\w.,/-]){re.escape(rendering)}(?!\\w)")','re.compile(rf"(?<!\\w){re.escape(rendering)}(?!\\w)")'),
"C18 NM3 int_part rendered for non-integral": ("    if quantised == quantised.to_integral_value():\n        variants.add(int_part)","    variants.add(int_part)"),
"C19 NM3 numeric leaf gate removed": ("            if leaf_decimal in token_map.amounts() and _is_money_shaped_amount(\n                leaf_decimal, str(leaf)\n            ):","            if leaf_decimal in token_map.amounts():"),
"C20 basis not passthrough": ('        "basis",\n',''),
"C21 year words: 'of' re-added": ('_YEAR_CONTEXT_WORDS = frozenset({"in", "since", "until", "till", "by", "year", "fy"})','_YEAR_CONTEXT_WORDS = frozenset({"in", "since", "until", "till", "by", "year", "fy", "of"})'),
"C22 possessive curly quote dropped": ("_POSSESSIVE_RE = re.compile(r\"['’]s$\", re.IGNORECASE)","_POSSESSIVE_RE = re.compile(r\"[']s$\", re.IGNORECASE)"),
"C23 N7-equiv: bare-branch suffix dropped (MONEY_RE)": ('+ r"|(?<![\\w.,/-])\\d{5,}(?:\\.\\d+)?" + _MONEY_SUFFIX + _NO_TRAILING_WORD','+ r"|(?<![\\w.,/-])\\d{5,}(?:\\.\\d+)?" + _NO_TRAILING_WORD'),
"C24 N10-equiv: unclassified numeric check removed": ("        if isinstance(value, (int, float, Decimal)):\n            raise PlaintextLeakError(\n                f\"unclassified","        if False:\n            raise PlaintextLeakError(\n                f\"unclassified"),
"C25 N10+NM1 both numeric raises removed": None,
"C26 word span: '_' becomes separator": ('return ch.isalnum() or ch == "_" or unicodedata.category(ch)[0] == "M"','return (ch.isalnum() and ch != "_") or unicodedata.category(ch)[0] == "M"'),
"C27 guard numeric-leaf skip for passthrough keys removed": ("            if key in _NON_AMOUNT_NUMERIC_KEYS:\n                continue","            pass"),
}
tests=["tests/unit/application/agent/test_tokeniser.py","tests/unit/application/agent/test_tokeniser_egress.py"]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",QT_QPA_PLATFORM="offscreen")
try:
  for name,ab in M.items():
    if ab is None:
      a1,b1=M["C10 NM1 _tokenise_free numeric no raise"]; a2,b2=M["C24 N10-equiv: unclassified numeric check removed"]
      if orig.count(a1)!=1 or orig.count(a2)!=1: print("PATTERN",name); continue
      src=orig.replace(a1,b1).replace(a2,b2)
    else:
      a,b=ab
      if orig.count(a)!=1: print("PATTERN",orig.count(a),name); continue
      src=orig.replace(a,b)
    open(F,"w").write(src)
    r=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","-x",*tests],cwd=T,env=env,capture_output=True,text=True)
    lines=[l for l in r.stdout.splitlines() if l.strip()]
    fail=[l for l in lines if l.startswith("FAILED") or l.startswith("ERROR")]
    print(("KILLED  " if r.returncode else "SURVIVED"),name,"|",(fail[0][:120] if fail else lines[-1][:90]))
finally:
  open(F,"w").write(orig)
