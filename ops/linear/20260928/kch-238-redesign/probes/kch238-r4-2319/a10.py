from common import *
ctx='{"ok": true, "today": "2026-09-25", "weekday": "Friday", "fy_label": "FY2026-27", "quarter": "Q2"}'
for prompt in ["Q2 2026 overdue?","loans from 2025 to 2026","due Sep 26, 2026","H1 2026 summary","what happened in 2026?","2026 overdue list","gave 2026 to b1"]:
    tm=TokenMap(R); u=tm.tokenise_prompt(prompt)
    for later in [ctx, "As of 2026-09-25 there are 20 overdue loans.", "due 26 Sep 2026", "FY2026-27"]:
        try: assert_no_plaintext({"messages":[{"role":"user","content":u},{"role":"tool","content":later}]},tm); g="ok"
        except PlaintextLeakError as e: g="RAISE"
        print(f"{prompt!r:28}->{u!r:26} then {later[:40]!r:44} {g}")
tm=TokenMap(R); tm.tokenise_prompt("Q2 2026")
print("scrub corrupts dates:", tm.tokenise_observation({"message":"no loans due after 2026-09-25", "next_action":"retry in FY2026-27"}))
