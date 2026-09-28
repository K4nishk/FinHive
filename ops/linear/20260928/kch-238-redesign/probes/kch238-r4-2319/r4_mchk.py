from common import *
for p in ["bg 13","BG 13","bg-13","bg_13","bg1 vs bg13","b 1"]: run(p)
print("MONEY_RE 2,026:", bool(MONEY_RE.search("2,026")), " 2,000:", bool(MONEY_RE.search("paid 2,000")))
tm=TokenMap(R); tm.tokenise_prompt("Q2 2026")
print(tm.tokenise_observation({"message":"paid 2,026 on 2026-09-25"}))
