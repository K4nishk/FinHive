import random, re, itertools
import loan_manager.application.agent.tokeniser as T
src=T.MONEY_RE.pattern
a=r'|(?<![\w.,/-])\d{5,}(?:\.\d+)?' + T._MONEY_SUFFIX + T._NO_TRAILING_WORD
assert src.count(a)==1
mut=re.compile(src.replace(a, r'|(?<![\w.,/-])\d{5,}(?:\.\d+)?' + T._NO_TRAILING_WORD), re.I)
orig=T.MONEY_RE
alpha=list("0123456789")*4+list(".,/- _rsRSinupeINRkKlL₹%a\n")+["rs","rupees","inr","/-"," rs","Rs.","lakh","cr","thousand","₹"]
random.seed(7); diff=0; n=0
for L in range(1,14):
  for _ in range(40000):
    s="".join(random.choice(alpha) for _ in range(L)); n+=1
    if bool(orig.search(s))!=bool(mut.search(s)):
      diff+=1
      if diff<10: print("DIFF",repr(s))
# exhaustive structured corpus
pre=["","x ","a-","₹","Rs ","1,","/"]; nums=["45000","45000.5","123456789","99999","100000.00"]; suf=["","/-","rs","rs."," rs","rupees"," rupees","inr"," inr","RS"]; post=["",".",",","x","-","5",".5",",5"," ","/","%"]
for p,nm,sf,po in itertools.product(pre,nums,suf,post):
  s=p+nm+sf+po; n+=1
  if bool(orig.search(s))!=bool(mut.search(s)): diff+=1; print("DIFF",repr(s))
print("cases",n,"diffs",diff)
