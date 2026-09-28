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
prompts=[
 "What is Meera Iyer's exposure?",
 "how much does rakesh sharma owe?",
 "how much does Rakesh Sharma owe",
 "loans of sharma group's members",
 "Did Suresh lend 45,000/- to anyone",
 "lend him 45000/-",
 "lend him 45000.",
 "lend 50000, then stop",
 "lend him 5000.",
 "a 2 lakh loan to anil sharma",
 "₹50,000 loan for pooja",
 "250000 loan",
 "gave 2000 to b1",
 "1.5L to naveen",
 "45000rs to naveen",
 "Rs 1,00,00,000 to naveen rao",
 "Rs.45000 and INR45000",
 "Meera's loans",
 "kavita nair (depositor)",
 "\"deepak menon\"",
 "deepak-menon",
 "farhan's deposits",
 "iyer chem and verma textiles",
 "gupta & sons",
 "ramesh gupta, pooja verma; asha bhat.",
 "rao holdings: status?",
 "sharma",
 "bg1 vs bg13 vs bg 13",
 
 "2026_03_004 on 26/09/2026 for 3 months at 12%",
 "top 5 borrowers in FY2026-27",
 "Meera Iyer",
]
for p in prompts:
    tm=TokenMap(R)
    out=tm.tokenise_prompt(p)
    body={"messages":[{"role":"user","content":out}]}
    try:
        assert_no_plaintext(body,tm); g="guard-ok"
    except PlaintextLeakError as e: g="GUARD-RAISED"
    print(f"{p!r:50} -> {out!r:45} {g}  map={dict(tm._reverse)}")
