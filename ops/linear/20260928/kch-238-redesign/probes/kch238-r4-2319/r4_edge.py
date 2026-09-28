from common import *
print("longest DEMO values:", sorted(ALL_NAMES,key=len)[-3:])
from loan_manager.domain.services.entity_resolver import EntityResolver
def t(vals,p):
    tm=TokenMap(EntityResolver(vals)); o=tm.tokenise_prompt(p)
    try: assert_no_plaintext({"messages":[{"role":"user","content":o}]},tm); g="ok"
    except PlaintextLeakError: g="RAISE"
    print(f"  {p!r:30} -> {o!r:30} {g} {dict((k,str(v[1])) for k,v in tm._reverse.items())}")
print("char cap vs typo of longest single-word value")
V={"borrower_name":["srinivasan","anil sharma"]}
for p in ["srinivasan","sriniivasan","srinivasann","srinivsan","srinviasan"]: t(V,p)
V2={"borrower_name":["venkatesh srinivasan","anil sharma"]}
for p in ["venkatesh srinivasan","venkatessh sriniivasan","venkatesh sriniivasan"]: t(V2,p)
print("group-hint/noise window vs stored group 'sharma' (no value contains the word 'group')")
V3={"borrower_name":["anil sharma"],"borrower_group":["sharma"]}
for p in ["sharma group","sharma family","sharma grp","the sharma family loans"]: t(V3,p)
print("same on HEAD? run with PYTHONPATH=tree_head")
print("compact codes")
for p in ["bg1 vs bg13","bg 13","bg-13","bg_13","b1,b2,b3","bg10/bg13","dg1,dg2","BG 13","bg1 0"]: run(p)
print("stored value with no separator typed with a space")
V4={"borrower_name":["anil sharma"],"borrower_group":["trust2024","iyerchem"]}
for p in ["trust 2024","iyer chem","iyerchem"]: t(V4,p)
