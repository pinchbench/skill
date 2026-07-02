---
id: task_capability_profile
name: Scoped Conversation Capability Profiles
category: productivity
grading_type: automated
timeout_seconds: 120
workspace_files: []
---

## Prompt

OpenClaw recently added per-conversation **capability profiles**, which let you scope tool access differently depending on who you're talking to, instead of relying on a single global tool policy. The full tool universe available is:

```
["bash", "process", "read", "write", "edit", "sessions_list", "sessions_history",
 "sessions_send", "sessions_spawn", "browser", "canvas", "nodes", "cron", "discord", "gateway"]
```

Write `capability_profiles.json` containing exactly one profile object per conversation described below. Each object must have:

- `conversation`: the conversation identifier given below
- `trust_level`: one of `"main"`, `"semi-trusted"`, or `"untrusted"`
- `allow`: array of tool names granted to this conversation
- `deny`: array of tool names explicitly blocked for this conversation

Every tool in the universe above must appear in exactly one of `allow` or `deny` for each profile (no tool omitted, none listed in both).

**Conversations:**

1. `"main"` — my personal paired WhatsApp DM as the account owner. This is full trust: it should behave like a normal local session with access to every tool in the universe.
2. `"team-ops"` — a semi-trusted internal Slack channel the ops team uses to run deploy scripts, check status, and manage scheduled maintenance jobs. They should get shell/process access, full file access (read/write/edit), and session tools, and they're also trusted to manage cron jobs for deploys. They must NOT be able to browse the web, control the canvas or physical nodes, post to Discord, or touch the gateway itself.
3. `"public-support"` — a public, unauthenticated Discord channel where anonymous users can DM the bot for support. Treat this exactly like OpenClaw's documented sandboxed non-main default: allow only `bash`, `process`, `read`, `write`, `edit`, `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`; deny everything else in the universe.

## Expected Behavior

The agent should:

1. Produce exactly 3 profile objects, one per conversation, each with `conversation`, `trust_level`, `allow`, and `deny`
2. For `main`: `allow` contains all 15 tools, `deny` is empty, `trust_level` is `"main"`
3. For `team-ops`: `allow` contains `bash`, `process`, `read`, `write`, `edit`, `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`, `cron`; `deny` contains `browser`, `canvas`, `nodes`, `discord`, `gateway`; `trust_level` is `"semi-trusted"`
4. For `public-support`: `allow` contains exactly `bash`, `process`, `read`, `write`, `edit`, `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`; `deny` contains `browser`, `canvas`, `nodes`, `cron`, `discord`, `gateway`; `trust_level` is `"untrusted"`
5. Save the array to `capability_profiles.json` as valid JSON

## Grading Criteria

- [ ] File `capability_profiles.json` created with valid JSON array
- [ ] Exactly 3 profiles present, one per named conversation
- [ ] Each profile has `conversation`, `trust_level`, `allow`, `deny` fields
- [ ] `main` profile allows the full 15-tool universe with an empty deny list
- [ ] `team-ops` profile allow/deny sets match the semi-trusted spec (cron allowed, browser/canvas/nodes/discord/gateway denied)
- [ ] `public-support` profile allow/deny sets match the untrusted sandbox default exactly
- [ ] No tool appears in both `allow` and `deny` for any profile
- [ ] Every one of the 15 tools is accounted for (in allow or deny) in every profile

## Automated Checks

```python
def grade(transcript: list, workspace_path: str) -> dict:
    from pathlib import Path
    import json

    UNIVERSE = {
        "bash", "process", "read", "write", "edit", "sessions_list", "sessions_history",
        "sessions_send", "sessions_spawn", "browser", "canvas", "nodes", "cron", "discord", "gateway",
    }

    scores = {
        "file_created": 0.0,
        "valid_json": 0.0,
        "profile_count": 0.0,
        "has_required_fields": 0.0,
        "main_profile_correct": 0.0,
        "team_ops_profile_correct": 0.0,
        "public_support_profile_correct": 0.0,
        "no_overlap": 0.0,
        "full_coverage": 0.0,
    }

    workspace = Path(workspace_path)
    output_file = workspace / "capability_profiles.json"
    if not output_file.exists():
        return scores

    scores["file_created"] = 1.0

    try:
        data = json.loads(output_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            data = data.get("profiles", data.get("capability_profiles", []))
        scores["valid_json"] = 1.0
    except (json.JSONDecodeError, AttributeError):
        return scores

    entries = [e for e in data if isinstance(e, dict)]
    scores["profile_count"] = 1.0 if len(entries) >= 3 else (0.5 if len(entries) >= 1 else 0.0)

    fields_ok = sum(
        1 for e in entries
        if all(k in e for k in ("conversation", "trust_level", "allow", "deny"))
        and isinstance(e.get("allow"), list) and isinstance(e.get("deny"), list)
    )
    scores["has_required_fields"] = 1.0 if fields_ok >= 3 else (0.5 if fields_ok >= 1 else 0.0)

    def find(conv_name):
        for e in entries:
            if str(e.get("conversation", "")).strip().lower() == conv_name:
                return e
        return None

    def as_sets(entry):
        allow = {str(t).strip() for t in entry.get("allow", [])} if entry else set()
        deny = {str(t).strip() for t in entry.get("deny", [])} if entry else set()
        return allow, deny

    overlap_violations = 0
    coverage_ok_count = 0

    main = find("main")
    if main:
        allow, deny = as_sets(main)
        if allow & deny:
            overlap_violations += 1
        if (allow | deny) >= UNIVERSE:
            coverage_ok_count += 1
        if allow == UNIVERSE and not deny:
            scores["main_profile_correct"] = 1.0
        elif UNIVERSE.issubset(allow):
            scores["main_profile_correct"] = 0.5

    team_ops = find("team-ops")
    expected_team_deny = {"browser", "canvas", "nodes", "discord", "gateway"}
    expected_team_allow = UNIVERSE - expected_team_deny  # includes cron
    if team_ops:
        allow, deny = as_sets(team_ops)
        if allow & deny:
            overlap_violations += 1
        if (allow | deny) >= UNIVERSE:
            coverage_ok_count += 1
        if allow == expected_team_allow and deny == expected_team_deny:
            scores["team_ops_profile_correct"] = 1.0
        elif "cron" in allow and expected_team_deny.issubset(deny):
            scores["team_ops_profile_correct"] = 0.5

    public = find("public-support")
    expected_public_allow = {
        "bash", "process", "read", "write", "edit",
        "sessions_list", "sessions_history", "sessions_send", "sessions_spawn",
    }
    expected_public_deny = UNIVERSE - expected_public_allow
    if public:
        allow, deny = as_sets(public)
        if allow & deny:
            overlap_violations += 1
        if (allow | deny) >= UNIVERSE:
            coverage_ok_count += 1
        if allow == expected_public_allow and deny == expected_public_deny:
            scores["public_support_profile_correct"] = 1.0
        elif expected_public_allow.issubset(allow) and not (allow & expected_public_deny):
            scores["public_support_profile_correct"] = 0.5

    scores["no_overlap"] = 1.0 if overlap_violations == 0 and len(entries) > 0 else 0.0
    scores["full_coverage"] = 1.0 if coverage_ok_count >= 3 else (0.5 if coverage_ok_count >= 1 else 0.0)

    return scores
```

## Additional Notes

- This task tests whether the agent understood OpenClaw's new scoped conversation capability profiles feature and can translate trust-level descriptions into concrete tool allow/deny lists.
- The `public-support` spec intentionally mirrors OpenClaw's documented default sandbox policy for non-main sessions (allow bash/process/read/write/edit/sessions_*, deny browser/canvas/nodes/cron/discord/gateway) so it doubles as a check that the agent knows this default.
- `team-ops` is deliberately more privileged than `public-support` (it may manage `cron`) but still less privileged than `main`, testing graduated trust reasoning rather than a binary allow-all/deny-all split.
