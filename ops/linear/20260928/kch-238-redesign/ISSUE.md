# NEW ISSUE (to file in Linear): Redesign the ingress/egress tokeniser (supersedes KCH-238's approach)

Labels: product:finhive, agent, security · Project: FinHive M1.1 · Ask FinHive · Blocks: KCH-239 (agent loop), and therefore 240/241/246/248–251/253 and the D-17 spike.

## Why
KCH-238 was parked by the owner on 2026-09-28 after four reviews and three fix cycles (the third owner-approved). The rules-based approach — regex word windows over the typed prompt, fuzzy-resolving each window, plus a regex backstop guard over outbound bodies — kept producing new edge cases, and cycle 3 introduced two regressions while fixing three findings:
- honorific split leaked stored names ending in ji/bhai/ben ("azim premji" → "azim prem-ji" at egress; guard blind)
- multi-word prefilter left collapsed stored values ("iyerchem" typed as "iyer chem") in clear
- realistic 2,000-char prose 505 ms on DEMO (budget 100–150 ms); 1.86 s at ~1,200 names

Full findings: `review3.md`, `review4.md` here. Cycle-3 code (not merged): `round3-uncommitted.diff`. Reviewer's 70-line fix prototype for the round-4 findings: `review4-prototype.diff`. The cycle-2 code is on draft PR #49 (branch feature/kch-238).

## What held (keep / reuse)
TokenMap token scheme (B/D/G/Q/AMOUNT, stable numbering, 999 budget error), egress walk of tool observations with fail-closed unclassified numbers, detokenise_args field-kind checks, rehydrate, INR amount grammar, guard restricted to `messages`, recorded-fake egress test (0 leaks over 56 READ calls + a 98-message replay).

## Redesign direction (for the planner to evaluate, not decided)
- Invert ingress: scan the prompt for the known entity universe (Aho–Corasick / trie over normalised stored names and their word-parts, with separator-insensitive matching), instead of resolving every n-gram window through the fuzzy resolver. Fuzzy resolution only for what's left, via a distance-1 index (SymSpell) — linear in prompt length.
- Treat any unmatched capitalised/name-like span adjacent to a loan verb as a novel-name Q token (covers KCH-243's create/update new names).
- Keep amount handling (grammar held up across reviews).
- Acceptance: every reproducer in review1–4 + the three egress probe sets; realistic 2,000-char prompt < 100 ms at 1,200 names; guard 0 false raises on a full replayed conversation.
