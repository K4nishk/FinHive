from decimal import Decimal
from loan_manager.application.agent.tokeniser import *
from loan_manager.domain.services.entity_resolver import EntityResolver
R=EntityResolver({"borrower_name":["suresh iyer","lakshmi iyer"],"depositor_name":["meera iyer"],"borrower_group":["iyer chem"]})
tm=TokenMap(R)
print("prompt:",tm.tokenise_prompt("how much does iyer owe"))
print("A order:",tm.tokenise_observation({"message":"meera iyer and iyer chem are linked"}))
tm=TokenMap(R)
print("B unknown num key:",tm.tokenise_observation({"amount":250000,"new_amount":"250000.00","paid":Decimal("5000.00")}))
print("C 4-digit free text:",tm.tokenise_observation({"notes":["lent 5000.", "year 2000 amount 2000", "45,000/-"]}))
tm=TokenMap(R)
tm.token_for(TokenKind.AMOUNT, Decimal("150000"))
print("D rehydrate:",tm.rehydrate("AMOUNT_1 and AMOUNT_01 and B0010"))
# detokenise kinds
tm=TokenMap(R); tm.tokenise_prompt("iyer chem lent 1,50,000.50")
print(tm._reverse)
print("E:",tm.detokenise_args('{"amount":"AMOUNT_1","text":"G001"}'))
print("F:",tm.detokenise_args('{"amount":AMOUNT_1}'))
print("G:",tm.detokenise_args('{"note":"B0001"}') if False else "")
try: print(tm.detokenise_args('{"text":"Q1000 results"}'))
except UnknownTokenError as e: print("H UnknownTokenError on non-token text Q1000:",e)
# guard false positives
tm=TokenMap(R)
for t in ["call_1234567","2026_03_004","ts 1727300000","phone 9876543210","id=abc12345","2026-09-26T10:00:00","26/09/2026","12,00,000 rows? no", "rate 12.5", "v1.2.3", "limit 10"]:
    try: assert_no_plaintext({"messages":[{"role":"user","content":t}]},tm); print("ok  ",t)
    except PlaintextLeakError: print("RAISE",t)
# names guard against tool schema leaves
R2=EntityResolver({"borrower_name":["amount"],"borrower_group":["status"]})
tm=TokenMap(R2)
try: assert_no_plaintext({"messages":[],"tools":[{"description":"the loan amount in rupees"}]},tm); print("ok schema")
except PlaintextLeakError as e: print("RAISE schema",e)
# numeric leaf known amount collides with count
tm=TokenMap(R); tm.token_for(TokenKind.AMOUNT, Decimal("3"))
try: assert_no_plaintext({"messages":[{"role":"tool","months":3}]},tm); print("ok")
except PlaintextLeakError as e: print("RAISE months=3 when AMOUNT 3 known")
