from decimal import Decimal
from loan_manager.application.agent.tokeniser import *
from loan_manager.domain.services.entity_resolver import EntityResolver
R=EntityResolver({"borrower_name":["suresh iyer","lakshmi iyer"],"depositor_name":["meera iyer"],"borrower_group":["iyer chem"]})
def t(label,f):
    try: print(label, f())
    except Exception as e: print(label, "RAISE", type(e).__name__, str(e)[:110])
tm=TokenMap(R); print(tm.tokenise_prompt("how much does iyer owe"))
t("M2",lambda: tm.tokenise_observation({"message":"meera iyer and iyer chem are linked"}))
for obs in [{"amount":250000},{"new_amount":"250000.00"},{"paid":Decimal("5000.00")},{"paid":5000.5},{"note_x":"paid 250000 yesterday"},{"x":["250000"]},{"x":{"y":250000}},{"x":[250000]}, {"x":"1,50,000"},{"x":"₹45,000"},{"x":"2 lakh"},{"x":True},{"x":None},{"x":"2026"},{"x":"3"}]:
    t(f"M3 {obs}", lambda: TokenMap(R).tokenise_observation(obs))
t("C", lambda: TokenMap(R).tokenise_observation({"notes":["lent 5000.", "year 2000 amount 2000", "45,000/-", "in 2026 paid 2000"]}))
tm=TokenMap(R); tm.token_for(TokenKind.AMOUNT, Decimal("150000"))
print("D rehydrate:",tm.rehydrate("AMOUNT_1 and AMOUNT_01 and B0010 Q1000"))
tm=TokenMap(R); print(tm.tokenise_prompt("iyer chem lent 1,50,000.50"), tm._reverse)
t("E",lambda: tm.detokenise_args('{"amount":"AMOUNT_1","text":"G001"}'))
t("F",lambda: tm.detokenise_args('{"amount":AMOUNT_1}'))
t("H Q1000",lambda: tm.detokenise_args('{"text":"Q1000 results"}'))
t("m6 G in borrower_name",lambda: tm.detokenise_args('{"borrower_name":"G001"}'))
t("m6 AMOUNT in borrower_group",lambda: tm.detokenise_args('{"borrower_group":"AMOUNT_1"}'))
t("m6 G in amount",lambda: tm.detokenise_args('{"amount":"G001"}'))
t("m6 embedded G in amount str",lambda: tm.detokenise_args('{"amount":"G001 x"}'))
t("m6 nested items",lambda: tm.detokenise_args('{"items":[{"borrower_name":"G001"}]}'))
t("m6 list under borrower_group",lambda: tm.detokenise_args('{"borrower_group":["G001","AMOUNT_1"]}'))
tm=TokenMap(R)
for x in ["call_1234567","2026_03_004","ts 1727300000","phone 9876543210","id=abc12345","2026-09-26T10:00:00","26/09/2026","rate 12.5","v1.2.3","limit 10","12%","3 months","Q1 2026","01/04/2026","+91 98765 43210","98765-43210","pin 560001","ISBN 978-3-16"]:
    try: assert_no_plaintext({"messages":[{"role":"user","content":x}]},tm); print("ok   ",x)
    except PlaintextLeakError: print("RAISE",x)
R2=EntityResolver({"borrower_name":["amount"],"borrower_group":["status"]})
tm=TokenMap(R2)
t("schema", lambda: assert_no_plaintext({"messages":[],"tools":[{"description":"the loan amount in rupees"}]},tm))
tm=TokenMap(R); tm.token_for(TokenKind.AMOUNT, Decimal("3"))
t("months3", lambda: assert_no_plaintext({"messages":[{"role":"tool","months":3}]},tm))
t("count3 unlisted", lambda: assert_no_plaintext({"messages":[{"role":"tool","n":3}]},tm))
