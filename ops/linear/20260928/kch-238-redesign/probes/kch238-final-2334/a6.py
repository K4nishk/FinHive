import time, random, statistics
from common import vals
from loan_manager.domain.services.entity_resolver import EntityResolver
from loan_manager.application.agent.tokeniser import TokenMap
random.seed(3)
first=["anil","sunil","meera","ravi","pooja","asha","deepak","naveen","kavita","farhan","suresh","lakshmi","rakesh","vikram","sunita","arjun","ramesh","priya","rohit","neha"]
last=["sharma","iyer","gupta","verma","rao","nair","menon","bhat","qureshi","reddy","patel","shah","das","joshi","kulkarni","pillai","singh","khan","mehta","desai"]
p="what is the total exposure of anil sharma and meera iyer this month, and who is overdue?"
p2=(p+" ")*23; p2=p2[:2000]
for n in (75,300,1000):
    names=list({f"{random.choice(first)} {random.choice(last)}{'' if i<400 else ' '+str(i)}" for i in range(n)})
    v={"borrower_name":names,"borrower_group":[f"{l} group" for l in last],"depositor_name":names[:n//3],"depositor_group":["mumbai desk","dg1"]}
    R=EntityResolver(v)
    for label,q in (("88-char",p),("2000-char",p2)):
        ts=[]
        for _ in range(3):
            t=time.perf_counter(); TokenMap(R).tokenise_prompt(q); ts.append((time.perf_counter()-t)*1000)
        print(f"universe~{len(R.entities()):5} {label:9}: {statistics.median(ts):9.1f} ms")
