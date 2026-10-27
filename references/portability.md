# Local validation and another Agent

The planning/copy/review layer is ordinary Skill content. The configured image executor is Starcanvas, whose model profile, tool mapping and transport schema are isolated in `starcanvas-execution.md`. The bundled executor implements Starcanvas. Prefer that route for pages, supplemental assets and repairs. Other host tools remain available; if used, identify the actual backend and do not fabricate Starcanvas execution records.

## Capabilities

- Read this entire folder and follow its relative references. `agents/openai.yaml` is host metadata, not a portable MCP installation mechanism.
- Inspect product/reference images and generated originals. Text-only file access cannot establish visual acceptance.
- Run Python with Pillow for layout, editor construction and ordered previews. Supply an available language-appropriate font with `--font`; Windows discovery and a Linux Noto path are conveniences, not bundled fonts.
- Open standalone HTML in a modern JavaScript browser for copy/layout review. Source images are embedded for viewing; exported original asset paths remain local and must be remapped on a different machine.
- For production, complete the bundled setup in `installation.md`: reuse or import the official local connection, verify the live guide/catalog and local file access. The executor may connect directly over stdio without duplicate host registration. Credentials and spending permission are never included in a Skill package.

No frontend app, new server or Codex SDK is required for offline rendering. Node is needed only for the bundled JavaScript regression checks; Playwright and a browser are optional test dependencies for `test_review_editor.cjs`. They are not required to open the generated HTML manually. Do not install packages or download browsers merely to inspect a plan.

## Offline handoff check (developer validation, not normal installation)

Do not execute this section when simply installing for an end user. In particular, do not generate or pop up an example review page. Browser tests require an explicit developer-test task.

From the skill root, in an environment with those dependencies, use new output paths:

```text
python -X utf8 -B -m unittest discover -s scripts -p "test_*.py" -v
node scripts/test_review_model.cjs
node scripts/test_editor_handoff.cjs NEW_TEST_FOLDER
python scripts/render_layout_preview.py examples/layout-preview.json NEW_LAYOUT_FOLDER --font LOCAL_FONT
python scripts/prepare_review.py examples/layout-preview.json NEW_REVIEW_FOLDER --font LOCAL_FONT
```

Open the HTML; edit one page, switch to another page's annotation mode, add/remove a module, export and re-import. The inspector must not retain a different page's selection. Adopt a valid draft separately and render it again. An empty page remains an incomplete draft; restoring content does not authorize generation.

For transport, build a synthetic manifest with real local fixture paths, fake model settings and explicitly labelled test evidence; compile from a different working directory and inspect the package. Compilation and synthetic evidence do not authorize submitting it. Use the current shapes in examples/reviewed-workflow.json; older copy-led/master fixtures are compatibility evidence, not new-job defaults.

Report separately: structure, local scripts, real browser interactions, target-Agent behavior, and actual generated-image quality. A pass in one category does not establish the others.

## Release order

Fix and regress locally, then test this same revision in the intended Agent, then publish a reviewed source-only package. If that Agent requires a repository to install, use a test branch or prerelease after local checks. Include scripts/references/examples/tests; exclude project outputs, backups, credentials, cache files and synthetic approval records. Record the exact tested revision. Do not claim cross-OS or cross-Agent support until it has been exercised.

## Capability-based handoff

Use the same acceptance criteria on every Agent: editable review artifact delivered, actual user confirmation, correct tool inputs, inspected originals and complete output files. The workflow does not branch by model or client name.

| Needed capability | When unavailable |
|---|---|
| Execute the bundled scripts and save files | Report the missing capability; do not replace the editor with a static picture or claim script completion. |
| Present/open editable HTML | Prefer a host-supported preview/open action. Otherwise provide a downloadable standalone HTML or a local path accessible on the user's own machine. If none is possible, pause for an explicit user-selected alternative. |
| Read actual product/output images | Mark visual review unverified; do not claim quality acceptance from filenames or dimensions. |
| Call Starcanvas MCP | Inspect existing tools and actual host settings, then use the bundled local setup. If no pairing source exists, request the official local export only. Never guess config paths or switch backends. |

The Skill cannot force an unsupported client to open a window. Its invariant is delivery of an accessible editable artifact and the approval gate, not a particular popup mechanism. The transport validation catches missing artifacts when used; it is not an enforcement layer over arbitrary Agents that ignore the workflow.

Use the normal editable-review -> design approval -> all final pages -> delivery flow for a production trial. Offline developer checks above are not a substitute for that trial, and are not a questionnaire the end user must execute.

## Compatibility limits

Compatibility is capability-based, not guaranteed by an Agent brand. A local host needs Python 3.10+, Pillow, permission to start the official stdio bridge, and the same accessible files as Starcanvas. Native MCP registration is optional for the direct executor. Planning and visual review also require actual image inspection and user-accessible HTML. The host may use its own interpreter; keep the absolute interpreter from ready.json. Invoke Python with -X utf8 for portable Chinese console output; do not install into unrelated global environments.

Automatic app startup currently targets Windows only. Generic Python/stdio code and POSIX locks do not establish a tested macOS/Linux desktop integration. HTTP-only connectors, browser-only chatbots and cloud sandboxes without local process/file access cannot use this execution route as-is. No per-Agent language-model speed or planning-quality guarantee is made; scripts reduce tool-orchestration work, not all model latency.
