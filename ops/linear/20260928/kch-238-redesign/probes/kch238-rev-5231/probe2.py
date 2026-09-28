import json, re, sys
sys.path.insert(0, sys.argv[1])
from decimal import Decimal
from fx import make_loan, uow_factory_for
from loan_manager.application.agent.tokeniser import *
from loan_manager.application.agent.tool_registry import parse_args
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY
loans=[make_loan(borrower_name=f.borrower_name,borrower_group=f.borrower_group,depositor_name=f.depositor_name,depositor_group=f.depositor_group,amount=f.amount,giving_date=f.giving_date,due_date=f.due_date) for f in DEMO_LOANS if f.paidoff_date is None]
uf=uow_factory_for(loans); reg=build_read_registry(uf,FixedClock(FIXTURE_TODAY))
R=BuildEntityResolver(GetAutocompleteValues(uf)).execute()
names={v for f in DEMO_LOANS for v in (f.borrower_name,f.borrower_group,f.depositor_name,f.depositor_group) if v}
calls=[("resolve_entity",{"text":t}) for t in ["iyer","sharma","meera iyer","rakesh","sharmaa group","zzz","b1","iyer chem"]]
calls+=[("query_loans",{"status":s}) for s in ("overdue","active","pending")]
calls+=[("query_loans",{"status":"overdue","borrower_group":g}) for g in ("sharma group","iyer chem","rakesh sharma")]
calls+=[("get_portfolio_summary",{"limit":50}),("format_inr",{"amount":"250000"})]
refs=sorted(l.reference_id.value if hasattr(l.reference_id,'value') else str(l.reference_id) for l in loans)
calls+=[("calculate_interest",{"ref_id":r,"rate":12,"months":3}) for r in refs[:40]]
def leaves(o,k=None):
    if isinstance(o,dict):
        for kk,v in o.items(): yield from leaves(v,kk)
    elif isinstance(o,list):
        for v in o: yield from leaves(v,k)
    else: yield k,o
for mode in ("fresh","shared"):
  tm=TokenMap(R); leaks=[]
  for name,a in calls:
    if mode=="fresh": tm=TokenMap(R)
    obs=reg.handler(name)(parse_args(name,a))
    tok=tm.tokenise_observation(obs)
    s=json.dumps(tok,ensure_ascii=False)
    for n in names:
        if re.search(r"(?<!\w)"+re.escape(n)+r"(?!\w)",s,re.I): leaks.append((name,a,"NAME",n))
    # raw numeric-ish leaves in raw obs that look like money
    for k,v in leaves(obs):
        if isinstance(v,str) and re.fullmatch(r"\d+\.\d\d",v) and k not in("rate_percent",):
            if re.search(r"(?<![\w.])"+re.escape(v)+r"(?![\w])",s) or re.search(r"(?<![\w.])"+re.escape(str(int(Decimal(v))))+r"(?![\w])",s):
                leaks.append((name,a,"AMT",k,v))
    try: assert_no_plaintext({"messages":[{"role":"tool","content":s}]},tm)
    except PlaintextLeakError as e: leaks.append((name,a,"GUARD",str(e)[:120]))
  print(mode, "leaks:", len(leaks))
  for l in leaks[:30]: print("  ",l)
tm=TokenMap(R)
print(json.dumps(tm.tokenise_observation(reg.handler("resolve_entity")(parse_args("resolve_entity",{"text":"iyer"}))),ensure_ascii=False))
print(json.dumps(tm.tokenise_observation(reg.handler("get_portfolio_summary")(parse_args("get_portfolio_summary",{"limit":3}))),ensure_ascii=False))
print(json.dumps(tm.tokenise_observation(reg.handler("calculate_interest")(parse_args("calculate_interest",{"ref_id":refs[20],"rate":12,"months":3}))),ensure_ascii=False))
