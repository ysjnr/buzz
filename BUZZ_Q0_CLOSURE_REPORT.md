# BUZZ Q0 CLOSURE REPORT

## AX/Hermes pin: `915f1bf` (v0.18.2, 2026-07-13) | Integration present at pin: **NO** | Integration introduced in: **v2026.7.30** (commit `66fc2e2`, 2026-07-25)

**Hermes source examined:** `NousResearch/hermes-agent` @ `743dc94ab90adb0529bb233b8498c6fd6ee0e020`
(`main`, v0.20.0, 2026-08-04), obtained by public clone.

---

## ⚠️ SOURCE-AVAILABILITY CORRECTION — read before the verdict

**The spike premise "You have what that spike lacked: the Hermes source tree" was
false in this environment.** No AX or Hermes tree was mounted; the only repo present
was `ysjnr/buzz`. The sanctioned attach path failed:

```
add_repo(NousResearch/hermes-agent) →
  "cross-tier adds are not supported in v1: requested nousresearch/hermes-agent
   but session already has repos from owner(s) [ysjnr]. Start a new session with
   the requested repo as the initial source..."
```

I obtained Hermes by **public clone** of the MIT-licensed repo instead, so all
Hermes findings below are genuine `OBSERVED-SOURCE` / `OBSERVED-RUNNING`.

**What is still missing: the AX distribution source.** Every AX-side claim in this
report's framing (STEP-0 seeding, `AgentXTenantManager`, tenant resolvers, the
output guard, the identity-core patch) comes from the **prompt's description, not
from source I read**. Consequences are flagged inline as `UNRESOLVED (AX-side)`.

One strong corroboration that the prompt's AX description is accurate: the stated
pin resolves exactly. `915f1bf1bc2f939356226250e0eade3c9b3c5960` is a real commit
("fix(api): reserve cron fire work during drain", 2026-07-13) and `pyproject.toml`
at that commit reads `version = "0.18.2"` — both halves of the prompt's
`915f1bf`/v0.18.2 claim check out.

**Docs re-attempt:** `hermes-agent.nousresearch.com/docs/integrations/buzz` returned
**HTTP 403 again**. Verdicts below come from source only.

---

## HEADLINE VERDICT

**The integration is SINGLE-OPERATOR — but the disappointment is narrower and more
fixable than the parent spike assumed, because it sits on a harness that is already
genuinely multi-instance.**

Hermes ships a real profile-multiplexing gateway: one process serves N profiles,
each with its own `HERMES_HOME`, its own `.env`, a **fail-closed** context-local
secret scope (`agent/secret_scope.py`), per-profile authz stores, and refusal to let
two profiles consume the same credential. Inbound turns are wrapped in
`_profile_runtime_scope` before `_handle_message` runs. That is, structurally, the
seam AX needs — Hermes independently built its own STEP-0 equivalent.

**The Buzz adapter is not wired into it.** Only `BUZZ_PRIVATE_KEY` is read through
the scope. The adapter's entire *community binding* — relay URL, watched channels,
home channel, transport, allowlist — is read from raw process-global `os.environ`,
and its YAML→env bridge **writes into `os.environ` first-writer-wins**. I proved by
execution that with two profiles configured for two different Buzz communities,
profile B silently binds **tenant A's relay, channels, home channel and allowlist**
while still holding its own key. Worse, the inbound `MessageEvent` carries **no
community/relay dimension at all** (`scope_id`/`guild_id` are never set), so nothing
in the event itself could be used to re-derive the right tenant downstream.

**What AX must build.** The core fix is small and lives in **one file**:
`plugins/platforms/buzz/adapter.py` (1,528 lines, 9 commits of history). Route ~6
config reads in `__init__` and 2 in `_standalone_send` through the existing scope
helper instead of `os.getenv`, and stop the YAML bridge from mutating global env.
That is a Hermes-side patch — it adds to the fork, but it is *bounded, additive, and
in a plugin*, not in the identity core AX already patches. The **cron path is the
expensive part**: fixing it means reordering `reset_secret_scope` versus
`_deliver_result` in `cron/scheduler.py` and giving delivery a per-profile adapter
map instead of `runner.adapters` — that is genuine core surgery in files AX already
patches. The zero-fork alternative is one Hermes process per tenant, which costs
processes, not code.

**Effect on the parent spike's cost picture: LEAVES IT ROUGHLY UNCHANGED, with the
mix shifted.** The parent spike concluded "co-building, not extending." Q0 does not
overturn that — the integration is single-operator as inferred, and cron is worse
than inferred (it cross-delivers identity *and* destination). But it is meaningfully
**less bad than "rebuild its tenancy integration"**: the multi-tenant machinery
already exists and works; Buzz is simply the one platform plugin that hasn't been
migrated onto it. This is a *wiring* gap in young code (10 days old at HEAD), not an
architectural absence. "Less work" is **PARTIALLY TRUE**.

---

## FINDINGS

### Q0.1 — Where it runs; one-per-operator or one-per-tenant? 🔴 THE HINGE

**Verdict: `OBSERVED-SOURCE` + `OBSERVED-RUNNING` — SINGLE-OPERATOR adapter running
on a tenant-capable harness.**

**The integration is a bundled plugin, structured exactly like the reference
platforms.** `plugins/platforms/buzz/` sits alongside `telegram`, `discord`, `slack`,
`matrix` and 18 others. Its manifest declares the same single-account shape as
Telegram's single bot token:

`plugins/platforms/buzz/plugin.yaml:14-22` — `requires_env`: **one**
`BUZZ_RELAY_URL`, **one** `BUZZ_PRIVATE_KEY` ("the only Buzz secret").
Compare `plugins/platforms/telegram/plugin.yaml:13-18` — **one**
`TELEGRAM_BOT_TOKEN`. Same construction: one credential, one identity, one process.

**But the harness underneath is multi-instance.** Hermes' multiplexing gateway
(`agent/secret_scope.py:1-21`) serves many profiles from one process and explicitly
refuses to union their credentials into `os.environ` "(that would leak profile A's
keys to profile B's turns, and to every subprocess spawned with
`env=dict(os.environ)`)". Each profile gets its own adapter instance, constructed and
connected under its own scope — `gateway/run.py:13149-13200`
(`_start_one_profile_adapters`), and same-credential collisions are refused outright
(`gateway/run.py:13215-13228`). Buzz is **not** in `PORT_BINDING_PLATFORM_VALUES`
(`gateway/config.py:384-394`), so secondary profiles *are* permitted to run it —
unlike `api_server`/`webhook`.

**The decisive question — what tenant context does an inbound Buzz message carry?**
`plugins/platforms/buzz/adapter.py:1227-1241` builds the event with only:

```python
source = self.build_source(
    chat_id=chat_id, chat_name=..., chat_type=chat_type,
    user_id=user_id, user_name=user_name,
)
```

`scope_id` and `guild_id` — the generic "which server/workspace" discriminators
`build_source` offers (`gateway/platforms/base.py`, `gateway/session.py:175-176`) —
are **never set by the Buzz adapter**. So the inbound event carries **no community,
relay, or tenant dimension of its own**. The only tenant-ish field is
`source.profile`, and that is stamped by the *harness* based on **which adapter
instance received the message** (`gateway/run.py:13485-13486`), not by anything in
the Buzz event.

That is the definition of single-operator: identity is a property of the process's
configuration, not of the traffic.

**And the per-instance binding is contaminated.** `BuzzAdapter.__init__`
(`adapter.py:365-412`) reads its whole community binding from **raw
`os.getenv`**, with env winning over the profile's own config:

```python
self.relay_url   = (os.getenv("BUZZ_RELAY_URL") or extra.get("relay_url", "")).strip()   # :365
raw_channels     = os.getenv("BUZZ_CHANNELS") or extra.get("channels", [])               # :371
self.home_channel= (os.getenv("BUZZ_HOME_CHANNEL") or ...).strip()                        # :376
raw_allowed      = os.getenv("BUZZ_ALLOWED_USERS") or extra.get("allowed_users", [])      # :405
```

Only the secret is scoped (`adapter.py:253`, via `_get_scoped_secret` at `:56-73`).
And `_apply_yaml_config` (`adapter.py:1289-1318`) bridges each profile's config.yaml
into **process-global `os.environ`**, every write guarded by `not os.getenv(env)` —
first-writer-wins, permanently, process-wide. Hermes itself names this hazard:
`gateway/authz_mixin.py:53-56` — *"the YAML→env bridges in the Discord/Telegram
adapters' `_apply_yaml_config` are first-writer-wins ... falling through would leak
profile A's allowlist into profile B (issue #72348)."*

**Proven by execution** (`scratchpad/proof_first_writer_wins.py`, running the real
`_apply_yaml_config` and the real `BuzzAdapter.__init__` from disk with only the
import graph stubbed):

```
after profile A config load:
  BUZZ_RELAY_URL = https://tenant-a.communities.buzz.xyz
after profile B config load (B wants tenant-b relay):
  BUZZ_RELAY_URL = https://tenant-a.communities.buzz.xyz
RESULT: profile B silently bound to TENANT A's relay -> CROSS-TENANT BINDING

BuzzAdapter constructed under profile B's config.extra:
  self.relay_url    = https://tenant-a.communities.buzz.xyz
  self.channels     = ['aaaaaaaa-...-a']
  self.home_channel = aaaaaaaa-...-a
  -> env won over profile B's own extra: True
```

Two tenants, two keys, **one community**: N agent identities all posting into tenant
A's workspace. It fails silently — no error, no warning.

---

### Q0.2 — Does AX's tenant propagation survive the integration path?

**Verdict: `OBSERVED-SOURCE` — the inbound path DOES enter where a STEP-0 equivalent
runs, so AX's binding would flow; but it binds a profile that is already pointing at
the wrong community. Needs explicit wiring, and one authz read bypasses the fix
upstream already shipped.**

**The entry point is correctly scoped.** Buzz dispatches through the standard base
contract (`adapter.py:1243` → `self.handle_message(event)` → the handler installed by
the harness). For a multiplexed profile that handler is
`_make_profile_message_handler` (`gateway/run.py:13469-13494`), which stamps
`source.profile` and wraps the **entire** call in `_profile_runtime_scope`:

```python
if getattr(event, "source", None) is not None and not event.source.profile:
    event.source.profile = profile_name
if profile_home is not None:
    with _profile_runtime_scope(profile_home):
        return await self._handle_message(event)
```

`_profile_runtime_scope` (`gateway/run.py:1819-1850`) installs **both** seams —
`set_hermes_home_override` (config, skills, memory, SOUL, sessions) and
`set_secret_scope` — as contextvars that "propagate into the agent worker thread via
`copy_context()`". This is Hermes' own STEP-0, and it is **generic over all platform
adapters**, plugins included. Nothing about the Buzz path bypasses it.

So: an AX tenant binding keyed to `source.profile` would propagate correctly through
this path. `UNRESOLVED (AX-side)` — I could not verify AX's STEP-0 actually keys on
`source.profile`, having no AX source.

**But the profile it scopes to is bound to the wrong community** (Q0.1). Correct
tenant scoping of a session that is talking to the wrong relay is not isolation.

**Collision with the AX patch — one concrete instance.** Upstream fixed the
cross-profile allowlist leak by making gate reads scope-authoritative:
`_platform_gate_env` (`gateway/authz_mixin.py:46-72`) returns `default` rather than
falling through to `os.environ` when a scope is installed under multiplex. Buzz
registers its gates with the core (`adapter.py:1514-1515`,
`allowed_users_env`/`allow_all_env`), so **that** path is protected. However
`BuzzAdapter.__init__:405-412` *also* keeps its own copy in `self._allowed_pubkeys`,
read via raw `os.getenv` — re-opening exactly the hole #72348 closed, for whichever
checks consult the adapter's local set.

More broadly: 301 commits touch `agent/secret_scope.py`, `gateway/run.py` and
`cron/scheduler.py` between AX's pin and HEAD — the precise files an identity-core
patch and enforcer would sit in.

---

### Q0.3 — Cron delivery and tenant scoping 🔴

**Verdict: `OBSERVED-SOURCE` — scheduling and execution ARE tenant-scoped; DELIVERY
IS NOT. Cron delivery into Buzz is single-operator, and leaks both identity and
destination.**

**Scheduling/execution: correctly isolated.** Under multiplex the ticker iterates
every served profile, scoping each tick to that profile's home and cron store
(`cron/scheduler_provider.py:273-279, 299-332`), and job execution installs the
profile secret scope explicitly (`cron/scheduler.py:3934-3949`):

```python
# Run the job under the profile's secret scope. get_secret() fails
# closed outside a scope once profile isolation is in play ...
_scope_token = set_secret_scope(build_profile_secret_scope(_get_hermes_home()))
```

**Delivery: outside the scope.** That token is released in `run_job`'s `finally`
(`cron/scheduler.py:3972`) — and `_deliver_result` is called *after*, at
`cron/scheduler.py:~4023`, in the block the source itself introduces with
*"Everything from here through delivery runs with the agent still live."* So at
delivery time **no secret scope is installed**. `_resolve_private_key`
(`adapter.py:253`) then hits `_get_scoped_secret` → `UnscopedSecretError` →
`os.getenv("BUZZ_PRIVATE_KEY")` (`adapter.py:69-73`) — the **process-global**, i.e.
default profile's, key.

**And the live-adapter path is primary-only.** `gateway/run.py:26609`:

```python
cron_start_kwargs: Dict[str, Any] = {"adapters": runner.adapters, "loop": ...}
```

`runner.adapters` is the **active/primary** profile's adapter map. `profile_homes` is
passed separately (`:26618-26626`) so secondary stores get *ticked*, but delivery
still resolves against the primary's adapters (`cron/scheduler.py:1461`,
`resolve_delivery_transport(platform, config, adapters)`).

**Net:** a secondary tenant's `deliver=buzz` cron job runs its agent correctly under
its own config, memory and model keys — then posts the result **into the primary
tenant's community, signed with the primary tenant's Nostr key**, targeting the
first-writer-wins `BUZZ_HOME_CHANNEL` (`adapter.py:1384`). Whichever route it takes —
primary live adapter, or `_standalone_send` reading global
`BUZZ_RELAY_URL`/`BUZZ_HOME_CHANNEL` (`adapter.py:1375, 1384`) — the destination and
the identity both belong to the wrong tenant.

This is the sharpest finding in the report: it is a silent cross-tenant **write**, on
the unattended path AX hard-governs.

---

### Q0.4 — The per-tenant-harness cost

**Verdict: `OBSERVED-SOURCE` — N instances are structurally viable today; the fix is
mostly one plugin file (AX-side-ish), except cron, which is core.**

**What already works in AX's favour:**

- **No mutable module-level state in the adapter.** Every module-level name is an
  immutable constant (`adapter.py:90-112` — ints, floats, strings, one `Path`). All
  connection state lives on `self` (`adapter.py:417-430`). N instances do not collide
  in the adapter itself.
- **Buzz may run on secondary profiles** — absent from `PORT_BINDING_PLATFORM_VALUES`
  (`gateway/config.py:384-394`).
- **Per-profile adapter instances, authz stores, and credential-collision refusal**
  already exist (`gateway/run.py:13149-13228`, `:13135-13145`).
- **Per-channel routing exists** — `gateway/profile_routing.py` matches
  platform + `chat_id`, so Buzz channel-UUID→profile routing is expressible today.
  (Community-level routing is not, since Buzz never sets `scope_id`.)

**What AX must build:**

| Fix | Where | Weight |
|---|---|---|
| Route the ~6 config reads in `__init__` (`adapter.py:365-412`) + 2 in `_standalone_send` (`:1375,1384`) through the scope instead of `os.getenv` | `plugins/platforms/buzz/adapter.py` | Small — 1 file, self-contained |
| Stop `_apply_yaml_config` mutating global `os.environ` (`adapter.py:1289-1318`); seed `PlatformConfig.extra` per profile instead | same file | Small |
| Drop the adapter-local `_allowed_pubkeys` copy in favour of the scope-authoritative gate (`authz_mixin.py:46-72`) | same file | Small |
| **Cron: install a profile scope around delivery** (reorder vs `cron/scheduler.py:3972`) | `cron/scheduler.py` | **Core surgery** |
| **Cron: per-profile adapter map for delivery** instead of `runner.adapters` (`gateway/run.py:26609`) | `gateway/run.py` | **Core surgery** |

The first three are a bounded patch to a **plugin** — additive, in a 1,528-line file
with 9 commits of history, low merge-conflict surface. The last two are in
`cron/scheduler.py` and `gateway/run.py`, files with 301 commits of churn since AX's
pin, and they are exactly the kind of change that deepens a fork.

**Zero-fork alternative:** run **one Hermes process per tenant**, each with its own
env and its own Buzz identity. Nothing in the adapter prevents this — it is the
configuration the plugin was designed for. Cost is process/memory/ops per tenant, not
code. For a T3-employee-scale deployment this may well be the right first move, with
the plugin patch as the consolidation step later.

---

### Q0.5 — Output guard on the integration path

**Verdict: `OBSERVED-SOURCE` — the Hermes→Buzz outbound path IS guardable. Content
reaches Buzz as author-controlled bytes through two narrow chokepoints. Two
Hermes-generated additions land *after* the agent, and are worth knowing about.**

**The adapter does not compose.** `BuzzAdapter.send` (`adapter.py:602-635`) passes
content **verbatim** on stdin — never argv:

```python
args = ["messages", "send", "--channel", str(chat_id), "--content", "-"]
...
code, out, err = await self._run_cli(args, input_text=content)
```

`_standalone_send` (`adapter.py:1388-1396`) is identical in shape. Two chokepoints,
both narrow, both in one file — a good place for AX to scrub. The private key travels
via subprocess env, never argv (`adapter.py:288-295`), so it stays out of process
listings and logs.

**Additions after the agent's bytes** (Hermes-generated boilerplate, not model
output, but not scrubbed by an agent-output guard either):

1. **Cron wrapper** — `cron/scheduler.py:1505-1520` prepends
   `Cronjob Response: <name> / (job_id: …)` and appends a *"To stop or manage this
   job…"* trailer, unless `cron.wrap_response: false`.
2. **Runtime footer** — `gateway/runtime_footer.py:1-19` can append model id, context
   %, latency and **`cwd`** to the final message of a turn. **Off by default**; if
   enabled, `cwd` puts a host path into a Buzz channel.
3. **Chunking** — long messages are split by `truncate_message`
   (`tools/send_message_tool.py`), so a guard operating on whole messages should run
   before chunking.

`gateway/response_filters.py:1-6` is a delivery *gate* (silence markers), not a
transformer — it does not alter bytes.

`UNRESOLVED (AX-side)`: whether AX's output guard actually wraps these two chokepoints
depends on AX source I do not have.

---

## VERSION GAP

**The integration post-dates AX's pin. Adopting it is also an upstream-merge
decision.**

| Fact | Evidence |
|---|---|
| AX pin `915f1bf` = 2026-07-13, `version = "0.18.2"` | `git log -1 915f1bf`; `git show 915f1bf:pyproject.toml` |
| Buzz plugin **absent** at the pin | `git ls-tree -r 915f1bf -- plugins/platforms/buzz` → empty |
| Introduced `66fc2e2`, 2026-07-25 ("feat(plugin): add Buzz (Block/Nostr) platform adapter") | `git log --reverse -- plugins/platforms/buzz` |
| First release containing it: **v2026.7.30** | `git tag --contains 66fc2e2` → `v2026.7.30`, `v2026.8.3` |
| **5,322** commits between pin and HEAD | `git rev-list --count 915f1bf..HEAD` |
| **301** of them touch `agent/secret_scope.py`, `gateway/run.py`, `cron/scheduler.py` | `git rev-list --count 915f1bf..HEAD -- <those files>` |
| Integration is **9 commits old**, all 2026-07-25 | `git log --oneline -- plugins/platforms/buzz` |

Two implications:

1. **AX cannot adopt this without moving its pin** — minimum v2026.7.30, ~5.3k
   commits forward, across the exact identity/secret-scope/cron files AX patches.
2. **The integration is 10 days old at HEAD.** The tenancy gaps documented above are
   consistent with young code that hasn't been migrated onto the multiplex seam yet
   (as Slack, WhatsApp, Discord and Telegram progressively were — see the `#59739`,
   `#64674`, `#72348`, `#75349` references scattered through those adapters). AX
   should expect this to move upstream, and could plausibly **contribute the fix**
   rather than carry it — the smaller three items are exactly the shape of the
   migrations already merged for other platforms.

---

## NET COST IMPACT

Combined with the parent spike (erasure = co-build, no plugin system on the Buzz side
= core fork, isolation = shipped, attestation = works):

**Q0 leaves the commitment roughly as costly as the parent spike concluded, but
shifts the mix from "architectural absence" toward "unfinished wiring."**

- **More costly than inferred, in one place:** cron. The parent spike inferred
  single-operator; the reality on the cron path is a *silent cross-tenant write* —
  wrong identity **and** wrong destination — on precisely the unattended surface AX
  hard-governs. Fixing it is core surgery in high-churn files.
- **Less costly than feared, in the main place:** AX does **not** have to build
  tenant isolation from nothing. Hermes already has the fail-closed secret scope, the
  per-profile adapter lifecycle, per-profile authz, credential-collision refusal, and
  a routing engine. Buzz is one un-migrated plugin on top of working machinery. The
  primary fix is one file.
- **Unchanged:** the parent spike's finding that the *Buzz side* is single-identity by
  construction stands — `plugin.yaml` requires exactly one relay and one key, and the
  inbound event carries no community dimension. Nothing on the Hermes side hands AX a
  free multi-tenant seam **through Buzz**; the seam is in the harness around it.

**Is "less work" TRUE, PARTIALLY TRUE, or FALSE with this variable closed?**

**PARTIALLY TRUE.** "Adopt a strong substrate and maintain a bounded fork" is a fair
description of the *inbound/live* path — the fork there is one plugin file, and
plausibly upstreamable. It is **not** a fair description once cron delivery and the
parent spike's erasure finding are included; those remain co-build. The honest
framing: **bounded fork for the messaging surface, co-build for cron delivery and
erasure.** And a real interim option the parent spike didn't have: **process-per-tenant
today, zero code, consolidate later** — which converts the whole Q0 problem into an
ops cost while the upstream migration lands.

---

## UNRESOLVED

Not proven — not converted to passes:

1. **All AX-side claims.** No AX source was available. STEP-0's actual binding key,
   whether `AgentXTenantManager` keys on `source.profile`, whether AX's output guard
   wraps `BuzzAdapter.send`/`_standalone_send`, and whether AX's identity-core patch
   textually conflicts with the 301 churned commits — **all UNRESOLVED**. *Source
   needed:* the AX distribution tree and its build-pin ledger.
2. **AX's current pin.** I verified `915f1bf`/v0.18.2 is a real, self-consistent
   Hermes commit, but I could not confirm it is AX's *current* pin — that claim comes
   from the prompt. *Source needed:* AX's build-pin ledger.
3. **Runtime behaviour of the multiplexed Buzz path.** I proved the config-binding
   collapse by executing the real functions, but never ran a live multiplexed gateway
   against two real Buzz relays. The cron cross-delivery conclusion is traced through
   source (scope reset ordering + `runner.adapters`), **not executed**. *To close:* a
   two-profile gateway against two relays with a `deliver=buzz` cron job on the
   secondary.
4. **Whether the primary's live Buzz adapter or `_standalone_send` wins** for a given
   secondary-profile cron delivery. Both routes land on the wrong tenant, so the
   verdict holds either way, but I did not trace `resolve_delivery_transport`'s
   selection to the end.
5. **Modes 1 and 2** (Desktop-spawned ACP runtime; relay bridge over stdio) were not
   analysed — the spike scoped Q0 to mode 3, the gateway plugin. The parent spike's
   finding that Buzz's ACP surface is one env default still stands on the Buzz side
   (`crates/buzz-acp/src/config.rs:723`, verified in this repo).
6. **Official docs** — still HTTP 403. No `DOC-CLAIM` was used in any verdict. Public
   search snippets (`require_mention: true`, `allow_all_users: false`, transport
   `auto|websocket|poll`, `poll_interval` 4s) matched source exactly, but source was
   the authority throughout.

---

## RAW EVIDENCE APPENDIX

### Obtaining source

```
$ add_repo(NousResearch/hermes-agent)
  → cross-tier adds are not supported in v1 ... [ysjnr]
$ git clone --quiet https://github.com/NousResearch/hermes-agent.git hermes   # EXIT=0
$ git log -1 --format='%H %ci'
743dc94ab90adb0529bb233b8498c6fd6ee0e020 2026-08-04 11:26:39 +0530
$ grep -m1 '^version' pyproject.toml
version = "0.20.0"
```

### Version gap

```
$ git log -1 --format='%H %ad %s' --date=short 915f1bf
915f1bf1bc2f939356226250e0eade3c9b3c5960 2026-07-13 fix(api): reserve cron fire work during drain
$ git show 915f1bf:pyproject.toml | grep -m1 '^version'
version = "0.18.2"
$ git ls-tree -r --name-only 915f1bf -- plugins/platforms/buzz
(empty)
$ git log --reverse --format='%H %ad %s' --date=short -- plugins/platforms/buzz | head -1
66fc2e2a92f53a826d836c167fc13bc68c5030c1 2026-07-25 feat(plugin): add Buzz (Block/Nostr) platform adapter
$ git tag --contains 66fc2e2
v2026.7.30
v2026.8.3
$ git rev-list --count 915f1bf..HEAD
5322
$ git rev-list --count 915f1bf..HEAD -- agent/secret_scope.py gateway/run.py cron/scheduler.py
301
$ git log --oneline -- plugins/platforms/buzz | wc -l
9
```

### Integration layout

```
plugins/platforms/buzz/
  __init__.py        3 lines
  adapter.py      1528 lines
  nostr_auth.py    230 lines
  plugin.yaml       59 lines

siblings: a2a discord dingtalk email feishu google_chat homeassistant irc line
          matrix mattermost ntfy photon raft simplex slack sms teams telegram
          wecom whatsapp
```

### Q0.1 — single-account manifest shape

`plugins/platforms/buzz/plugin.yaml:14-22`
```yaml
requires_env:
  - name: BUZZ_RELAY_URL
    description: "Base URL of the Buzz community relay (e.g. https://mycommunity.communities.buzz.xyz)"
  - name: BUZZ_PRIVATE_KEY
    description: "Nostr private key for the agent's Buzz identity (nsec or hex) — the only Buzz secret"
```

`plugins/platforms/telegram/plugin.yaml:13-18`
```yaml
requires_env:
  - name: TELEGRAM_BOT_TOKEN
    description: "Telegram bot token from @BotFather"
```

### Q0.1 — inbound carries no community dimension

`plugins/platforms/buzz/adapter.py:1227-1241`
```python
source = self.build_source(
    chat_id=chat_id,
    chat_name=self._channel_names.get(chat_id, chat_id),
    chat_type=chat_type,
    user_id=user_id,
    user_name=user_name,
)                       # scope_id / guild_id never passed
event = MessageEvent(text=text, message_type=MessageType.TEXT, source=source, ...)
await self.handle_message(event)
```

### Q0.1 — raw-env binding + first-writer-wins bridge

`adapter.py:365-412` (excerpt)
```python
self.relay_url    = (os.getenv("BUZZ_RELAY_URL") or extra.get("relay_url", "")).strip()
raw_channels      = os.getenv("BUZZ_CHANNELS") or extra.get("channels", [])
self.home_channel = (os.getenv("BUZZ_HOME_CHANNEL") or str(extra.get("home_channel","") or "")).strip()
raw_allowed       = os.getenv("BUZZ_ALLOWED_USERS") or extra.get("allowed_users", [])
```

`adapter.py:1298-1301`
```python
for src, env in _str_keys.items():
    val = extra.get(src)
    if val and not os.getenv(env):       # ← first-writer-wins into GLOBAL env
        os.environ[env] = str(val)
```

`gateway/authz_mixin.py:53-56`
```
Under multiplex the process env may hold ANOTHER profile's first-writer-bridged
value (the YAML→env bridges in the Discord/Telegram adapters' _apply_yaml_config
are first-writer-wins), so falling through would leak profile A's allowlist into
profile B (issue #72348).
```

### Q0.1 — executed proof

`scratchpad/proof_first_writer_wins.py` — loads the real `adapter.py` from disk
(import graph stubbed only), calls the real `_apply_yaml_config` twice, then the real
`BuzzAdapter.__init__`:

```
after profile A config load:
  BUZZ_RELAY_URL    = https://tenant-a.communities.buzz.xyz
  BUZZ_CHANNELS     = aaaaaaaa-0000-0000-0000-00000000000a
  BUZZ_HOME_CHANNEL = aaaaaaaa-0000-0000-0000-00000000000a
  BUZZ_ALLOWED_USERS= npub1tenant_a_user

after profile B config load (B wants tenant-b relay):
  BUZZ_RELAY_URL    = https://tenant-a.communities.buzz.xyz
  BUZZ_CHANNELS     = aaaaaaaa-0000-0000-0000-00000000000a
  BUZZ_HOME_CHANNEL = aaaaaaaa-0000-0000-0000-00000000000a
  BUZZ_ALLOWED_USERS= npub1tenant_a_user

RESULT: profile B silently bound to TENANT A's relay -> CROSS-TENANT BINDING

BuzzAdapter constructed under profile B's config.extra:
  self.relay_url    = https://tenant-a.communities.buzz.xyz
  -> env won over profile B's own extra: True
```

### Q0.2 — inbound enters a scoped path

`gateway/run.py:13485-13494`
```python
if getattr(event, "source", None) is not None and not event.source.profile:
    event.source.profile = profile_name
if profile_home is not None:
    with _profile_runtime_scope(profile_home):
        return await self._handle_message(event)
```

`gateway/run.py:1819-1834` (`_profile_runtime_scope` docstring)
```
1. set_hermes_home_override — config, skills, memory, SOUL, sessions
2. set_secret_scope — the profile's .env secrets as the authoritative
   credential source ... never the process-global os.environ
```

`agent/secret_scope.py:1-19`
```
Each profile has its own .env ... we cannot union them into the process-global
os.environ (that would leak profile A's keys to profile B's turns...).
get_secret ... RAISES rather than silently falling back to os.environ.
```

### Q0.3 — cron scope released before delivery

`cron/scheduler.py:3934-3949`
```python
# Run the job under the profile's secret scope. get_secret() fails
# closed outside a scope once profile isolation is in play ...
_scope_token = set_secret_scope(build_profile_secret_scope(_get_hermes_home()))
```
`cron/scheduler.py:3970-3972`
```python
        finally:
            reset_secret_scope(_scope_token)          # ← released HERE
```
`cron/scheduler.py:3975-3979` (next block) → *"Everything from here through delivery
runs with the agent still live"* → `_deliver_result(...)` at `~:4023`.

`adapter.py:69-73` (unscoped fallback)
```python
try:
    val = _scoped_get_secret(name, default)
except _UnscopedSecretError:
    val = os.getenv(name)          # ← process-global = default profile's key
```

`gateway/run.py:26609`
```python
cron_start_kwargs: Dict[str, Any] = {"adapters": runner.adapters, "loop": ...}
```

`adapter.py:1375,1384` (standalone fallback)
```python
relay  = (os.getenv("BUZZ_RELAY_URL") or extra.get("relay_url", "")).strip()
target = (chat_id or "").strip() or (os.getenv("BUZZ_HOME_CHANNEL") or ...).strip()
```

### Q0.4 — no mutable module state; Buzz not port-binding

`adapter.py:90-112` — all module-level names are constants
(`_CHAT_KIND=9`, `_FETCH_LIMIT=50`, `_SEEN_CAP=500`, `_DM_DISCOVERY_EVERY=5`,
`_DEFAULT_POLL_INTERVAL=4.0`, `_MIN_POLL_INTERVAL=1.0`, `_CLI_TIMEOUT=30.0`,
`_WS_*`, `_DEFAULT_CREDENTIALS_DIR`). No module-level dict/set/list.

`gateway/config.py:384-394`
```python
PORT_BINDING_PLATFORM_VALUES = frozenset({
    "webhook","api_server","msgraph_webhook","feishu","wecom_callback",
    "bluebubbles","sms","whatsapp_cloud","line",
})          # "buzz" absent → permitted on secondary profiles
```

### Q0.5 — verbatim outbound

`adapter.py:611-615`
```python
args = ["messages", "send", "--channel", str(chat_id), "--content", "-"]
if reply_target: args += ["--reply-to", str(reply_target)]
code, out, err = await self._run_cli(args, input_text=content)
```

`adapter.py:288-295` (key never in argv)
```python
env = os.environ.copy()
env["BUZZ_RELAY_URL"] = relay_url
env["BUZZ_PRIVATE_KEY"] = private_key
```

`cron/scheduler.py:1505-1520` (post-agent composition)
```python
delivery_content = (
    f"Cronjob Response: {task_name}\n(job_id: {job_id})\n-------------\n\n"
    f"{content}\n\nTo stop or manage this job, send me a new message ..."
)
```

`gateway/runtime_footer.py:1-19` — appends `model, context_pct, latency, cwd` to the
final message of a turn; **off by default**.

### Buzz-side corroboration (this repo, `block/buzz` @ `631b05c`)

```
crates/buzz-acp/src/config.rs:723
  "hermes" | "hermes-agent" | "hermes-acp" => &[("HERMES_ACP_SKIP_CONFIGURED_MCP", "1")],
desktop/public/harness-logos/CREDITS.md:13
  NousResearch/hermes-agent | 6ad632b | MIT © 2025 Nous Research
```
The parent spike's "entire Hermes-specific surface in Buzz is a single env default"
holds — the Buzz repo knows Hermes only as an ACP preset harness (mode 1), with no
gateway-plugin surface of its own.
