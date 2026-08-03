# BUZZ SPIKE REPORT
## Pin: `19d57b0d46baa55814ac737041a36d0b405c9f64` | Sat Aug 1 07:36:56 2026 +0500 | License: Apache-2.0

Evaluation spike: can `block/buzz` serve as the AX-governed T3 collaboration surface,
where AX is the sole intelligence and authority and Buzz is a governed surface?

Every finding below is labelled `OBSERVED-RUNNING`, `OBSERVED-SOURCE`,
`DOC-CLAIM-UNVERIFIED`, `ABSENT`, or `UNRESOLVED`. Nothing is reported as working
on the strength of a doc claim.

---

## HEADLINE VERDICT

**Buzz is fit to be an AX-governed T3 surface, and the multi-tenancy premise held up
better than expected — but the "less work" claim is only PARTIALLY TRUE, and one
sealed AX guarantee is structurally broken.**

The single most important positive: **hard multi-community isolation is shipped and
running, not roadmap.** I stood up one relay process with two communities and proved
by execution that the same key, presenting the same channel UUID, reads its canary
message on host A and gets `[]` on host B (Q1). Host binding fails closed on unmapped
hosts. This was the question most likely to flip the decision to "no," and it passed.
Equally important: **the owner-attestation model works and gives AX the light custody
model** — AX holds only an owner key, employees/agents hold their own keys, and AX
grants and revokes access without ever holding an employee private key (Q3/Q6, all
five steps `OBSERVED-RUNNING`).

The single biggest risk: **erasure is structurally blocked.** After a NIP-09 delete,
I read the full plaintext, the populated FTS search vector, the signature, and the
author pubkey straight out of Postgres (Q4, `OBSERVED-RUNNING`). Deletion in Buzz is a
visibility tombstone (`deleted_at`), not erasure. There is **no per-principal erasure
API anywhere in the codebase**. If AX's "forget me" guarantee is sealed, AX must build
erasure into Buzz — that is co-building, not extending.

Three further control gaps land on AX rather than being inherited: NIP-OA attestation
**conditions are not enforced at the relay authorization gate** (a `kind=1`-scoped and
even a long-expired attestation both granted full read *and write* access —
`OBSERVED-RUNNING`); **any rank-and-file channel member can create a persistent
relay-executed cron job** (`OBSERVED-RUNNING`, fired twice, relay-signed); and the
`buzz-acp` harness **defaults to `bypassPermissions`** and additionally auto-approves
any permission request that still arrives (`OBSERVED-SOURCE`) — this is in the harness
that the Hermes relay-bridge path uses, not merely in Desktop.

On the cost claim: what is genuinely pre-built and adoptable is substantial and real
(tenancy, identity, attestation, the bidirectional seam, the admin authority surface).
What must be co-built is erasure, attestation-condition enforcement, scheduling
governance, liveness, and — critically — **there is no plugin/extension system**, so
any behavioral change lands inside the `buzz-*` Rust crates and becomes permanent
merge surface.

---

## SETUP RESULT

**Did the relay stand up?** Yes, but not by following the documented quick-start, and
with two hard blockers worth recording as part of the maintenance-cost answer.

| Requirement | Result |
|---|---|
| Rust 1.95.0 (pinned in `rust-toolchain.toml`) | Present |
| Node 22 / pnpm | Present (not needed for relay) |
| Postgres | **Required.** Used local PG 16 cluster (repo's compose pins PG 17) |
| Redis | **Required.** Relay will not start without it |
| S3 / MinIO | **Effectively required** — see friction below |
| Docker | **Unavailable in this environment** (no daemon) |

**Friction encountered (all `OBSERVED-RUNNING`):**

1. `just setup` / `docker compose up` was unusable — no Docker daemon. I stood up
   Postgres and Redis natively instead. A self-hosting customer without Docker faces
   the same manual path.
2. **Migrations do not run by default.** First boot logged
   `Skipping database migrations because BUZZ_AUTO_MIGRATE is not enabled`, then
   cascaded into `relation "events" does not exist`. Requires `BUZZ_AUTO_MIGRATE=true`.
3. **The relay refuses to boot without a working S3 backend.** A startup "git
   object-store conformance probe (A3 gate)" hard-fails the process:
   `Error: git conformance probe failed: s3 backend error`. I had to set
   `BUZZ_GIT_CONFORMANCE_PROBE=false` to boot. This is a real self-host topology cost:
   the relay is not a "Postgres + Redis" service, it expects object storage too.
4. Release build of `buzz-relay` + `buzz-cli` took roughly 25 minutes cold.

**buzz-cli working?** Yes — this was my primary instrument and it is
agent-appropriate: JSON in/out, `--format compact` as a global flag, clean exit codes.
Minor friction: several subcommand/flag names differ from the documented examples
(`--content` not `--text`; channel `--type stream|forum`, `--visibility open|private`;
`messages get` not `messages list`; `messages search` rejects `--kinds`, which the
project's own CLAUDE.md tells agents to pass). Instrument readiness: **good.**

I also built two tiny helpers against the repo's own crates to act as the external
authority: `crates/buzz-sdk/examples/mint_oa.rs` (mints NIP-OA attestations via
`buzz_sdk::nip_oa::compute_auth_tag`) and `crates/buzz-ws-client/examples/observe.rs`
(NIP-42-authenticated event-stream observer).

---

## CRITICAL FINDINGS (Q0–Q6b)

### Q0 — THE FIRST-PARTY HERMES↔BUZZ INTEGRATION

> **WHICH WORLD ARE WE IN: `UNRESOLVED` on the decisive sub-question, but the
> evidence available points to *single-operator convenience*, not a governed
> multi-tenant seam.**

**What I could not do, stated plainly.** The integration's substance lives in
**Hermes**, which is not in this repo and which I could not obtain:
`hermes-agent.nousresearch.com/docs/integrations/buzz` returned **HTTP 403** to my
fetch, and I have no Hermes source tree and no AX Hermes pin to compare against.
Therefore: *which Hermes version introduced it*, whether it is **tenant-aware or
tenant-blind**, and whether it survives AX's distribution patch + enforcer are all
**`UNRESOLVED`**. I am not going to convert a plausible reconstruction into a verdict —
this is the single highest-leverage question in the spike and it remains open.

What secondary reporting describes (all `DOC-CLAIM-UNVERIFIED`, from a web search of
the announcement, not from source): three paths — Desktop spawning Hermes as a managed
ACP runtime; the `buzz-acp` relay bridge hosting a Hermes identity server-side; and a
native gateway plugin making Buzz a Hermes messaging platform alongside Telegram and
Discord, with channels, DMs, threads, reactions and cron delivery.

**What I *can* prove, from the Buzz side (`OBSERVED-SOURCE`):**

Buzz's half of the bridge is genuinely thin and generic — Hermes is treated as one
more ACP binary, not a privileged partner. The *entire* Hermes-specific surface in
Buzz is command-name recognition and one environment default:

- `crates/buzz-acp/src/config.rs:716` —
  `"hermes" | "hermes-agent" | "hermes-acp" => &[("HERMES_ACP_SKIP_CONFIGURED_MCP", "1")]`

That is the whole integration on the Buzz side. There is **no tenant plumbing, no
per-tenant credential handling, and no isolation concept** in Buzz's Hermes path —
because Buzz's ACP harness is a single-identity process: one `BUZZ_PRIVATE_KEY`, one
relay URL, one agent identity. **`INFERENCE` (unverified):** a bridge built on this
shape is single-operator by construction; making it multi-tenant means running one
harness per tenant identity and keeping them isolated — which is AX's work, not
inherited. I flag this as inference precisely because I could not read the Hermes side.

**Auto-approve check — this one I resolved, and it matters (`OBSERVED-SOURCE`):**

The prompt asked whether Desktop's auto-approve is Desktop-only (acceptable) or leaks
into the gateway/bridge path (blocker). **It is not Desktop-only. It is in `buzz-acp`,
the harness the relay-bridge path runs on, and it is default-on at two layers:**

- `crates/buzz-acp/src/config.rs:435-444` — `BUZZ_ACP_PERMISSION_MODE`
  **`default_value = "bypass-permissions"`**, documented as *"Defaults to
  `bypassPermissions` which skips the per-tool-call permission flow."*
- `crates/buzz-acp/src/acp.rs:1148` — the core message loop:
  *"`session/request_permission` requests → auto-approved with `allow_once`"*
- `crates/buzz-acp/src/acp.rs:1856` — `handle_permission_request` finds the
  `allow_once` option and responds with it. No policy check, no gate.

So the harness both tells the agent to skip its own permission flow *and* rubber-stamps
any request that still arrives. It **is** configurable
(`BUZZ_ACP_PERMISSION_MODE=default` restores the agent's built-in behaviour) — that is
the mitigation, and it is a one-line deployment change. But the default is unsafe for
tenant work, and **an AX tenant agent routed through `buzz-acp` at defaults would have
its approval gate silently satisfied by Buzz.**

**Plugin-vs-renderer extension path (`ABSENT` — decision-relevant):**

I searched for a first-class plugin/extension system that would let an external party
add *behavior* without modifying core Rust crates. `grep -rn -i "plugin" crates/*/src/lib.rs`
returns **nothing**; `find crates -name '*plugin*'` returns **nothing**. There is no
plugin registry, no dynamic loading, no extension trait surface for third parties.
Extension points that do exist are configuration (env vars), the workflow YAML engine,
the ACP harness boundary, and the canvas. **Any behavioral gap AX needs closed lands
inside the `buzz-*` crates — i.e. a maintained fork.** This is the finding that most
directly stresses the "light extension" thesis.

**Bottom line for Q0:** on the evidence I could actually obtain, this does **not**
give AX a governed, multi-tenant, output-guarded Buzz surface for free. The Buzz-side
seam is single-identity, the permission default is bypass, and there is no plugin path.
But the decisive tenant-awareness question about the *Hermes* side is genuinely
**UNRESOLVED** and should be closed before the decision, by reading the Hermes
integration source directly.

---

### Q1 — MULTI-COMMUNITY ISOLATION: shipped, or roadmap?

> **VERDICT: `OBSERVED-RUNNING` — hard multi-tenant isolation is SHIPPED and enforced
> at N>1. This is the strongest result in the spike.**

**Implementation (`OBSERVED-SOURCE`).** `crates/buzz-relay/src/tenant.rs` implements
"row zero": `req.community = resolve_host(connection.host)`, bound at connection
establishment, with a `HostResolver` trait and a fail-closed `bind_community`. The
module is explicit that there is *deliberately no path that yields a default or
fallback community*, and it fails closed **before** the resolver lookup when the host
is empty (`tenant.rs:85-90`), so a missing Host header cannot bind to a misconfigured
empty-host row. `bind_community` is called at **every** entry door — WebSocket/SPA
(`router.rs:300`), audio (`audio/handler.rs:79`), NIP-05 (`api/nip05.rs:39`), git
transport (`api/git/transport.rs:131`), invites (`api/invites.rs:240`), the generic
Nostr bridge `POST /events` `/query` `/count` (`api/bridge.rs:630,898,1341,1821,2076`),
media (`api/media.rs:165,484`), and NIP-11 (`nip11.rs:251,283`). `community_id` is a
foreign key on every tenant table (`events`, `channels`, `channel_members`,
`audit_log`, `archived_identities`, …).

**Proof by running.** One relay process, one Postgres, one Redis, two communities:

```
localhost:3000    → 6bf45b56-0fda-4821-97bc-908abb1a12b2   (community A)
b.localhost:3000  → 7e182a3e-ce22-40c6-b62f-c626fb31f64b   (community B)
```

*Fail-closed host binding:*
```
Host: localhost:3000          → 200
Host: b.localhost:3000        → 200
Host: unknown.localhost:3000  → 404  "relay: no community is configured for this host"
Host: evil.example.com        → 404  "relay: no community is configured for this host"
```
The rejection is byte-identical across unmapped hosts and does not echo the host — an
unauthenticated caller cannot probe which communities exist.

*Cross-tenant read attempt — same key, same channel UUID, adversarial `h` scope:*
```
[1] HOST A: messages get --channel 9440798a-…   → [{"content":"TENANT-A-SECRET-CANARY-12345", …}]
[2] HOST B: messages get --channel 9440798a-…   → []
[3] HOST B: channels list                        → []
[A] HOST A: messages search --query CANARY       → [{"content":"TENANT-A-SECRET-CANARY-12345", …}]
[B] HOST B: messages search --query CANARY       → []
```
Community B cannot see A's channel, A's messages, or A's content through full-text
search, even though the caller holds A's own key and supplies A's exact channel UUID.

**The honest caveat.** The repo ships an executable conformance harness
(`crates/buzz-test-client/tests/conformance_multitenant.rs`) that mirrors an obligation
table one row per module. **8 of roughly 20 obligations are `todo!()` stubs** via a
`pending_lane()` marker — i.e. named but *not yet proven* by the project itself:

| Pending obligation | Lane | Line |
|---|---|---|
| `archived_identities` — A's archive invisible to B | buzz-auth | 907 |
| same event id / d-tag coexist across communities | buzz-db | 1292 |
| **DM in A never cross-delivers to B's subscription** | buzz-pubsub | 1302 |
| feed mentions don't cross communities over the wire | feed read-side | 1327 |
| approval token minted in A can't be satisfied on B | WF-08 | 1942 |
| A cannot read B's media upload metadata/quota/audit | buzz-media | 2623 |
| same owner/repo git push in A doesn't advance B | buzz-media | 2641 |
| one key in two communities — no membership/profile bleed | relay-wiring | 2659 |

The rows with real bodies cover the core: row-zero binding, client-supplied community
cannot override host, NIP-11 non-enumeration, token minted in A doesn't authorize in B,
NIP-98 replay scoping, distinct profiles per community, per-host NIP-05, and channel
UUID isolation. **What I proved by running is the channel/message/search path. DM
cross-delivery, media metadata, and git pointer isolation are the project's own
acknowledged gaps and I did not test them** — treat those three as unproven.

**What it means:** the "we're extending strong foundations" premise **holds** for
tenancy. AX is not building Buzz's multi-tenancy. But AX should independently verify
the three pending isolation lanes that touch data it cares about — especially **DM
cross-delivery**, which is a member-visible leak shape.

---

### Q2 — THE BRAIN QUESTION: does Buzz accept an externally-brained member?

> **VERDICT: `OBSERVED-RUNNING` — YES, cleanly. No local model is required anywhere.
> AX can be the only brain.**

**Proof by running.** Every write in this entire spike — channels created, messages
posted, workflows registered, canary written, event stream consumed — was performed by
`buzz-cli` and by my own `observe.rs`, i.e. **external processes holding nothing but a
Nostr private key, with no `buzz-agent`, no model, and no LLM of any kind running.**
The relay accepted all of it. That is the question, answered by execution.

**Source corroboration (`OBSERVED-SOURCE`):**

- The persona `model` field is **optional at every layer**: `Option<String>` in
  `buzz-persona/src/manifest.rs:51`, `merge.rs:26`, `pack.rs:83`, `persona.rs:143`,
  `resolve.rs:37`. Persona config is separable from a runtime brain.
- Crucially, **"agent-ness" in Buzz is a cryptographic relationship, not a runtime
  property**: `crates/buzz-relay/src/handlers/ingest.rs:1703` derives `is_agent` from
  `users.agent_owner_pubkey IS NOT NULL` — i.e. an identity is an agent because it has
  a NIP-OA owner, **not** because a model is attached to it. Nothing in the relay
  inspects, requires, or invokes a model.

**Assumptions that would push toward a local model:** the ACP harness (`buzz-acp`)
does assume a spawnable agent subprocess — but that is the harness, which AX would
simply not use if AX is the brain. Presence, typing indicators, canvas updates and
workflow steps are all plain event publications an external process can emit directly.

**What it means:** the clean design (AX is the only model, no `buzz-agent` LLM) is
supported today with no seam required. This is a genuine "adoptable as-is."

---

### Q3 — EXTERNAL AUTHORITY / POLICY PROJECTION

> **VERDICT: `OBSERVED-RUNNING` — an external authority CAN fully govern access,
> grant and revoke, per-identity. But the mechanism is NOT the one the framing
> assumed, and two governance holes are real.**

**All five required steps passed by execution.** Relay restarted in the governed
(AX-style) configuration — `BUZZ_REQUIRE_RELAY_MEMBERSHIP=true`,
`BUZZ_ALLOW_NIP_OA_AUTH=true`, `RELAY_OWNER_PUBKEY=<AX>` — then, acting purely as an
external authority via `buzz-admin`:

```
(a) before grant   → {"error":"auth_error","message":"relay error 403: relay_membership_required"}
    control (AX)   → [{"channel_id":"9440798a-…","name":"spike-a"}]
(b) grant          → added a521e442… as member
(c) after grant    → [{"channel_id":"9440798a-…","name":"spike-a"}]
(d) revoke         → removed a521e442…
(e) after revoke   → {"error":"auth_error","message":"relay error 403: relay_membership_required"}
```

**The owner-attestation spine is REAL and works (`OBSERVED-RUNNING`).** NIP-OA is
specified in `docs/nips/NIP-OA.md` and implemented. I minted an attestation with AX's
owner key over a *separate* agent key and proved transitive admission:

```
agent WITHOUT attestation (non-member) → 403 relay_membership_required
agent WITH AX's attestation            → [{"channel_id":"9440798a-…","name":"spike-a"}]
```

And transitive **revocation** works — removing the *owner* from `relay_members`
immediately killed the attested agent's access:
```
removed d808921f… (owner)
agent with that owner's attestation → 403 relay_membership_required
  (BUZZ_AUTH_TAG is set — it may be stale or revoked; try unsetting it)
```

Mechanism at source: `crates/buzz-relay/src/api/mod.rs:61-111` (`check_relay_membership`)
— if the caller is not a direct member, the relay verifies the NIP-OA `auth` tag and
grants `MembershipDecision::ViaOwner(owner)` **iff the owner is a relay member**.
Persisted first-write-wins by `materialize_nip_oa_owner` (`api/mod.rs:174`).

**Now the three corrections to the framing — all decision-relevant:**

**(1) Revocation is NOT by attestation. It is by relay-member removal.**
`docs/nips/NIP-OA.md` has **no revocation primitive**. Its own Security Properties
section says only: *"Owners SHOULD bound authorization lifetime with a `created_at<…`
clause when revocation latency matters. Owners MAY revoke future authorization by
refusing to issue new `auth` tags."* Revocation therefore requires AX to hold the
**relay admin surface**, not merely the owner key. That works — I proved it — but it
means AX's authority path runs through `buzz-admin`/DB, not through signed attestations
alone.

**(2) 🔴 Attestation CONDITIONS ARE NOT ENFORCED at the authorization gate
(`OBSERVED-RUNNING`).** This is the most important negative finding in Q3. The NIP-OA
conditions vocabulary is only `kind=<n>`, `created_at<t>`, `created_at>t` — **there is
no channel scope and no capability scope expressible at all.** Worse, the conditions
that *do* exist are ignored by the relay's membership gate:

```
attestation scoped "kind=1" (i.e. NOT chat kind 9):
  → read kind-9 chat:                    SUCCEEDED (returned channel messages)
  → WRITE a kind-9 chat message:         {"accepted":true,"event_id":"fc917296…"}

attestation scoped "created_at<1700000000" (expired ~Nov 2023):
  → channels list:                       [{"channel_id":"9440798a-…","name":"spike-a"}]
```

A narrowly-scoped attestation grants **full read and write**, and an **expired
attestation still grants access.** This is technically NIP-OA-conformant — the spec
says relays *"MUST NOT be required to verify"* the tag and that conditions constrain
*events*, evaluated by clients — but the practical consequence for AX is blunt:
**time-boxed and scoped attestations do not work as governance at the relay.** The
attestation is a binary "does this chain to a member?" check.

**(3) The `Scope` enum is not a governance lever in the shipping path
(`OBSERVED-SOURCE`).** `crates/buzz-auth/src/scope.rs:1-5` states it outright:
*"In pure Nostr mode, all NIP-42 authenticated connections receive the full scope set;
per-channel access is enforced by NIP-29 membership checks."* Confirmed in code —
`buzz-auth/src/lib.rs:138` assigns `Scope::all_known()` (all 16 scopes), and
`api/bridge.rs:833` comments *"Pure Nostr: full scopes, channel access via membership."*
So the real levers are exactly two: **relay membership** (binary, community-wide) and
**NIP-29 channel membership**.

**Also worth flagging (`OBSERVED-SOURCE`): Buzz ships OPEN by default.** In
`crates/buzz-relay/src/config.rs`: `require_auth_token=false` (:524),
`pubkey_allowlist_enabled=false` (:528), `require_relay_membership=false` (:532 —
documented as *"the check is a no-op and all authenticated callers are permitted"*),
`allow_nip_oa_auth=false` (:200). Since Nostr keys are self-generated, a default Buzz
relay admits **anyone** and grants them all 16 scopes. AX must explicitly flip
`BUZZ_REQUIRE_RELAY_MEMBERSHIP=true` and `BUZZ_ALLOW_NIP_OA_AUTH=true`. This is the
peer-model default the framing predicted, and it is a deployment-config fix, not a
code fix.

---

### Q4 — ERASURE / DELETION vs. the append-only log

> **VERDICT: `OBSERVED-RUNNING` — ERASURE IS STRUCTURALLY BLOCKED. Deletion is a
> visibility tombstone. This is a hard collision with a sealed AX guarantee.**

**API-level deletion looks clean:**
```
messages delete --event 459588fe…  → {"accepted":true,…}
messages get    --channel …        → []
messages search --query CANARY     → []
```

**Raw Postgres tells the truth:**
```sql
SELECT encode(id,'hex'), content, deleted_at IS NOT NULL AS tombstoned
  FROM events WHERE content LIKE '%CANARY%';

 459588fe…  | TENANT-A-SECRET-CANARY-12345 | t
```
```sql
SELECT left(search_tsv::text,120) FROM events WHERE content LIKE '%CANARY%';

 '12345':6 'a':3 'canary':5 'secret':4 'tenant':2 'tenant-a-secret-canary':1
```
```sql
SELECT (sig IS NOT NULL) AS sig_kept, encode(pubkey,'hex') FROM events WHERE content LIKE '%CANARY%';

 t | aea89bb491abcf0f27ce86a3cde78155e2e1b4e808fdc9849d5ef197ec9b2bd7
```

After a successful NIP-09 delete: **full plaintext retained, FTS tokens still indexed,
signature retained, author pubkey retained.** Only `deleted_at` was set.

**Source confirms this is by design, not a bug (`OBSERVED-SOURCE`):**
`crates/buzz-db/src/event.rs:775` — `soft_delete_event` is literally
`UPDATE events SET deleted_at = NOW() …`. Nothing nulls `content`, `sig`, or
`search_tsv`. `crates/buzz-search/src/query.rs:242` filters reads with
`AND deleted_at IS NULL` — so search *hides* but does not *forget*.

**There is no erasure API (`ABSENT`).** A codebase-wide search for
`gdpr|right to be forgotten|forget_user|purge_user|erase` returns **no
per-principal erasure path**. The only `DELETE FROM events` statements are: test
fixture cleanup (`admin_moderation.rs:441` — I checked, it is inside a `#[ignore]`
test), and an internal NIP-RS read-state housekeeping delete for superseded kind-30078
coordinates (`buzz-db/src/lib.rs:4889`). Neither is a user- or tenant-erasure feature.

`archived_identities` is **not** erasure — `crates/buzz-db/src/archived_identities.rs`
exposes only `is_archived` / `archive` / `unarchive` / `list_archived`. It is a
visibility flag on the identity; it deletes no content.

**Partial-erasure precision, as requested:** it is not "body gone, hash retained." It
is **nothing gone.** Body, signature, author, and search vector all persist in the
primary event store indefinitely after deletion.

**What it means:** if AX's "forget me" / tenant-deletion guarantee is sealed, adopting
Buzz means **building erasure into Buzz** — a hard-delete path plus FTS purge plus
media/CAS purge plus an audit-chain story. That is co-building, and it touches
`buzz-db`, `buzz-search`, `buzz-media`, and `buzz-audit` — i.e. core crates, with no
plugin seam (see Q0). **This is the finding most likely to change the decision.**

---

### Q5 — THE BIDIRECTIONAL AX↔BUZZ SEAM + OUTPUT GUARD

> **VERDICT: `OBSERVED-RUNNING` — the seam is cleanly bidirectional and externally
> controllable. BUT there is one real unguardable human-read output path.**

**INTO Buzz (`OBSERVED-RUNNING`).** An external process controls the exact bytes:
```
messages send --content "AX-CONTROLLED-BYTES-<<guarded>>"  → {"accepted":true,…}
SELECT content FROM events WHERE content LIKE 'AX-CONTROLLED%';
  → AX-CONTROLLED-BYTES-<<guarded>>
```
Byte-exact, no transformation, no injection. **This is structurally guaranteed, not
merely observed:** events are BIP-340 Schnorr-signed by their author and
`crates/buzz-core/src/verification.rs:11,27` (`verify_event` → `verify_signature()`)
rejects anything whose signature doesn't match. The relay *cannot* alter author-signed
content without invalidating it. AX's output guard can wrap emission safely.

**OUT of Buzz (`OBSERVED-RUNNING`).** My external observer authenticated over NIP-42
and consumed the channel's live event stream as structured Nostr events:
```
AUTHENTICATED as aea89bb4…
STREAM: Event { subscription_id: "spike", event: Event { id: EventId(67625af2…), pubkey: PublicKey(4f355bdc…), created…
… 12 events received (backlog + live)
```
The relay correctly refuses unauthenticated subscription
(`["NOTICE","auth-required: authenticate before subscribing"]`), which is the right
fail-closed behavior. Real-time, externally consumable, structured enough to drive
reasoning and write records into Twenty/GBrain on the AX side.

**🔴 The unguardable path (`OBSERVED-RUNNING`).** The relay itself composes, signs and
posts human-readable messages into channels. My cron workflow (Q6a) produced:
```
relay log: "Workflow SendMessage: posting kind 9 event"
           event_id=42b1b494… channel_id=9440798a… author=a521e442…(workflow creator)
DB:        content='beacon tick'  pubkey=4f355bdc…(THE RELAY KEY)  has_sig=t
```
The stored event is **signed by the relay key**, not the agent's — content originated
server-side, with no agent process running, and reached a human-readable channel. **An
external AX-side output guard cannot intercept this, because AX never emits those
bytes.** The text is workflow-YAML-defined so the blast radius is bounded, but workflow
steps support templating and `call_webhook`, so this is a genuine hole, not a
technicality. AX must either disable relay-side workflows or treat relay-authored
events as an unguarded channel.

---

### Q6 — IDENTITY CUSTODY MODEL

> **VERDICT: `OBSERVED-RUNNING` — (b) ATTESTATION/DELEGATION. The LIGHT model. AX does
> NOT need to hold employee private keys.**

This is a clean, favorable answer and I proved it end to end.

- **Who generates the keypair / where does the private key live?** Whoever holds it.
  Buzz is self-sovereign by default; `buzz-admin generate-key` will mint one, and
  `buzz-cli` accepts any key via `BUZZ_PRIVATE_KEY`. Nothing requires the authority to
  custody it.
- **Delegation without holding the key: YES.** In my test, AX (owner) held **only**
  its own private key. The agent held a **separate** key AX never possessed. AX minted
  a NIP-OA attestation over the agent's *public* key — and the agent was admitted:

```
mint_oa <AX_SECRET> <AGENT_PUBKEY> ""
  → ["auth","aea89bb4…","","d7272991…"]

agent (non-member, no attestation) → 403
agent (same key, + AX attestation) → [{"channel_id":"9440798a-…","name":"spike-a"}]
```

  Per `docs/nips/NIP-OA.md`, this is explicitly **not** NIP-26 impersonation: the event
  remains authored by the agent key (*"Clients MUST treat the agent key in
  `event.pubkey` as the only author key"*), and the attestation is authorization
  evidence only. Compromise of an agent key does not imply compromise of the owner key.

**The concrete custody model AX would adopt:** AX holds **one owner key per
tenant/authority boundary**. T3 employees and agents hold their own keys. AX authorizes
by (i) adding the owner to `relay_members` and (ii) minting attestations over member
public keys; AX revokes by removing the owner or the member from `relay_members` —
which I proved cascades transitively to every agent attested under that owner.

**The caveats that come with it** (carried from Q3, restated because they shape the
design): the attestation cannot express *channel* or *capability* scope at all, and its
`kind=`/`created_at` conditions are **not enforced** at the relay gate. So attestation
gives AX **admission and revocation**, not **scoping**. Scoping must come from NIP-29
channel membership, which AX also controls.

---

### Q6a — INVISIBLE AGENT-CREATED SCHEDULED JOBS

> **VERDICT: `OBSERVED-RUNNING` — agents CAN create persistent relay-executed
> scheduled work with only ordinary membership. But it is NOT invisible: it is fully
> queryable by an authority. The reviewer's "invisible" is a Desktop UI gap, not a
> protocol gap.**

**The hole is real.** A **non-owner, rank-and-file** identity, holding nothing but
channel membership, registered an every-minute cron job:
```
workflows create --channel 9440798a-… --yaml "name: covert-beacon
trigger: {on: schedule, cron: '*/1 * * * *'}
steps: [{id: s1, action: send_message, text: beacon tick}]"
  → {"accepted":true,"workflow_id":"2f80451f-effd-40d7-b70a-a181af0f1437"}
```
**And it executed, unattended, server-side:**
```
23:07:33  Workflow SendMessage: posting kind 9 event  event_id=42b1b494…
23:08:33  Workflow SendMessage: posting kind 9 event  event_id=2f85bcfb…
workflow_runs count → 2
```

**Source: the authorization bar is a chat message (`OBSERVED-SOURCE`).**
`crates/buzz-relay/src/handlers/ingest.rs:317` —
`KIND_WORKFLOW_DEF | KIND_WORKFLOW_TRIGGER => Ok(Scope::MessagesWrite)`. Creating a
persistent cron job requires the *same* scope as sending a message, and every NIP-42
connection holds all scopes (Q3). `handle_workflow_def`
(`handlers/command_executor.rs:653`) additionally requires only channel membership
(`:673-681`). **There is no scheduling authority, no admin scope, no approval gate.**

**But visibility is better than reported — an important correction.** The workflow was
immediately visible to the channel owner via the ordinary API, and in the DB:
```
workflows list --channel 9440798a-…
 → [{"content":"name: covert-beacon\ntrigger:\n  on: schedule\n  cron: '*/1 * * * *'…",
     "pubkey":"a521e442…","workflow_id":"2f80451f-…"}]

SELECT id,name,encode(owner_pubkey,'hex'),enabled FROM workflows;
 → 2f80451f-… | covert-beacon | a521e442… | t
```
Workflow definitions are kind `30620` events, **not** in `AUTHOR_ONLY_KINDS`
(`buzz-core/src/kind.rs:120`), so they are normal queryable, `h`-tag-scoped events.

**One partial gate does exist (`OBSERVED-SOURCE`):** workflows containing
exfiltration-capable actions (`call_webhook`) require owner/admin role —
`command_executor.rs:692-704`, *"plain membership is not enough, because the workflow
will forward channel content outward with the owner's standing authority."* Good
instinct, narrowly scoped.

**What it means for AX:** AX **can** see, authorize and revoke every scheduled job —
the data is there. The costs are (i) enumeration is **per-channel** (`workflows list
--channel <id>`), so AX needs to sweep all channels rather than call one relay-wide
"list all jobs" endpoint, and (ii) creation is **not gated**, so AX's cron-scoping and
unattended-action floor cannot be enforced *preventively* by Buzz — only detected
after the fact. AX should disable relay-side workflow creation (or gate kind 30620) and
be the sole scheduling authority.

---

### Q6b — AGENT LIVENESS / STUCK-AGENT DETECTION

> **VERDICT: `OBSERVED-SOURCE` — the RELAY provides no liveness enforcement. Timeouts
> exist, but only in the `buzz-acp` harness, which AX would not be running. AX's
> watchdog must own liveness entirely — but AX has better raw signals than expected.**

**Timeouts exist, in the harness (`OBSERVED-SOURCE`).**
`crates/buzz-acp/src/acp.rs:723-756` implements `session_prompt_with_idle_timeout` with
**two** deadlines: an *idle* deadline that **resets on any stdout activity**, and a
**hard wall-clock cap** (`max_duration`) as a safety valve. This both corroborates and
refines the reviewer's observation — pinging a stalled agent *does* extend the idle
deadline, which is exactly the "can't tell active from stuck" failure mode, **but**
there is a hard cap behind it, so a stall is not unbounded. Default turn timeout is
320s (`BUZZ_ACP_TURN_TIMEOUT`, `.env.example`); `BUZZ_ACP_MAX_TURNS_PER_SESSION`
defaults to **0 = disabled**.

**Critically: none of this is in the relay.** These are properties of the ACP harness
process. If AX is the brain (Q2) and does not run `buzz-acp`, **AX inherits none of it.**
The relay enforces no turn limits, no completion conditions, and no stuck detection.

**Raw signals AX would actually work with (`OBSERVED-SOURCE`):**

1. **`kind:44200` Agent Turn Metric (NIP-AM)** — the strongest signal, and better than
   the framing assumed. `crates/buzz-core/src/agent_turn_metric.rs` — one event per
   *completed* turn, NIP-44-encrypted **from the agent key to the owner pubkey**. It
   carries a `StopReason` (`EndTurn`, `MaxTokens`, `Cancelled`, `Error`, `Unknown`) plus
   token/cost counters. **Because it is encrypted to the owner, AX-as-owner-key can
   decrypt it** — this is a real completion signal that fits the AX authority model.
2. Presence (online/away/offline) and typing indicators — ephemeral kinds.
3. Last-event timestamp per channel from the event stream (Q5).

**The gap:** all of these are *positive* signals. A stuck agent emits **nothing** — no
turn metric, no completion. So "done" is observable; **"stuck" vs "dead" is only
inferable from absence-of-signal plus AX's own timeout.** AX's watchdog must own that
entirely, keyed on last-event timestamp and its own dispatch deadline.

**Corroborated informed prior (`OBSERVED-RUNNING`): rate limits are configured but not
enforced on the message path.** `.env.example` documents
`BUZZ_RATE_LIMIT_HUMAN_MESSAGES_PER_MIN=60`, and the limiter infrastructure exists
(`RedisRateLimiter`, `state.rs:584,713`). I sent **85 messages in ~1 minute from one
identity — all 85 accepted** (25 then 60, `{"accepted":true}` every time). The limiter
*is* wired for media uploads (`api/media.rs:223` → `UploadRateLimitExceeded`), but I
observed no enforcement on chat. AX must supply admission control.

---

## SECONDARY FINDINGS (Q7–Q11)

### Q7 — UPSTREAM MERGE REALITY — `OBSERVED-SOURCE` (partial)
I did not run a rebase-against-upstream experiment in the time box (**UNRESOLVED** for
the empirical half). The structural half is answered and is the part that matters:
**there is no plugin or extension system** (Q0 — `grep -i plugin` over
`crates/*/src/lib.rs` and `find crates -name '*plugin*'` both return nothing). The
available no-fork extension points are **configuration** (env vars — genuinely broad),
the **workflow YAML engine**, the **ACP harness boundary**, and the **canvas**. Anything
behavioral — erasure (Q4), attestation-condition enforcement (Q3), scheduling
authorization (Q6a) — lands **inside** `buzz-db`, `buzz-auth`, `buzz-relay`,
`buzz-search`. Those are the highest-churn crates in the repo. **Merge-conflict risk for
AX's needed changes is high, and permanent.**

### Q8 — DELETION vs SEARCH/AUDIT — `OBSERVED-RUNNING`
Covered in Q4 and confirmed directly. **`buzz-search` retains content after delete**:
the `search_tsv` vector remained fully populated with the canary tokens; queries merely
filter `AND deleted_at IS NULL` (`buzz-search/src/query.rs:242`). Content is hidden, not
removed from the index. **`buzz-audit`** is a hash-chain (`crates/buzz-audit/` —
`hash.rs`, `entry.rs`, `service.rs`) and is by construction append-only; I did **not**
empirically test what it retains for a deleted event (**UNRESOLVED**), but a hash chain
cannot have entries removed without breaking the chain, so treat audit retention as
structurally certain.

### Q9 — SELF-HOST TOPOLOGY COST — `OBSERVED-RUNNING`
Required to run the relay: **Postgres** (17 in compose; 16 worked), **Redis 7**
(mandatory — pub/sub, presence, rate limiting, cache invalidation), and
**S3-compatible object storage** (MinIO locally) — which is *not* optional in practice:
the startup git object-store conformance probe **hard-fails the process** without a
reachable S3 backend, and I had to set `BUZZ_GIT_CONFORMANCE_PROBE=false` to boot.
The compose file also ships Adminer, Keycloak, and Typesense for the fuller dev stack.
Plus the relay binary itself, and a ~25-minute cold Rust release build.
**Assessment: a self-hosting AX customer can realistically also self-host Buzz, but it
is a 4-service stateful deployment (relay + Postgres + Redis + object storage), not a
sidecar.** Migrations need `BUZZ_AUTO_MIGRATE=true` or an explicit `buzz-admin migrate`.

### Q10 — CANVAS FEATURE GAP — `UNRESOLVED` (shallow)
I did not assess this properly and will not guess. What I saw: the ACP harness tracks
`canvas_sections: HashMap<Uuid, String>` per channel (`buzz-acp/src/pool.rs:105`), and
`buzz-cli` exposes `canvas get`/`canvas set` for channel canvas documents. That shape —
a per-channel string document — suggests something considerably simpler than a
versioned, auto-re-rendering, signed-URL-shareable "living artifact," i.e. **the
extension delta is probably large**. But I did not verify versioning, rendering, or
sharing, so this is explicitly **not** a finding. Needs its own investigation.

### Q11 — POOLED/SHARED COMPUTE — `OBSERVED-SOURCE` (partial)
The feature is real: `docs/buzz-shared-compute-dev.md` documents the path
`Buzz Desktop → buzz-acp → buzz-agent → MeshLLM SDK → local/remote compute`, driven by
a **"Share this machine"** control in Desktop, with a dedicated `buzz-relay-mesh` crate
and a `just mesh-dev-fresh` recipe. **Default-off and strictly opt-in on the relay
side (`OBSERVED-SOURCE`)**: `crates/buzz-relay/src/config.rs:148-149` — *"Opt-in: mesh
forms only when `BUZZ_MESH=on` is explicit"*; `:545-547` — anything other than the exact
string `on` (absent, `off`, other values) leaves it off. My relay logged
`mesh disabled (BUZZ_MESH is not 'on') — single-instance behavior` on every boot
(`OBSERVED-RUNNING`). **Verdict: cleanly disableable — in fact it is off unless
deliberately enabled, on both the relay (env) and the Desktop (explicit user action).**
I did **not** trace the MeshLLM data path to characterize exactly what crosses a member
boundary when it *is* on (**UNRESOLVED**) — so "safe to enable for internal Spectre use"
is not established, only "safe to leave off for tenant work," which is the operative
requirement.

---

## COLLISION REGISTER

| # | Collision | Verdict | Detail |
|---|---|---|---|
| Q0 | First-party integration tenant-aware? | **UNRESOLVED** | Hermes docs 403'd; no Hermes source available. Buzz's half is single-identity by construction (one key, one relay, one harness) and Hermes-specific code is *one env default*, `buzz-acp/src/config.rs:716`. Must be closed by reading Hermes source. |
| Q0 | Survives AX's distribution patch + enforcer? | **UNRESOLVED** | Same reason. Cannot be answered from the Buzz side. |
| Q0 | Auto-approve leaks into the gateway/bridge path? | **YES — 🔴** | Not Desktop-only. `BUZZ_ACP_PERMISSION_MODE` **defaults to `bypassPermissions`** (`config.rs:435-444`) *and* `handle_permission_request` auto-approves with `allow_once` (`acp.rs:1148,1856`). Mitigation: set `BUZZ_ACP_PERMISSION_MODE=default`. Tenant agents must never run at defaults. |
| Q0 | Plugin/extension system for behavior? | **ABSENT — 🔴** | No plugin registry, no dynamic loading, no third-party extension trait. Behavioral changes ⇒ core-crate fork. |
| Q3 | AX-as-owner-key authorizes AND revokes every agent? | **YES, with caveats** | Grant/revoke/transitive-revoke all `OBSERVED-RUNNING`. **But** revocation is via `relay_members` removal, **not** by attestation — NIP-OA has no revocation primitive. AX needs the admin surface, not just the owner key. |
| Q3 | Attestation conditions enforced (scoping/expiry)? | **NO — 🔴** | `kind=1`-scoped attestation granted full kind-9 **read and write**; **expired** attestation still granted access. Conditions cannot express channel or capability scope at all. Attestation = admission, not scoping. |
| Q4 | Can a principal be fully forgotten? | **NO — 🔴 SEALED-GUARANTEE COLLISION** | Not partial — **nothing is erased.** After NIP-09 delete: plaintext, FTS vector, signature, author pubkey all retained in Postgres. No per-principal erasure API exists anywhere. |
| Q5 | Any unguardable human-read output path? | **YES** | Relay-side workflow execution composes and **relay-signs** kind-9 messages into channels with no agent process running. An external output guard cannot intercept it. Bounded (workflow-YAML-defined) but real. |
| Q6a | Can agents create persistent jobs AX doesn't see? | **CREATE: YES / SEE: YES** | Creation needs only `MessagesWrite` + channel membership (`ingest.rs:317`) — no scheduling authority. But jobs are queryable kind-30620 events and DB rows, so AX **can** enumerate. Cost: per-channel enumeration, and detection-only (not prevention). |
| Q6b | Can AX tell active from stuck from done? | **DONE yes; STUCK/DEAD no** | Relay enforces nothing. Signals: `kind:44200` turn metric with `StopReason`, **encrypted to the owner key** (fits AX); presence; last-event timestamp. Stuck is only inferable from absence-of-signal. Idle+hard deadlines exist but live in `buzz-acp`, which AX wouldn't run. |
| Q6b | Rate limiting enforced? | **NO (chat path)** | 85 messages in ~1 min from one identity, all accepted, past the documented 60/min. Limiter enforced for media uploads only. |
| Q1 | Isolation shipped or roadmap? | **SHIPPED ✅** | Proven at N>1 by execution: cross-tenant channel/message/FTS reads all return `[]`; unmapped hosts 404 generically. Caveat: 8 of ~20 conformance obligations are `todo!()` stubs — notably **DM cross-delivery**, media metadata, git pointer isolation. |
| Q6 | Must AX hold employee private keys? | **NO ✅ — light model** | Attestation/delegation proven end to end. AX holds one owner key; employees/agents hold their own; AX never possessed the agent key it authorized. |

---

## COST READ — is "less work / just extending / light fork" true?

**Verdict: PARTIALLY TRUE.** Genuinely stronger than a from-scratch build, materially
weaker than "light extension."

**Genuinely pre-built and adoptable as-is (real, load-bearing, would cost months):**
- **Multi-community isolation** — host-bound, fail-closed, `community_id` FK on every
  tenant table, enforced at every entry door. Proven at N>1. *AX is not building Buzz's
  multi-tenancy.* This is the headline "less work" win.
- **Owner attestation (NIP-OA)** — a specified, implemented, cryptographically
  self-proving delegation primitive that gives AX the **light custody model**. Rare and
  valuable; would be expensive to design correctly from scratch.
- **External authority surface** — `buzz-admin` grant/revoke, proven working, including
  transitive revocation through owner removal.
- **Externally-brained membership** — no local model required anywhere. AX-as-only-brain
  works today with zero seam.
- **Clean bidirectional seam** — byte-exact ingress (signature-guaranteed) and
  real-time authenticated egress.
- Plus: NIP-42 auth, audit hash-chain, FTS, media, git hosting, workflow engine,
  Desktop + mobile clients.

**What must be built or co-built (all inside core Rust crates — no plugin seam):**
1. **Erasure** — 🔴 the big one. Hard-delete + FTS purge + media/CAS purge + audit-chain
   story. Touches `buzz-db`, `buzz-search`, `buzz-media`, `buzz-audit`. Nothing exists to
   extend.
2. **Attestation-condition enforcement** — making scoped/expiring attestations actually
   bind at the authorization gate, and inventing channel/capability scope, which the
   NIP-OA conditions grammar cannot express at all.
3. **Scheduling governance** — gate kind 30620 creation; add relay-wide job enumeration.
4. **Liveness/watchdog** — entirely AX's, keyed on `kind:44200` + last-event timestamp.
5. **Admission control / rate limiting** on the message path.
6. **Deployment hardening** — flip the open-by-default switches
   (`BUZZ_REQUIRE_RELAY_MEMBERSHIP`, `BUZZ_ALLOW_NIP_OA_AUTH`,
   `BUZZ_ACP_PERMISSION_MODE=default`, `BUZZ_MESH` left off). *Config, not code — cheap.*
7. **Per-tenant harness isolation**, if the Hermes bridge is used (pending Q0).

**Two-codebase (Rust + Python) maintenance texture:** this is where "light fork" is
weakest. **There is no extension surface for behavior.** Items 1–3 and 5 all land in
`buzz-relay`/`buzz-db`/`buzz-auth`/`buzz-search` — the repo's highest-churn crates.
Every upstream pull will conflict with AX's changes there, indefinitely. The honest
framing is **"adopt a strong substrate and maintain a real fork of its core,"** not
"extend via plugins." Config-level hardening and the canvas are the only genuinely
no-fork paths, and neither covers erasure.

**Net:** the "we're extending strong foundations" premise **survives** — the
foundations are real and I verified the most important one by running it. But "less
work" is **PARTIALLY TRUE**, and it is *conditional on the erasure guarantee*. If
"forget me" is sealed and non-negotiable, that single item converts this from
"extending" to "co-building," and it should be scoped before committing.

---

## UNRESOLVED

Explicitly not proven. **None of these should be read as passes.**

1. **🔴 Q0 — the decisive tenant-awareness question.** Hermes docs returned HTTP 403;
   no Hermes source, no AX Hermes pin available. Tenant-aware vs. single-operator,
   which Hermes version introduced it, whether it survives AX's patch + enforcer, and
   whether "cron delivery" respects tenant scoping are **all open**. My single-operator
   read is labelled `INFERENCE` from the Buzz side only. **This is the highest-leverage
   open item and should be closed first, from Hermes source.**
2. **Q1 — three isolation lanes the project itself has not proven**: DM cross-delivery
   between communities, media upload metadata/quota boundary, git repo pointer
   isolation. All `todo!()` in the repo's own conformance suite. I did not test them.
   DM cross-delivery matters most.
3. **Q4 — audit hash-chain retention** not empirically tested for a deleted event
   (structurally certain, but unverified by running).
4. **Q7 — no rebase-against-upstream experiment run.** The structural finding
   (no plugin system) stands; the empirical merge-pain measurement does not exist.
5. **Q10 — canvas** not properly assessed. The "extension delta is probably large" read
   is a hunch from two code sightings, not a finding.
6. **Q11 — MeshLLM data path** not traced. I established mesh is off-by-default and
   cleanly disableable; I did **not** establish what crosses a member boundary when on.
7. **Media/S3 tenant boundary** untested — no MinIO available (no Docker), and I booted
   with the S3 conformance probe disabled.
8. **Desktop app** not exercised at all — auto-approve findings are from `buzz-acp`
   source, not from running Desktop.
9. **N=1 wire-parity** (that existing clients see byte-identical behavior) not verified.

---

## RAW EVIDENCE APPENDIX

### Environment
```
Pin:      19d57b0d46baa55814ac737041a36d0b405c9f64  (Sat Aug 1 07:36:56 2026 +0500)
License:  Apache-2.0
Rust:     1.95.0 (pinned)      Postgres: 16.13 (compose pins 17)     Redis: 7 (native)
Docker:   UNAVAILABLE (no daemon) → no MinIO, no compose
Relay boot flags required: BUZZ_AUTO_MIGRATE=true  BUZZ_GIT_CONFORMANCE_PROBE=false
Spike helpers added: crates/buzz-sdk/examples/mint_oa.rs
                     crates/buzz-ws-client/examples/observe.rs
```

### Q1 — two communities, one relay process
```sql
SELECT id, host FROM communities;
 6bf45b56-0fda-4821-97bc-908abb1a12b2 | localhost:3000
 7e182a3e-ce22-40c6-b62f-c626fb31f64b | b.localhost:3000
```
```
curl -H 'Host: localhost:3000'          → 200
curl -H 'Host: b.localhost:3000'        → 200
curl -H 'Host: unknown.localhost:3000'  → 404 "relay: no community is configured for this host"
curl -H 'Host: evil.example.com'        → 404 "relay: no community is configured for this host"

HOST A  messages get --channel 9440798a-15e4-4d1a-a909-ed52112f8316
        → [{"content":"TENANT-A-SECRET-CANARY-12345","id":"459588fe…"}]
HOST B  messages get --channel 9440798a-15e4-4d1a-a909-ed52112f8316   → []
HOST B  channels list                                                  → []
HOST A  messages search --query CANARY  → [{"content":"TENANT-A-SECRET-CANARY-12345",…}]
HOST B  messages search --query CANARY  → []
```

### Q3/Q6 — grant → access → revoke → deny, and attestation delegation
```
(a) 403 relay_membership_required   (b) added a521e442…   (c) [{"channel_id":"9440798a-…"}]
(d) removed a521e442…               (e) 403 relay_membership_required

mint_oa <AX_SECRET> a521e442… ""
 → ["auth","aea89bb491abcf0f27ce86a3cde78155e2e1b4e808fdc9849d5ef197ec9b2bd7","","d7272991…"]
agent WITHOUT attestation → 403
agent WITH attestation    → [{"channel_id":"9440798a-…","name":"spike-a"}]

transitive revocation:
 added d808921f… (owner) → agent via its attestation: [{"channel_id":…}]
 removed d808921f…       → 403 relay_membership_required
                            (BUZZ_AUTH_TAG is set — it may be stale or revoked…)

conditions NOT enforced:
 attestation "kind=1"                → read kind-9: OK; WRITE kind-9: {"accepted":true,"event_id":"fc917296…"}
 attestation "created_at<1700000000" → channels list: [{"channel_id":"9440798a-…"}]   (expired, still admitted)
```

### Q4 — erasure
```
messages delete --event 459588fe… → {"accepted":true}
messages get → []      messages search --query CANARY → []

-- but in Postgres:
 id=459588fe…  content='TENANT-A-SECRET-CANARY-12345'  tombstoned=t
 search_tsv = '12345':6 'a':3 'canary':5 'secret':4 'tenant':2 'tenant-a-secret-canary':1
 sig_kept=t   author=aea89bb491abcf0f27ce86a3cde78155e2e1b4e808fdc9849d5ef197ec9b2bd7
```
Source: `buzz-db/src/event.rs:775` `UPDATE events SET deleted_at = NOW() …`;
`buzz-search/src/query.rs:242` `AND deleted_at IS NULL`.

### Q5 — bidirectional seam
```
IN:  messages send --content "AX-CONTROLLED-BYTES-<<guarded>>" → {"accepted":true}
     SELECT content … → AX-CONTROLLED-BYTES-<<guarded>>        (byte-exact)
OUT: AUTHENTICATED as aea89bb4…
     STREAM: Event { subscription_id: "spike", event: Event { id: EventId(67625af2…) … }
     (12 events: backlog + live)
     unauthenticated REQ → ["NOTICE","auth-required: authenticate before subscribing"]
UNGUARDABLE PATH:
     relay log: "Workflow SendMessage: posting kind 9 event" event_id=42b1b494…
     DB:        content='beacon tick'  pubkey=4f355bdc…(RELAY KEY)  has_sig=t
```

### Q6a — agent-created cron
```
workflows create (non-owner member) → {"accepted":true,"workflow_id":"2f80451f-…"}
23:07:33  Workflow SendMessage: posting kind 9 event  event_id=42b1b494…
23:08:33  Workflow SendMessage: posting kind 9 event  event_id=2f85bcfb…
SELECT count(*) FROM workflow_runs; → 2
workflows list --channel … → [{"content":"name: covert-beacon…cron: '*/1 * * * *'…"}]   (VISIBLE)
```
Source: `handlers/ingest.rs:317` `KIND_WORKFLOW_DEF … => Ok(Scope::MessagesWrite)`;
`handlers/command_executor.rs:673-681` membership only; `:692-704` `call_webhook`
requires owner/admin.

### Q6b — rate limiting
```
25 sends → 25 × {"accepted":true}
60 sends → 60 × {"accepted":true}      (85 total in ~1 min, documented limit 60/min)
```

### Key source citations
```
crates/buzz-relay/src/tenant.rs:1-95          row-zero host binding, fail-closed
crates/buzz-relay/src/router.rs:300           bind_community at the WS/SPA door
crates/buzz-relay/src/api/mod.rs:61-111       check_relay_membership + NIP-OA ViaOwner
crates/buzz-auth/src/lib.rs:138               Scope::all_known() on NIP-42 auth
crates/buzz-auth/src/scope.rs:1-5             "all NIP-42 connections receive the full scope set"
crates/buzz-relay/src/config.rs:524,528,532   open-by-default governance switches
crates/buzz-relay/src/config.rs:148-149,545   BUZZ_MESH strict opt-in
crates/buzz-acp/src/config.rs:435-444         BUZZ_ACP_PERMISSION_MODE = bypass-permissions
crates/buzz-acp/src/acp.rs:1148,1856          auto-approve session/request_permission
crates/buzz-acp/src/config.rs:716             the entire Hermes-specific surface in Buzz
crates/buzz-acp/src/acp.rs:723-756            idle + hard deadline (harness-side only)
crates/buzz-core/src/agent_turn_metric.rs     kind:44200, StopReason, encrypted to owner
crates/buzz-core/src/verification.rs:11,27    verify_event → verify_signature
crates/buzz-relay/src/handlers/ingest.rs:1703 is_agent := agent_owner_pubkey IS NOT NULL
docs/nips/NIP-OA.md                           owner attestation spec (no revocation primitive)
crates/buzz-test-client/tests/conformance_multitenant.rs:907,1292,1302,1327,1942,2623,2641,2659
                                              the 8 pending isolation obligations
```
