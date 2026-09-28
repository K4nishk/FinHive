from decimal import Decimal
from loan_manager.application.agent.tokeniser import *
from loan_manager.application.agent.tool_registry import ToolMode, tool_schemas
from loan_manager.domain.services.entity_resolver import EntityResolver
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS
vals={f:[] for f in ("borrower_name","borrower_group","depositor_name","depositor_group")}
for fl in DEMO_LOANS:
    for f in vals:
        v=getattr(fl,f)
        if v: vals[f].append(v)
R=EntityResolver(vals)
tools=tool_schemas(frozenset({ToolMode.READ}))
for p in ["show me the overdue loans for this month with interest and exposure",
          "which borrowers are due next week, give total amount",
          "list active loans by depositor desk",
          "who owes the most money right now",
          "raise rate for bg to 14 percent", "any loans in mumbai or chennai", "show d1 and b1 and dg1",
          "What's the status of Anil?", "is naveen overdue"]:
    tm=TokenMap(R); out=tm.tokenise_prompt(p)
    try: assert_no_plaintext({"messages":[{"role":"user","content":out}],"tools":tools},tm); g="ok"
    except PlaintextLeakError as e: g="RAISE "+str(e)
    print(repr(p),"->",repr(out),g)
for s in ["٤٥٠٠٠","𝟒𝟓𝟎𝟎𝟎","४५,०००"]:
    print(s, parse_amount(s), TokenMap(R).tokenise_prompt("lend "+s+" now"))
