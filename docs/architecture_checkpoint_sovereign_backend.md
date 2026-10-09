# Architecture checkpoint: the "Sovereign Enterprise AI" proposal

**Status:** proposal, 2026-10-09. **No code written.** Awaits the owner's `PROCEED` or
`PROCEED WITH MODIFICATIONS` on §6 (CLAUDE.md stage gate).

Read with ARB M1.1: D-4a, D-15, D-16, OQ-01 (as amended).

---

## 1. Checkpoint: M1.1 on `development` at `b88c30e`

| Area | State |
|---|---|
| Ask FinHive tab, end to end | Merged. KCH-230 to KCH-246, plus KCH-248 (eval harness) and KCH-250 (grounding) |
| Fixes from owner testing | #58–#65 merged. F-001 to F-004 and F-006 are 🟢. F-005 is 🟡: doc fixed, eval case planned for KCH-249 |
| Encryption key | Created on first launch at `data/encryption/master_key.key`; Opus-reviewed (#64, #65) |
| Gates on `b88c30e` | App suite: 5226 passed, 6 skipped, 8 xfailed. Root unit: 258 passed, 2 skipped. Integration: 17 passed, 1 skipped. `lint-imports`: 3 contracts kept. CI 3/3 green |
| Open | KCH-247 (owner runs it on the real ledger), KCH-249 evals, KCH-251 nightly (needs a budget cap), KCH-253, D-17 spike; owner's Windows re-test |

---

## 2. The proposal's premises, checked against the code

| Premise | Evidence | Verdict |
|---|---|---|
| Inference runs locally on the user's machine | `data/settings.json` `llm.base_url = https://openrouter.ai/api/v1`, model `qwen/qwen-2.5-72b-instruct`. No `torch`, `transformers`, `llama` or `vllm` in any requirements file. ARB D-4a | **False.** Inference has always been remote |
| The MacBook (18 GB) lacks memory to run models alongside its normal work | Measured 2026-10-09: the desktop app, offscreen, on the 27-loan demo, peaks at **129 MiB RSS** (`VmHWM`, Linux) | **Not a constraint.** No model is loaded; 129 MiB is about 0.7% of 18 GB |
| The desktop uses local Postgres/pgvector | `src/Loan Manager` runs SQLite with SQLAlchemy. The `pgvector/pgvector:pg16` image is in MVP2's `docker-compose.yml` only, with the extension not enabled (D-16) | **Partly false** |
| The agent loop is heavy | `run_agent_turn.py` is 487 lines of pure Python. `openai` is the only AI dependency, and it is an HTTP client | **Light.** Moving the loop off the desktop saves nothing measurable |
| A "Laya judge model" | No reference in the repo, the ARB, the Linear CSV or the spec | **Unknown** `[REVIEW REQUIRED]` |
| RAG pipelines | No retrieval corpus exists. Every question is answered by structured tools over the ledger | **No use case yet.** D-16 keeps `CREATE EXTENSION vector` as a one-line migration for when one appears |

**What the proposal gets right is inference sovereignty.**
- Today, tokenised prompts go to OpenRouter, a third party.
- OQ-01 (amended) records that inference is the one path that still leaves the machine.
- Self-hosting vLLM in your own cluster, in India per OQ-01, removes that third party.
- This is independent of where the agent loop runs.
- D-4a already planned it: "the self-hosted exit … survives as `base_url` + server launch flags (vLLM requires `--enable-auto-tool-choice --tool-call-parser <family>`)".

**A gap the proposal rightly names is resilience.**
- `openai_compat_client.py:66` sets `max_retries=0` (by design: "the agent loop owns retry").
- `RunAgentTurn` has no retry: `run_agent_turn.py:326` catches `LLMError` and fails the turn.
- So one dropped connection, or a cold-starting server, fails the turn. This needs fixing under any option.

---

## 3. Why the loop cannot just move to the server

`RunAgentTurn` is the only place where the tokeniser and the tools meet (`run_agent_turn.py:3-8`). One step runs:

```
LLM → tool call → detokenise_args → handler → tokenise_observation → LLM
```

- `detokenise_args` needs the `TokenMap`, the plaintext ↔ token map.
- The handler reads the encrypted local ledger in 8 of the 10 tools. Only `get_current_context` and `format_inr` don't.

The key and the `TokenMap` never leave the desktop (D-15, OQ-01). So a server-side loop must call back to the desktop on **every tool step**: a remote brain with local hands.

*Example:* `What is overdue for the sharma group?` takes 4 model calls and 3 tools. As a server loop that is 4 server→vLLM calls plus 3 server→desktop→server round trips. The server must also hold the state of each in-flight turn.

**Stays on the desktop under either option:**
- the tokeniser and entity resolver;
- all 10 tool handlers and their pydantic argument checks;
- `assert_no_plaintext` before anything leaves;
- the encrypted `agent_turns` recorder and grounding;
- **enforcing the READ/PROPOSE gate.** A server must never be able to make the desktop run a PROPOSE tool that the user's own words did not unlock.

**Moves to the server under the outline:** the step loop, building the system prompt, and the `openai` SDK.

**New failure modes the outline adds:**
- a disconnect while a tool call is outstanding;
- a pod restart that loses turn state, which then needs a session store;
- replay and idempotency of tool results;
- a new authenticated API that can trigger local tool execution. The server becomes a remote controller of the ledger's read path. That falls under policy item 3 (agent tool permissions), so it needs an Opus review.

---

## 4. Options

### A. Sovereign inference; the loop stays on the desktop (recommended)

- **Backend:**
  - vLLM, which serves the OpenAI-compatible API, on a GPU node pool;
  - a model-weights PVC so restarts don't re-download;
  - readiness on `/health`;
  - DCGM-Exporter for GPU metrics;
  - auth via vLLM's `--api-key` behind TLS ingress, or a thin FastAPI gateway only if you need more (per-device keys, rate limits, request logs of tokenised bodies only).
- **Desktop:**
  - `settings.json` `llm.base_url`, `model` and `api_key_env` ("a `base_url` change by construction", D-4a);
  - plus the resilience fix: retry with backoff on connect, 502/503 and timeout; a longer first-call timeout; and a visible "model is warming up" state in the tab instead of a failed turn.
- **Gate before switching:** the D-4a spike, suite E2, run against the vLLM endpoint. It must pass the tool-call parser, the `rate=0.12` quirk, and resolve-before-query. D-4a: fidelity "is verified, not assumed".
- **How your phases map:**
  - **Phase 2** applies almost as written.
  - **Phase 1** shrinks to the optional gateway.
  - **Phase 3** shrinks to resilience and a status UI; the `openai` SDK stays as the HTTP client.
- **Zero PII leakage:** unchanged. The tokeniser and `assert_no_plaintext` stay where they are.

### B. The outline as written: server loop, desktop tools over SSE + POST

- **Protocol sketch:**
  - `POST /v1/turns`, with `{conversation_id, tokenised_text, tokenised_history, mode}`. The mode comes from the desktop's own gate.
  - `GET /v1/turns/{id}/events` as SSE: `thought`, `tool_call`, `final`, `error`. Resume with `Last-Event-ID`.
  - `POST /v1/turns/{id}/tool-results`, with `{call_id, tokenised_observation}`, idempotent per `call_id`.
  - The desktop checks every `tool_call` against its own registry and mode before running it.
- **Needs:**
  - a session store (Redis or Postgres) for in-flight turns;
  - resume semantics;
  - device auth (mTLS or per-device key);
  - a server-side plaintext check as defence in depth.
- **Effort** `[estimate, REVIEW REQUIRED]`:
  - several issues each in Phases 1 and 3;
  - an Opus security review (tool permissions and egress);
  - a new e2e suite for the transport.
  - The 71 tests in the files that exercise `RunAgentTurn` would need porting to the server or duplicating.
- **When B pays off.** Any of these would trigger it, and none exists today:
  - several clients sharing one agent (MVP2 web);
  - server-side retrieval over a shared corpus;
  - evaluation on live traffic.

---

## 5. Cost and policy

- **GPU** `[estimate from model size; REVIEW REQUIRED against your provider's prices]`.
  - Qwen 2.5 72B at fp16 is about 145 GB of weights: 2 × 80 GB GPUs.
  - An AWQ/INT4 build is about 40 GB: one 48–80 GB GPU.
  - An always-on node is billed per GPU-hour, against today's measured $0.00037 per model call.
  - A smaller tool-capable model (7–14B) is far cheaper, but must pass E2 again.
  - Scale-to-zero cuts the bill but makes cold starts the normal case, which is why the resilience fix comes first.
- **CLAUDE.md policy 6 (thinnest visible slice first; evals after):** the judge-model service is eval infrastructure, so it comes after you have seen self-hosted inference answer a question.
- **MVP2 is paused after KCH-109.** A FastAPI backend is MVP2-shaped work. Decide whether this un-pauses MVP2 or is its own track.
- **OQ-01:** the cluster's region is India.

---

## 6. Decisions needed

| # | Question | Default if unanswered |
|---|---|---|
| S-1 | Option A or B? | **A** |
| S-2 | What is "Laya"? Model id, source and licence. Judge for which suite? (E3 faithfulness is computed deterministically today by `grounding.py`) | Judge service deferred |
| S-3 | Cluster provider, region, GPU type, monthly cap | None. Manifests can be written and linted, but not applied |
| S-4 | Model to serve | `Qwen2.5-72B-Instruct-AWQ`; must pass E2 |
| S-5 | Desktop → backend auth | Per-device API key from the key file or env, over TLS |
| S-6 | Order versus M1.2/M1.3 (KCH-247, 249, 251) | Resilience fix first; then A after KCH-247; B as M2 |
| S-7 | ARB entry | Record as **D-18**: amends D-4a's provider; OQ-01's transfer ends once inference is self-hosted |

---

## 7. If A: issue slices, thinnest first

1. **Desktop resilience.** Retry with backoff on connect, 5xx and timeout inside the step budget; a warming-up state in the tab; tests with the recorded fake. This is useful today against OpenRouter.
2. **vLLM on K8s manifests.** A Deployment with a GPU `nodeSelector` and toleration, the model PVC, and readiness; a Service; a DCGM-Exporter DaemonSet; plus `kubeconform` in CI.
3. **E2 spike against the vLLM endpoint.** The owner runs `ops/probe_openrouter.py` with the new `base_url`. This is the gate.
4. **Switch `settings.json`**, plus a D-18 ARB entry.
5. **Gateway**, only if S-5 needs more than `--api-key`.
6. **Judge service**, after S-2, together with KCH-249 evals.

---

## 8. Owner decisions, interview of 2026-10-09

These supersede the defaults in §6 and the slicing in §7.

| Topic | Decision | What it means |
|---|---|---|
| Drivers | Sovereignty, cost at scale, showcase/learning. **Not** several clients | Nothing triggers Option B |
| Agent loop | **Option A.** The loop, the tools and the tokeniser stay on the desktop | The desktop calls the home box by `base_url` |
| Ledger and key | **Desktop, plus escrow.** A sealed backup of `master_key.key` is kept in Vault/OpenBao on the box | The box only ever sees tokens; a dead laptop no longer loses the key |
| Hardware | **Own box:** RTX 3090 with **8 GB VRAM free**. A low-tier model is acceptable | Main model at most about 7B at 4-bit; vLLM `gpu_memory_utilization` ≈ 0.3 |
| Box OS | **Windows, native** | vLLM runs in Linux containers via Docker Desktop (WSL2 backend, GPU passthrough) |
| Runtime | **Docker Compose on the box; K8s manifests validated in CI** | The manifests are portfolio-complete (`kubeconform` plus a GPU-less `kind` smoke test) and are not applied at home |
| Box availability | **On when the owner works.** The GPU's other 16 GB is used by other work | Cold starts (model load, about 30–90 s) are routine, so a warming-up state is required |
| Network | **Same LAN only** | Away from the LAN, or with the box off: a clear "AI server unreachable" in the tab, and **no fallback to OpenRouter** |
| Main model | **Chosen by the E2 spike** from 2–3 candidates that fit 8 GB, e.g. Qwen2.5-7B-Instruct-AWQ, Qwen2.5-3B-Instruct, Llama-3.1-8B-Instruct-AWQ | The owner runs the spike on the box; the cloud cannot reach the LAN |
| Laya ([`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya); owner: an open-source alternative to TypeSafeAI's Jev) | Roles: **offline evals, the eval pipeline, and a live guard in shadow mode**. Size **≤ 2B** (owner) | The shadow verdict is logged per turn and never changes the answer; it runs after the turn, off the user's path |
| Eval pipeline | **Both**: an on-demand eval command now, and a self-hosted GitHub runner on the box later | Scheduled jobs queue until the box is on; the PR lane stays zero-network |
| Order | **Resilience fix, then KCH-247, then this track** | KCH-249 and 251 are re-scoped to the home box and Laya |

**VRAM budget** (estimates, `[REVIEW REQUIRED]` on the box):
- A 7B at 4-bit is about 5.5 GB of weights; a 3B at 4-bit about 2 GB.
- Laya at ≤ 2B is about 4 GB at fp16, or about 1.5 GB at 4-bit.
- A 7B plus Laya at fp16 does not fit in 8 GB. The E2 winner sets whether Laya runs on the GPU or on CPU (fine for shadow mode).

### Revised slices (one issue each, thinnest first)

| # | Slice | Review |
|---|---|---|
| 1 | **Desktop resilience.** Retry with backoff on connect, 5xx and timeout inside the step budget; warming-up and unreachable states in the tab. Useful against OpenRouter today | Self-review + CI |
| 2 | **KCH-247.** The owner migrates the real ledger | (existing) |
| 3 | **Box stack (Compose).** vLLM with a model cache volume and a `gpu_memory_utilization` cap; a thin FastAPI gateway (OpenAI-compatible pass-through, `/health` reporting warming or ready, a per-device API key, a route to Laya); DCGM-Exporter. Windows setup guide | Opus: it carries prompts off the machine |
| 4 | **E2 spike** on 2–3 candidates, run by the owner on the box, which picks the model | — |
| 5 | **Desktop provider switch** to the home box, plus ARB **D-18** | Opus: egress path |
| 6 | **K8s manifests:** Deployments, Services, PVCs, GPU `nodeSelector`/taints/tolerations, DCGM DaemonSet; `kubeconform` + `kind` smoke in CI | Self-review + CI |
| 7 | **Laya in evals:** an offline judge in the KCH-249 harness plus the on-demand eval command | Self-review + CI |
| 8 | **Laya shadow guard:** an async verdict stored per turn; needs a schema change | Opus: migration |
| 9 | **Key escrow** to OpenBao on the box | Opus: keys |
| 10 | **Self-hosted runner** for the eval pipeline (KCH-251 re-scoped) | Self-review |

### Still to verify before slice 3
- **Laya's licence, serving method and exact size**, from its model card. `huggingface.co` is blocked by this session's network policy.
- **DCGM-Exporter on a GeForce 3090:** basic metrics are expected; profiling metrics are data-centre-GPU only.
- **Docker Desktop GPU passthrough** for the vLLM image on the owner's box: `docker run --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`.
- **Owner's OK to record D-18** in `ARB_DECISIONS.md`, which is LIVE and authoritative.
