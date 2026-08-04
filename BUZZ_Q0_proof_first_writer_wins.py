"""Prove: plugins/platforms/buzz/adapter.py::_apply_yaml_config is
first-writer-wins into the PROCESS-GLOBAL os.environ.

We load the REAL adapter.py module from disk. Only its import graph is
stubbed (agent.secret_scope, gateway.platforms.base, gateway.config) so the
file can be imported without Hermes' full runtime deps. The function under
test, _apply_yaml_config, is the genuine one and touches only `os`.

Scenario: two tenants, each with their own profile config.yaml block naming a
DIFFERENT Buzz relay/community. Simulates the multiplexer loading profile A's
config, then profile B's (gateway/run.py:13155 load_gateway_config() per
profile, which dispatches apply_yaml_config_fn at gateway/config.py:1668).
"""
import importlib.util
import os
import sys
import types

HERMES = "/tmp/claude-0/-home-user-buzz/e4e36f1e-f4d1-53d2-a718-38a291c4755a/scratchpad/hermes"

# ---- stub the import graph (NOT the function under test) ----------------
m = types.ModuleType("agent.secret_scope")


class UnscopedSecretError(RuntimeError):
    pass


m.UnscopedSecretError = UnscopedSecretError
m.get_secret = lambda name, default=None: os.getenv(name, default)
agent_pkg = types.ModuleType("agent")
agent_pkg.secret_scope = m
sys.modules["agent"] = agent_pkg
sys.modules["agent.secret_scope"] = m

base = types.ModuleType("gateway.platforms.base")


class BasePlatformAdapter:
    def __init__(self, *a, **k):
        pass


base.BasePlatformAdapter = BasePlatformAdapter
base.SendResult = object
base.MessageEvent = object
base.MessageType = types.SimpleNamespace(TEXT="text")

gcfg = types.ModuleType("gateway.config")
gcfg.Platform = lambda v: v

gw = types.ModuleType("gateway")
gwp = types.ModuleType("gateway.platforms")
sys.modules["gateway"] = gw
sys.modules["gateway.platforms"] = gwp
sys.modules["gateway.platforms.base"] = base
sys.modules["gateway.config"] = gcfg

# ---- load the REAL adapter module --------------------------------------
spec = importlib.util.spec_from_file_location(
    "buzz_adapter_under_test", f"{HERMES}/plugins/platforms/buzz/adapter.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

# ---- the two tenants ---------------------------------------------------
tenant_a = {
    "extra": {
        "relay_url": "https://tenant-a.communities.buzz.xyz",
        "channels": ["aaaaaaaa-0000-0000-0000-00000000000a"],
        "home_channel": "aaaaaaaa-0000-0000-0000-00000000000a",
        "allowed_users": ["npub1tenant_a_user"],
    }
}
tenant_b = {
    "extra": {
        "relay_url": "https://tenant-b.communities.buzz.xyz",
        "channels": ["bbbbbbbb-0000-0000-0000-00000000000b"],
        "home_channel": "bbbbbbbb-0000-0000-0000-00000000000b",
        "allowed_users": ["npub1tenant_b_user"],
    }
}

for k in list(os.environ):
    if k.startswith("BUZZ_"):
        del os.environ[k]

print("start: BUZZ_* env =", {k: v for k, v in os.environ.items() if k.startswith("BUZZ_")})

adapter._apply_yaml_config({}, tenant_a)
print("\nafter profile A config load:")
for k in ("BUZZ_RELAY_URL", "BUZZ_CHANNELS", "BUZZ_HOME_CHANNEL", "BUZZ_ALLOWED_USERS"):
    print(f"  {k} = {os.environ.get(k)}")

adapter._apply_yaml_config({}, tenant_b)
print("\nafter profile B config load (B wants tenant-b relay):")
for k in ("BUZZ_RELAY_URL", "BUZZ_CHANNELS", "BUZZ_HOME_CHANNEL", "BUZZ_ALLOWED_USERS"):
    print(f"  {k} = {os.environ.get(k)}")

leaked = os.environ.get("BUZZ_RELAY_URL") == tenant_a["extra"]["relay_url"]
print(
    "\nRESULT:",
    "profile B silently bound to TENANT A's relay -> CROSS-TENANT BINDING"
    if leaked
    else "profile B correctly bound to its own relay",
)

# ---- and what BuzzAdapter.__init__ would read for profile B ------------
cfg = types.SimpleNamespace(extra=tenant_b["extra"])
a = adapter.BuzzAdapter(cfg)
print("\nBuzzAdapter constructed under profile B's config.extra:")
print("  self.relay_url   =", a.relay_url)
print("  self.channels    =", a.channels)
print("  self.home_channel=", a.home_channel)
print(
    "  -> env won over profile B's own extra:",
    a.relay_url == tenant_a["extra"]["relay_url"],
)
