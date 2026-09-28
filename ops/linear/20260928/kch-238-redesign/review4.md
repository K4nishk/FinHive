# KCH-238 review 4 — FINAL, after fix cycle 3

Reviewer: opus. Worktree `/home/user/wt/kch-238`: cycle 3 is uncommitted and touches 2 files. The worktree was never edited.
- `tokeniser.py` md5 is `cb1eba83bc961a494329222c6b0c5834`, identical before and after every mutant run.
- Scratch dir: `/tmp/claude-0/-home-user-FinHive/c2cf79a7-e479-5303-814c-46d460e117b4/scratchpad/kch238-r4-2319/`.
  - Trees: `tree/` (cycle 3), `tree_head/` (HEAD, before cycle 3), `tree_fix/` (prototype fixes), `tree_mut/` (mutants).
  - New attacks: `r4_f1.py` (honorific), `r4_f2.py` (year exemption), `r4_edge.py`, `r4_perf.py`, `r4_perf2.py`, `r4_mchk.py`.
  - `mut4.py` holds the mutants. The fix prototype is `fix_prototype.diff`, 70 lines.
  - Reproducers from reviews 1–3 were copied in and rerun: `r1_probe*`, `probe*`, `p3b`, `p5*`, `p6`, `p7`, `a2`, `a3`, `a6`, `a9`, `a9b`, `a10`.

File:line refs are into `src/Loan Manager/loan_manager/application/agent/tokeniser.py` (TK) and
`src/Loan Manager/tests/unit/application/agent/test_tokeniser.py` (TT).

## VERDICT: FAIL

- **One BLOCKER, a cycle-3 regression.** The honorific split rewrites a stored name that itself ends in ji/bhai/ben
  ("Azim Premji", "Rameshbhai Patel", "Balaji Rao", "Hansaben Shah"). That happens whenever the stem is another
  stored name's word. The egress scrub then no longer finds the name. The full name leaks through a real
  `resolve_entity` observation, and the guard does not see it. HEAD scrubbed all of these cleanly.
- **Two MAJORs.**
  - The multi-word prefilter leaks an unseparated stored value typed with a space. This is also a regression.
  - F3 is not met on realistic input. The passing 150 ms test repeats one sentence 23×.
- **What cycle 3 did achieve:**
  - F2 is fixed: 0 false raises, 0 leaks.
  - m1 works at ingress.
  - Every earlier reproducer is unchanged.
  - The 56-call sweep has 0 leaks.
  - Coverage is 100%.

All three problems have small, tokeniser-local fixes. The scratch prototype (`tree_fix/`) closes the BLOCKER and
MAJOR-1 and brings realistic 2,000-char prose from 505 ms to 149 ms. With it, the agent suite passes 300/300 and
every reproducer and sweep is unchanged (0 leaks, 0 false raises).

## Gates (reviewer-run, CI parity)

Env: `QT_QPA_PLATFORM=offscreen` and `PATH=/home/user/FinHive/.venv_pg/bin:$PATH`. The integration lane also sets
`TEST_DATABASE_URL=…:5433/finhive_test_disposable`.

| Gate | Result |
|---|---|
| MVP1 `pytest tests/ --cov` | **804 passed, 1 skipped**. TOTAL 61% (pre-existing) |
| tokeniser coverage | 198 passed. `tokeniser.py` 511 stmts, **100%** |
| root `pytest tests/unit` | **241 passed, 2 skipped** (opt-in `test_local_dev_setup.py:201,217`) |
| `lint-imports` | 3 kept, 0 broken |
| integration | 17 passed, 1 skipped (`test_seed_service_account.py:47`) |
| `ruff check` (2 files) | **FAILED, 2 errors**: TT:1801:22 and TT:1959:11 `S311` (see m-R4) |

## Task 1 — the ruling items, verified independently

- **F1 (ruled cases): works.**
  - `anil sharmaji`→`B001-ji`; `Guptaji ko 5000 do`→`Q001-ji ko AMOUNT_1 do`; `Sharma-ji`→`Q001-ji`.
  - `puja` and `raji` stay plain.
  - `naveen raoji`→`B001-ji`. Case variants work: `sharmaJI`, `SHARMAJEE`, `-sahib`, `-bhaiya`, `-ben`, `-didi`, `-behen`.
  - Egress `ask anil sharmaji to confirm`→`ask B001-ji to confirm`.
  - The separator lets TOKEN_RE `\b` match again.
  - The attacks below break it.
- **F2: fixed.**
  - `a9.py` is the realistic 98-message conversation with "in Q2 2026" in turn 5, dated 2026-09-25 throughout,
    built through `build_request_body`. It gives **0 false raises, 0 independent leaks** (review 3: 41 false raises).
  - `a9b.py` also gives 0/0.
  - `a10.py`: every one of the 28 year-prompt × date-body pairs is ok.
  - The scrub no longer corrupts `due after 2026-09-25`.
  - The TT:1516 re-ruling is correct: `in 1999 paid 1999`→`in 1999 paid AMOUNT_1`, and the guard does not raise.
- **The year exemption opens no ingress hole.** Every one of these is tokenised: `₹2000`, `2,000`, `2000 rs`,
  `paid 2000`, `2000/-`, `Rs. 1999`, `gave 2026 to b1`, `loan of 2000`, `amount 2050`, `till 2000 rs`,
  `since 2000 he owes 2000`→`since 2000 he owes AMOUNT_1`.
- **The guard, with 2000 known:**
  - Caught: `₹2000`, `Rs 2000`, `INR 2000`, `2,000`, `2000/-`, `2000 rupees`, `2000rs`, `₹ 2,000`.
  - Bare `2000` and numeric leaf `2000` pass. The ruling allows that.
  - Beyond the ruling: `2000.00`, `2000.50`, `1899.50`, numeric leaf `2000.5` and `Decimal("2000.00")` also pass
    (see m-R1).
- **F3:** see MAJOR R3.
- **m1: works at ingress.**
  - `anil_sharma_loans`→`B001_loans`, `iyer_chem_bg1`→`G001_G002`, `b1_b2`→`B00x_B00y`.
  - Ref ids are unchanged: `2026_03_004`, `…'s`, and comma-joined.
  - The emitted token is invisible to TOKEN_RE (m-R2).

## BLOCKER

### R1 — The honorific split rewrites stored names that end in ji/bhai/ben, and the egress scrub then leaks them in full with the guard blind (regression)
**Where:** TK:701-735 `_split_honorifics`, called from egress `_scrub` at TK:1035, before `_scrub_names`, and at
ingress at TK:752.
- The split fires whenever the stem is a word of *any* stored value. It never checks whether the whole word is itself
  a stored word.
- `_scrub_names` (TK:1041) then matches the stored value `azim premji` against text that now reads `azim prem-ji`.
  That match fails.
- The guard uses the same whole-value pattern (TK:1280), so it misses the name as well.

**Reproducer** (`r4_f1.py`; real `build_read_registry` over 7 synthetic loans; stored `azim premji` + `prem kumar`,
`rameshbhai patel` + `ramesh gupta`, `balaji rao` + `bala krishnan`, `hansaben shah` + `hansa mehta`):
```
egress resolve_entity("azim")   next_action: "did you mean Q001 prem-ji?"                    guard-ok   (surname in clear)
egress resolve_entity("premji") next_action: "choose between 'azim Q001-ji' or 'Q001-ji group'"  guard-ok   ("azim" in clear)
egress resolve_entity("patel")  next_action: "choose between 'ramesh-bhai Q001' or 'G001'"   guard-ok
egress resolve_entity("rao")    next_action: "choose between 'bala-ji Q001' or 'G001'"       guard-ok
egress free text "azim premji owes" -> "azim prem-ji owes"   guard-ok   (FULL stored name in clear)
                 "rameshbhai patel owes" -> "ramesh-bhai patel owes" ; "hansaben shah" -> "hansa-ben shah" ; "shivaji more" -> "shiva-ji more"
HEAD (tree_head/): every one of the above -> B001 / G001, 0 clear.
ingress "azim premji" -> "Q001 Q002-ji" (was exact B001); "rameshbhai patel" -> "Q001-bhai Q002" (was B001)
```
- Stored names like "Rameshbhai Patel", "Hansaben Shah", "Premji" and "Balaji" are ordinary. So is a ledger that
  also holds a "Ramesh …" or a "Hansa …".
- `resolve_entity` echoes candidate values into `next_action`, so this is a live egress path.
- This is the ARB D-15 class: a stored borrower name reaches the LLM and the backstop is blind.

**Fix** (prototyped in `tree_fix/`, `fix_prototype.diff` hunk 1): in `_split_honorifics`, `continue` when
`word.lower() in self._entity_words`. A stored word is never split. With this, all of the reproducers above give
`B001`/`G001` and 0 clear, and the ruled F1 cases are unchanged.

Tests to add:
- `azim premji` + `prem kumar` at ingress. It must stay an exact `B001`.
- The same pair at egress, through `tokenise_observation({"next_action": "... 'azim premji' ..."})`.
- `rameshbhai patel` + `ramesh gupta`.

## MAJOR

### R2 — The multi-word prefilter skips a window whose collapsed form is a stored value, which leaks it (regression)
**Where:** TK:880. `span_clears` requires every word longer than 3 characters to resolve on its own (TK:841-862).
A stored value typed without a separator (`iyerchem`, `sharmatraders`) only resolves through the resolver's
**collapsed-equality** path. That path compares the whole string, never word by word. The ≤3-char exemption only
rescues short codes such as `bg 13`.

**Reproducer** (`r4_edge.py`, stored group `iyerchem`):
```
cycle 3:  "iyer chem" -> "iyer chem"   guard-ok   (stored group text in clear)
HEAD:     "iyer chem" -> "G001"
```
The guard only knows the whole value `iyerchem`, so it is blind to this.

**Fix** (prototyped, `fix_prototype.diff`): do not skip a multi-word window when its separator-stripped lowercase form
is in a precomputed `frozenset` of collapsed stored values. That is one set lookup.

Test to add: stored `iyerchem`; the prompt `iyer chem` must give `G001`.

### R3 — F3 is not met on realistic input; the passing 150 ms test repeats one 88-char sentence 23× (so 22/23 of the work is cache hits)
**Where:**
- TT:1855 `prompt = ((sentence + " ") * 23)[:2000]`. This is the orchestrator's "43 ms on a realistic 2,000-char prompt".
- TT:1911 `< 900` on the word salad.

**Measured** (median of 5, no tracer, DEMO universe of ~75 names, this container):
```
repeated sentence 2000 chars           60 ms   (TT:1855 shape)
single 88-char question                75 ms   <- the real per-turn floor
DISTINCT realistic prose, 2000 chars  505 ms   (r4_perf2.py: ordinary multi-request paragraph, no repetition)
DISTINCT realistic prose, 1000 chars  452 ms
a3 word salad 2000                    671 ms   (TT:1911 threshold 900 -> only 1.34x headroom here)
5000 / 20000 chars                   1260 / 2913 ms
synthetic universe, 88-char question:  ~112 names 115 ms · ~342 names 336 ms · ~1,204 names 1,858 ms (review3: 4.3 s)
synthetic universe, 2000-char repeat:  ~1,204 names 1,935 ms (review3: 112 s)
```
- The profile is unchanged in kind: 98% is in `entity_resolver.resolve`, about 2 ms for each **distinct** word × 75
  names. The cache only helps when words repeat.
- The prefilter was not built as ruled. The ruling said "first word shares no prefix with any stored name word".
  The implementer built a per-word resolve instead. TT:1880's claim, that the ruled prefilter "could not be applied"
  without breaking `bg 13`, does not hold: `bg` is a prefix of the stored word `bg13`.

**Judgement.**
- The 900 ms word-salad bound is **acceptable as DEBT**, as a regression guard. It needs a note on flake headroom:
  1.34× here.
- The 150 ms test **is not evidence that F3 is met**. It measures a cached replay.
- Nothing leaks, and KCH-239 tokenises off the UI thread. So this alone would be a waivable MAJOR, not a correctness
  stop.
- But a cycle is needed anyway for R1, and the fix is cheap. Fold it in.

**Fix** (prototyped, `fix_prototype.diff`): a symmetric-delete (SymSpell, distance 1) neighbourhood index.
- Build it once per `TokenMap` over every stored token, whole normalised value and collapsed value.
- Before resolving a single-word core, check whether any of its ≤1-deletion variants is in that index.
- This is sound for the resolver's gate. Every fuzzy path needs OSA ≤ 1 or equality (`entity_resolver.py:181-193`,
  `:199-203`), and the collapse path needs equality.
- Measured with it: distinct prose 2,000 chars **149 ms**, 88-char question 30 ms, repeated 2,000 chars 40 ms,
  word salad 395 ms. For ~1,204 names: 88-char 1,154 ms.
- Replace TT:1855's corpus with non-repeating prose (the paragraph is in `r4_perf2.py`) and assert < 150 ms.
- If the owner waives this instead: DEBT to **KCH-239**. Tokenise off the UI thread, cap the prompt at 2,000 chars,
  and measure the real ledger size **[REVIEW REQUIRED]**.

## MINOR

| id | Finding (file:line) | Reproducer | Fix | DEBT? |
|---|---|---|---|---|
| m-R1 | The year exemption is keyed on the amount's magnitude, not on the rendering (TK:1209-1219, TK:1238). The ruling said a "bare 4-digit" rendering. `to_integral_value` rounds half-even, so 1899.50 counts as year-shaped too. | Known 2000.50 / 1899.50 / 2000: the guard passes `2000.50`, `1899.50`, `2000.00`, leaf `2000.5`, leaf `Decimal("2000.00")`. The scrub still tokenises them through `_pass_amounts`. | `if rendering.isdigit() and _is_year_shaped_amount_value(amount)` (prototyped; all tests pass). | Safe; this is backstop-only. Fold into the cycle, or **KCH-239**. |
| m-R2 | A token emitted before `_` is invisible to TOKEN_RE `\b` (TK:122). TT:2000 pins the broken form `B001_loans`. | `rehydrate("B001_loans")`→`B001_loans`. `detokenise_args` does not restore it. `b1_b2`→`B003_B004` is shown to the user as is. | Emit `token + "-"` after `_`, or accept `_` in TOKEN_RE's right boundary. | **KCH-239** |
| m-R3 | The possessive after an honorific leaks the surname (TK:721). The regex is `$`-anchored on `sharmaji's`. | `anil sharmaji's loans`→`Q001 sharmaji's loans`, guard-ok. | Peel `_POSSESSIVE_RE` before matching the suffix (prototyped). | Fold in with R1 (same function), else **KCH-239** with m2. |
| m-R4 | ruff S311 fails. `random.choice`/`random.Random` at TT:1801 and TT:1959. Root CI ruff only covers `finhive tests`, so CI stays green, but the brief's gate is red. | `ruff check …/test_tokeniser.py` | `# noqa: S311` (a test corpus, not crypto) | Fix in the cycle (gate). |
| m-R5 | Test gaps (mutant survivors, below). No test pins `bg 13`/`bg-13`/`bg_13`, although TT:1880 cites it as the reason for the ≤3 rule, and removing the rule leaks `bg 13` in clear. There is also no ruled "full read-tool turn" F2 test: TT:1685 uses a hand-built body, where the ruling asked for "report for Q2 2026" through tools. | `mut4.py` F3/F2/D2–D5 | Tests: `bg 13`→bg13 token with a 1-value universe; `rameshbhai`/`-ben` suffixes; upper-case suffix; stem-in-store check (a stored `pu`); a real `get_current_context` turn. | Fold in. |
| m-R6 | The char cap and the prefilter change pass-3 grouping for noise words. `sharma group`/`sharma family` with the stored group `sharma` becomes `Q001 group` (HEAD: one `Q001` = `sharma group`), which loses the group hint for resolve. Nothing leaks. | `r4_edge.py` | Treat `NOISE_TOKENS` words as clearing (prototyped). Exclude noise words from `_collapsed_len`. | **KCH-239** |
| m-R7 | A Devanagari honorific is not split (the ruling's list is Latin only; review 3 F1 item 3 asked for it). | `anil sharmaजी`→`Q001 sharmaजी` | Split at a Latin↔Devanagari script change. | **KCH-239** (m3 family) |
| m-R8 | The egress `_` boundary: `_value_boundary_pattern` (TK:458) and the guard use `(?<!\w)`. Tools do not emit `_`-glued names today. | `tokenise_observation({"message":"anil sharma_2026"})` is unchanged; the guard passes `anil sharma_x`. | Use `(?<![^\W_])`/`(?![^\W_])`. | **KCH-239** |

Carried DEBT is unchanged from review 3: m2–m8, plus the KCH-239/243/250 items. It goes in the PR body per the ruling.

## Task 4 — regressions

- Every earlier reproducer (`r1_probe1/3/4`, `probe1/3/4`, `p3b`, `p5`, `p6`, `p7`) gives **byte-identical output**
  to review 3. The only differences are column truncation and traceback line numbers.
- Compact codes are intact:
  - `bg1 vs bg13`→`G001 vs G002`;
  - `bg 13`, `BG 13`, `bg-13` and `bg_13`→the bg13 token;
  - `b1,b2,b3`, `bg10/bg13` and `dg1,dg2` resolve per code;
  - `bg1 0`→`G001 0`.
- **The 56-call READ sweep has 0 leaks and 0 guard raises**, with both a fresh map and a shared map (`probe2.py`).
- `a9b` 0/0 and `a9` 0/0.
- The `tree_fix/` prototype gives the same result on every item above.

## Task 5 — mutants of the cycle-3 properties (`mut4.py`, 22 run)

| Mutant | Result |
|---|---|
| D1 `ji` dropped | killed |
| D2 bhai/bhaiya/ben/behen/didi dropped | **SURVIVED** (only `ji`/`jee` tested) |
| D3 suffix case-sensitive | **SURVIVED** (no upper-case suffix test) |
| D4 stem-is-stored-word check removed | **SURVIVED** (masked by the 3-char floor: `puja`/`raji` stems are 2 chars) |
| D5 stem floor 3→1 | **SURVIVED** (masked by D4's check) |
| D6 no `-` separator | killed |
| D7 not applied at ingress | killed |
| D8 not applied in egress scrub | killed |
| D9 stem compared case-sensitively | killed |
| E1 guard year exemption removed | killed |
| E2 scrub year exemption removed | killed |
| E3 scrub skips grouped too | SURVIVED, **equivalent** (`_pass_amounts` retokenises `2,026`) |
| E4 year range → any 4-digit | killed |
| E5 grouped check after year exemption | SURVIVED, **equivalent** (MONEY_RE flags `2,026` independently) |
| F1 resolve cache disabled | killed (timing) |
| F2 char cap on raw len | **SURVIVED** (behaviour differs only for a tiny universe: `bg 13` vs sole `bg13`) |
| F3 ≤3-char always-clear rule removed | **SURVIVED, and it LEAKS**: `bg 13`/`bg-13`/`bg_13` stay in clear |
| F4 multi-word prefilter removed | killed (timing) |
| F5 window char cap removed | killed |
| F6 both char caps removed | killed |
| F7 pass-3 noise skip removed | killed |
| G1 `_` back as a word char | killed |

Of 22 mutants, 14 were killed and 8 survived: 2 equivalent and 6 test gaps (m-R5). F3 is the serious one: a leak
guard with no test.

## What cycle 4 needs (all tokeniser-local; prototype in `fix_prototype.diff`)
1. R1: never split a stored word. Add the tests.
2. R2: collapsed-value rescue in the prefilter. Add the test.
3. R3: the SymSpell-1 prefilter, and a non-repeating 150 ms corpus.
4. Recommended, all cheap: m-R1 (rendering check), m-R3 (possessive), m-R4 (noqa), m-R5 (tests).
