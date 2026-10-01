# KCH-238R — tokeniser redesign plan (planner: opus, 2026-09-28) — AWAITING OWNER APPROVAL

Recommendation: approve. Ingress stops asking the resolver about every word window; instead one scan of the prompt against an index built from the loan book. The guard uses the same index. Everything else = the cycle-2 code on PR #49, kept.

Prototype (in-memory, not committed): 3.1 ms for 1,924 chars of distinct prose at 1,158 names; 8.6 ms for 2,000 chars of names only. Cycle-2: 18.9 s for 300 chars at that size. Exactness agreed with EntityResolver.resolve().exact on 158/158 sampled windows.

## Facts
- Cycle-2 _match_windows calls EntityResolver.resolve per window/size/pass; one resolve ≈ 63 ms at 1,017 names → cannot meet 100 ms.
- .exact needs equality or collapsed equality with same digit runs, unique at score 1.0 → only values sharing all query words or the collapsed form matter; run the real resolver over that tiny set (rules stay in KCH-236).
- Name set = GetAutocompleteValues active_only=True → inactive-loan names, pending-report names, and KCH-243 novel names are outside it.
- \w misses Devanagari marks → own char classifier.

## Architecture
New application/agent/entity_index.py (stdlib only), built per TokenMap (18–23 ms at 1,158 names).
- View: NFKC+casefold, fold ’ʼ‘`´→', strip Latin accents, drop Cf; offset map back to original.
- Runs: alnum+marks, one script; everything else (incl. _ - . ' , / & — :) separates; script change separates; issued tokens opaque.
- Tables: FULL (collapsed value → (field,value)); PART (words ≥3 chars, not noise/digits; weak = safe-word & group-only); INV (word → values); DEL1 (SymSpell 1-deletes); DYNAMIC (issued Q/N texts).
- Scan, longest first: whole-name via joined runs in FULL (digit runs must match; else retry minus suffix ji/jee/bhai/bhaiya/ben/behen/didi/sahab/saheb/sahib/saab/s/जी/भाई) → exact? via EntityResolver over the tie set (memoised) → B/D/G else Q; else strong PART or DEL1 typo (EntityResolver.score ≥ THRESHOLD); else unknown non-safe word → N (D2=A); merge adjacent hits across whitespace/./-; noise word "group/family/grp" joins; whole-name never merged.
- Emission: tokens never touch a word char (insert '-'); property test TOKEN_RE round-trips.
- Precedence: known name > safe word > typo > unknown. Whole run looked up before suffix peel (R4-R1 can't recur).
- Ingress: typed-token reject → _pass_amounts → scan → emit.
- Egress: key walk reused; _scrub step 1 replaced by scan — system text (next_action/message/notes): whole names + dynamic + distinctive parts (≥4, not safe) + suffixes, no typo/N; user echo (query/rejected_value): full ingress settings. _scrub_issued_amounts reused + F2 year exemption + m-R1 (all-digits 1900–2099 only). KCH-243 keys added. borrower_name/depositor_name accept {B,Q,N}.
- Guard: messages only, id keys skipped, TOKEN_RE spans ignored. G1 FULL whole names (separator-blind), G2 distinctive parts, G3 issued Q/N texts, G4 money (reused + F2/m-R1). Per-message verdict cache.
- Rejected: char-level Aho–Corasick (mid-word hits, 2× code, no gain); reviewer's cycle-4 prototype (149 ms DEMO, 1,154 ms at 1,204 names; patches again).

## Reused vs replaced (tokeniser.py cycle 2)
Reused: token kinds/errors, TOKEN_RE (+N if D2=A), NAME_KEYS/_FIELD_EXPECTED_KINDS (extended), egress tables (extended), whole amount grammar, token_for/_lookup/budget, typed-token reject, _pass_amounts, egress walk, detokenise_args, rehydrate, guard money loop, test_tokeniser_egress.py, ~60/103 unit tests.
Replaced: _value_boundary_pattern, _POSSESSIVE_RE, _word_spans, _fold_apostrophe, _strip_window_edges, _max_entity_words, _match_windows, _scrub_names, names()/regex cache, guard name loop.

## Failure classes → why they can't recur
Punctuation/possessive → separators, never in keys. Scrub order → one leftmost-longest scan. Per-name cost/window cap → O(runs × longest name). Glued names → runs split on every non-word char, joins separator-blind. Devanagari marks → run chars. Curly/fullwidth/ZWSP → NFKC + folds before lookup. Glued honorifics → suffix peel after whole-run lookup. R4-R1 stored names ending in ji → whole run first; guard collapsed lookup. R4-R2 "iyer chem" vs iyerchem → collapsed key. Latency → no per-window resolver. `_` → separator everywhere. Token invisible before `_` → emission rule + property test. Group noise words → merge. Guard blind to what ingress missed → same index (honest limit: not an independent classifier; the test oracle is an independent scanner). Amounts/years/typed tokens/field kinds → reused code, re-run reproducers. Novel names/inactive names → N layer (D2) + wider set (D3).

## Risks
Over-tokenising (N/Q rate reported); novel names that are English words (Rose, Grace) pass; guard false raises on model prose (KCH-239 needs recovery path); out of scope: transliteration, homoglyphs, numbers in words, space-grouped digits; stored name inside a longer glued word only via N; name set frozen per conversation; amount grammar still regex; timing tests must also handle sys.monitoring (3.12+); tie-set shortcut depends on resolver's score-1.0 = equality (differential test); prototype numbers exclude emission/merge/N — re-measure.

## Size
entity_index.py ~220 lines; tokeniser.py 1,126 → ~920; safe_words.py frozenset ~8–10k words (only if D2=A); tests ~800–1,000 new lines; one build + one review.

## Acceptance suite (written first; must fail on cycle-2 for R1/R2/F1/F3)
A. Reproducer corpus (probes/ in this folder, copied into tests as data) over DEMO, iyer, Devanagari/o'brien, honorific, V–V4 and 1,200-name sets; independent scanner finds nothing; guard doesn't raise; ruled outputs pinned (e.g. `ramesh gupta, pooja verma; asha bhat.` → `B001, B002; D001.`, azim premji exact at ingress+egress, iyer chem → G, anil sharmaji → B001-ji, bg1/bg13/bg 13/bg-13/bg_13, 2026_03_004 unchanged); a7 false-positive list stays plain; accepted over-tokenising pinned; typed tokens raise.
B. Variant fuzz: every stored value × ~20 deterministic variations → 0 scanner hits.
C. Egress: 56-call READ sweep, p7 errors, r4_f1 resolve_entity, PROPOSE sweep of 4 KCH-243 tools incl. every ErrorCode.
D. Conversation replay (a9 with "Q2 2026", a9b): 0 false raises, 0 leaks at DEMO and 1,200 names.
E. Properties: exactness differential vs resolver; TOKEN_RE round-trip; guard never raises on tokenised output; every token rehydrates.
F. Performance (trace suspended, median of 5, 40×30 itertools names, committed distinct ≥2,000-char prose): tokenise < 100 ms at 1,200 names and DEMO; names-only and pathological < 100 ms; index build < 100 ms; guard replay < 50 ms, < 10 ms per new message.
G. Mutation: review mutants that still apply + new (no collapsed key, suffix before whole-run, union tie set, no NFKC, no script boundary, no emission hyphen, no G2, no N layer).
H. Gates per BRIEF.

## Owner decisions
D1 threat model: (a) accidental disclosure by a trusted operator incl. common Unicode quirks [recommended] / (b) also deliberate evasion (not reachable with stdlib/deterministic code).
D2 novel names: (A) closed list — non-safe words → N token [recommended; word-list licence REVIEW REQUIRED] / (B) name-shaped words near loan verbs → Q (rule-based again) / (C) none; KCH-243 new names via form only.
D3 protected set: (a) active loans only / (b) + inactive loans + pending-report names [recommended].
D4 guard: (a) same index G1–G4 with cache [recommended] / (b) re-tokenise and require no change / (c) keep cycle-2 whole-value guard.
D5 delivery: (a) new branch on feature/kch-243, acceptance suite first, one build, one review, stop and re-plan if a leak class §3 doesn't claim appears [recommended] / (b) stay on feature/kch-238, KCH-243 via fixtures.

## OWNER DECISIONS (2026-09-28) — binding
- Approved as planned. D1 = (a) accidental disclosure incl. common Unicode quirks.
- D2 = (A) closed list: non-safe unknown words → N token. The safe-word list source's licence is [REVIEW REQUIRED]: prefer a public-domain or MIT/BSD-compatible list; record source + licence in the module header and PR body; do not vendor anything GPL.
- D3 = (b) protected set = active + inactive loans + names in pending reports (resolver stays active-only).
- D4 = (a) guard uses the same index (G1–G4) with a per-message cache.
- D5 = (a) branch feature/kch-238-redesign on feature/kch-243 (cycle-2 tokeniser files brought over from feature/kch-238). Acceptance suite FIRST (show it failing on cycle-2 for R1/R2/F1/F3), then one build, then one review. If the review finds a leak class §3 does not claim, STOP and re-plan — no patch cycles.
