from common import *
import random, statistics
random.seed(1)
words=["show","me","the","overdue","loans","for","anil","sharma","and","meera","iyer","lent","45,000/-","2 lakh","in","2026","ref","2026_03_004","b1,b2","bg10/bg13","sharma-ji","o'brien","what","is","exposure?","12%","3","months","Q2","iyer chem","gupta & sons","naveen","rao's","mumbai","desk","rs 500","x","y","please","total"]
def mk(n):
    s=[]
    while len(" ".join(s))<n: s.append(random.choice(words))
    return " ".join(s)[:n]
for label,p in [("realistic 2000",mk(2000)),("no-space 2000","a"*2000),("punct 2000",",;/"*667),("digits 2000","1"*2000),("names-only 2000",("anil sharma "*170)[:2000]),("sep-glued 2000",("b1,"*667)[:2000]),("unicode marks 2000",("शर्मा "*334)[:2000]),("apostrophes","o'"*1000),("5000 chars", mk(5000)),("20000 chars", mk(20000))]:
    ts=[]
    for _ in range(5):
        tm=TokenMap(R); t=time.perf_counter()
        try: out=tm.tokenise_prompt(p)
        except Exception as e: out=repr(e)
        ts.append((time.perf_counter()-t)*1000)
    t=time.perf_counter()
    try: assert_no_plaintext({"messages":[{"role":"user","content":out}]},tm); g="ok"
    except PlaintextLeakError as e: g="RAISE "+str(e)[:60]
    gt=(time.perf_counter()-t)*1000
    print(f"{label:18} len={len(p):6} tokenise median={statistics.median(ts):8.1f}ms max={max(ts):8.1f}ms  guard={gt:7.1f}ms {g} leak={leak_scan(out)[:5]}")
