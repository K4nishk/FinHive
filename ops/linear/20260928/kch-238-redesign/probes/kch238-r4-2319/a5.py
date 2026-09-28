import sys, importlib.util, time, random, statistics, cProfile, pstats, io
from common import R
random.seed(1)
words=["show","me","the","overdue","loans","for","anil","sharma","and","meera","iyer","lent","45,000/-","2 lakh","in","2026","ref","2026_03_004","b1,b2","bg10/bg13","sharma-ji","o'brien","what","is","exposure?","12%","3","months","Q2","iyer chem","gupta & sons","naveen","rao's","mumbai","desk","rs 500","please","total"]
s=[]
while len(" ".join(s))<2000: s.append(random.choice(words))
p=" ".join(s)[:2000]
for label,path in [("final",None),("cycle1",sys.argv[1])]:
    if path:
        spec=importlib.util.spec_from_file_location("tokc1",path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    else:
        import loan_manager.application.agent.tokeniser as m
    ts=[]
    for _ in range(3):
        tm=m.TokenMap(R); t=time.perf_counter()
        try: tm.tokenise_prompt(p)
        except Exception as e: print(label, "raise", e); break
        ts.append((time.perf_counter()-t)*1000)
    print(label, "2000-char median ms", statistics.median(ts) if ts else None)
pr=cProfile.Profile(); pr.enable()
import loan_manager.application.agent.tokeniser as m
m.TokenMap(R).tokenise_prompt(p); pr.disable()
st=io.StringIO(); ps=pstats.Stats(pr,stream=st); ps.sort_stats("cumulative")
for (f,l,fn),(cc,nc,tt,ct,callers) in sorted(ps.stats.items(), key=lambda kv:-kv[1][3])[:14]:
    print(f"{ct:7.2f}s cum {nc:8} calls  {f.split('/')[-1]}:{l} {fn}")
