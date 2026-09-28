import json
from decimal import Decimal
from loan_manager.application.agent.tokeniser import *
from loan_manager.domain.services.entity_resolver import EntityResolver
R=EntityResolver({"borrower_name":["suresh iyer","lakshmi iyer","o'brien shah","anil sharma"],"depositor_name":["meera iyer","राम शर्मा"],"borrower_group":["iyer chem","sharma group"]})
def t(label,f):
    try: print(label,"->", f())
    except Exception as e: print(label, "RAISE", type(e).__name__, str(e)[:100])

# fail-closed gaps
for obs in [{"x":[250000]},{"message":250000},{"notes":[250000,"a"]},{"x":[Decimal("5000.00")]},{"x":5000.5},{"x":[[250000]]}]:
    t(f"unclassified {obs}", lambda: TokenMap(R).tokenise_observation(obs))
# guard FP: small / 1200 known amount against real serialised bodies
for amt,content in [(Decimal("1200"),json.dumps({"ok":True,"ref_id":"2026_01_021","principal":"AMOUNT_1","rate_percent":"12.00","months":3,"interest":"AMOUNT_2","basis":"amount×rate×months/1200"},ensure_ascii=False)),
                    (Decimal("12"),'{"ref_id":"2026_01_021","rate":12,"months":3}'),
                    (Decimal("3"),'{"months":3}'),
                    (Decimal("450"),"top 450")]:
    tm=TokenMap(R); tm.token_for(TokenKind.AMOUNT,amt)
    t(f"guard known {amt} vs {content[:60]}", lambda: assert_no_plaintext({"messages":[{"role":"tool","content":content}]},tm))
tm=TokenMap(R); tm.token_for(TokenKind.AMOUNT,Decimal("12"))
t("guard tool_calls args", lambda: assert_no_plaintext({"messages":[{"role":"assistant","tool_calls":[{"id":"c1","function":{"name":"calculate_interest","arguments":'{"ref_id":"2026_01_021","rate":12,"months":3}'}}]}]},tm))
# ingress attacks
for p in ["(meera iyer)","[Meera Iyer]","meera iyer's's","Meera Iyer’s","MEERA IYER'S","meera iyers","o'brien shah owes","O’Brien Shah owes","o'brien's loan","राम शर्मा का लोन","राम शर्मा।","«meera iyer»","meera iyer…","meera iyer—exposure","meera iyer/anil sharma","meera iyer&anil sharma","meera.iyer","meera_iyer","@meera iyer","#iyer","iyer?!","'iyer'","meera iyer","meera\tiyer","MEERA\nIYER","Anil Sharma-ji","anil sharmaji","sharma group's","sharma groups"]:
    tm=TokenMap(R)
    try:
        out=tm.tokenise_prompt(p)
        try: assert_no_plaintext({"messages":[{"role":"user","content":out}]},tm); g="ok"
        except PlaintextLeakError as e: g="GUARD-RAISE"
        print(f"{p!r:28} -> {out!r:30} {g} {dict((k,v[1]) for k,v in tm._reverse.items())}")
    except Exception as e: print(p, "RAISE", type(e).__name__, e)
