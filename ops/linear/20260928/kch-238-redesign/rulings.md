# KCH-238R review 1 — ORCHESTRATOR RULINGS (owner decision 2026-09-28: digit-glued names = DEBT)

OWNER: the STOP-AND-REPLAN class (stored name glued to digits: UPI ids, e-mail, handles — `rakeshsharma92@okicici`, `anil.sharma85@gmail.com`, `@deepakmenon77`) is accepted as DEBT owned by KCH-239. Do NOT fix it here. Add ONE xfail(strict=True) test per example documenting the known leak, so a future fix flips it loudly.

Fix in this cycle (cycle 1 of 2):
- M1 (peel makes a different person an exact token): a hit found ONLY by peeling a suffix is never exact — emit Q carrying the full typed text (e.g. "sharmaji", "vishwas"), so the KCH-236 confirm step always applies. This re-rules F1: `anil sharmaji` → a Q token (masked, needs confirm), NOT `B001-ji`. Whole-run exact matches are unchanged. Update the F1 tests to assert masked + Q, and add tests for vishwas / sai balaji / ravi tejas. The egress/guard side keeps catching peeled forms (no leak).
- M2 (guard G3 raises on the model's own replies): (a) a string that already passed the guard is never re-checked against Q/N texts issued LATER; (b) skip G3 (issued Q/N texts) for assistant-role message content — G1/G2/G4 still apply to it. Tests: the reviewer's 4 realistic replies (Hinglish/domain/chatty) and the "type `unconfirmed` once, system prompt raises forever" case → no raise; a real leak in a user or tool message is still caught.
- m5 (licence notices): add the full VarCon / Kuenning BSD text and the full WordNet 1.6 disclaimer to safe_words.py's header, per SCOWL's README. Not deferrable (public repo).
- m8 (test gaps): kill surviving mutants R5, R6, R11 (depositor_name must reject B), R19 (novel-name min length), R20 with named tests. R1 is equivalent.
- m1–m4, m6, m7, m9, m10: DEBT, listed in the PR body with owners (KCH-239 / KCH-243).

## ORCHESTRATOR RULINGS — review 2 (PASS) → cycle 2 of 2 (small, then commit)
- n1 (FIX NOW — it is a leak path): write guard-cache verdicts only after the WHOLE request body passes; a request that raises caches nothing. Test = the reviewer's p2_m2.py reproducer (fails first on current code).
- n3 (FIX NOW): test that after N001 = "Rohan Kapadia", "rohan kapadia will pay" passes in an assistant message and raises in a tool message (kills C7).
- n4 (FIX NOW): test that `developer`, `System` (other case), a message with no role, and a non-Mapping message all still get G3 (kills C12).
- `bg 13ji`, `b1ji`: add to DIGIT_GLUED_LEAKS as xfail(strict) — owner-ruled DEBT class.
- n2 (DEBT, KCH-239 hard requirement, PR body): the G3 skip trusts the role label. KCH-239 must add contract tests — the system message equals the content-hashed prompt constant, and assistant history equals the raw completion — or register app/model-authored strings explicitly.
- No other changes.
