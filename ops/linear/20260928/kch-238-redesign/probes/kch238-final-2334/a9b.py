import json, re, sys
from decimal import Decimal
from datetime import date
sys.path.insert(0, "pkg")
from fx import make_loan, uow_factory_for
from loan_manager.application.agent.tokeniser import *
from loan_manager.application.agent.tool_registry import parse_args, tool_schemas, ToolMode
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY
from loan_manager.infrastructure.llm.request_body import build_request_body
from loan_manager.infrastructure.llm.settings import LLMSettings
import inspect
loans=[make_loan(borrower_name=f.borrower_name,borrower_group=f.borrower_group,depositor_name=f.depositor_name,depositor_group=f.depositor_group,amount=f.amount,giving_date=f.giving_date,due_date=f.due_date) for f in DEMO_LOANS if f.paidoff_date is None]
uf=uow_factory_for(loans); reg=build_read_registry(uf,FixedClock(FIXTURE_TODAY))
R=BuildEntityResolver(GetAutocompleteValues(uf)).execute()
names=sorted({v for _,v in R.entities()})
refs=sorted(l.reference_id.value for l in loans)
SYS=open("sysprompt.txt").read()
tools=tool_schemas(frozenset({ToolMode.READ}))
class S: model="x"; temperature=0
tm=TokenMap(R)
msgs=[{"role":"system","content":SYS}]
raw_amounts=set(Decimal(str(l.amount.amount if hasattr(l.amount,'amount') else l.amount)) for l in loans)
false_raises=[]; bodies=[]
def leaves(o,k=None):
    if isinstance(o,dict):
        for kk,v in o.items(): yield from leaves(v,kk)
    elif isinstance(o,list):
        for v in o: yield from leaves(v,k)
    else: yield k,o
cid=[0]
def check():
    body=build_request_body(S, msgs, tools); bodies.append(body)
    try: assert_no_plaintext(body, tm)
    except PlaintextLeakError as e: false_raises.append((len(msgs), str(e)[:140]))
def tool(name, args_tok):
    cid[0]+=1; c=f"call_{cid[0]}"
    a=json.dumps(args_tok)
    msgs.append({"role":"assistant","content":None,"tool_calls":[{"id":c,"type":"function","function":{"name":name,"arguments":a}}]})
    obs=reg.handler(name)(parse_args(name, tm.detokenise_args(a)))
    for k,v in leaves(obs):
        if isinstance(v,str) and re.fullmatch(r"\d+\.\d\d",v) and k!="rate_percent": raw_amounts.add(Decimal(v))
    t=tm.tokenise_observation(obs)
    msgs.append({"role":"tool","tool_call_id":c,"name":name,"content":json.dumps(t,ensure_ascii=False)})
    check(); return t
def user(text):
    msgs.append({"role":"user","content":tm.tokenise_prompt(text)}); check(); return msgs[-1]["content"]
def say(text):
    msgs.append({"role":"assistant","content":text}); check()
# ---- turn 1
print(user("Hi! What's today's date and which FY quarter are we in?"))
tool("get_current_context",{}); say("Today is Friday 2026-09-25, in FY2026-27, quarter Q2 (2026-07-01 to 2026-09-30).")
# ---- turn 2
print(user("How much does Meera Iyer's group owe, and is anything overdue for iyer chem?"))
r=tool("resolve_entity",{"text":"G001"}) if False else None
q=[k for k,v in tm._reverse.items()]
print(" map:",{k:str(v[1]) for k,v in tm._reverse.items()})
g=[k for k,v in tm._reverse.items() if v[0] is TokenKind.GROUP]
tool("query_loans",{"status":"overdue","borrower_group":g[0]})
say(f"{g[0]} has overdue loans totalling AMOUNT_1 -- 3 of them are more than 90 days late. Rates are 12% p.a.")
# ---- turn 3
print(user("who owes the most? show top 5 with exposure, and the total in rupees"))
tool("get_portfolio_summary",{"limit":5})
say("The top 5 borrowers hold most of the exposure; B001 leads with AMOUNT_2 across 1 loan (ref 2026_01_026).")
# ---- turn 4
print(user(f"interest on {refs[3]} at 12% for 3 months? and for {refs[7]} at 14.5% for 6 months"))
t1=tool("calculate_interest",{"ref_id":refs[3],"rate":12,"months":3})
t2=tool("calculate_interest",{"ref_id":refs[7],"rate":"14.5","months":6})
tool("format_inr",{"amount":t1["interest"]})
say(f"Interest on {refs[3]} at 12% for 3 months is {t1['interest']} (basis amount×rate×months/1200); for {refs[7]} at 14.5% over 6 months it is {t2['interest']}.")
# ---- turn 5: ambiguous name + amount typed
print(user("did sharma lend 45,000/- to anil sharma this quarter? also check 1.5 lakh loans"))
qtok=[k for k,v in tm._reverse.items() if v[0] is TokenKind.MENTION][-1]
tool("resolve_entity",{"text":qtok})
say(f"'{qtok}' matches several people; which one do you mean? Also, B00x — I cannot filter by amount.")
# ---- turn 6: ref id / date / pct heavy
print(user("status of 2026_01_004 due 26 Sep 2026? and overdue loans for d1, dg1, bg13 since 2025"))
for k,v in list(tm._reverse.items()):
    pass
tool("query_loans",{"status":"overdue"}); tool("query_loans",{"status":"active"}); tool("query_loans",{"status":"pending"})
say("As of 2026-09-25: 20 overdue (2 undated), 0 active, 0 pending. Max 140 days overdue. See refs 2026_01_001, 2026_01_002.")
# ---- the 56-call sweep appended into the same session
calls=[("resolve_entity",{"text":t}) for t in ["Q001","G001","B001","D001"] if t in tm._reverse]
calls+=[("get_portfolio_summary",{"limit":50}),("format_inr",{"amount":"AMOUNT_1"})]
calls+=[("calculate_interest",{"ref_id":r,"rate":12,"months":3}) for r in refs[:40]]
for n,a in calls: tool(n,a)
say("Done.")
# independent leak scan over every body
leaks=[]
for b in bodies:
    s=json.dumps(b["messages"],ensure_ascii=False)
    for n in names:
        if re.search(r"(?<![^\W_])"+re.escape(n)+r"(?![^\W_])",s,re.I): leaks.append(("NAME",n))
    for a in raw_amounts:
        q=a.quantize(Decimal("0.01"))
        for rnd in {f"{q:f}", str(int(q)) if q==q.to_integral_value() else None}:
            if rnd and len(rnd.replace('.',''))>=4 and re.search(r"(?<![\d.])"+re.escape(rnd)+r"(?![\d])",s): leaks.append(("AMT",rnd))
print("messages:",len(msgs),"bodies:",len(bodies),"tool calls:",cid[0])
print("false raises:",len(false_raises)); [print("  ",f) for f in false_raises[:8]]
print("independent leaks:",len(set(leaks)), sorted(set(leaks))[:10])
import time
t=time.perf_counter(); assert_no_plaintext(bodies[-1], tm); print("guard on final body (98 msgs) ms:", round((time.perf_counter()-t)*1000,1))
obs=reg.handler("get_portfolio_summary")(parse_args("get_portfolio_summary",{"limit":50}))
t=time.perf_counter(); tm.tokenise_observation(obs); print("tokenise_observation portfolio(50) ms:", round((time.perf_counter()-t)*1000,1))
obs=reg.handler("resolve_entity")(parse_args("resolve_entity",{"text":"iyer"}))
t=time.perf_counter(); tm.tokenise_observation(obs); print("tokenise_observation resolve ms:", round((time.perf_counter()-t)*1000,1))
