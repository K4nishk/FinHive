from common import *
def guard_text(text, tm, role="user"):
    try: assert_no_plaintext({"messages":[{"role":role,"content":text}]},tm); return "ok"
    except PlaintextLeakError as e: return "RAISE:"+str(e)[:70]
print("## ingress false positives (should stay plain) + guard on output")
fps=["due on 2026-09-26","due 26/09/2026","due 26-09-2026","due 09/26/2026","due 26.09.2026","due 26 Sep 2026","due Sep 26, 2026","due 26th September 2026","due September 2026","loans from 2025 to 2026","FY2026-27","FY 2026-27","FY26","Q2 2026","Q2-2026","2026 Q2","H1 2026","12%","12 %","12.5% p.a.","rate 12 percent","3 months","3 month","90 days","extend by 6 months","top 5","top 1000 borrowers","ref 2026_03_004","2026_03_004","refs 2026_03_004 and 2026_03_005","call 9876543210","phone +91 98765 43210","+91-9876543210","pin 560001","loan #1234","page 1000","1500 loans","since 1999","year 2027","in 2030","by 2026 end","2026","12:30","10:30 am","v1.2.3","between 1 and 3 months","3/4 of loans","50% of 2 lakh"]
tm=TokenMap(R)
for p in fps:
    t2=TokenMap(R)
    try: out=t2.tokenise_prompt(p)
    except Exception as e: print(f"{p!r:34} RAISE {e}"); continue
    changed = "" if out==p else "  <-- CHANGED"
    print(f"{p!r:34} -> {out!r:36} guard={guard_text(out,t2)}{changed}")
