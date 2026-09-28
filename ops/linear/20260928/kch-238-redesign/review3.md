# KCH-238 review 3 — FINAL, after fix cycle 2

Reviewer: opus. Worktree `/home/user/wt/kch-238`: uncommitted, 4 files, never edited.
- `tokeniser.py` md5 is `8405326c45684e06c48142135ac65fb0`, identical before and after every mutant run.
- Scratch dir: `/tmp/claude-0/-home-user-FinHive/c2cf79a7-e479-5303-814c-46d460e117b4/scratchpad/kch238-final-2334/`.
  - Reproducers from reviews 1 and 2: `r1_probe*`, `probe*`, `p3b`, `p5`/`p5b`, `p6`, `p7`.
  - New attacks: `a1`–`a10`, `a9b`.
  - Mutant runs: `mut2.py`, `mut_extra.py`, `mut3.py`.
  - N7 fuzz: `eq7.py`.
  - Stand-in system prompt: `sysprompt.txt`.

LM = `src/Loan Manager/loan_manager`. File:line refs are into `LM/application/agent/tokeniser.py`
unless another file is named.

## VERDICT: FAIL

Three ship-stoppers remain. None is a regression of the cycle-1 or cycle-2 fixes.
1. An ordinary way of naming a person leaks the surname, and the guard does not see it.
2. An ordinary way of naming a period ("Q2 2026") permanently bricks the conversation.
3. Tokenising is 40× over the latency budget.

Everything the review-2 rulings asked for is done and tested. Egress is clean.

Each ship-stopper has a small fix. Two of the three were prototyped in scratch, and the scratch
suite stays green (see each item). The owner decides between a cycle 3 and a waiver.

## Gates (reviewer-run, CI parity)

Env: `QT_QPA_PLATFORM=offscreen`, `PATH=/home/user/FinHive/.venv_pg/bin:$PATH`, plus
`TEST_DATABASE_URL=…:5433/finhive_test_disposable` for the integration lane.

| Gate | Result |
|---|---|
| MVP1 `pytest tests/ --cov` | 703 passed, 1 skipped (`test_openrouter_live.py:22`, no key). TOTAL 58% (pre-existing) |
| tokeniser coverage | 178 passed. `tokeniser.py` 452 stmts, **100%** |
| root `pytest tests/unit` | 247 passed, 2 skipped (opt-in `test_local_dev_setup.py:201,217`) |
| `lint-imports` | 3 kept, 0 broken |
| integration | 17 passed, 1 skipped (`test_seed_service_account.py:47`) |
| `ruff check` (4 files) | All checks passed |

## Task 1 — earlier reproducers and mutants, rerun on the final code

- **Every reproducer from reviews 1 and 2 is fixed.** The review-2 list is covered in full:
  - NB1 suffixes: `2000 rupees`, `of 2000/-`, `in 2000 rs`, `999/-`, `750rs`, `500 rupees`.
  - NB2 separators: `meera iyer,anil sharma` → `D001,B001`, `Mr.Sharma` → `Mr.Q001`,
    `anil sharma-ji` → `B001-ji`, em dash, `/` and `&`.
  - NM1: every list, nested-list, float and free-text numeric case raises.
  - NM2: the 1000th Q token raises `TokenBudgetExceededError`.
  - NM3: known 1200/12/3/450 against the real content strings and tool_call args gives 0 raises.
  - NM4: `राम शर्मा का लोन` → `D001 का लोन`.
  - NM5: `5 thousand rupees` → `AMOUNT_1`.
  - `O’Brien Shah` resolves exact.
- **Mutants:** `mut2.py` plus `mut_extra.py` killed 31 of 33. The two survivors are N7 and N10′.
- **The implementer's claim is VERIFIED: N7 and N10′ are equivalent mutants.**
  - **N7**, dropping `_MONEY_SUFFIX` from MONEY_RE's `\d{5,}` branch (`:449`). The `suffixed`
    branch (`:453`) has the same lookbehind, `\d+` ⊇ `\d{5,}` and the same suffix set.
    `MONEY_RE` is only ever used as a boolean `.search` (`:1108`), so the mutant cannot change
    any outcome. `eq7.py` compared original and mutant on 523,850 random and structured strings
    and found **0** differences. The redundancy is pinned the other way too: deleting the
    `suffixed` branch (C7) is killed.
  - **N10′**, removing the numeric raise in `_tokenise_unclassified` (`:806-810`). The value
    then falls to `_tokenise_free` (`:816`), which raises `PlaintextLeakError` for the same
    type set, with the same bool exclusion first (`:853-861`). Only the message text differs,
    so every input the removed line covered is still enforced. Removing both lines (C25) is
    killed, and so is float-exempt in both (C11).

## Task 4 — egress

- **The 56-call READ sweep has 0 leaks and 0 guard raises**, with a fresh and a shared map
  (`probe2.py`, `r1_probe2.py`).
- **`p7` error paths are clean:** `UNSUPPORTED_STATUS`, `UNRESOLVED_ENTITY`,
  `REF_ID_NOT_FOUND`, `format_inr` 0.01 and 99999999999.
- **The realistic conversation (`a9b.py`) is clean when it contains no year-shaped amount.**
  It has 98 messages across 55 bodies:
  - a system prompt, 6 user turns and 42 tool calls (all six READ tools plus the 56-call sweep);
  - model text such as "as of 2026-09-25, FY2026-27, Q2, 12%, 3 months, 90 days";
  - every body built through `build_request_body`.

  The independent scanner finds **0 leaks** and the guard **0 false raises**. With a
  year-shaped amount the result is 41 false raises; see MAJOR F2.

---

## BLOCKER

### F1 — A name with an honorific glued on ("Sharmaji", "Guptaji") leaks the surname, and the guard is blind to it
**Where:** `_word_spans` `:487-517` and `_match_windows` `:709-747`. A word span with no
separator in it goes to `resolver.resolve` whole. `sharmaji` is 2 edits away from `sharma`, so
it scores `no_match` and passes through. The guard (`:1088-1096`) only matches whole stored
values.

**Reproducer** (`a2.py`, `p5b.py`, DEMO resolver). Every case is guard-ok and leaks:
```
"anil sharmaji"        -> "Q001 sharmaji"        (surname of B 'anil sharma' in clear)
"Sharmaji"             -> "Sharmaji"
"Guptaji ko 5000 do"   -> "guptaji ko AMOUNT_1 do"   ("gupta": ramesh gupta / gupta & sons)
"naveen raoji"         -> "Q001 raoji"
"anil sharmaजी"         -> "Q001 sharmaजी"         (mixed script, same class)
```
This is the review-1 B1 class: a surname leaks next to a tokenised first name. B1 was graded
BLOCKER, and the fix for it was ruled. The glued form `-ji`/`ji` is ordinary Indian English.
Review 2 had `anil sharmaji` in its `p5` input list but did not report it, so this is new here,
not a regression.

**Fix** (about 10 lines, prototyped in scratch; 178/178 tests still pass):
1. In `_match_windows`, after `_word_spans`, split a span that ends in
   `(?i)(ji|jee|sahab|saheb|saab|bhai|ben)$` when the part before it is at least 3 characters
   **and** is a word of a stored entity. That condition leaves `raji` and `puja` whole.
2. **Emit a separator between the token and the suffix** (`B001-ji` or `B001 ji`). Otherwise
   `TOKEN_RE` `\b…\b` (`:122`) never matches `B001ji` again, and neither rehydrate nor
   detokenise can find the token. The prototype showed exactly this: it produced `B001ji`.
3. Cover the Devanagari suffix by splitting a span at a Latin↔Devanagari script change.
4. Tests: every reproducer above, plus `raji` and `puja` staying plain.

---

## MAJOR

### F2 — A year-shaped AMOUNT (from "Q2 2026" and similar) permanently bricks the conversation
This is fail-closed: nothing leaks.

**Where:**
- Ingress (`_is_excluded_amount` `:404-434`, `_YEAR_CONTEXT_WORDS` `:374`) makes a year an
  AMOUNT whenever the word before it is not in the context list. That is ruling-mandated
  over-tokenising, and safe in itself.
- The guard's known-amount check (`_is_money_shaped_amount` `:1039-1052`, patterns
  `:1098-1103`) then treats the bare rendering `2026` as money-shaped (4 digits). Its lookahead
  is `(?!\w)`, so `2026-09-25` matches.
- Every `get_current_context`/`as_of` observation, and ordinary model text such as
  "due 26 Sep 2026", contain a date.
- Because the `TokenMap` is session-scoped, **every later request raises**.

**Reproducer** (`a10.py`, `a9.py`):
```
tokenise_prompt("Q2 2026 overdue?") -> "Q2 AMOUNT_1 overdue?"   then any body holding
'{"today": "2026-09-25", ...}'  or  "As of 2026-09-25 ..."  or  "due 26 Sep 2026"  -> PlaintextLeakError
same for "loans from 2025 to 2026", "due Sep 26, 2026", "H1 2026 summary", "2026 overdue list"
a9.py: realistic conversation with "in Q2 2026" in turn 5 -> 41 false raises out of 55 bodies (0 without it)
side effects: _scrub rewrites free text "due after 2026-09-25" -> "due after AMOUNT_1-09-25" (:905-915);
              rehydrate shows "Q2 ₹2,026.00"
```
The brief requires 0 false raises. Ordinary phrasing of a period kills the chat, so this stops
shipping.

**Fix** (prototyped in scratch; the full conversation then gives 0 false raises, the sweep 0
leaks, and 177 of 178 tests pass):
1. In `_is_money_shaped_amount`, return False for a bare 4-digit rendering in 1900–2099. The
   grouped `2,026` and the `2026.00` forms stay flagged, and so do currency- or unit-marked
   forms (through MONEY_RE).
2. Skip the same renderings in `_scrub_issued_amounts`.
3. The one failing test is the ruling-mandated
   `test_year_left_in_clear_can_coincide_with_known_amount_and_guard_raises`
   (`test_tokeniser.py:1512`). It documents "in 1999 paid 1999 → the guard raises", which this
   fix turns into no raise. There is no leak either way: ingress already tokenised the amount.
   **The orchestrator must re-rule that test** (invert it).
4. Optional: add `q[1-4]|h[12]|from|to` as a preceding year context, and a `Mon dd, yyyy`
   shape, to `_is_year_context` (`:394`). That also fixes the rehydrate display.
5. Tests: the four prompts above, each followed by a `get_current_context` body. Assert no
   raise.

### F3 — `tokenise_prompt` latency is 40× over budget and linear in the size of the ledger
**Where:** `_match_windows` `:721-747` calls `EntityResolver.resolve` (KCH-236, OSA fuzzy over
the whole universe) once per window, per size, **per pass**. Pass 3 repeats pass 2's calls, and
nothing is memoised. The profile puts 99.6% of the time in `entity_resolver.py:346 resolve`
(2,001 calls for 2,000 characters).

**Measured** (`a3.py`, `a4.py`, `a6.py`, median of 3–5 runs):
```
DEMO universe (~75 names):  62-char prompt 87 ms · 500 chars 973 ms · 2,000 chars 3,900-4,200 ms (budget: well under 100 ms)
2,000-char single word "aaaa…" 1.1 s (OSA on a long string) · 2,000 chars of "b1," 6.8 s
~342 names: 88-char prompt 1.0 s · ~1,204 names: 88-char prompt 4.3 s, 2,000 chars 112 s
```
Nothing leaks. KCH-239 will call this on every user turn. A 300-name ledger then takes about a
second per ordinary question, before the LLM call even starts. **[REVIEW REQUIRED]:** the real
ledger size is unknown to me. DEMO has 75 names.

**Fix (tokeniser-local):**
1. Memoise `resolve` by the folded core for the life of the `TokenMap`. The universe is fixed at
   construction, so pass 3 then reuses pass 2's results and repeated words become free.
2. Skip any word longer than the longest stored name word + 2. It can never clear OSA ≤ 2.
3. Prefilter a multi-word window: resolve it only if every word individually clears the
   resolver's per-token threshold. That result is memoised per distinct word. A multi-word
   query needs every word to clear anyway (`entity_resolver.py:408-415`).
4. Add a test: 2,000 characters with DEMO under 100 ms, with generous CI headroom or marked
   slow.

This is the one ship-stopper that is not about correctness. It could be carried as DEBT only
with the owner's sign-off, and only if KCH-239 then (a) runs tokenising off the UI thread and
(b) caps the prompt length.

---

## MINOR (every one is safe as DEBT; the owning issue is named)

- **m1 A name glued with `_` leaks.** `_is_word_char` `:484` counts `_` as a word character
  (the ruling said `\w` semantics). The guard's `(?<!\w)` misses it as well.
  - Repro: `b1_b2` stays plain; `anil_sharma_loans` stays plain; `naveen_rao_holdings` stays
    plain; `iyer_chem_bg1` stays plain.
  - Fix: count `_` as a separator. Mutant C26 shows every test still passes. Ref ids are
    unaffected, because amounts are handled first and `2026_03_004` resolves to no_match.
  - Emit the token followed by a non-word separator, for the same `TOKEN_RE \b` reason as F1.
  - DEBT to **KCH-239**. Chat input rarely does this.
- **m2 Contractions after a name leak the surname.** Only a trailing `'s` is peeled (`:471`).
  - Repro: `deepak menon’ll pay` → `Q001 menon’ll`, and `anil sharma'd lend` leaks the same way.
  - Fix: `_POSSESSIVE_RE = ['’](?:s|ll|d|re|ve)$`.
  - DEBT to **KCH-239**.
- **m3 Unicode lookalikes pass through.**
  - Repro: `ａｎｉｌ　ｓｈａｒｍａ` (fullwidth); `meera iyerʼs`, where U+02BC counts as a
    letter so the possessive is not peeled and `iyer` leaks; `५० हजार`.
  - Fix: NFKC-fold and map U+02BC to `'` before spanning.
  - DEBT to **KCH-239**.
- **m4 Amounts spelled out, or grouped with spaces or dots, pass through.** Both ingress and
  the guard miss them.
  - Repro: `five thousand rupees`, `forty five thousand`, `50 hazar`, `45 000`, `5 00 000`,
    `45.000`.
  - DEBT: ingress to **KCH-239**; model-output numbers to **KCH-250** grounding.
- **m5 Test gaps (mutant survivors).** The behaviour is right today, but no test pins it:
  - C9: the `hundred` unit can be dropped (`2 hundred rupees`), although the NM5 ruling named it.
  - C18: `int_part` is emitted for a non-integral amount (NM3).
  - C19: the money-shape gate on numeric leaves is missing (`:1121`).
  - C20: `basis` is not passthrough. The ruling said "classify basis", and today it only works
    because `/` sits in the lookbehind.

  Four one-line tests. DEBT to **KCH-239**, or fold them into a cycle 3.
- **m6 The guard costs O(names × leaves)** (`:1088-1096`): 89 ms on the 98-message body with 75
  names, and it grows with the ledger. `_scrub_names` (`:901-902`) still recompiles one pattern
  per name on every call. Fix: one alternation regex, cached per `TokenMap`. DEBT to **KCH-239**.
- **m7 Constraint on the system prompt:**
  - `/ 36500` or `divide by 36500` in the system message raises on **every** call through
    MONEY_RE.
  - `/ 1200` with a space raises once an amount of 1200 is known.
  - `sysprompt.txt` written with `…/1200`, `…/36500` gives 0 raises. With it, none of the 48
    ordinary words that become Q mentions (`desk`, `son`, `mumbai`, surnames…) bricks the
    system message.

  DEBT to **KCH-239**: pin a test that runs the real system prompt through
  `assert_no_plaintext`.
- **m8 Over-tokenised non-amounts** (safe; accepted by the ruling):
  - phone numbers become AMOUNT on ingress: `call 9876543210`, `+91 98765 43210`;
  - so do `pin 560001`, `page 1000`, `loan #1234` and `1500 loans`;
  - ordinary words become Q mentions and force a confirm round-trip: `son`, `desk`, `mumbai`.

  Carry to **KCH-239** UX.

## Carried DEBT (from reviews 1 and 2, still valid)
- **KCH-239:**
  - Put `assert_no_plaintext` right before `complete()`.
  - Map `UnknownTokenError` to `UNKNOWN_TOKEN`. The ingress rejection "token codes cannot be
    typed" needs a user-facing message.
  - Keep a session `TokenMap`, and start a new session on `TokenBudgetExceededError`.
  - The system prompt must say that amount arguments are token strings.
- **KCH-243:** extend the classification tables. Any unclassified number now raises. Brand-new
  names in `create_loan`/`update_loan` must be tokenised.
- **KCH-250 grounding:** add D/Q tokens and this money regex
  (`docs/MVP1_1_ASK_FINHIVE.md:229-233`).
- **`read_resolve.py:5-8`:** the docstring should point to `tokenise_observation`.

## Task 5 — cycle-2 mutants (`mut3.py`, 26 run + C11 run by hand)

| Mutant | Result |
|---|---|
| C1 combining marks not word chars (NM4) | killed |
| C2 in-word apostrophe not kept (NB2) | killed |
| C3 curly-apostrophe fold off | killed |
| C4 currency/unit mark never recognised (NB1) | killed |
| C5 suffix marks ignored, prefix only (NB1) | killed |
| C6 ingress `suffixed` branch removed | killed |
| C7 MONEY_RE `suffixed` branch removed | killed |
| C8 thousand/hundred units removed | killed |
| C9 `hundred` alone removed | **SURVIVED** (m5) |
| C10 `_tokenise_free` numeric raise removed (NM1) | killed |
| C11 float exempt in both raises | killed |
| C12 budget off by one, `>1000` (NM2) | killed |
| C13 budget check removed | killed |
| C14 TOKEN_RE back to `\d` | killed |
| C15 money-shape gate always True (NM3) | killed |
| C16 money-shape threshold of 3 digits | killed |
| C17 rendering lookbehind back to `(?<!\w)` | killed |
| C18 `int_part` rendered for non-integral | **SURVIVED** (m5) |
| C19 numeric-leaf money-shape gate removed | **SURVIVED** (m5) |
| C20 `basis` not passthrough | **SURVIVED** (m5; equivalent today) |
| C21 `of` back in the year words | killed |
| C22 curly possessive dropped | killed |
| C23 = N7 | SURVIVED, **equivalent** (0/523,850 fuzz diffs) |
| C24 = N10′ | SURVIVED, **equivalent** (C25 killed) |
| C25 both numeric raises removed | killed |
| C26 `_` as separator | SURVIVED (no test pins `_`; this is also the m1 fix) |
| C27 guard numeric-leaf passthrough skip removed | killed |

Of 27 mutants, 20 were killed. There are 7 survivors: 2 equivalent, 1 neutral (C26), and 4
test gaps (m5).

## Clean checks
- **Empty and whitespace input**: `""`, `" "`, `"\n\t"`, U+3000, U+200B and `"..."` are all
  returned unchanged, with no raise.
- **Reference ids**: `2026_03_004` (alone, with `'s`, comma-joined or in a range) is never
  tokenised.
- **Exact-match codes**: `bg1 vs bg13` → `G001 vs G002`; `bg 13`, `bg-13` and `bg_13` → the
  bg13 token; `b1,b2,b3`, `bg10/bg13` and `dg1,dg2` each resolve per code.
- **Emails and URLs** are over-tokenised, which is safe: `anil.sharma@gmail.com` →
  `Q001@gmail.com`, `…/loans/anil-sharma` → `…/loans/B001`, `?amt=45000&who=b1` → `AMOUNT_1`,
  `B001`.
- **Mixed-script exact names** tokenise: `meera iyer का लोन` → `D001 का लोन`, and
  `राम शर्मा।` → `D001।`.
- **Ingress false positives:** all of these stay plain.
  - Dates: `2026-09-26`, `26/09/2026`, `26-09-2026`, `26.09.2026`, `26 Sep 2026`,
    `26th September 2026`, `FY2026-27`.
  - Rates, durations and limits: `12%`, `12.5% p.a.`, `3 months`, `90 days`, `top 5`,
    `top 1000`.
  - Ref ids, and `since 1999`, `by 2026 end`.
  - The years in `Q2 2026` and `from 2025 to 2026` are over-tokenised, which is safe, but see F2.

---
## ORCHESTRATOR RULINGS — cycle 3 (owner-approved, 2026-09-27; scope is ONLY what is listed)
- **F1:** a trailing honorific glued to a word that is (part of) a stored name is split off: `ji|jee|sahab|saheb|sahib|bhai|bhaiya|ben|behen|didi` (case-insensitive). Resolve the stem; emit the token + a hyphen separator + the honorific verbatim (`B001-ji`, `Q001-ji`), so TOKEN_RE's `\b` still matches. Apply the same split in the egress scrub. Tests: "anil sharmaji", "Guptaji ko 5000 do", "Sharma-ji" (already separated), and a non-name word ending in "ji" left alone (e.g. "puja", "raji" if not stored).
- **F2:** in the guard, a bare 4-digit 1900–2099 rendering is NOT money-shaped (grouped, currency/unit-marked, or ≥5 digits still are). Re-ruling of test_tokeniser.py:1512: "in 1999 paid 1999" must NOT raise; assert instead that the paid amount was tokenised at ingress and the year stays in clear. Add the end-to-end test: "report for Q2 2026" then a full read-tool turn whose history contains 2026-09-25 → 0 raises.
- **F3:** cache resolutions per TokenMap (keyed on the normalised window); skip windows longer than the longest stored name (chars) and multi-word windows whose first word shares no prefix with any stored name word. Budget test: DEMO universe, 2,000-char prompt, median of 5 runs < 150 ms (target 100 ms; 150 ms is the flake margin). Report measured times, including a ~1,200-name synthetic universe (no hard assert there; report it).
- **m1:** `_` is a separator. Reference IDs (`2026_03_001`) must still pass through unchanged — test it.
- No other changes. m2–m8 stay DEBT (PR body).
