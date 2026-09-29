# KCH-238R review 2 — re-review after fix cycle 1

Reviewer: opus. Worktree `/home/user/wt/kch-238r` (9a763b4 + 7 uncommitted files). Never edited: md5 of the
agent modules identical before and after (`md5.orig`). All mutation and the MVP1 gate ran on copies.
Scratch: `/tmp/claude-0/-home-user-FinHive/c2cf79a7-e479-5303-814c-46d460e117b4/scratchpad/kch238r-rr-2754/`
(`tree/` = gate copy, `mut/lm` + `mut2.py` + `mut2_results.txt` = cycle-1 mutants, `mutB/lm` + `mut_r.py` +
`mut_r_results.txt` = review-1 mutants rerun, `probes/p2_*.py` = new attacks, `out/`, `out2/` = probe output).

Refs: EI = `src/Loan Manager/loan_manager/application/agent/entity_index.py`, TK = `.../agent/tokeniser.py`,
SW = `.../agent/safe_words.py`, TA = `src/Loan Manager/tests/unit/application/agent/test_tokeniser_acceptance.py`.

## VERDICT: PASS

M1, M2(a), M2(b), m5 and m8 are fixed and verified independently. No BLOCKER. No MAJOR. No new leak class.
Four MINORs (two are guard-backstop gaps, two are test gaps) plus notes. All gates are green at the expected counts.
Digit-glued names are owner-ruled DEBT (KCH-239) and pinned by 6 strict xfails that fail on the leak assertion
itself. They are not re-flagged here.

## Task 1 — cycle-1 fixes verified

| Item | Result | Evidence |
|---|---|---|
| **M1** peel → Q of full typed text | **Fixed.** `vishwas`, `sai balaji's`, `ravi tejas`, `tejas`, `balaji`, `hansaben` all give Q with the full typed text. `anil sharmaji/JI/SHARMAJEE/sahib/bhaiya`, `meera iyerben/didi/behen`, `iyer chemji` all give Q. Whole-run exact names (`azim premji`, `rameshbhai patel`, `balaji rao`, `shivaji more`, `mukherjee`) stay B/G. `rohanji` after N001=`rohan` becomes a new Q (EI:548-549). | `out2/p_peel.txt`, `out2/r4_f1.txt`, differential below |
| **M2(a)** no re-check for later Q/N | **Fixed** (TK:692-708; cache key `(text, G3?)`, amounts still re-checked from `since`). `p_sysp`: 0/136 system-prompt words brick the session (was 2). | `out2/p_sysp.txt`, `p2_m2.py` §M2(a)-1/-3 |
| **M2(b)** G3 skipped for assistant + system | **Fixed** (TK:1012, TK:1052-1053). All 4 realistic replies pass (review 1: 3/4 raised). G1 still raises on a stored name in assistant or system text. G3 still raises in user and tool text. An unknown role, a missing role or a tuple body gets G3 (fails safe). | `out2/p_guardfp.txt`, `p2_m2.py` |
| **m5** licence notices | **Fixed.** SW:42-146 carries SCOWL `Copyright` verbatim: the Atkinson collective notice (664 chars), the full WordNet 1.6 notice and disclaimer (1,653), and the full VarCon block with Atkinson, Titze and the Kuenning BSD text including the disclaimer (2,958). Checked by whitespace-normalised substring against `kch238r-build-19840/scowl-2020.12.07/Copyright`. Kuenning clause 3 (modifications marked) is met at SW:148. Tarball sha256 `5587667c…` matches. Levels used: 10/20 (Moby, Kelk: public domain; WordNet inflections), plus contraction files 35/40/50 (12Dicts/3esl: public domain). UKACD (level 80, verbatim-text clause) is not used. Nothing GPL. **Redistribution in this Apache-2.0 public repo is compatible.** | see note N3 |
| **m8** R5/R6/R11/R19/R20 | **Fixed.** All five are now killed by their named tests (`test_r5_…` … `test_r20_…`). The rerun of all 22 review-1 mutants: 21 killed, and R1 survives (equivalent, as ruled). | `mut_r_results.txt` |
| xfail DEBT pins | 6 `xfail(strict=True)` cases (TA:996-1002, `DIGIT_GLUED_LEAKS` in `tokeniser_reproducers.py:495`). Run with `--runxfail`, each fails on `AssertionError: assert '<name>' not in '<out>'`, never on an error. | — |

## Task 2 — every earlier probe rerun

- Review 1-4 reproducers `r1_probe1-4`, `probe1/1b/2/3/4`, `p3b`, `p5`, `p5b`, `p6`, `p7`, `a1`-`a10`, `r4_edge`,
  `r4_f1`, `r4_f2`, `r4_mchk`, `eq7` (523,850 cases, 0 diffs): no name or amount leaves in clear. The rc=1 cases are
  the intended raises: typed token (`probe1`, `r1_probe1`), unclassified numeric (`probe3`, `r1_probe3`), and
  budget (`p5`). `a5` and `r4_perf2` need a cycle-1 path or old attributes; `a3` and `p_perf` supersede them.
  All `plan/probes/*` copies are byte-identical to the rerun set.
- **56-call READ sweep** (`probe2`, `r1_probe2`): fresh 0 leaks, shared 0 leaks.
- **Replays** `a9`/`a9b` with "Q2 2026": 0 false raises, 0 leaks.
- **Resolver differential:** DEMO 3,906 queries, 0 diffs (`p_diff_demo`, `p_diff`). HARD1200 `p_diff_big`: see
  appendix.
- **Review-1 attack probes:** `p_digitglue` is unchanged (DEBT). `p_d3` gives Q/B at egress, and the guard raises
  on whole names and parts (m2 as before). `p_system` is m1/m7 as before. `p_novel` is m3 as before. In
  `p_propose`, every N/Q round-trips and the only clear word is `Ram` (m3). `p_crossrole` is m6 as before.
  In `a7`, only `Sep 26, 2026` changes (already accepted).

## Task 3 — attacks on the fixes

### M1: can any path still emit an exact B/D/G for text the resolver would not call exact?
Code path: the only ENTITY source is `_whole_hit` with `suffix_len == 0` (EI:535-545). Ingress asks
`exact_entity` of the full typed slice (EI:540). Every suffixed hit, stored (EI:533-534) or dynamic (EI:548-549), and
every single-run peel (EI:562), goes through `_peeled_hit` → MENTION. Merge never extends a whole hit.

Differential (`p2_peel_diff.py`). The oracle: every ENTITY hit's span must be `EntityResolver.resolve(span).exact`
with the same value, and it must not cut an alphanumeric word. Forms: each stored value × (14 honorifics + `jis bhaiji
saabji sji ss a u i am an ya ta raj kumar`) glued to every word, in Title and UPPER case. Also the suffix after
`- space . _ ' ’ ZWJ SHY`, `'s`, `’s`, `s'`, and a collapsed form + `ji`/`s`. Each form sits in 4 contexts. The
token count in `tokenise_prompt` output must equal the ENTITY hit count.

| universe | prompts | not-exact ENTITY | word-cutting ENTITY | token/hit mismatch |
|---|---|---|---|---|
| R1 peel set | 12,500 | 0 | 0 | 0 |
| DEMO active | 94,508 | 0 | 0 | 0 |
| HARD1200 (1/4 of values = 340, scan only, 2 contexts) | 153,564 | 0 | 0 (ASCII-adjacent) | n/a |

The first raw pass flagged 112/1,136 "not exact" and 280/2,568 "cuts". Every one of them was either a ZWJ or soft
hyphen inside the span (the index drops Cf, the resolver does not, which is by design) or a Devanagari suffix glued
to a Latin stem (`vishwaभाई` → `B001-भाई`). The script-change rule pins that case: `anil sharmaजी` → `B001-जी`.
Both were excluded in the refined pass. **Verdict: M1 closed. No Latin peel path yields an exact token.**

### M2(a): can a string that passed earlier hide a leak because it is never re-checked?
- **Same string, already sent, a word in it issued later as N (`p2_m2.py` §1): false alarm.** The bytes already
  left in turn 1. Re-sending them discloses nothing new, and re-checking them only bricks the session (review 1 M2).
- **Same string, cached but NEVER sent: real, narrow → n1 (MINOR).** The cache commits a string's verdict as each
  leaf passes (TK:708), even when a later leaf in the same body raises and nothing is sent.
- **Amounts:** still re-checked from `since`, and R9/R16 are killed.
- **Role separation in the cache key:** correct in code (`p2_c7.py`: the assistant copy passes, and the same string
  in a tool message raises). It is untested → n3.

### M2(b): can a name reach a system-role (or assistant-role) message?
- **Today: no.** No system prompt or loop exists yet. `grep` finds no system-message construction in
  `application/agent` or `tools/`. Spec `docs/MVP1_1_ASK_FINHIVE.md:154,176`: the system prompt is WIKI §3 rules
  inlined, and it is content-hashed (`finhive.prompt_version`), so it is static by design. The KCH-239 text puts tool
  results inside a delimiter in tool messages (G3 applies) and returns validation errors to the model as tool
  results (G3 applies).
- **By construction: yes, if KCH-239 or a later change puts non-static text in those roles → n2 (MINOR).**
  Measured with `p2_m2.py`. The user typed `lend 5000 to Rohan Kapadia, also check sharmma and vishwas`, which gave
  N001, Q001 and N002. Then a `system` message `Context: user asked to lend to Rohan Kapadia; check sharmma;
  vishwas` → **ok (passes)**, and a rehydrated `assistant` history entry `I have prepared a loan for Rohan Kapadia.`
  → **ok (passes)**. G1/G2 would still catch a stored name, so the gap is **novel names (N) and typo/peel Q texts
  only**. Paths that would do this: a turn summary or a "previous request was …" nudge in a system message, history
  trimming that summarises, or UI-rehydrated assistant text written back into history. `developer`, `System`, no
  role and a tuple body all get G3 (fail-safe).

### Over-tokenising: 4 fresh paragraphs (`p2_prose.py`, not the ones pinned in tests)

| para | DEMO | HARD1200 | N/Q words |
|---|---|---|---|
| formal English | 0.0% | 0.0% | — |
| Hinglish | 25.8% | 27.4% | `yaar hafte hue naye aaye mujhe lagta galat isliye baar jinka nikal unko karna padega toh alag hisaab dobara dekh pichli thoda gadbad` (+Q `haan`, `nikal gaya` at 1,200) |
| domain English | 2.9% | 2.9% | `mid`, `sanction` |
| chatty | 13.0% | 13.0% | `yday dupes whats ballpark gonna tmrw` |

This is unchanged from review 1 (the old paragraphs still give 0 / 20.3 / 4.5 / 15.7%). N still merges across
". " (`naye aaye. Mujhe lagta`). This is m4, DEBT KCH-239. The cycle made no change here and none was expected.

## Task 4 — mutation (13 new cycle-1 mutants, `mut2.py`; tests = `tests/unit/application/agent` + protected names)

11 killed, 2 survived.

| id | mutant | result |
|---|---|---|
| C1 | M1 reverted (peeled hit exact on the stem) | killed |
| C2 | peeled whole hit ENTITY in SYSTEM mode | killed |
| C3 | peeled issued Q/N text reuses its token | killed |
| C4 | single-run peel keyed on the stem | killed |
| C5 | G3 skipped for every role | killed |
| C6 | G3 skipped for assistant only (system checked) | killed |
| **C7** | **guard cache key ignores the G3 flag** | **SURVIVED → n3** |
| C8 | guard cache off (M2(a) reverted) | killed |
| C9 | `first_leak` ignores `dynamic=False` | killed |
| C10 | `tool` added to authored roles | killed |
| C11 | multi-run peeled Q keyed on the stem | killed |
| **C12** | **role read case-insensitively, missing role treated as authored** | **SURVIVED → n4** |
| C13 | peeled hit not flagged `suffixed` | killed |

The review-1 set rerun on the new code gives 21/22 killed, and R1 survives (equivalent).

## Findings

No BLOCKER. No MAJOR.

### n1 — MINOR — the guard cache commits a verdict for a body that is never sent
**Where:** TK:708 `self._guard_cache[key] = n_amt` is written per leaf inside `assert_no_plaintext`'s walk
(TK:1051-1053). If leaf k raises, leaves 1..k-1 are already cached as passed, but nothing left the machine.
**Reproducer** (`probes/p2_m2.py` §M2(a)-2, DEMO):
```
turn1 body [tool {"message": "note: call kapadia before friday"}, tool "anil sharma"] -> RAISE (nothing sent)
user: "lend 5000 to kapadia" -> "lend AMOUNT_1 to N001"
turn2 body [same tool obs] -> ok   <- first real send of 'kapadia' while it is N001
control (fresh TokenMap, same order) -> RAISE 'kapadia'
```
**Reach:** it needs both (1) a prior guard raise followed by a resend of the same leaf (the KCH-239 recovery path)
and (2) an unstored, non-safe word in tool SYSTEM text. Today's templates never contain one; it takes the m10 path
(pydantic `input_value`) or a raw leaf. The same holds after a network failure following a pass.
**Fix (≈6 lines):** collect `(key, n_amt)` in a local list during the walk and write it to `_guard_cache` only after
the whole body passes. Test: the reproducer above must raise in turn 2.
**DEBT owner: KCH-239** (it owns the raise/recovery path). The fix is cheap enough to fold in now.

### n2 — MINOR — G3 skip trusts the role label, not provenance
**Where:** TK:1012 `_AUTHORED_ROLES`, TK:1052-1053. The ruling ("app-authored and static", "raw model output")
holds only while KCH-239 keeps two invariants that nothing enforces.
**Reproducer:** `probes/p2_m2.py` §M2(b). A system message that interpolates the user's text passes, and so does a
rehydrated assistant history entry. Novel names (`Rohan Kapadia`) and Q texts (`sharmma`, `vishwas`) leave in
clear. Stored names are still caught by G1/G2.
**Fix, pick one (KCH-239):**
- (a) Contract tests in RunAgentTurn: the system message equals the hashed static prompt constant byte for byte,
  and every assistant history entry equals `Completion.content`/`tool_calls` byte for byte, never rehydrated.
- (b) Stronger: replace the role skip with a provenance skip. Add `TokenMap.mark_authored(text)`, called for the
  static prompt and for each raw completion, and skip G3 only for strings in that set. Every other string in any
  role gets G3.
**DEBT owner: KCH-239.** It is not a leak today because no system or assistant text is built yet.

### n3 — MINOR (test gap) — C7: the cache key's G3 flag is untested
**Where:** TK:695 `key = (text, issued_texts)`. Mutant `key = (text, True)` passes all 4,337 agent tests. Under
that mutant, a string first seen in an assistant message (G3 skipped) is cached, and the same string later in a
tool or user message passes. That is a real leak the code prevents today but no test pins.
**Reproducer:** `probes/p2_c7.py`: N001=`Rohan Kapadia`, then `[assistant "rohan kapadia will pay"]` gives ok,
and then `[tool "rohan kapadia will pay"]` must raise.
**Fix:** add that as a test (3 lines). **Fold in before merge. If deferred, DEBT owner KCH-239.**

### n4 — MINOR (test gap) — C12: the fail-safe for unknown or missing roles is untested
**Where:** TK:1052-1053. The mutant `(role or 'assistant').lower() not in _AUTHORED_ROLES` survives: it skips G3
for role-less, `System` and `ASSISTANT` messages.
**Fix:** parametrised test over `developer`, `System`, a message with no `role`, and a non-Mapping message; each
must raise on an issued N text. **Fold in before merge. If deferred, DEBT owner KCH-239.**

### Notes (no action beyond DEBT bookkeeping)
- **N1 digit-glued class, extra examples** (owner-ruled DEBT **KCH-239**): `bg 13ji` and `b1ji` stay clear
  (`probes/p2_bgji.py`). The honorific stem `13`/`b1` is under `_MIN_STEM = 3` (EI:73). `bg1ji`, `bg13ji`,
  `bg13s` and `dg1bhai` are masked. Suggest adding `bg 13ji` and `b1ji` to `DIGIT_GLUED_LEAKS` so the KCH-239 fix
  covers them.
- **N2 coverage:** `tokeniser.py` 413 stmts 100%, `entity_index.py` 352 100%, `safe_words.py` 100%,
  `get_protected_names.py` 100%. Repo TOTAL is 64%, the same as review 1 (6,528 → 6,522 stmts). The deficit is
  presentation at 0% (no UI tests in prototype scope) and predates this issue.
- **N3 SW header nits:** the provenance sentence (SW:34-38) credits levels 10/20 only. The contraction files at
  35/40/50 (12Dicts/3esl, public domain) are listed but not attributed. No notice is legally required. The
  `[REVIEW REQUIRED]` tag (SW:12) stays until the owner clears it on the PR.
- **N4 `ruff format --check`:** 7 changed files would be reformatted, and the same 7 were already unformatted at
  HEAD 9a763b4. That is pre-existing and not a gate (`ruff check` passes).
- m1-m4, m6, m7, m9 and m10 from review 1 are unchanged and remain DEBT as ruled (KCH-239/KCH-243).

## Task 5 — gates

| Gate | Result |
|---|---|
| MVP1 `pytest tests/ --cov` (scratch copy, 2026-09-28) | **4850 passed, 1 skipped, 6 xfailed** (expected 4,850/1/6) |
| coverage | changed modules 100%. TOTAL 64% (pre-existing, N2) |
| root `pytest tests/unit` (PYTHONPATH=worktree) | **247 passed, 2 skipped** |
| `lint-imports` | **3 kept, 0 broken** |
| integration `…:5433/finhive_test_disposable` | **17 passed, 1 skipped** (`test_seed_service_account.py:47`, needs Supabase env) |
| `ruff check` 7 changed files | All checks passed |
| `src/Loan Manager/data/` | `settings.json` only |
| env | `QT_QPA_PLATFORM=offscreen`, `PATH=/home/user/FinHive/.venv_pg/bin:$PATH`, `PYTHONDONTWRITEBYTECODE=1` |

Performance (`p_perf`, a busy 4-CPU box, median of 5): DEMO build 1.0 ms, worst case 26.8 ms (500 comma-separated
novel words). HARD1200 build 40.8 ms, worst case 41.4 ms (distinct typos). Guard, 40 messages: 1.6 ms cold and
0.03 ms warm. All inputs are under the 100 ms budget.

## DEBT summary for the PR body

| id | owner |
|---|---|
| digit-glued names (+ `bg 13ji`, `b1ji`) | KCH-239 (owner ruling) |
| n1 guard cache commits before send | KCH-239 (or fold now) |
| n2 G3 role skip relies on unenforced KCH-239 invariants | KCH-239 |
| n3, n4 test gaps | fold now. Else KCH-239 |
| m1, m2, m3, m4, m7, m9, m10 | KCH-239 (m7 also KCH-243) |
| m6 | KCH-243 |

## Appendix — HARD1200
- Resolver differential `p_diff` (full, not sampled): **23,403 queries, 0 diffs** in `exact_entity` and in "prompt is
  one B/D/G token iff the resolver says exact". `p_diff_big` (review-1 1/4 sample): 5,851 queries, 0 diffs.
- Peel differential `p2_peel_hard3.py` (every 4th value = 340 values, forms as above minus UPPER and the
  ZWJ/SHY separators, 2 contexts): 153,564 prompts, 672 distinct resolver calls, **0 not-exact ENTITY, 0 ASCII
  word-cuts**. `p2_peel_hard2.py` (every 20th value, all cuts counted): 30,620 prompts. It found 520 cuts, and every
  one sampled is a Devanagari suffix glued to a Latin stem (`anhul chopraजी` → `B-जी`), the pinned script-change
  case.
- The first HARD1200 attempt, which built a TokenMap per prompt at ~40 ms each over ~600k prompts, was infeasible
  and was replaced by the scan-only oracle above. Token/hit agreement is covered by PEEL and DEMO (0 mismatches in
  107,008 prompts).
