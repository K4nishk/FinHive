import json, re, time
from decimal import Decimal
from loan_manager.application.agent.tokeniser import *
from loan_manager.application.agent.tokeniser import MONEY_RE
from loan_manager.domain.services.entity_resolver import EntityResolver
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS
vals={f:[] for f in ("borrower_name","borrower_group","depositor_name","depositor_group")}
for fl in DEMO_LOANS:
    for f in vals:
        v=getattr(fl,f)
        if v: vals[f].append(v)
R=EntityResolver(vals)
ALL_NAMES=sorted({v for vs in vals.values() for v in vs})
NAME_WORDS=sorted({w for n in ALL_NAMES for w in re.split(r"[\s&]+",n) if len(w)>=2 and w not in("and","the")})
def leak_scan(out):
    """independent: any stored-name WORD as a standalone alnum run (split on non-alnum incl _)"""
    runs=set(re.findall(r"[^\W_]+",out.lower()))
    return sorted(w for w in NAME_WORDS if w in runs)
def run(p, tm=None, show=True):
    tm=tm or TokenMap(R)
    try:
        out=tm.tokenise_prompt(p)
    except Exception as e:
        print(f"{p[:60]!r:62} RAISE {type(e).__name__}: {str(e)[:70]}"); return None,tm
    try: assert_no_plaintext({"messages":[{"role":"user","content":out}]},tm); g="guard-ok"
    except PlaintextLeakError as e: g="GUARD-RAISE:"+str(e)[:50]
    lw=leak_scan(out)
    if show: print(f"{p[:60]!r:62} -> {out[:60]!r:62} {g} leakwords={lw} map={[ (k,str(v[1])) for k,v in tm._reverse.items()][:6]}")
    return out,tm
