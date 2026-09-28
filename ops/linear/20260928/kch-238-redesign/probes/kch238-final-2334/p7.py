import json
from decimal import Decimal
from datetime import date
from fx import make_loan, uow_factory_for
from loan_manager.application.agent.tokeniser import *
from loan_manager.application.agent.tool_registry import parse_args
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY
loans=[make_loan(borrower_name=f.borrower_name,borrower_group=f.borrower_group,depositor_name=f.depositor_name,depositor_group=f.depositor_group,amount=f.amount,giving_date=f.giving_date,due_date=f.due_date) for f in DEMO_LOANS if f.paidoff_date is None]
loans.append(make_loan(borrower_name="undated guy",borrower_group="nodate grp",depositor_name="dx",depositor_group="dg",amount=type(DEMO_LOANS[0].amount)(40000),giving_date=date(2026,1,1),due_date=None))
uf=uow_factory_for(loans); reg=build_read_registry(uf,FixedClock(FIXTURE_TODAY))
R=BuildEntityResolver(GetAutocompleteValues(uf)).execute()
calls=[("get_current_context",{}),("query_loans",{"status":"paidoff"}),("query_loans",{"status":"overdue"}),("query_loans",{"status":"overdue","depositor_group":"zz unknown 45000"}),
("calculate_interest",{"ref_id":"2099_01_001","rate":12,"months":3}),("format_inr",{"amount":"0.01"}),("format_inr",{"amount":"99999999999"}),("get_portfolio_summary",{"limit":1}),("resolve_entity",{"text":"45000"}),("resolve_entity",{"text":"meera iyer 45000"})]
tm=TokenMap(R)
for name,a in calls:
    obs=reg.handler(name)(parse_args(name,a))
    try:
        tok=tm.tokenise_observation(obs)
        s=json.dumps(tok,ensure_ascii=False)
        try: assert_no_plaintext({"messages":[{"role":"tool","content":s}]},tm); g="guard-ok"
        except PlaintextLeakError as e: g="GUARD "+str(e)[:80]
        print(name,a,"->",s[:230],g)
    except Exception as e: print(name,a,"RAISE",type(e).__name__,e)
