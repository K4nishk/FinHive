import sys
F=sys.argv[1]; s=open(F).read()
def rep(a,b):
    global s
    assert s.count(a)==1, a[:60]; s=s.replace(a,b)
# FIX-A (BLOCKER R1): never split a word that is itself a stored entity word; peel a possessive first
rep("""            word = text[start:end]
            m = _HONORIFIC_SUFFIX_RE.search(word)""","""            word = text[start:end]
            if word.lower() in self._entity_words:
                continue
            poss = _POSSESSIVE_RE.search(_fold_apostrophe(word))
            if poss:
                end -= len(poss.group(0))
                word = text[start:end]
            m = _HONORIFIC_SUFFIX_RE.search(word)""")
# FIX-B (MAJOR R3/minor): prefilter must not skip a window whose collapsed form equals a stored collapsed value; noise words always clear
rep("""        self._resolve_cache: dict[str, Any] = {}
""","""        self._resolve_cache: dict[str, Any] = {}
        self._collapsed_values: frozenset[str] = frozenset(
            re.sub(r"[\\s_-]+", "", v.lower()) for _f, v in resolver.entities()
        )
        idx: set[str] = set()
        for _f, v in resolver.entities():
            norm = re.sub(r"\\s+", " ", re.sub(r"[_-]+", " ", v.lower())).strip()
            for s_ in {norm, norm.replace(" ", ""), *norm.split(" ")}:
                idx.add(s_)
                idx.update(s_[:k] + s_[k + 1 :] for k in range(len(s_)))
        self._del1_index: frozenset[str] = frozenset(idx)
""")
rep("""            if len(core) <= 3:""","""            if core.lower() in NOISE_TOKENS:
                return True
            q = re.sub(r"\\s+", " ", re.sub(r"[_-]+", " ", _fold_apostrophe(core).lower())).strip()
            if " " not in q and not ({q} | {q[:k] + q[k + 1 :] for k in range(len(q))}) & self._del1_index:
                return False
            if len(core) <= 3:""")
rep("""                if size > 1 and not all(span_clears[i : i + size]):
                    continue
                window_start = spans[i][0]
                window_end = spans[i + size - 1][1]""","""                window_start = spans[i][0]
                window_end = spans[i + size - 1][1]
                if size > 1 and not all(span_clears[i : i + size]) and re.sub(
                    r"[\\W_]+", "", text[window_start:window_end].lower()
                ) not in self._collapsed_values:
                    continue
                if size == 1 and not span_clears[i] and len(span_cores[i]) > 3:
                    continue""")
# FIX-C (MINOR): year exemption only for a bare 4-digit rendering
rep("""    if _is_year_shaped_amount_value(amount):
        return False""","""    if rendering.isdigit() and _is_year_shaped_amount_value(amount):
        return False""")
open(F,"w").write(s)
