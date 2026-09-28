from common import *
import random, statistics, cProfile, pstats
random.seed(1)
words=["show","me","the","overdue","loans","for","anil","sharma","and","meera","iyer","lent","45,000/-","2 lakh","in","2026","ref","2026_03_004","b1,b2","bg10/bg13","sharma-ji","o'brien","what","is","exposure?","12%","3","months","Q2","iyer chem","gupta & sons","naveen","rao's","mumbai","desk","rs 500","please","total"]
def mk(n):
    s=[]
    while len(" ".join(s))<n: s.append(random.choice(words))
    return " ".join(s)[:n]
for n in (60,120,250,500,1000,2000):
    p=mk(n); ts=[]
    for _ in range(5):
        tm=TokenMap(R); t=time.perf_counter(); tm.tokenise_prompt(p); ts.append((time.perf_counter()-t)*1000)
    print(f"len {n:5}: median {statistics.median(ts):8.1f} ms")
p="what is the exposure of anil sharma and meera iyer this month?"
t=time.perf_counter(); TokenMap(R).tokenise_prompt(p); print("typical 62-char:", round((time.perf_counter()-t)*1000,1),"ms")
pr=cProfile.Profile(); pr.enable(); TokenMap(R).tokenise_prompt(mk(2000)); pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(14)
