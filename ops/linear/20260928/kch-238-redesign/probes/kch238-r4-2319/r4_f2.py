from common import *
from decimal import Decimal
print("--- ingress: 4-digit year-range amounts")
for p in ["lend ₹2000 to b1","lend 2,000 to b1","lend 2000 rs to b1","paid 2000","2000/-","Rs. 1999 due","gave 2026 to b1","in 2000 paid 2000","2000 rupees","loan of 2000","since 2000 he owes 2000","amount 2050","in 2000","by 2000","FY 2000","year 2000","till 2000 rs"]:
    run(p)
print("--- guard: known amount 2000 (from 'paid 2000'); leaked renderings")
tm=TokenMap(R); tm.tokenise_prompt("paid 2000"); tm.tokenise_prompt("paid 2000.50"); tm.tokenise_prompt("paid 1899.50")
print(" amounts:", sorted(tm.amounts()))
for s in ["₹2000","Rs 2000","Rs.2000","INR 2000","2,000","2000.00","2000/-","2000 rupees","2000rs","2000 rs","the loan is 2000","2000","2000.50","2,000.50","1899.50","1,899.50","due 2000-01-01","₹ 2,000"]:
    try: assert_no_plaintext({"messages":[{"role":"assistant","content":s}]},tm); r="PASS (not caught)"
    except PlaintextLeakError as e: r="caught"
    print(f"  {s!r:22} {r}")
for leaf in [2000, 2000.5, Decimal("2000.00"), 1899.5]:
    try: assert_no_plaintext({"messages":[{"role":"tool","content":{"principal":leaf}}]},tm); r="PASS"
    except PlaintextLeakError: r="caught"
    print("  numeric leaf",repr(leaf),r)
for args in ['{"amount": 2000}','{"amount": "2000"}','{"amount": 2000.5}']:
    try: assert_no_plaintext({"messages":[{"role":"assistant","content":None,"tool_calls":[{"id":"c1","type":"function","function":{"name":"format_inr","arguments":args}}]}]},tm); r="PASS"
    except PlaintextLeakError: r="caught"
    print("  tool_call args",args,r)
print("--- scrub: observation free text with plaintext year-shaped amount")
for obs in [{"message":"principal 2000 overdue"},{"message":"principal 2000.50 overdue"},{"message":"principal 2,000 overdue"},{"message":"in 2000 principal"},{"message":"due after 2026-09-25"}]:
    tm2=TokenMap(R); tm2.tokenise_prompt("paid 2000 and 2000.50 in Q2 2026")
    try: print("  ",obs,"->",tm2.tokenise_observation(obs))
    except Exception as e: print("  ",obs,"RAISE",type(e).__name__,str(e)[:80])
