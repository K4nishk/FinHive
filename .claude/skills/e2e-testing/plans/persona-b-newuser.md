# Persona B — new user

> Part of the `e2e-testing` skill — loaded only for `/e2e newuser`. Rules of engagement and severity live in [`../SKILL.md`](../SKILL.md); log findings with [`../findings.md`](../findings.md).

## §B · Persona B — The New User

> **Who you are**: an SMB bookkeeper who has never seen this product. Nobody trained you. You have your loan data in a spreadsheet and about ten minutes of patience.
>
> **What you are testing**: whether a stranger can get to value alone.

### B1 · Signup

| # | Check |
|---|---|
| B1.1 | Signup is findable from the landing state without instructions |
| B1.2 | Required fields are labelled and their constraints stated **before** submitting |
| B1.3 | Password rules are shown up front, not revealed by rejection |
| B1.4 | Weak password is rejected with a specific, actionable message |
| B1.5 | Invalid email is caught client-side with a clear message |
| B1.6 | Duplicate email fails **without confirming the account exists** (enumeration) |
| B1.7 | Email verification, if required, states clearly what to do next |
| B1.8 | The submit button disables while in flight — double-submit cannot create two accounts |
| B1.9 | A failed signup preserves what you typed |

### B2 · Login & session

| # | Check |
|---|---|
| B2.1 | Login succeeds and lands somewhere useful — not a blank page |
| B2.2 | Wrong password gives a generic failure (no enumeration) |
| B2.3 | Password field is masked, with a deliberate reveal toggle |
| B2.4 | Password manager autofill works (correct `autocomplete` attributes) |
| B2.5 | Session survives a page refresh |
| B2.6 | Token expiry refreshes transparently — no surprise logout mid-task |
| B2.7 | Logout actually clears the session; Back does not restore the app |
| B2.8 | Deep-linking to an authed route while logged out redirects to login, **then returns you there** after login |
| B2.9 | Password reset completes end to end |

### B3 · Empty state & first value

The moment most products lose the user.

| # | Check |
|---|---|
| B3.1 | A zero-data account shows guidance, not an empty grid |
| B3.2 | There is one obvious next action (create a loan, or import) |
| B3.3 | Import is discoverable from the empty state |
| B3.4 | The expected import format is documented **before** you have to guess it |
| B3.5 | A malformed import fails with a row-level, human-readable error |
| B3.6 | Creating the first loan visibly succeeds and appears immediately |
| B3.7 | The agent is discoverable, and says what it can do before you type |
| B3.8 | Asking the agent something with zero data gives a helpful answer, not an error |

### B4 · Time to first value

Measure and record. This is a product metric, not a pass/fail.

| Milestone | Target |
|---|---|
| Signup → logged in | ≤ 60s |
| Logged in → first loan saved | ≤ 3 min unaided |
| Logged in → first useful agent answer | ≤ 2 min |
| Spreadsheet → data imported | ≤ 5 min |

### B5 · Role boundaries

| # | Check |
|---|---|
| B5.1 | A `bookkeeper` sees no Approve control |
| B5.2 | A `bookkeeper` calling the approve endpoint **directly** gets 403 — not a hidden button |
| B5.3 | A `viewer` cannot create or edit |
| B5.4 | Role restrictions are explained, not just enforced silently |
| B5.5 | A brand-new org sees **only its own** data (cross-check with a second account) |
