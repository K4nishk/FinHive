import subprocess, sys, os, shutil
T=sys.argv[1]; F=f"{T}/loan_manager/application/agent/tokeniser.py"
orig=open(F).read()
M={
"M1 scrub issued not longest-first": ("key=lambda pair: -len(pair[0])","key=lambda pair: len(pair[0])"),
"M2 guard money scans whole body not messages": ("    for leaf in _walk_leaves(messages):\n        if isinstance(leaf, str):","    for leaf in _walk_leaves(body):\n        if isinstance(leaf, str):"),
"M3 candidate kind ignores sibling field": ('kind = NAME_KEYS.get(candidate.get("field"))','kind = TokenKind.BORROWER if candidate.get("field") else None'),
"M4 rehydrate Q returns token": ("            return str(key)\n\n        return TOKEN_RE.sub(repl, text)\n\n\ndef _walk","            return token if kind is TokenKind.MENTION else str(key)\n\n        return TOKEN_RE.sub(repl, text)\n\n\ndef _walk"),
"M5 depositor_group own namespace": ('"depositor_group": TokenKind.GROUP,','"depositor_group": TokenKind.DEPOSITOR,'),
"M6 HALF_EVEN in token_for": ("key = Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)","key = Decimal(value).quantize(_TWO_PLACES)"),
"M7 no NOISE skip in pass3": ("if not only_exact and first_word in NOISE_TOKENS:","if False and first_word in NOISE_TOKENS:"),
"M8 names() only issued, not resolver universe": ("resolver_names = frozenset(value for _field, value in self._resolver.entities())","resolver_names = frozenset(v for (k, v) in self._reverse.values() if k is not TokenKind.AMOUNT and k is not TokenKind.MENTION)"),
"M9 scrub skips amount pass": ("        text = self._scrub_resolver_names(text)\n        text = self._pass_amounts(text)","        text = self._scrub_resolver_names(text)"),
"M10 scrub issued amounts skipped": ("        for key, token in amount_entries:","        for key, token in amount_entries[:0]:"),
"M11 unit multiplier k=100": ('"k": Decimal(1000),','"k": Decimal(100),'),
"M12 detok embedded amount keeps token": ("                return str(int(key)) if key == key.to_integral_value() else str(key)","                return match.group(0)"),
"M13 prompt amount pass skipped": ("        text = self._pass_amounts(text)\n        text = self._match_windows(text, only_exact=True)","        text = self._match_windows(text, only_exact=True)"),
"M14 guard name check case-sensitive": ('return re.compile(rf"(?<!\\w){body}(?!\\w)", re.IGNORECASE)','return re.compile(rf"(?<!\\w){body}(?!\\w)")'),
"M15 max window 6 -> 2": ("max_n = min(6, self._max_entity_words())","max_n = min(2, self._max_entity_words())"),
"M16 AMOUNT_KEYS drop principal+interest": ('{"total_amount", "exposure", "total_exposure", "principal", "interest"}','{"total_amount", "exposure", "total_exposure"}'),
}
tests=["tests/unit/application/agent/test_tokeniser.py","tests/unit/application/agent/test_tokeniser_egress.py"]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",QT_QPA_PLATFORM="offscreen")
for name,(a,b) in M.items():
    if orig.count(a)!=1: print(name,"PATTERN COUNT",orig.count(a)); continue
    open(F,"w").write(orig.replace(a,b))
    r=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","-x",*tests],cwd=T,env=env,capture_output=True,text=True)
    last=[l for l in r.stdout.splitlines() if l.strip()][-1]
    print(("KILLED  " if r.returncode else "SURVIVED"),name,"|",last)
open(F,"w").write(orig)
