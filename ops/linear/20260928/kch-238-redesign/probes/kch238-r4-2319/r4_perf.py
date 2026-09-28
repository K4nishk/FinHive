from common import *
import statistics, time
s="what is the total exposure of anil sharma and meera iyer this month, and who is overdue?"
for label,p in [("realistic-repeat 2000",((s+" ")*23)[:2000]),("realistic 88",s),("realistic 500",((s+" ")*6)[:500])]:
    ts=[]
    for _ in range(5):
        tm=TokenMap(R); t=time.perf_counter(); tm.tokenise_prompt(p); ts.append((time.perf_counter()-t)*1000)
    print(f"{label:22} median {statistics.median(ts):7.1f} ms runs={[round(x) for x in ts]}")
