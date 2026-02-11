Agent Send
openclaw agent runs a single agent turn without needing an inbound chat message. By default it goes through the Gateway; add --local to force the embedded runtime on the current machine.
​
Behavior
Required: --message <text>
Session selection:
--to <dest> derives the session key (group/channel targets preserve isolation; direct chats collapse to main), or
--session-id <id> reuses an existing session by id, or
--agent <id> targets a configured agent directly (uses that agent’s main session key)
Runs the same embedded agent runtime as normal inbound replies.
Thinking/verbose flags persist into the session store.
Output:
default: prints reply text (plus MEDIA:<url> lines)
--json: prints structured payload + metadata
Optional delivery back to a channel with --deliver + --channel (target formats match openclaw message --target).
Use --reply-channel/--reply-to/--reply-account to override delivery without changing the session.
If the Gateway is unreachable, the CLI falls back to the embedded local run.

openclaw agents add --help

🦞 OpenClaw 2026.2.9 (33c75cb) — Less middlemen, more messages.

Usage: openclaw agents add [options] [name]

Add a new isolated agent

Options:
--agent-dir <dir> Agent state directory for this agent
--bind <channel[:accountId]> Route channel binding (repeatable) (default: [])
-h, --help display help for command
--json Output JSON summary (default: false)
--model <id> Model id for this agent
--non-interactive Disable prompts; requires --workspace (default: false)
--workspace <dir> Workspace directory for the new agent

agents add [name]
Add a new isolated agent. Runs the guided wizard unless flags (or --non-interactive) are passed; --workspace is required in non-interactive mode.
Options:
--workspace <dir>
--model <id>
--agent-dir <dir>
--bind <channel[:accountId]> (repeatable)
--non-interactive
--json
Binding specs use channel[:accountId]. When accountId is omitted for WhatsApp, the default account id is used.
​
agents delete <id>
Delete an agent and prune its workspace + state.
Options:
--force
--json

Add another agent
Use openclaw agents add <name> to create a separate agent with its own workspace, sessions, and auth profiles. Running without --workspace launches the wizard.
What it sets:
agents.list[].name
agents.list[].workspace
agents.list[].agentDir
Notes:
Default workspaces follow ~/.openclaw/workspace-<agentId>.
Add bindings to route inbound messages (the wizard can do this).
Non-interactive flags: --model, --agent-dir, --bind, --non-interactive.
​
Agent Workspace
The workspace is the agent’s home. It is the only working directory used for file tools and for workspace context. Keep it private and treat it as memory.
This is separate from ~/.openclaw/, which stores config, credentials, and sessions.
Important: the workspace is the default cwd, not a hard sandbox. Tools resolve relative paths against the workspace, but absolute paths can still reach elsewhere on the host unless sandboxing is enabled. If you need isolation, use agents.defaults.sandbox (and/or per‑agent sandbox config). When sandboxing is enabled and workspaceAccess is not "rw", tools operate inside a sandbox workspace under ~/.openclaw/sandboxes, not your host workspace.
​
Where state lives
On the gateway host:
Store file: ~/.openclaw/agents/<agentId>/sessions/sessions.json (per agent).
Transcripts: ~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl (Telegram topic sessions use .../<SessionId>-topic-<threadId>.jsonl).
The store is a map sessionKey -> { sessionId, updatedAt, ... }. Deleting entries is safe; they are recreated on demand.
Group entries may include displayName, channel, subject, room, and space to label sessions in UIs.
Session entries include origin metadata (label + routing hints) so UIs can explain where a session came from.
OpenClaw does not read legacy Pi/Tau session folders.

Multi-Agent Routing
Goal: multiple isolated agents (separate workspace + agentDir + sessions), plus multiple channel accounts (e.g. two WhatsApps) in one running Gateway. Inbound is routed to an agent via bindings.
​
What is “one agent”?
An agent is a fully scoped brain with its own:
Workspace (files, AGENTS.md/SOUL.md/USER.md, local notes, persona rules).
State directory (agentDir) for auth profiles, model registry, and per-agent config.
Session store (chat history + routing state) under ~/.openclaw/agents/<agentId>/sessions.
Auth profiles are per-agent. Each agent reads from its own:
~/.openclaw/agents/<agentId>/agent/auth-profiles.json
Main agent credentials are not shared automatically. Never reuse agentDir across agents (it causes auth/session collisions). If you want to share creds, copy auth-profiles.json into the other agent’s agentDir.
Skills are per-agent via each workspace’s skills/ folder, with shared skills available from ~/.openclaw/skills. See Skills: per-agent vs shared.
The Gateway can host one agent (default) or many agents side-by-side.
Workspace note: each agent’s workspace is the default cwd, not a hard sandbox. Relative paths resolve inside the workspace, but absolute paths can reach other host locations unless sandboxing is enabled. See Sandboxing.
​
Paths (quick map)
Config: ~/.openclaw/openclaw.json (or OPENCLAW_CONFIG_PATH)
State dir: ~/.openclaw (or OPENCLAW_STATE_DIR)
Workspace: ~/.openclaw/workspace (or ~/.openclaw/workspace-<agentId>)
Agent dir: ~/.openclaw/agents/<agentId>/agent (or agents.list[].agentDir)
Sessions: ~/.openclaw/agents/<agentId>/sessions
​
Single-agent mode (default)
If you do nothing, OpenClaw runs a single agent:
agentId defaults to main.
Sessions are keyed as agent:main:<mainKey>.
Workspace defaults to ~/.openclaw/workspace (or ~/.openclaw/workspace-<profile> when OPENCLAW_PROFILE is set).
State defaults to ~/.openclaw/agents/main/agent.
​
Agent helper
Use the agent wizard to add a new isolated agent:
openclaw agents add work
Then add bindings (or let the wizard do it) to route inbound messages.
Verify with:
openclaw agents list --bindings
​
Multiple agents = multiple people, multiple personalities
With multiple agents, each agentId becomes a fully isolated persona:
Different phone numbers/accounts (per channel accountId).
Different personalities (per-agent workspace files like AGENTS.md and SOUL.md).
Separate auth + sessions (no cross-talk unless explicitly enabled).
This lets multiple people share one Gateway server while keeping their AI “brains” and data isolated.
​
