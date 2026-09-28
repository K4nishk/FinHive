from loan_manager.application.agent.tokeniser import *
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS
from loan_manager.domain.services.entity_resolver import EntityResolver
vals={f:[] for f in ("borrower_name","borrower_group","depositor_name","depositor_group")}
for fl in DEMO_LOANS:
    for f in vals:
        v=getattr(fl,f)
        if v: vals[f].append(v)
R=EntityResolver(vals)
ps=["2000 rupees","a loan of 2000 rupees","of 2000/-","of 2000rs","by 2000 inr","in 2000 rs","since 2000/-","sep 2000 rupees","500 rupees","750rs","999/-","50 thousand","5 thousand rupees","meera iyer,anil sharma","meera iyer/anil sharma","Sharma-ji","anil sharma-ji","Mr.Sharma","mr. anil sharma","anil sharma's'","deepak menon's,","naveen rao-ka loan"]
for p in ps:
    tm=TokenMap(R)
    try:
        out=tm.tokenise_prompt(p)
        try: assert_no_plaintext({"messages":[{"role":"user","content":out}]},tm); g="ok"
        except PlaintextLeakError as e: g="GUARD-RAISE"
        print(f"{p!r:30} -> {out!r:34} {g} {[str(v[1]) for v in tm._reverse.values()]}")
    except Exception as e: print(p,"RAISE",type(e).__name__,e)
