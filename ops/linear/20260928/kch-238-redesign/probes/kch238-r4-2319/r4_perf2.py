from common import *
import statistics, time, cProfile, pstats, random
prose=("Hi, I need a quick overview before the Monday review. First, how much is anil sharma carrying right now, "
"and is any of it overdue beyond ninety days? Second, meera iyer mentioned she lent money to naveen rao last "
"quarter; can you confirm the principal and whether the interest was already paid out? Third, I think the "
"iyer chem group had two loans that were extended in July, please check their due dates and tell me if either "
"is now pending or active. Also compare total exposure for sharma group against gupta & sons, and list the top "
"five borrowers by outstanding amount with their reference ids. If deepak menon has anything due this week, "
"flag it. Finally, remind me which depositors have the largest share of the book and whether the Mumbai desk "
"still handles kavita nair's accounts. Please keep the answer short, use a table where it helps, and do not "
"round the figures. After that, draft a polite reminder message I can send to each overdue borrower, mention "
"the loan reference and the due date, but leave the amount out because I will add it myself. Also check whether "
"suresh or pooja have any pending loans starting next month, and whether farhan qureshi's loan was renewed. "
"Thanks, and sorry for the long list; the auditors are visiting on Thursday and I want everything ready.")
prose=(prose+" "+prose)[:2000]
print(len(prose))
ts=[]
for _ in range(5):
    tm=TokenMap(R); t=time.perf_counter(); out=tm.tokenise_prompt(prose); ts.append((time.perf_counter()-t)*1000)
print(f"distinct prose 2000 median {statistics.median(ts):.1f} ms runs={[round(x) for x in ts]}")
p1=prose[:1000]
ts=[]
for _ in range(5):
    tm=TokenMap(R); t=time.perf_counter(); tm.tokenise_prompt(p1); ts.append((time.perf_counter()-t)*1000)
print(f"distinct prose first 1000 chars median {statistics.median(ts):.1f} ms")
print(out[:400])
tm=TokenMap(R)
cProfile.run("tm.tokenise_prompt(prose)","prof.out")
st=pstats.Stats("prof.out"); st.sort_stats("cumulative").print_stats(8)
print("resolve cache size", len(tm._resolve_cache))
