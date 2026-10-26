# Agent-operated installation and readiness

When asked to install/configure this Skill and MCP, complete setup before entering production. Do not hand the user a developer test checklist. Reuse existing approvals for routine local installation. Do not run image generation during installation. Do not create or open sample review HTML, call prepare_review.py, launch a browser or run browser/full regression suites as an installation step. Check dependencies, installed files and the read-only live doctor only. Installation-only requests end at readiness; continue into planning only when the user also requested production. Editable review remains part of actual production, not installation.

## One short setup route

1. Locate the host's existing usable Python 3.10+ and the actual Skill destination using host-provided information. Use that interpreter's absolute path for all commands. Do not assume bare `python` is the managed interpreter. Do not install Node, Playwright or a browser for ordinary setup: they are developer test dependencies only.
2. Inspect already connected Starcanvas tools first. A missing guessed `mcp.json` does not prove no connection exists. Locate an existing trusted local connection source through the host's actual settings or the user's official Starcanvas export. The setup script accepts standard `mcpServers` JSON, a single stdio connection JSON, or an explicitly selected TOML `mcp_servers` entry. It never scans unrelated credential stores. JSON is preferred on Python 3.10 without tomli.
3. Run the bundled setup with the actual interpreter and paths. `--apply --fix-deps` reuses Pillow when available, otherwise installs it in a dedicated user-local virtual environment. `--install-to` is optional when the Skill is already installed. Never guess a host-specific configuration path.

```text
ABSOLUTE_PYTHON SKILL_DIR/scripts/setup_detail_flow.py --connection-source EXISTING_LOCAL_CONFIG --install-to VERIFIED_SKILL_DIRECTORY --apply --fix-deps
```

The default private runtime directory is `~/.detail-flow`, outside the distributable Skill. `--state-dir` may select another private user-local location; never choose a shared repository or packaged output folder. The script stores connection information locally without printing tokens. Do not attach its connection JSON or backups to chats, archives or commits.

4. Read only the non-secret `~/.detail-flow/ready.json`. Require `status=ready`, a successful live workspace read and required tools (including `canvas_prepare_run`). It records the exact Python, installed Skill path, executor, local connection path, `skill_revision` and `skill_content_sha256`. Setup probes the actual installed executor. For a released package, run `ABSOLUTE_PYTHON INSTALLED_SKILL/scripts/skill_release.py verify --receipt READY_JSON` and require a matching sealed fingerprint. Use the recorded paths for production; do not revert to bare `python`. After upgrading, a newly downloaded ZIP or an old ready receipt is insufficient: verify the installed files against that release. Do not reseal an installation to conceal differences.
5. For an installation-only request, report readiness and stop without an HTML demo. If production was also requested, proceed with the user's product materials and normal editable review → design approval → whole-set generation flow. Do not ask the user to perform installation unit tests, manually install libraries or repeatedly confirm completed setup. Do not require a new conversation by default. If the Agent can read this Skill and run its scripts, continue in this conversation. Only an actually observed discovery limitation and a documented host requirement justify suggesting a reload/new conversation; do not claim the native tool catalog refreshed.

## Direct executor is a valid MCP connection

Installer backups are stored outside the Skill scanning parent, under its sibling `skill-backups` directory. Never leave backup folders containing `SKILL.md` inside `skills`, where the host may load a duplicate old skill. Installation records the exact `backup_path`. Existing old backups are preserved; inspect and move individually only within the user's authorized cleanup scope.

The unified executor starts the official Starcanvas local stdio bridge itself. A host that can run the scripts does **not** need a duplicate native connector just for image execution. `ready.json` reports the verified direct stdio route. An optional native connector being untested is not a missing installation requirement and must not be turned into a user-facing blocker.

To check/reuse a cached connection next time:

```text
ABSOLUTE_PYTHON SKILL_DIR/scripts/setup_detail_flow.py --apply --fix-deps
```

Then execute using the receipt's Python and connection:

```text
RECEIPT_PYTHON RECEIPT_EXECUTOR --connection RECEIPT_CONNECTION prepare PACKAGE.json NEW_RUN_DIR
```

The actual `run --execute` remains subject to stage approval; setup readiness is not spending authority. Native MCP tools alone also do not give an external Python process connection details: obtain an actual local connection source for the executor.

## When a human action is unavoidable

| Condition | Agent action / minimal user action |
|---|---|
| Starcanvas absent | Explain that the separate desktop app must be installed; do not bundle or download an unverified binary. |
| App closed / MCP unavailable | Setup/executor first probes the connection. On Windows it checks the verified official process path, starts the desktop app once if absent and waits about 30 seconds for readiness. If still blocked, diagnose the actual returned error; do not guess a trust requirement. |
| No existing valid local pairing/export | Ask only for a local official exported MCP configuration file. Do not ask the user to paste tokens into chat. |
| An actual permission denial blocks a required operation | Identify the returned error and verify the applicable host documentation or visible UI before suggesting an action. Do not invent a button or location. A working direct executor does not need an optional native connector to be enabled. |
| No local process/file access | Explain that the direct executor is unavailable in this host; preserve planning work. Do not pretend a cloud host can access desktop paths. |
| Disabled existing connection | Preserve its disabled state; do not silently enable it. |
| Missing Pillow / package access unavailable | Use the existing managed runtime or private venv. Report only the unresolved dependency step, without exposing pip credentials. |

Do not build per-Agent custom installers. If native registration is needed, use the host's documented schema/import UI and preserve other entries; this generic setup deliberately does not write guessed client configuration files. Reuse an existing connector rather than adding another.

## What is packaged and what is not

Included: Skill instructions, executor, stdio transport, setup script and developer regressions. Not included: the Starcanvas app executable, private pairing tokens, the user's host configuration, product data or permission to generate. Native client permissions are separate from the direct executor; never add speculative permission steps to successful installation.

Installation uses a read-only live doctor check, not the full developer test suite. Real generation, output quality and speed must be tested separately under production authority. Dependency repair affects only the private venv; installing/updating the Skill backs up existing files and preserves unrelated files.

## Automatic desktop startup

The bundled executor CLI (doctor, prepare, run, resume) uses `starcanvas_startup.py`; setup uses the same doctor entry. It first probes the guide and workspace read without generating. If unavailable on Windows, it accepts only the existing absolute official SynMewInfiniteCanvas.exe path with bridge args exactly --mcp-server. After closing its own failed bridge, it checks desktop process identity and uses an OS startup lock to avoid concurrent duplicate launches. An absent app is started once with no bridge arguments; an already running app is never restarted or terminated. Read-only probes wait for readiness with a roughly 30-second budget; process inspection/bridge cleanup can add a few seconds. Unknown process state, invalid paths or missing pairing lead to an explicit blocker, not guessed launches or repeated restarts.

The script starts the real desktop application, which may show its window; it does not configure OS boot autostart. Windows automatic launch is implemented; other platforms may reuse a live connection but cold startup is not implemented. Do not claim cross-platform automatic startup.

A startup check never retries a submitted generation. If a running command later loses connection, keep its durable state. Within the existing authorization, use resume for that run after readiness recovery, never run a new package as a substitute. Resume queries recorded task IDs and may submit only original never-submitted pages within the authorized batch. Ambiguous task identities remain blocked. Local status/collect do not open the app.

## Installation completion message

If the live check succeeds, say installation and direct MCP execution are ready and request product materials or continue the already requested planning. Do not append a stock list of manual trust, restart, new-session or configuration steps. Mention one only when an observed blocker requires it and its exact resolution is verified. Do not label another host's Skill folder obsolete without comparing actual content/version; do not recommend cleanup merely because multiple hosts each have a copy.

## No invented MCP enable switch

For this Starcanvas integration, starting the desktop app is the normal prerequisite. Do not tell the user to find an enable-MCP/control switch. A generic server message mentioning one is diagnostic text, not proof that such UI exists. When the app is running, inspect the configured endpoint, local pairing/configuration and actual bridge response. State only confirmed causes; retry bounded read-only readiness checks before asking for a user action. Never request a speculative switch, trust button or restart.
