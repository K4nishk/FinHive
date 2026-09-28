import subprocess, sys, os
T=sys.argv[1]; F=f"{T}/loan_manager/application/agent/tokeniser.py"
orig=open(F).read()
M={
"D1 honorific: 'ji' dropped from suffix list": ('r"(ji|jee|sahab','r"(jee|sahab'),
"D2 honorific: bhai/bhaiya/ben/behen/didi dropped": ('|bhai|bhaiya|ben|behen|didi)$"',')$"'),
"D3 honorific: case-sensitive suffix": ('didi)$", re.IGNORECASE','didi)$"'),
"D4 honorific: stem-is-stored-word check removed": (" or stem.lower() not in self._entity_words:",":"),
"D5 honorific: min stem 3 -> 1": ("_MIN_HONORIFIC_STEM_LEN = 3","_MIN_HONORIFIC_STEM_LEN = 1"),
"D6 honorific: no separator emitted (B001ji)": ('            out.append(\"-\")\n',''),
"D7 honorific: split not applied at ingress": ("        text = self._pass_amounts(text)\n        text = self._split_honorifics(text)\n","        text = self._pass_amounts(text)\n"),
"D8 honorific: split not applied in egress scrub": ("        text = self._split_honorifics(text)\n        text = self._scrub_names(text)","        text = self._scrub_names(text)"),
"D9 honorific: stem compared case-sensitively": ("stem.lower() not in self._entity_words","stem not in self._entity_words"),
"E1 F2: guard year exemption removed": ("    if _is_year_shaped_amount_value(amount):\n        return False\n",""),
"E2 F2: scrub year exemption removed": ('                if year_shaped and "," not in rendering:\n                    continue\n',''),
"E3 F2: scrub exemption also skips grouped": ('if year_shaped and "," not in rendering:','if year_shaped:'),
"E4 F2: year range widened to any 4-digit": ("    return len(str(integer_part)) == 4 and _YEAR_MIN <= integer_part <= _YEAR_MAX","    return len(str(integer_part)) == 4"),
"E5 F2: grouped check moved after year exemption": ('    if "," in rendering:\n        return True\n    if _is_year_shaped_amount_value(amount):\n        return False\n','    if _is_year_shaped_amount_value(amount):\n        return False\n    if "," in rendering:\n        return True\n'),
"F1 F3: resolve cache disabled": ("        cached = self._resolve_cache.get(folded)\n","        cached = None\n"),
"F2 F3: char cap uses raw len (breaks 'bg 13'?)": ("    return len(core.replace(\" \", \"\").replace(\"-\", \"\").replace(\"_\", \"\"))","    return len(core)"),
"F3 F3: short-word always-clear rule removed": ("            if len(core) <= 3:\n","            if False:\n"),
"F4 F3: multi-word prefilter removed": ("                if size > 1 and not all(span_clears[i : i + size]):\n                    continue\n",""),
"F5 F3: window char cap removed": ("                if max_chars is not None and _collapsed_len(core) > max_chars:\n                    continue\n",""),
"F6 F3: both char caps removed": None,
"F7 F3: pass-3 noise-word skip removed": ("            if not only_exact and span_cores[i].lower() in NOISE_TOKENS:\n                i += 1\n                continue\n",""),
"G1 m1: '_' back as a word char": ('    return ch.isalnum() or unicodedata.category(ch)[0] == "M"','    return ch.isalnum() or ch == "_" or unicodedata.category(ch)[0] == "M"'),
}
tests=["tests/unit/application/agent/test_tokeniser.py","tests/unit/application/agent/test_tokeniser_egress.py"]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",QT_QPA_PLATFORM="offscreen")
try:
  for name,ab in M.items():
    if ab is None:
      a1=M["F5 F3: window char cap removed"][0]; a2="            if max_chars is not None and _collapsed_len(core) > max_chars:\n                return False\n"
      if orig.count(a1)!=1 or orig.count(a2)!=1: print("PATTERN",name); continue
      src=orig.replace(a1,"").replace(a2,"")
    else:
      a,b=ab
      if orig.count(a)!=1: print("PATTERN",orig.count(a),name); continue
      src=orig.replace(a,b)
    open(F,"w").write(src)
    r=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider",*tests],cwd=T,env=env,capture_output=True,text=True)
    lines=[l for l in r.stdout.splitlines() if l.strip()]
    fail=[l.split("::")[-1][:90] for l in lines if l.startswith("FAILED") or l.startswith("ERROR")]
    print(("KILLED  " if r.returncode else "SURVIVED"),name,"|",(f"{len(fail)} fail: "+"; ".join(fail[:3]) if fail else lines[-1][:90]))
finally:
  open(F,"w").write(orig)
