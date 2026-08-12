# BUZZ AX-SIDE CLOSURE REPORT

## Repos actually mounted
- **Buzz:** `ysjnr/buzz` @ `631b05c883f58e9533e9038b4669ebdfb1d9cf27` (branch `claude/new-session-vpz86r`)
- **Hermes:** `NousResearch/hermes-agent` @ `a3bcb2c23265dd6bc571fd7522ca4f6475c1b9a6` (2026-08-12), full history, 21,783 commits
- **AX distribution tree (`ysjnr/ax`): NOT MOUNTED — `ABSENT`.** See BLOCKER below.
- AX's current Hermes pin, from AX's ledger: **`UNRESOLVED`** — the ledger is inside the AX tree.

---

## 🔴 BLOCKER — the AX tree could not be mounted

This spike was scoped to run *inside* AX's own repo. It could not.

- `add_repo(ysjnr/ax)` → `repository "ysjnr/ax" was not found on github.com, or this session's GitHub credential doesn't have access to it. Detail: you don't have access to ysjnr/ax` — `OBSERVED-RUNNING`
- `list_repos` returns the account's **complete** repo list (`has_more: false`): 12 repos — `buzz`, `free-claude-code`, `voicebox`, `financial-services`, `public-apis`, `hermes-workspace`, `blnk`, `zeroclaw`, `blnk-docs`, `nanoclaw`, `openclaw`, `insanely-fast-whisper`. **No `ax`.** — `OBSERVED-RUNNING`
- `ysjnr/hermes-workspace` was checked as a candidate and is **not** the AX tree: it is a fork of `outsourc-e/hermes-workspace` v2.3.0, a TypeScript "zero-fork" UI workspace running on vanilla `NousResearch/hermes-agent`. It contains **no** `agent/secret_scope.py`, `gateway/run.py`, `cron/scheduler.py`, `_profile_runtime_scope`, or any `AgentXTenantManager`. — `OBSERVED-SOURCE`

**Consequence, stated plainly:** every finding that requires reading AX's identity-core patch —
`AgentXTenantManager`, the tenant resolvers (`resolve_db_path` / `resolve_board` / `resolve_home_subtree`), STEP-0 propagation seeding, the output guard, and the build-pin ledger — is **UNRESOLVED**. I did not reconstruct them. The prior spike failed for this same reason; adding the repo as primary source was the stated fix, and the repo is not reachable from this session's credential.

**What I did instead:** the *other half* of both questions lives in Hermes, which is public and which I cloned in full. That half is now closed at source, and it is decisive enough to change the picture — including **falsifying the prompt's stated crux for Q-AX-2**.

---

## HEADLINE VERDICT

**(1) Q-AX-1 — tenant grain vs profile: `UNRESOLVED` on the AX side, but the Hermes side is closed and the inbound fix is genuinely one file *if* AX's tenant grain is the profile.** The Buzz adapter's cross-tenant binding bug is exactly ~8 unscoped `os.getenv` reads in one `__init__`, in a file that **already contains the correctly-scoped helper** and has **already had upstream apply that very fix to its credential read**. What I cannot confirm is whether AX keys tenancy on `source.profile`; that requires AX's tree.

**(2) Q-AX-2 — pin jump: the prompt's premise is FALSE, and the honest answer is CLEAN-ISH REBASE, not a fight — and explicitly *not* the hoped-for "simplification."** The prompt asserts the multiplex harness post-dates AX's pin. It does not: `agent/secret_scope.py` was introduced **2026-06-18**, and the pin `915f1bf` is **2026-07-13** — `git merge-base --is-ancestor f538470 915f1bf` returns **YES**. The harness is *already inside AX's pinned Hermes*. AX did not build tenant isolation "before" Hermes shipped the harness, so the "two independent implementations that might subsume each other" scenario does not arise from the timeline given.

**(3) Commitment call:** on the evidence reachable from here, Buzz is **CONDITIONAL** — viable if and only if AX's tenant grain is the profile dimension (Q-AX-1, unverified). Every *other* cost this spike could measure came in **at or below** the prompt's estimate, and the pin jump specifically is far cheaper than feared. The remaining risk is concentrated in one unread file set.

---

## Q-AX-1 — tenant grain vs profile

### AX side: `UNRESOLVED`
Where AX seeds STEP-0 / the tenant binding, and whether `AgentXTenantManager` derives tenant from `source.profile`, a session key, or a `HERMES_HOME` path — **not answerable without the AX tree.** Not guessed.

### Hermes side: `OBSERVED-SOURCE`, closed

**Profile *is* stamped on inbound events, and the routing engine does it automatically.**
`gateway/platforms/base.py:6996-7003` — `build_source`'s docstring:
> "When `gateway.profile_routes` is configured, the routing engine resolves the matching profile from guild/chat/thread and stamps it on `source.profile`. Downstream code (`_resolve_profile_home_for_source` in run.py) reads that field to enter `_profile_runtime_scope` for per-profile HERMES_HOME isolation."

Resolution happens at `base.py:7011-7016` via `runner._profile_name_for_source(...)`, and the result is written to `SessionSource.profile` at `base.py:7060`.

**Route matching dimensions** — `gateway/profile_routing.py:7-9`:
```
1. platform + chat_id + thread_id (exact thread)  — specificity 14
2. platform + chat_id (channel route)             — specificity 6
3. platform + guild_id (guild/server route)       — specificity 2
```

**This materially qualifies the inherited claim.** The prior spike's finding — "inbound Buzz events carry no community dimension (`scope_id`/`guild_id` never set)" — is **confirmed**: `plugins/platforms/buzz/adapter.py:1226-1232` calls `self.build_source(chat_id=…, chat_name=…, chat_type=…, user_id=…, user_name=…)` and passes **neither** `scope_id` nor `guild_id`, both of which are optional params defaulting to `None` (`base.py:6988-6989`). But the conclusion drawn from it was too strong: **rule 2 (`platform + chat_id`) needs no guild dimension.** Buzz *can* route per-profile today by enumerating channel UUIDs.

**The real defect is the failure mode, not the missing dimension.** When no route matches, `profile` stays `None` (`base.py:7009`), and `gateway/session.py:184` documents `None => the gateway's active/default profile`. So a Buzz channel that is not explicitly enumerated in `profile_routes` **fails OPEN onto the primary tenant.** For a per-channel-UUID routing table this is a live hazard: every new channel created in a secondary tenant's community silently lands on the primary tenant until someone edits the route table. A true community/relay dimension would fail *closed* by construction.

### The inbound fix — measured, one file

`plugins/platforms/buzz/adapter.py` already imports and defines the correct scoped reader at **lines 52-72**:
```python
from agent.secret_scope import UnscopedSecretError as _UnscopedSecretError
from agent.secret_scope import get_secret as _scoped_get_secret

def _get_scoped_secret(name, default=None):
    """Scope-aware credential read with the default-profile startup fallback. …"""
```
It has exactly **one** call site — `adapter.py:253`, `BUZZ_PRIVATE_KEY`. Everything that determines *which tenant the adapter binds to* is still read unscoped in `__init__` (`adapter.py:365-405`):

| Line | Unscoped read | Binds |
|---|---|---|
| 365 | `BUZZ_RELAY_URL` | **the community/relay** |
| 367 | `BUZZ_CLI_PATH` | binary |
| 371 | `BUZZ_CHANNELS` | **watched channels** |
| 376 | `BUZZ_HOME_CHANNEL` | **default post target** |
| 379 | `BUZZ_POLL_INTERVAL` | timing |
| 388 | `BUZZ_REQUIRE_MENTION` | dispatch policy |
| 400 | `BUZZ_TRANSPORT` | transport |
| 405 | `BUZZ_ALLOWED_USERS` | **allowlist** |

**The scope carries non-secret config, so the migration works.** `agent/secret_scope.py:272-293` — `build_profile_secret_scope(hermes_home)` returns `load_env_file(home / ".env")` plus external secret sources. It is the profile's **whole `.env`**, minus genuinely-global vars. `BUZZ_RELAY_URL` et al. set in a profile's `.env` resolve correctly through `_get_scoped_secret`. This is the point on which "is it really one file?" turns, and it holds.

**Upstream has already written the template — into this exact file.** `f4b268b78` (2026-08-02) "fix(secrets): Slack-pattern scoped credential reads — Feishu, WeCom, Photon, Buzz" adds the 24-line helper and changes `os.getenv("BUZZ_PRIVATE_KEY", "")` → `_get_scoped_secret("BUZZ_PRIVATE_KEY", "")`. Total Buzz diff: **26 insertions, 1 deletion.** The remaining work is the same one-line substitution ×8.

**Verdict:** conditional on AX's tenant grain being the profile, the inbound fix is **one plugin file, ~8 single-line changes, against a helper already present and an upstream-blessed pattern.** Bounded — and slightly cheaper than the prompt's "~6 config reads" estimate implied, because the hard part (the helper, the fallback semantics) is already merged. If AX's tenant grain turns out to be **finer** than profile, the additional wiring is: a community/relay dimension stamped on the inbound event (`scope_id` in the `build_source` call at `adapter.py:1226`, sourced from `self.relay_url` or the community id), a `scope_id`-aware route rule in `gateway/profile_routing.py`, and a community→tenant resolver on AX's side — i.e. it stops being one file and becomes three, one of which is upstream's.

---

## Q-AX-2 — pin-jump collision

### The prompt's stated crux is factually inverted — `OBSERVED-SOURCE`

> Prompt: "AX built its own tenant isolation *before* Hermes shipped `_profile_runtime_scope` / `agent/secret_scope.py` (both post-date AX's pin — the pin predates the multiplex harness)."

| Fact | Observed |
|---|---|
| `agent/secret_scope.py` introduced | `f538470c` — **2026-06-18** — "feat(gateway): multiplex phase 2 — fail-closed profile credential isolation (Workstream A)" |
| AX's pin `915f1bf` | **2026-07-13** — "fix(api): reserve cron fire work during drain" |
| `git merge-base --is-ancestor f538470 915f1bf` | **YES — the multiplex harness IS ALREADY IN the pin** |

At the pin, `git grep _profile_runtime_scope 915f1bf` hits `cron/scheduler.py`, `gateway/config.py`, `gateway/run.py` (×10), and three multiplex test files. `git ls-tree 915f1bf` lists `agent/secret_scope.py`, `tests/agent/test_secret_scope.py`, and six `tests/gateway/test_multiplex_*.py` files.

**The "simplification" case the prompt asked me to hunt for does not exist as framed** — not because I couldn't find it, but because its precondition is false. Hermes' native multiplex harness cannot *newly* subsume AX's patch across the pin jump, because AX is already pinned to a Hermes that has it. Whether AX's patch duplicates the harness *today* is a real question, but it is a question about AX's current tree, not about the jump — and it is `UNRESOLVED`.

### The pin, located precisely — `OBSERVED-SOURCE`
The repo is dual-versioned (semver ↔ calendar). `v0.18.2` = tag `v2026.7.7.2` = commit `9de9c25f6` (2026-07-07). The pin `915f1bf` is **not** that release commit — it is 448 commits *after* it, and before `v0.19.0`/`v2026.7.20`:
- `merge-base --is-ancestor 9de9c25f6 915f1bf` → YES
- `merge-base --is-ancestor 915f1bf v2026.7.20` → YES
- `git describe --tags --abbrev=0 915f1bf` → `v2026.7.7.2`

So "`915f1bf` / v0.18.2" is *approximately* right (nearest preceding release) but the pin is a mainline commit, not a tagged release.

### Churn, measured — the prompt overstates it

| Metric | Prompt | Observed (`915f1bf..v2026.7.30`) |
|---|---|---|
| Total commits | ~5,300 | **4,326** |
| Touching the 3 identity files | 301 | **248** |
| — `gateway/run.py` | | 216 |
| — `cron/scheduler.py` | | 40 |
| — `agent/secret_scope.py` | | **2** |

(The prompt's larger figures are closer to `915f1bf..HEAD`: 6,478 commits / 384 file-touches. Against the actual adoption target v2026.7.30, the surface is ~20% smaller than stated.)

### The seams AX would hook are stable across the jump — `OBSERVED-SOURCE`

This is the decisive test, and it is strongly favorable.

**`_profile_runtime_scope` is byte-identical.** Extracted the full 34-line function body from `915f1bf:gateway/run.py` and `v2026.7.30:gateway/run.py` and diffed: **no differences.** Only its line number moved (1441 → 1779) — i.e. the file grew *around* it.

**Almost nothing was removed from `gateway/run.py`.** Comparing the full set of `def` names across the 216-commit churn: 374 defs at the pin → 455 at v2026.7.30. **Exactly one def was removed** — `_dequeue_pending_with_transcription`, unrelated to identity or tenancy.

**All twelve profile/tenant seams survive by name:**
`_active_profile_name`, `_gateway_config_home`, `_home_target_env_var`, `_home_thread_env_var`, `_make_profile_message_handler`, `_prepare_profile_scoped_inbound_message_text`, `_profile_runtime_scope`, `_redact_gateway_user_facing_secrets`, `_resolve_profile_home_for_source`, `_send_home_channel_startup_notifications`, `_start_one_profile_adapters`, `_start_secondary_profile_adapters`.

**`agent/secret_scope.py`'s 2 commits are additive hardening, not refactors.** `0583692c2` (scope BWS-injected provider keys) and `c758ded6d` (fall back to `os.environ` on scope miss when multiplexing is off): +35/−5 lines. No signature changes to `get_secret`, `set_secret_scope`, `reset_secret_scope`, or `build_profile_secret_scope`. The isolation semantics under multiplexing are explicitly preserved by the `_MULTIPLEX_ACTIVE` gate (`secret_scope.py:150-161`) — the new fallthrough fires **only** when multiplexing is off.

### Verdict
**CLEAN-ISH REBASE, with the collision risk concentrated in code I could not read.** The upstream half of the collision surface is close to a best case: the seam AX would patch is unchanged, one unrelated function was removed across 216 commits, and the credential-isolation module changed only additively. The churn is real but overwhelmingly *additive* — `gateway/run.py` gained 81 defs.

**This is not a "simplification" and I will not report it as one.** The premise for that outcome is false. What I can say is the weaker, true thing: the jump is cheaper than the prompt feared, for a different reason than hoped.

**The residual risk, stated honestly:** this verdict holds *if* AX's patch hooks Hermes through these named seams. If AX instead patches by line-offset, copies vendored file bodies, or depends on internals of the 216 `gateway/run.py` commits I did not enumerate function-by-function, the conflict surface could be materially worse. **Unverifiable without AX's tree.**

---

## Cron cross-tenant write — `OBSERVED-SOURCE`, confirmed at both revisions

The prior spike's most severe finding is confirmed structurally, at HEAD and at v2026.7.30.

`cron/scheduler.py` (HEAD): the profile secret scope is installed at **4660** around `run_job`, and released in that try's `finally` at **4684** — while `_deliver_result` is not called until **4769**. Delivery therefore runs **outside** the profile scope. The same ordering holds at v2026.7.30 (`reset_secret_scope(_scope_token)` at 3958, `_deliver_result(...)` at 4011).

The scope is keyed on the profile home — `build_profile_secret_scope(_get_hermes_home())` (4660) — and the code comments at 4646-4652 state the scope exists precisely because "`get_secret()` fails closed outside a scope once profile isolation is in play."

**Adapter selection compounds it.** `_deliver_result` resolves its transport via `resolve_delivery_transport(platform, config, adapters)` (`gateway/delivery.py:92-105`), where `adapters: Optional[Dict[Platform, Any]]` is keyed by **`Platform`, not by profile** — `live_adapters.get(platform)`. There is one registered adapter per platform. A secondary tenant's cron job delivering to `platform="buzz"` gets the single registered Buzz adapter, with the profile scope already torn down. This is a cross-tenant **write**, and it is core surgery, not a plugin fix — it sits in `cron/scheduler.py` + `gateway/delivery.py`, both upstream-owned.

---

## Buzz-side spot-check — one refinement to the inherited erasure finding

Not re-litigating the prior spike, but one cheap check changed a load-bearing detail. — `OBSERVED-SOURCE`

Erasure is **not** uniformly blocked. **Community-grain hard deletion exists:** `crates/buzz-db/src/admin_moderation.rs:441` — `DELETE FROM events WHERE community_id = ANY($1)`, alongside `DELETE FROM communities` (386-392, 436-446). Retention machinery genuinely deletes rows (`migrations/0007_nip_rs_retention.sql:118`, `0019_mesh_status_retention.sql`).

What is absent is **per-principal** erasure: a search across `crates/` for `DELETE FROM events WHERE pubkey`, `delete_by_pubkey`, `erase_user`, `forget_user` returns **nothing**. NIP-09 handling is soft/tombstone (`crates/buzz-db/src/event.rs:793-839`, `admin_moderation.rs:67` "Soft-deletion time").

**Why this matters to the ruling:** if the tenancy model is one community per tenant, **"delete the tenant" is already achievable** — `DELETE FROM events WHERE community_id = ANY(...)` is exactly tenant offboarding. It is *per-user* erasure (GDPR Art. 17 against one member inside a surviving community) that requires the core co-build. That is a narrower and more deferrable obligation than "erasure is structurally blocked" implies.

---

## REVISED COST PICTURE

| Item | Prior status | This spike |
|---|---|---|
| Multi-community isolation (Buzz) | shipped, proven | unchanged — inherited |
| Owner attestation | works, light custody | unchanged — inherited |
| Erasure | "structurally blocked" | **PARTIALLY REVISED** — community-grain delete exists; only *per-user* erasure needs core co-build |
| No plugin system in Buzz | core Rust fork | unchanged — inherited |
| **Inbound cross-tenant bind** | "~6 config reads, one file" | **CONFIRMED, slightly cheaper** — 8 one-line changes; helper + upstream template already merged into that file (`f4b268b78`) |
| **Cron cross-tenant write** | "core surgery" | **CONFIRMED** — scope released before delivery; adapters keyed by Platform not profile; `cron/scheduler.py` + `gateway/delivery.py` |
| **Pin jump** | "~5,300 commits, 301 touches, possible fight" | **CHEAPER** — 4,326 / 248; seam byte-identical; 1 unrelated def removed; secret_scope additive |
| **Native-multiplex subsumption** | hoped-for upside | **PREMISE FALSE** — harness already in the pin; upside does not exist as framed |
| Process-per-tenant | zero-code interim | unchanged — and remains the correct interim, since it sidesteps both the inbound and cron defects entirely |

**Is "less work" TRUE / PARTIALLY TRUE / FALSE?**

**PARTIALLY TRUE — and more true than the prior two spikes concluded, on everything I could measure.** Three of the four cost drivers this spike could touch came in *below* estimate (inbound, pin jump, erasure scope). One is confirmed at full cost (cron). One hoped-for upside is gone (subsumption). But the load-bearing unknown — AX's tenant grain — is **untouched**, and it is the one that decides whether the inbound fix is one file or a three-file cross-repo change. I cannot convert that to a pass.

---

## THE RULING INPUTS

**Option BUZZ — honestly summed:**
- *Already done:* Buzz multi-community isolation, owner attestation, light key custody.
- *Bounded, upstream-shaped:* inbound per-profile binding — 8 one-line changes in `plugins/platforms/buzz/adapter.py`, template already merged. Plausibly upstreamable rather than forked, since upstream is actively migrating sibling plugins the same way.
- *Real, core:* cron cross-tenant write — `cron/scheduler.py` + `gateway/delivery.py`. Upstream-owned; either a carried patch or an upstream PR.
- *Real, Buzz-side core:* per-user erasure, if the compliance model requires it. Community-grain offboarding is already there.
- *Cheaper than feared:* the pin jump — additive churn, stable seam.
- *Fail-open hazard to design around:* unrouted Buzz channels default to the primary profile. Needs either exhaustive channel routing with an operational discipline, or a `scope_id` community dimension.
- *Available today at zero code:* process-per-tenant, which moots the inbound and cron defects at the cost of process overhead.
- **Unpriced:** whether AX's tenant grain is the profile. If yes, the above is the whole bill. If no, add a community dimension end-to-end.

**Option NATIVE — build the T3 collaboration surface on AX directly:**
- No pin jump, no upstream patch-carrying, no dependence on a 9-commit-old third-party plugin (`plugins/platforms/buzz/` was created 2026-07-25 and is still being actively fixed — `1b9377b1f` scoped identity lock, `f4b268b78` scoped credentials).
- No inherited fail-open routing semantics.
- Forgoes Buzz's already-shipped and *proven* multi-community isolation, attestation, and the whole relay/event substrate — the part of Option BUZZ that is genuinely finished.

**The honest tradeoff:** Option BUZZ's remaining engineering is small and well-shaped *where I could measure it*, and its largest feared cost (the pin jump) substantially deflated under inspection. Its risk is not volume of work — it is **dependency posture**: carrying patches against a fast-moving upstream (6,478 commits in ~4 weeks past the pin) whose Buzz plugin is three weeks old and still landing isolation fixes. Option NATIVE trades a large amount of already-finished substrate for control over that posture.

**I am not making the ruling.** The one input that would most change it is Q-AX-1, and it is unanswered.

---

## UNRESOLVED

Not converted to passes:

1. **AX's tenant grain (Q-AX-1 core).** Whether `AgentXTenantManager` derives tenant from `source.profile`, a session key, or a `HERMES_HOME` path. **AX tree inaccessible.**
2. **AX's current Hermes pin.** The prompt supplies `915f1bf`; the build-pin ledger was never read, so I cannot confirm it is *current*. `915f1bf` is a real Hermes commit and is consistent with the stated v0.18.2 neighborhood — that is all I verified.
3. **AX's patch surface against Hermes.** Which files AX modifies, and how it attaches — named seams vs. line offsets vs. vendored bodies. My Q-AX-2 verdict is conditional on the first.
4. **Whether AX's patch duplicates the harness today.** A live question (the harness has been in AX's pin for ~4 weeks), but not answerable, and not a *jump* effect.
5. **Function-level review of all 216 `gateway/run.py` commits.** I tested seam survival by name-set diff and by byte-diffing `_profile_runtime_scope`. I did not read all 216 diffs; a behavioral change inside a surviving function could still bite.
6. **The prior spikes' adapter execution.** I confirmed the mechanism at source but did not re-run the two-profile experiment.

---

## RAW EVIDENCE APPENDIX

### Mounting
```
add_repo(ysjnr/ax) → "you don't have access to ysjnr/ax"
list_repos → 12 repos, has_more:false, no `ax`
git clone https://github.com/nousresearch/hermes-agent   # full, 21,783 commits
```

### Q-AX-2 premise falsification
```
$ git log -1 --format='%H %ad' --date=iso 915f1bf
915f1bf1bc2f939356226250e0eade3c9b3c5960 2026-07-13 22:57:54 +0530
$ git log --diff-filter=A --format='%H %ad %s' --date=short -- agent/secret_scope.py
f538470cf4afddb9ae6cc476c4f71b671f5a8420 2026-06-18 feat(gateway): multiplex phase 2 — fail-closed profile credential isolation (Workstream A)
$ git merge-base --is-ancestor f538470 915f1bf && echo YES
YES
$ git grep -c "_profile_runtime_scope" 915f1bf
915f1bf:cron/scheduler.py:1
915f1bf:gateway/config.py:1
915f1bf:gateway/run.py:10
915f1bf:tests/gateway/test_multiplex_credential_isolation.py:10
…
```

### Churn
```
$ git rev-list --count 915f1bf..v2026.7.30                → 4326
$ git rev-list --count 915f1bf..v2026.7.30 -- agent/secret_scope.py gateway/run.py cron/scheduler.py → 248
$ git rev-list --count 915f1bf..HEAD                      → 6478
```

### Seam stability
```
# full body of _profile_runtime_scope extracted at both revs (34 lines each)
$ diff pin.txt new.txt   → IDENTICAL

$ comm -23 names_915f1bf.txt names_v2026.7.30.txt     # defs removed from gateway/run.py
_dequeue_pending_with_transcription

# 374 defs at pin → 455 at v2026.7.30; all 12 profile/tenant seams survive
```

### Pin location
```
$ git log --grep='release v0.18.2' → 9de9c25f6 2026-07-07 chore: release v0.18.2 (2026.7.7.2)
$ git merge-base --is-ancestor 9de9c25f6 915f1bf → YES
$ git merge-base --is-ancestor 915f1bf v2026.7.20 → YES
$ git rev-list --count 9de9c25f6..915f1bf → 448
$ git describe --tags --abbrev=0 915f1bf → v2026.7.7.2
```

### Buzz plugin age and upstream migration
```
$ git log --format='%h %ad %s' --date=short -- plugins/platforms/buzz/
f4b268b78 2026-08-02 fix(secrets): Slack-pattern scoped credential reads — Feishu, WeCom, Photon, Buzz
07e931fcb 2026-07-28 feat(buzz): WebSocket inbound transport — NIP-42 auth, live DM discovery, poll fallback
21c7b806a 2026-07-28 feat(buzz): dependency-free Nostr signing module (NIP-42 auth, BIP-340)
1b9377b1f 2026-07-28 fix(buzz): scoped identity lock, negative name caching, sidebar registration
7e1e3b92f 2026-07-25 fix(plugin): classify Buzz DMs by p-tag so un-mentioned DMs dispatch
ffb38f0c0 2026-07-25 feat(plugin): add require_mention setting to Buzz adapter
65f52d491 2026-07-25 fix(plugin): strip leading @mention from Buzz channel messages
01f8852cc 2026-07-25 fix(plugin): bridge Buzz config.yaml -> env + fix reaction flags
66fc2e2a9 2026-07-25 feat(plugin): add Buzz (Block/Nostr) platform adapter

# At v2026.7.30 the adapter had ZERO _get_scoped_secret call sites; at HEAD it has one.
```

### Unscoped binding reads (HEAD, `plugins/platforms/buzz/adapter.py`)
```
365: self.relay_url = (os.getenv("BUZZ_RELAY_URL") or extra.get("relay_url", "")).strip()
371: raw_channels = os.getenv("BUZZ_CHANNELS") or extra.get("channels", [])
376: self.home_channel = (os.getenv("BUZZ_HOME_CHANNEL") or …).strip()
405: raw_allowed = os.getenv("BUZZ_ALLOWED_USERS") or extra.get("allowed_users", [])
253: key = _get_scoped_secret("BUZZ_PRIVATE_KEY", "").strip()   # ← the only scoped read
```

### First-writer-wins env seeding (`adapter.py:1276-1318`, `_apply_yaml_config`)
```python
for src, env in _str_keys.items():        # relay_url, cli_path, home_channel, transport
    val = extra.get(src)
    if val and not os.getenv(env):        # ← first writer wins, process-global
        os.environ[env] = str(val)
```

### Cron ordering (HEAD)
```
4660:  _scope_token = set_secret_scope(build_profile_secret_scope(_get_hermes_home()))
4684:      reset_secret_scope(_scope_token)          # finally of the run_job try
4769:      delivery_error = _deliver_result(job, deliver_content, adapters=adapters, loop=loop)
```
`gateway/delivery.py:92-105` — `adapters: Optional[Dict[Platform, Any]]`; `native = live_adapters.get(platform)`.

### Buzz erasure
```
crates/buzz-db/src/admin_moderation.rs:441  DELETE FROM events WHERE community_id = ANY($1)
crates/buzz-db/src/admin_moderation.rs:67   /// Soft-deletion time, when the message has since been deleted.
# grep for DELETE FROM events WHERE pubkey | delete_by_pubkey | erase_user | forget_user → no matches
```
