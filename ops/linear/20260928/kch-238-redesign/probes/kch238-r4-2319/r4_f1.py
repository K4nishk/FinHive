import json, re, sys
from datetime import date
from decimal import Decimal
sys.path.insert(0,"pkg")
from fx import make_loan, uow_factory_for
from loan_manager.application.agent.tokeniser import *
from loan_manager.application.agent.tool_registry import parse_args
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.domain.services.entity_resolver import EntityResolver
rows=[("azim premji","premji group","prem kumar","kumar family"),
      ("rameshbhai patel","patel group","ramesh gupta","gupta sons"),
      ("hansaben shah","shah group","hansa mehta","mehta trust"),
      ("balaji rao","rao group","bala krishnan","krishnan co"),
      ("anil sharma","sharma group","meera iyer","iyer chem"),
      ("shivaji more","more group","shiva nair","nair family"),
      ("mukherjee","banerjee","sunil","raji"),]
loans=[make_loan(borrower_name=b,borrower_group=bg,depositor_name=d,depositor_group=dg,amount=Decimal(50000+i*1000),giving_date=date(2026,1,1),due_date=date(2026,6,1)) for i,(b,bg,d,dg) in enumerate(rows)]
uf=uow_factory_for(loans); reg=build_read_registry(uf,FixedClock(date(2026,9,25)))
R=BuildEntityResolver(GetAutocompleteValues(uf)).execute()
NAMES=sorted({v for _,v in R.entities()})
def scan(s):
    low=s.lower(); hits=[]
    for n in NAMES:
        # independent: name with any separator (space,-,_) or glued between its words, or any stored word >=4 chars in clear
        for w in n.split():
            if len(w)>=4 and re.search(r"(?<![^\W_])"+re.escape(w)+r"(?![^\W_])",low): hits.append(w)
            elif len(w)>=4 and re.search(re.escape(w[:-2] if w.endswith(("ji","ben")) else "\x00")+r"[-_ ]?(ji|ben|bhai)",low): hits.append(w+"*")
    return sorted(set(hits))
def guard(s,tm):
    try: assert_no_plaintext({"messages":[{"role":"user","content":s}]},tm); return "guard-ok"
    except PlaintextLeakError as e: return "GUARD-RAISE"
print("=== ingress")
for p in ["azim premji","Azim Premji ko 5000 do","premji","Premji","AZIM PREMJI","rameshbhai patel","Rameshbhai","hansaben shah","balaji rao","Balaji","shivaji more","mukherjee","banerjee","sunil","raji","anil sharmaji","anil sharmaJI","anil SHARMAJEE","anil sharmaji's loans","sharmaji, anil","anil sharmajee","anil sharmasahib","anil sharmabhaiya","meera iyerben","meera iyerdidi","meera iyerbehen","anil sharma ji","anil sharma-ji","Sharma-ji","anil sharmaजी","sharmaji ka loan","puja","pujaji","rajiji","sunilji","kumarji","guptaji ko 5000 do","iyer chemji","bg1ji"]:
    tm=TokenMap(R)
    out=tm.tokenise_prompt(p)
    print(f"  {p!r:28}-> {out!r:30} {guard(out,tm):12} clear={scan(out)} map={ {k:str(v[1]) for k,v in tm._reverse.items()} }")
print("=== egress: free-text scrub")
for s in ["ask the user to choose between 'azim premji' or 'prem kumar'","azim premji owes","rameshbhai patel owes","hansaben shah","balaji rao","shivaji more","anil sharmaji owes","Sharmaji owes","anil sharma owes","premji group"]:
    tm=TokenMap(R); tm.tokenise_prompt("hello")
    t=tm.tokenise_observation({"message":s})["message"]
    print(f"  {s!r:62}-> {t!r:50} {guard(t,tm)} clear={scan(t)}")
print("=== egress: real resolve_entity tool (ambiguous candidates in next_action)")
for q in ["premji","prem","azim","ramesh","hansa","bala","shiva","patel","rao"]:
    tm=TokenMap(R); qt=tm.tokenise_prompt(q)
    obs=reg.handler("resolve_entity")(parse_args("resolve_entity",{"text":tm.detokenise_args(json.dumps({"text":qt})) and q}))
    t=json.dumps(tm.tokenise_observation(obs),ensure_ascii=False)
    print(f"  {q!r:10} {obs.get('status')} {guard(t,tm)} clear={scan(t)} next={json.loads(t).get('next_action','')[:110]!r}")
