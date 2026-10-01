# KCH-238R review 1 — tokeniser redesign (single owner-mandated review)

Reviewer: opus. Worktree `/home/user/wt/kch-238r` (branch `feature/kch-238-redesign`, 13 files uncommitted). Never edited:
md5 of `tokeniser.py`, `entity_index.py`, `safe_words.py` identical before and after every run.
Scratch: `/tmp/claude-0/-home-user-FinHive/c2cf79a7-e479-5303-814c-46d460e117b4/scratchpad/kch238r-rev-3113/`
(`tree/` = copy for gates, `mut/lm/` = mutant copy, `mut.py`, `mut_results.txt`, `probes/p_*.py` = new attacks,
`probes/*.py` = review 1-4 reproducers rerun, `run_probe.sh` = runner).

Refs: EI = `src/Loan Manager/loan_manager/application/agent/entity_index.py`, TK = `.../agent/tokeniser.py`,
SW = `.../agent/safe_words.py`.

## VERDICT: STOP-AND-REPLAN

One leak class the plan's §3 table does not claim: **a stored name glued to digits** (UPI ids, e-mail
local parts, handles, usernames). Full stored names leave in clear and the guard is blind. Per owner rule this is
reported as STOP-AND-REPLAN, not as a patchable finding.

Everything else is in good shape: every earlier reproducer is clean, the 56-call sweep and both 98-message replays
have 0 leaks / 0 false raises, the exactness shortcut agrees with the real resolver on 5,851 queries at 1,200 names,
performance is 20-50x under budget, all gates green. If the owner instead rules the class out of scope (see
"Owner options"), the verdict becomes **FAIL** on two MAJORs (M1, M2), both small and local.

## STOP — leak class not claimed by §3: stored name glued to digits

**Where:** EI:302-307 `_novel_shaped` refuses any word with a digit ("a code, id or date fragment is never a novel
name"); EI:545-561 `_single_at` only matches a run that *equals* a part, a part+suffix, or a d=1 typo; EI:490-510
`_whole_at` only matches a run *sequence* that equals a FULL key. A run is letters+digits in one script (EI:17-21),
so `rakeshsharma92` is one run that is none of these. The guard uses the same scan (G1/G2) → blind.

**Reproducer** (`probes/p_digitglue.py`, DEMO active universe):
```
'his upi id is rakeshsharma92@okicici' -> 'his upi id is rakeshsharma92@N001'   guard(raw)=ok   (stored "rakesh sharma")
'call naveenrao2026 tomorrow'          -> 'call naveenrao2026 tomorrow'          guard(raw)=ok   (stored "naveen rao")
'@deepakmenon77'                       -> '@deepakmenon77'                       guard(raw)=ok   (stored "deepak menon")
'anilsharma2026'                       -> 'anilsharma2026'                       guard(raw)=ok
'send it to anil.sharma85@gmail.com'   -> 'send it to Q001.sharma85@N001'        surname in clear
'meera_iyer1990 on whatsapp'           -> 'Q001-_iyer1990 on whatsapp'           surname in clear
```
Not a regression: cycle 2 (`kch238r-build-19840/c2tree`) leaks the same four (`probes/p_dg_c2.py`). No earlier review
found it; no §3 row claims it:
- §3 "Glued names → runs split on every non-word char" — digits are word chars, never split.
- Risks "stored name inside a longer glued word only via N" — N explicitly excludes digit words, so the claimed
  mitigation does not apply.
- Risks "numbers in words" — read as spelled-out amounts (it sits beside "space-grouped digits"). If the owner
  meant digits-inside-words, this class is already accepted and becomes DEBT (see options).

Realistic: UPI ids (`name92@okicici`), e-mail addresses and handles are routine in an Indian lending chat.

**Likely replan delta (small):** keep the whole-run FULL lookup first (so `bg13`, `b10`, `dg1` stay codes), then split a
mixed run at letter↔digit boundaries and run each letter segment through FULL-as-prefix / PART / typo / N (ingress)
and G1/G2 (system, guard). Add the reproducers above to the acceptance corpus A and variant fuzz B (`v + "92"`,
`v.replace(" ", "") + "1990"`).

## MAJOR (ordinary; inside claimed classes)

### M1 — Suffix peel makes a DIFFERENT person's name an EXACT B/D token (resolver says not exact)
**Where:** EI:502-509 (peel), EI:533 `exact_entity(stem)` — exactness is asked of the stem, not of what was typed.
The `s` suffix (plan addition) and `ji` turn a distinct real name into a stored one.
**Reproducer** (`probes/p_peel.py`, stored `vishwa`, `sai bala`, `ravi teja`):
```
'how much does vishwas owe' -> 'how much does B001-s owe'  B001=vishwa     resolver('vishwas').exact=False
"sai balaji's loan"         -> "B001-ji's loan"            B001=sai bala   resolver('sai balaji') no_match
'ravi tejas loan'           -> 'B001-s loan'               B001=ravi teja  resolver('ravi tejas').exact=False
```
Vishwa/Vishwas, Teja/Tejas, Bala/Balaji are all common Indian names. An exact token lets a READ tool act without the
KCH-236 confirm step, so the model reports another person's loans as fact. Not a leak.
**Fix:** a peeled whole-name hit is ENTITY only when the stem is exact AND the unpeeled typed text is not itself a
plausible distinct name; simplest safe rule: peeled hit → Q whose text is the full typed span (suffix included), so
`resolve_entity` sees "vishwas". This changes the F1-ruled pin `anil sharmaji → B001-ji` → **[REVIEW REQUIRED]**
orchestrator re-ruling. Minimum if F1 must stand: drop `s` from the ENTITY-peel path (keep it for Q/guard).
Tests: the three lines above.

### M2 — G3 (issued Q/N texts) false-raises on the model's own replies and on the system prompt; bricks the conversation
**Where:** TK:690-708 `_check_outbound_string` re-checks every cached string when a new Q/N is issued; EI:540-542
REUSE in SYSTEM mode. Any word the user typed that became N is then banned from every outbound string, including
text the app or the model wrote before or independently.
**Reproducer** (`probes/p_guardfp.py`, `probes/p_sysp.py`, DEMO):
```
4 fresh prompts + a plausible reply each:  formal English ok; Hinglish reply FALSE RAISE 'bana';
  domain reply FALSE RAISE 'credited'; chatty reply FALSE RAISE 'accts'            -> 3/4 replies raise
stand-in system prompt (sysprompt.txt, 136 words): typing 'unconfirmed' or 'overwrites' once
  -> the system message raises on EVERY later request (2/136 words brick the session)
```
The a9/a9b replays pass only because their replies are curated formal English. Re-checking a string already sent
cannot prevent a disclosure (it already left); model-authored text cannot contain our plaintext except by guessing.
**Fix (small, in `assert_no_plaintext`/`_check_outbound_string`):** (a) a string that has passed the guard is never
re-checked for later Q/N or amounts (drop the `dynamic_may_occur` re-check and the amount re-check — simpler code);
(b) skip G3 for `role == "assistant"` leaves (keep G1/G2/G4). KCH-239 contract: history stores raw model output,
never rehydrated text. If the owner keeps D4 as is, this is DEBT → **KCH-239** (recovery path mandatory before ship).
Mutant X15/X16 tests pin the current behaviour and would be rewritten.

## MINOR

| id | Finding (file:line) | Reproducer | Fix | DEBT? |
|---|---|---|---|---|
| m1 | SYSTEM-mode whole hit takes `matching[0]` (EI:528-531): two stored values with one collapsed key get ONE token in system text while `candidates` gets two. | stored `raj kumar` + `rajkumar`: `next_action` → `choose between 'B001' or 'B001'`; `iyer chem`+`iyerchem` → `'G001' or 'G001'` (`p_system.py`). Ingress `raj kumar` and `rajkumar` share one Q whose text is whichever came first. | In SYSTEM mode prefer the entry whose resolver-normalised form equals the slice; ≥2 or none → Q. | Safe. **KCH-239** |
| m2 | Protected-only whole name becomes ENTITY (B/D/G) in SYSTEM mode (EI:528) but Q at ingress (EI:533-539). | `tokenise_observation({"message":"old kumarswamy is inactive"})` → `B001 is inactive`; same name typed → `Q001` (`p_d3.py`). | Filter `matching` to active in SYSTEM mode, else Q. | Safe. **KCH-239** |
| m3 | Novel names that are safe words pass in clear (plan-accepted risk), measured: 23 of ~130 common Indian names/nicknames are in SW (`ram sunny honey lucky happy babu baby rose grace joy hope mark bill will may june april august amber dawn gold silver jo`). Names < 3 chars never N (`om li wu ng jo`). | `new loan: Ram Prasad` → `Ram N001`; `Om Prakash ko 5000 do` → `Om N001 ...` (`p_novel.py`). | Subtract a curated given-name list (`ram, sunny, lucky, honey, happy, babu, ...`) from SW; consider N for 2-letter capitalised words. | Safe (accepted D2 risk). **KCH-239** |
| m4 | Over-tokenising, measured on 4 fresh paragraphs (`p_prose.py`, same at DEMO and 1,200 names): formal English 0%, domain English 4.5% (`mismatch UTR credited deduct`), chatty 15.7% (`accts wanna avg thx pls abt dont lol`), Hinglish 20.3% (`kaam bana dekho kaunse tak aayega toh usko bahar ...`), Hindi 9 tokens/32 words. N merges across "." (`N007='banega. Agar'`). Hinglish prompts lose their verbs. | as listed | Extend the 410 project words with ~300 Hinglish/chat words (`toh bana karna dekho tak mujhe alag kaam thx pls avg acct(s) dont`); stop N-merge at sentence "." + capital. | Safe. **KCH-239** |
| m5 | Licence notices incomplete (SW:11-60). `american-/british-words.*` come from VarCon (Atkinson 2000-2016, Benjamin Titze 2016, and Geoff Kuenning's Ispell BSD-style licence with disclaimer); none reproduced. WordNet licence requires its full notice and disclaimer on all copies; only the copyright line is reproduced. Source, release, sha256, file list: recorded correctly. Nothing GPL (checked SCOWL `Copyright`). Redistribution in this Apache-2.0 public repo: compatible (all permissive / public domain) once notices are complete. | read SCOWL `Copyright` (`kch238r-build-19840/scowl-2020.12.07/Copyright`) vs SW header | Paste SCOWL's `Copyright` file verbatim (or a `THIRD_PARTY_NOTICES` file referenced from the header and PR body). | **Not DEBT** — public repo; fix before merge (text only). |
| m6 | Cross-role person name refused: an existing borrower cannot be named as depositor via chat (TK:156-162). | `anil sharma is the depositor` → `B001`; `detokenise_args({"depositor_name":"B001",...})` → `UnknownTokenError ... expects D/N/Q` (`p_crossrole.py`). | [REVIEW REQUIRED] accept {B,D,Q,N} in both person-name fields (proposal is human-approved), or document. | Safe. **KCH-243** |
| m7 | SYSTEM mode / G2 blind to 3-char and safe-word name parts (by design): `rao`, `das`, `wei`, `om`, `grace` stay clear in `message` text. No current tool template writes a bare part (checked `read_*`, `propose_*`). | `p_system.py` | Any new template that writes a part must use an ECHO key. Add to the KCH-243 DEBT note beside the key tables. | Safe. **KCH-239/243** |
| m8 | Test gaps — mutant survivors R5, R6, R11, R19, R20 (below). R19 (N min length 3→4) would let 3-letter novel names (`raj`, `anu`, `jai`) through with no test failing. | `mut_results.txt` | Tests: `raj ko 500 do` → `N001 ...`; merge after a suffixed hit; token between two name words not joined; depositor_name rejects B; `sharma,group` does not join. | Fold in (cheap). |
| m9 | Guard cache unbounded per TokenMap; N/Q budget 999 reachable in a long Hinglish session (~14 N per paragraph). | — | Cap / note. | **KCH-239** |
| m10 | pydantic `ValidationError` text carries `input_value='…'` (truncated). If KCH-239 surfaces it under `message` (SYSTEM mode), a truncated N text no longer matches DYNAMIC and leaks. | design note | KCH-239: put validation text under an ECHO key or drop `input_value`. | **KCH-239** |

## Task 1 — earlier reproducers, sweeps, replays (all rerun against the new code)

- `r1_probe1/3/4`, `probe1/3/4`, `p3b`, `p5`, `p5b`, `p6`, `p7`, `a1`, `a2`, `a6`, `a7`, `a10`, `r4_f1`, `r4_f2`,
  `r4_edge`, `r4_mchk`, `eq7` (523,850 cases, 0 diffs): no name or amount in clear. Tracebacks in r1_probe1/3,
  probe1/3, p5 are the intended raises (typed token, unclassified numeric, budget).
- Review-4 BLOCKER R1: `azim premji`, `rameshbhai patel`, `hansaben shah`, `balaji rao`, `shivaji more` exact at
  ingress, egress free text and `resolve_entity` next_action; 0 clear. R2: `iyer chem` → G(iyerchem). m-R1, m-R3,
  m-R7 (`sharmaजी` → `B001-जी`), m-R8/`_` all fixed.
- 56-call READ sweep (`probe2`): fresh 0 leaks, shared 0 leaks. `r1_probe2` 0/0.
- Replays with "Q2 2026": `a9` 98 msgs / 55 bodies / 42 tool calls → 0 false raises, 0 leaks; `a9b` same.
  (But see M2: curated replies.)
- Accepted over-tokenising in a7 (`Sep 26, 2026`, `phone`, `pin`, `page 1000`) unchanged since review 3.

## Task 2 — attacks on the design

- **Separator-blind matching:** `ANIL-SHARMA`, `anilsharma`, `meera\xa0iyer`, `MEERA\nIYER`, `meera_iyer`, `b 10`,
  `bg-13`, ZWSP/soft hyphen, fullwidth → correct token. False merges produce tokens, never clear text (e.g. prose
  `vitamin b 12` would become B(b12) if stored — cosmetic). Wrong-entity from shared keys: m1.
- **Suffix peel vs stored word:** a stored word always wins (whole run first). Peel creating wrong exact: M1.
- **DEL1 typos:** typos only ever yield Q, never B/D/G, so no wrong-entity exact from DEL1. R1 mutant (≥ vs >) is
  equivalent (a d=1 ratio can never equal 0.85).
- **Tie-set differential vs `EntityResolver.resolve(...).exact`:** HARD1200 universe (1,200 names, 330 syllable
  first names × 40 shared surnames, groups, codes; `rv.hard_universe`) — **5,851 queries (1/4 sample), 0 diffs** in
  `exact_entity`, 0 diffs in "prompt is one B/D/G token iff resolver exact". DEMO: 3,906 queries, 0 diffs. Known designed
  divergence: fold-before-resolve makes `José` exact to stored `jose` (resolver: no match); wrong entity only if two
  stored values differ by accents alone.
- **Novel names:** English-word names m3; Devanagari names typed (`रमेश कुमार`, `मोहन लाल`, `गीता`) → N; Devanagari
  function words stay plain. PROPOSE: see below.
- **Egress SYSTEM template with a name part:** parts ≥4 non-safe tokenised (`pinto's` → `Q001's`); shorter/safe
  parts clear (m7).
- **Guard:** false raises M2. Cache correctness: soundness argument holds (new dynamic keys only add prefixes/REUSE
  hits; amounts rechecked from `since`); X15/X16/R16 mutants confirm it is tested. The design question is M2(a).
- **D3:** inactive and pending-report names (`GetProtectedNames`) → Q at ingress incl. parts, typos, `panditji`,
  `dg 2`; tokenised at egress; guard raises on whole and parts. Resolver stays active-only (`no_match` for both).
  Kind inconsistency m2. `GetProtectedNames` is not yet wired into the Container (KCH-239 wires TokenMap).
- **PROPOSE sweep** (`p_propose.py`, end to end: prompt → tokens → model args → `detokenise_args` → `parse_args` →
  handler → `tokenise_observation` → guard) with 12 novel names incl. `Kapoor\tRamanathan`, `रमेश यादव`,
  `O'Brien Fernandes`, `D'Souza-Pereira`, `Anita Sharmaa`: create_loan ok, update_loan ok / ALREADY_PENDING /
  GROUP_MISMATCH / REF_ID_NOT_FOUND. Every N/Q round-trips byte-exact into the pending record; 0 novel-name words in
  any observation; guard ok. Only clear word: `Ram` (m3). N/Q in a group field is refused (by design).

## Task 3 — performance (reviewer-measured, tracing suspended, median of 5, fresh TokenMap each run)

| input | DEMO | HARD1200 |
|---|---|---|
| index build | 0.8 ms | 13.5 ms |
| 4 fresh paragraphs, 1,789 chars | 1.8 | 2.1 |
| distinct named prose 2,000 | 2.8 | 4.3 |
| mixed 4,000 | 4.7 | 7.1 |
| 400 distinct names, 2,000 | 6.9 | 11.8 |
| distinct transposition typos, 2,000 | 5.7 | **41.2** (worst) |
| adversarial: 500 comma-separated novel words / single letters / prefix chains / `bg0,bg1,...` | 3.0-7.3 | 3.3-11.0 |
| guard, 40 messages cold / warm | 1.2 / 0.03 | 1.2 / 0.02 |

Budget (<100 ms) met with ≥2.4x headroom on the worst case. Review-4 figures for comparison: 505 ms DEMO, 1.86 s at
~1,200 names.

## Task 4 — safe-word list

- Header records source (SCOWL 2020.12.07, URL, sha256 `5587667c…` — matches the implementer's tarball), files,
  filter, counts, and SCOWL's Atkinson notice. **Incomplete notices: m5.**
- Nothing GPL: the used levels are Moby/Kelk (public domain) + WordNet inflections (Princeton, permissive) + VarCon
  (Atkinson/Titze permissive, Kuenning BSD-style). Generator `gen_safe.py` reproduces SW byte-exact.
- Redistribution in the public Apache-2.0 repo is compatible with those licences, provided the notices (m5) are
  carried.

## Task 5 — mutants (22 new, none overlap the implementer's 63; `mut.py`, `mut_results.txt`)

16 killed, 6 survived:
- R1 typo `>=`→`>`: survived, **equivalent**.
- R5 merge ignores `prev.suffixed`: survived (gap).
- R6 whole name crosses an opaque token: survived (gap; would swallow an issued token into a new one).
- R11 depositor_name accepts B: survived (gap; interpretation below is untested).
- R19 N min length 3→4: survived (**gap with leak potential**: 3-letter novel names).
- R20 group/family join without soft separator: survived (gap).
Killed: R2 distinct 4→5, R3 tie set FULL-only, R4 merge across comma, R7 no dynamic reuse at emit, R8 `_` not
touching, R9 amount recheck off-by-one, R10 ingress uses distinct parts, R12 noise kept in tie, R13 typo length
guard, R14/R15 protected set (pending / inactive), R16 no amount recheck, R17 SYSTEM digit-run check, R18
Devanagari script boundary, R21 Cf kept, R22 typed-token reject removed.

## Task 6 — gates (reviewer-run; MVP1 in scratch copy, others in the worktree with PYTHONDONTWRITEBYTECODE)

| Gate | Result |
|---|---|
| MVP1 `pytest tests/ --cov` | **4830 passed, 1 skipped**; `tokeniser.py` 416 stmts **100%**, `entity_index.py` 355 **100%**, `get_protected_names.py` 100% |
| root `pytest tests/unit` | **247 passed, 2 skipped** |
| `lint-imports` | 3 kept, 0 broken |
| integration (`…:5433/finhive_test_disposable`) | 17 passed, 1 skipped (`test_seed_service_account.py:47`) |
| `ruff check` 13 changed files | All checks passed |
| `src/Loan Manager/data/` | `settings.json` only |

## Verdict on the implementer's two interpretations

1. **depositor_name accepts {D,Q,N}: correct.** The plan's "{B,Q,N}" for both fields is a slip; B in depositor_name
   would reopen the review-1 m6 cross-kind hole. Cost: m6 (existing borrower as depositor refused) — owner ruling,
   DEBT KCH-243. Untested (mutant R11 survives) — add the test.
2. **Protected-only names become Q at ingress: correct.** D3 keeps the resolver active-only, so a B/D/G for an
   inactive or pending name would detokenise to a value every tool reports as not found; Q routes through
   confirm. Inconsistent at egress (m2).

## Owner options

- **(a) Replan (rule as written):** add "stored name glued to digits" to §3 with the split-at-digit-boundary rule;
  fold M1, M2 (or waive M2 to KCH-239), m5, m8 into the same build; one more review.
- **(b) Rule the class covered by "numbers in words" (accepted risk):** verdict becomes FAIL on M1 + M2; digit-glued
  names go to DEBT **KCH-239** with the reproducers above.

## Appendix — DEMO differential
DEMO active universe (`probes/p_diff_demo.py`): **3,906 queries** (every value × case/sep/glued/noise/reversed
variants, 6,000 word pairs, word+group/grp/"and co") — **0 diffs** in `exact_entity`, 0 diffs in the tokenise check.
