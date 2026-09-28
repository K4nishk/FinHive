from common import *
SYS=open("sysprompt.txt").read()
tm=TokenMap(R)
print("sys alone:", end=" ")
try: assert_no_plaintext({"messages":[{"role":"system","content":SYS}]},tm); print("ok")
except PlaintextLeakError as e: print("RAISE",e)
vocab="""amount rate months days interest total exposure borrower depositor group loan loans status overdue active pending due date giving extend extension paid paidoff history cheque tds flag rupee rupees money share trade traders textile textiles chem chemical holding holdings sons son circle desk bank branch office city mumbai chennai bangalore delhi pune family firm company client customer friend brother uncle aunty sir madam boss manager agent partner owner list show give tell find check search sort filter top most least biggest smallest next last this week month year quarter today tomorrow yesterday report summary portfolio please thanks hello hi okay yes no stop cancel help menu settings data record records ledger account accounts balance principal cash deposit deposits lend lent borrow borrowed repay repaid owe owes owed pay payment payments rao nair bhat iyer sharma gupta verma menon qureshi anil meera naveen pooja asha deepak kavita farhan suresh lakshmi rakesh vikram sunita arjun ramesh raman ravi ramu arun asha anita sunil sunny deep pooja verma textile gupta sons menon trader rao holding shah reddy patel singh khan joshi""".split()
qwords=[]
for w in vocab:
    t=TokenMap(R); out=t.tokenise_prompt(f"show {w} loans")
    q=[v[1] for k,v in t._reverse.items() if v[0] is TokenKind.MENTION]
    if q: qwords.append((w,q,out))
print("words that become Q mentions:", [(w,q) for w,q,_ in qwords])
# which of those brick the system prompt after the user types them
brick=[]
for w,q,out in qwords:
    t=TokenMap(R); u=t.tokenise_prompt(f"show {w} loans")
    try: assert_no_plaintext({"messages":[{"role":"system","content":SYS},{"role":"user","content":u}]},t)
    except PlaintextLeakError as e: brick.append((w,str(e)[:60]))
print("SYSTEM PROMPT BRICKED after user typed:", brick)
