# Unified executor

## Current readiness

The executor integrates Starcanvas 1.8.8 `canvas_prepare_run`. New tasks use `detail-flow-direct-v4`: plan/copy/layout approval -> complete final-page batch -> visual review, with no master or master-waiver field required. New final pages and requested previews use PT2.5-stable (`gpt-image-2.5-wd`), 1K and the confirmed ratio (default 9:16), profile `pt25-stable-sunburst-v4`. New previews attempt once with fallback disabled; do not switch to enterprise after a 503. Preserve older v2/v1 package semantics when inspecting or resuming; do not rewrite history.

The 2026-10-23 pet-harness run generated 16 no-master pages, with consistent overall style and several documented text/product defects. This supports the direct route for that case, not universal visual guarantees. The same day, a separately requested master successfully fell from a 503 at enterprise 2K to enterprise 1K/9:21; the third tier was not invoked.

Preparation explicitly sets generator gptStyle/transparent, materializes native rows without generating, then cross-checks the returned effective requests against exported rows, preparation IDs/digests and save destinations. Required capability absence blocks before submission; never use paid probes to populate rows.

The server returns one preparationId per workshop. For multiple nodeIds the executor preserves all bindings locally and relies on the documented per-workshop server validation; it does not pass one page's ID as the whole batch's ID. A single target passes its own preparationId. Stale-preparation rejection at the paid boundary still needs an authorized integration test. This version does not claim server-side submission idempotency.

## Cached model options

Use [model-settings.md](model-settings.md) and its JSON for known ratios. Do not repeat model/catalog/source inspection to rediscover them per page or repair. Keep a single normal availability check and actual execution-row readback. New stable compilations preserve a specified ratio; missing task ratios inherit the approved page/plan, then default to 9:16. New packages bind this with ratio_policy=confirmed-ratio-v1. Historical packages keep their recorded contract.

## Reviewed product/reference contract

New v4 tasks bind the current product_id to product_context in the approved plan, its asset inventory, language/count/ratio, page reference_images, product_display and visual_composition. Read [reviewed-workflow.md](reviewed-workflow.md). Text-only remains the default; selected mixed references are explicit and ordered. v2/v3 historical packages retain their existing rules.

## Agent responsibilities

Plan, confirm, compile approved tasks and visually review outputs. The executor owns node preparation, durable submission, polling and reconciliation. Never write a per-page serial runner or silently retry a failed task. An installed Skill does not change the host Agent's language model or the image provider's queue.

The executor supports local stdio MCP on Windows/macOS/Linux with Python 3.10+ and the adapter's existing Pillow dependency. Executor and Starcanvas must share accessible absolute file paths. HTTP-only or sandboxed hosts need an actual supported transport/file bridge; do not claim universal runtime compatibility.

## Connection and commands

On installation, follow `installation.md` and use `setup_detail_flow.py`. It reuses a trusted local connection and writes a non-secret ready.json receipt with the exact interpreter, executor and connection paths. Use those paths rather than asking end users to configure Python/MCP manually. Native host connector registration is not required for direct local stdio execution.

Use a user-provided local MCP JSON connection (`command`, `args`, optional `env`, `cwd`) or a `mcpServers` object with the `synmew-canvas` entry. It must point to the already installed Starcanvas stdio bridge. This is a host-neutral connection, not a client-specific installation. The subprocess inherits environment variables; JSON strings such as `${TOKEN}` are **not expanded**. Keep connection files outside the Skill, run directories and shared archives. Never print/copy secrets.

Run from the Skill directory; replace uppercase paths with actual local paths:

```text
python scripts/starcanvas_executor.py --connection LOCAL_MCP.json doctor
python scripts/starcanvas_executor.py --connection LOCAL_MCP.json prepare PACKAGE.json NEW_RUN_DIR
python scripts/starcanvas_executor.py --connection LOCAL_MCP.json run PACKAGE.json NEW_RUN_DIR --execute
python scripts/starcanvas_executor.py --connection LOCAL_MCP.json resume RUN_DIR
python scripts/starcanvas_executor.py status RUN_DIR
python scripts/starcanvas_executor.py recollect RUN_DIR
```

`doctor` reads capabilities only. Initial production `prepare` creates a dedicated project. Repair `prepare` reuses the source project and adds fresh per-page loader/generator/workshop chains, preserving original nodes. Each attempt still has a separate output folder and local run directory. Preparation checks real exported state and never generates; failure is not authorization to retry generation or fabricate a readback.

`run --execute` requires real stage authority as well as the flag. It can prepare a fresh run automatically. Normal production submits all approved page workshops in one `nodeIds` request before waiting; `--max-in-flight N` is only for a known service limit. There is no first-two-page barrier. Master and dependent production are separate approved packages.

Polling is local script orchestration, not a new Agent turn per image. Default wait is 600 seconds with 5-second polls; timeout leaves durable state and does not cancel, restart or retry tasks. `resume` queries known tasks, recovers an unknown acknowledgement only with an unambiguous project/workshop/time binding, and can submit original never-submitted tasks within the recorded concurrency limit. It never resubmits previously attempted tasks.

`collection_pending` means a reported result could not be read locally. `recollect RUN_DIR` retries local collection once per affected page using its saved task record, without a connection or generation request. It also rechecks historical `output_invalid` pages once; permanent identity/ratio errors remain rejected. `resume` includes this local recovery before polling. Use the selected child run reported by `status` when recollecting a fallback result. Recollection does not approve image quality.

## Recovering preparation without generation

Creation requests contain at most 80 operations and never split an individual page chain. Each batch saves an intent and a separate acknowledgement with its true idMap; completed mappings survive failures. Run the same `prepare PACKAGE.json RUN_DIR` to continue a new-version incomplete preparation. Confirmed batches are not recreated; an acknowledgement saved before a state-write crash is re-read and checked against actual nodes. A missing acknowledgement after commit remains unknown and blocks automatic recreation. Historical incomplete preparations without this protocol require inspection. No paid submission is issued by prepare.

Configuration replacements are idempotent; saved completed steps are skipped. All page preparations and full readback must succeed before run --execute. Finishing preparation does not imply any visual review or generation approval.

## Review revision binding

New copy-led compilations require `approved_plan: {path, sha256, approval_evidence}`. The path points to the adopted full plan JSON, whose `pages[].slice_id` and `text_exact` are authoritative. Record actual approval/delegation for that revision, reusing existing authority. This is a machine handoff within the existing design approval, not a new user gate. An editable-HTML receipt must match that plan or its exported `review_state.source_plan_sha256` lineage. Explicit alternative review formats still need the executable approved plan.

Each final task uses `page_id` equal to its plan `slice_id`; `screen-01` may omit it when the page ID is `01`. `production` must cover every approved page exactly once. Explicit `repair`, `sample` or `remaining` scopes may use a subset. The full approved plan stays bound, and the existing stage authority requirements remain. The compiler checks that every visible `text_exact` leaf is present in the final prompt, normalizing CR/LF line endings only for comparison; it never inserts or rewrites copy. This check does not prove image fidelity or understand contradictory prose elsewhere in a prompt.

A multi-page master must specify representative `page_ids`. It may use `copy_keys: {"01": ["headline", "labels.0"]}` to select approved text fields instead of packing every final page into the master. Final tasks cannot omit copy this way. Visual layout and comments remain Agent review responsibilities; a hash alone does not establish that those instructions were translated correctly.

Compiled packages record `review_binding_version=1` and the exact approved revision. Editing that revision or its prompts invalidates the package. Previously prepared, immutable packages without this field remain inspectable/resumable under their recorded contract; do not edit historical packages to invent approval or strip bindings from new ones. Any new normal CLI compilation requires the binding. A bounded child of an already-authorized historical fallback chain preserves that chain's old contract.

## Release identity

The publisher seals the completed Skill using `python scripts/skill_release.py seal --revision REVISION`. `release-manifest.json` identifies each shipped file and the whole content fingerprint; source/published Skill names normalize to the same fingerprint. Installation copies the sealed package, verifies the actual destination, then runs doctor from that installed path. `ready.json` and doctor report `skill_revision` and `skill_content_sha256`. Verify a handoff with `python scripts/skill_release.py verify --receipt READY_JSON` from the actual installed Skill. A matching ready path or a newly downloaded ZIP alone does not establish an upgrade.

Do not reseal a user installation to hide mismatches. Resolve the actual changed/missing files through the approved installation route. Developer source without a seal is reported as `development-unsealed`, never as a verified release. Local audit outputs and Python bytecode are excluded from release content.

Multiple valid output candidates require selection by actual file path/hash and review evidence:

```text
python scripts/starcanvas_executor.py collect RUN_DIR --selections SELECTIONS.json
```

This is local reconciliation only. Use the adapter's selected-candidate schema; no generation follows. Generation repairs require a new package and fresh attempt folders within the actual previously authorized scope/count. Reuse existing explicit repair authority; request confirmation only for additional paid requests outside that scope or approved direction/content changes. A technical collection failure is not generation failure: recover the existing outputs locally, never submit again merely because collection failed.

Mixed candidate outputs are evaluated individually after strict task/workshop/path/freshness binding. A wrong ratio or decode failure is recorded in `rejected_candidates`, preserving the original file; it does not discard other valid candidates. One valid candidate may be collected, multiple valid candidates require a path/hash/evidence selection. Invalid candidates cannot be selected. If none are valid, `candidate-audit.json` explains rejection and the page remains failed; regeneration is not automatic. Temporary missing/locked files retain the recoverable I/O path. Identity or configuration mismatches still block the binding rather than being ignored as ordinary bad images.

To recover a historical `output_invalid` page containing good candidates, run local `recollect RUN_DIR`, inspect the resulting valid candidates, then `collect RUN_DIR --selections SELECTIONS.json`. This updates the original task state and return manifest without a model call. Never manually copy a result and describe the run as technically complete while its recorded state still reports failure.

## Same-canvas repairs

New repair manifests require the original run binding below in addition to actual repair authorization. This is bookkeeping by the Agent, not another user confirmation:

```json
{"repair_context":{"source_run":"ABSOLUTE_ORIGINAL_RUN_DIRECTORY","issues":{"screen-01":"Actual observed defect being repaired"}}}
```

Keep the original task IDs/page IDs. `source_run` points to the actual initial or immediately preceding repair run that produced the problem page; for pages from different preceding runs, prepare separate repair batches in their shared canvas. The compiler freezes source package hash, run ID, project ID and page node IDs as `repair_canvas_version=1`. The default round is the source round plus one; an explicit integer `round` may advance it for a project-wide round number. Each issue must be a concise actual diagnosis, not a command to modify unrelated nodes.

The executor reads the bound original canvas and checks source nodes, then appends new chains to the right of all existing nodes, aligned to the corresponding source rows. Each chain gets a visible `text/note` annotation showing `返修R1·第01屏`, the defect, original generator/workshop IDs and an attempt suffix. Initial-production notes identify the page too. Notes explain the left-to-right material/prompt/result roles and are never connected to the generation graph. Starcanvas 1.8.9 rejects title writes on image loaders; do not rely on fabricated node titles. Full prompts stay in the generator; generated candidates stay in the new workshop. Original nodes, links, prompts and images are not overwritten or renamed. Only the new workshops are prepared/submitted. Keep new local package/run/output directories for immutable attempt records; a new local directory does not mean a new canvas.

`canvas-trace.json` records original/new node IDs, source task/return paths, repair reason, prompt hash/path, output directory, project and run IDs. The report links that file. Final handoff names the original canvas/project ID and which pages/rounds were repaired. Existing historical repair canvases remain untouched; do not automatically move their nodes across projects.

Missing source run, changed frozen source identity, missing original node, or unavailable original project blocks the repair. Never create a fallback canvas to hide that failure. Already frozen historical repair runs remain inspectable/collectible; preparing a fresh unbound historical repair package is rejected. Actual generation authority and allowance limits still apply.

## Repair authorization records

New repair compilation requires a record separate from initial production approval:

```json
{"repair_authorization":{"mode":"explicit","evidence":"Actual user approval for these additional generations","task_ids":["screen-04","screen-05"],"max_generations":2}}
```

`task_ids` must exactly match this repair batch. `max_generations` is a positive integer covering its tasks; it limits additional submission intents, not the number of final delivered files or the provider's billed amount. An optional master-repair fallback also stops at this limit across its chain. Normal production needs no additional field or new confirmation.

When the user already authorized a repair allowance, use `mode: "prior_allowance"` with the actual original approval evidence plus integer `allowance_total` and `used_generations`. The requested limit must fit the remaining allowance. The Agent must reconcile used attempts against prior run records and reserve a distinct allocation for each batch; this record performs per-batch arithmetic checks, not a shared cross-run accounting ledger. Do not copy an unchanged unused allowance into multiple batches or count a failed/unknown submission as automatically refundable. Never invent user approval from a nonempty evidence string.

State the initial generation count and any user-chosen repair allowance together at the existing design confirmation when applicable; do not add a questionnaire or require per-page confirmations. With no prior allowance, show the concrete defects and additional scope before requesting new paid calls. Existing actual authority remains valid within its scope.

Compiled repairs freeze `repair_authorization_version=1` and the record. Reports distinguish `generation_tasks_submitted` from delivery page count. Historical repair packages without this marker remain readable and locally collectible, but cannot issue new paid submissions; compile a newly authorized repair package instead. Do not retrofit approval into old frozen packages.

## Final quantity summary

After final visual review and file selection, follow [Delivery counts](delivery-accounting.md). Per-run report.json includes provisional usage; final cumulative delivery-summary includes all initial/repair/preview runs and the final selected files. The summary contains image/task counts only; currency reporting and billing inputs are not part of this workflow.

## Evidence and completion

Each run preserves `package.json`, `state.json`, `events.jsonl`, actual snapshots/readback, remote task snapshots and `report.json`. Atomic state writes and an OS run lock prevent concurrent writers. A pre-submit intent is saved before the network request; missing acknowledgement remains unknown, not failed-and-retryable.

Task status alone does not establish an output. Reconciliation checks task/workshop identity, new output path, freshness, decodability, ratio and input-byte echoes. Parameter/reference drift blocks completion. No automatic same-channel retry is performed. The bounded master service-failure channel fallback is the only automatic generation-recovery exception.

Exit codes: 0 = prepared/doctor/status success or execution `complete_needs_review`; 2 = blocked/failure; 3 = candidate selection needed; 4 = timed out; 5 = submission unknown. Read the command and recorded status, not just code 0. `complete_needs_review` still requires Agent visual review and is never final visual acceptance.

Offline tests prove orchestration behavior only. Real preparation tests prove accepted configuration only. Neither establishes provider concurrency, generation duration, typography or image quality.

## Stable profile migration

New compilations default to `pt25-stable-sunburst-v4`; old enterprise manifests must explicitly carry `execution_profile=pt25-stage-sunburst-v3` when inspected as historical fixtures. Already frozen packages retain their exact model and contract, and are never rewritten to stable in place. New production must be recompiled under stable; do not copy an old enterprise profile into a fresh job.

## Project names and profile migration

New projects are named DetailFlow·母版·9比21·1张·<run>, DetailFlow·正式页·9比16·10张·<run>, or DetailFlow·返修·01、09·2张·<run>. Counts, ratio labels and repair IDs come from actual tasks, not a hard-coded ratio or ten-page count. Each attempt retains a unique suffix. Existing canvas projects are not renamed.

The earlier pt25-stage-sunburst-v3 ratio migration remains historical context. Do not silently rewrite older packages under current ratios or models. Preserve old run evidence; changing a manifest ratio does not rewrite its prompt. Update the plan and prompt consistently before compiling a new stable-profile package. The layout editor can still inspect historical layouts; its generic rendering support does not authorize other production ratios.

## Native results and prompt transport

A generated child record may omit nodeId only when the observed frozen outputs.nodeId and remote runTargetId both match the recorded workshop. Conflicting identities fail; no identity is fabricated from the expected configuration. Input-byte echoes, output-directory/freshness checks and candidate selection still apply.

New copy-led packages record prompt_normalization=trailing-crlf-v1 and transport_prompt_sha256. Compilation removes only terminal CR/LF characters; original prompt files and their prompt_sha256 remain unchanged. Internal whitespace/newlines, leading spaces and text remain exact. Once packaged, even a source-only trailing-newline edit invalidates the original hash and requires recompilation.

## Desktop readiness

CLI doctor/prepare/run/resume reuse a live connection first, then on Windows can launch the verified official app once when its process is absent, followed by bounded read-only readiness probes. Setup inherits this through doctor. The desktop app is never killed, and operation errors inside a connected session are never automatically replayed. Follow installation.md for process-state and pairing boundaries. If connection drops after submission, recover via the existing run's resume command, not a new run.

## Current requested previews

New previews use stable 1K with their confirmed ratio (default 9:16), sunburst, auto, transparent=false and `master_fallback={enabled:false,max_attempts:1}`. A failure stops for diagnosis; another generation requires actual repair authority. Unsupported retry limits are rejected, never silently expanded. No preview is added to the normal direct-production flow.

## Historical enterprise preview fallback compatibility

For historical `pt25-stage-sunburst-v3` packages only: an explicit user request authorizes a `kind=master` task in `detail-flow-direct-v3`; record `master_request: {evidence}`. Normal final-page batches never enter this branch. Newly compiled requested master packages record master_fallback with enabled, max_attempts bounded by the remaining tiers and confirmed_terminal_service_failure trigger; an explicitly supplied lower limit must be preserved across compilation and resume. CLI run/resume use master_fallback.py to manage a durable fallback-chain.json in the original run directory. Default order is enterprise 2K/9:21, enterprise 1K/9:21, stable 1K/9:16. Each next tier requires confirmed ended error/failed status, exact task/project/workshop identity, no generated output and an eligible upstream-service error: HTTP 500/502/503/504 or a generic upstream model service error even without a code. Never fabricate a status code. Explicit account, authentication, quota, billing, rate-limit or moderation errors block automatic fallback even if the message also mentions the upstream service. No fallback on timeout, cancellation, unknown submission, output collection failure or visual rejection. The original run lock covers the chain; child runs also have their own locks. Deterministic child paths and a saved chain pointer prevent repeat submissions on resume. Each attempt report preserves actual model/settings and result; the chain report identifies the selected tier and total attempts.

Run the normal CLI, not ad hoc calls to Executor.run, to use the chain. Only read/collect existing results on an uncertain submission. An explicit single-attempt user constraint must set master_fallback.enabled=false before compilation. Do not recompile an already authorized/running job to add retries without actual authority.

2026-10-22 unpaid preparation: enterprise 1K/9:21 passes. Stable gpt-image-2.5-wd converts 9:21 to auto, so the user explicitly selected 1K/9:16 for this final fallback tier. Real preparation confirms stable 1K/9:16/sunburst. Keep auto rejected. No paid fallback generation was executed during implementation.

At the stable tier, preserve the original source prompt and append a non-visible 9:16 canvas override in a new file, with fallback_source_prompt_sha256 for provenance. Do not change consumer-facing copy. Each attempt is immutable; query fallback-chain.json to find the selected child run and its report. Resume the original root run to continue safely. A saved chain does not grant new authority after an explicit user cancellation.

### Direct lower-tier master requests

When the user explicitly chooses 1K/9:21, set the master task's master_fallback_tier=1, model_id=gpt-image-2.5-1k-qy, resolution=1K, aspect_ratio=9:21. A directly chosen stable master uses tier=2, model_id=gpt-image-2.5-wd, 1K and 9:16. These are valid root runs. master_fallback.enabled=false requests that tier alone; true allows only the remaining later tiers (two attempts from tier 1, one from tier 2). Do not try legacy contracts or tell the user to reselect an already supported choice.

Only children actually created by the fallback chain carry master_fallback_parent and must resume from their recorded root. The selected model tier by itself does not make a run a child. Default fresh master production still begins at tier 0. Existing terminal-failed runs can be resumed through the original chain after upgrading the runner; inspect submission state first and never recreate the same paid attempt. If the existing run was prepared under a different profile/authority, preserve it and report the specific incompatibility rather than claiming all lower tiers are impossible.

The chain persists the next preparation intent before creating its package. After interruption, an existing unsubmitted package is reused only if its exact contents match the deterministic approved package and it contains no unexpected output files. Unknown or conflicting states stop for inspection. This does not promise replay of a partially completed remote project/node mutation. `status ROOT_RUN_DIR` reports the selected child and the original root-attempt status separately; the root report summarizes the chain while original task/state records preserve failures.

Runtime error evidence is separate from configuration export. On the observed server, `project_export` omits workshop row errors: a generic failed frozen task must be supplemented by `canvas_get_node`, not guessed from an empty export field. Accept a live row error only when the project/task/workshop, prepared row ID, effective prompt/images/settings and failed-without-result state match, and task listing confirms this dedicated workshop has not been reused. Save `fallback-node-error-*.json` with the response and decision. Missing/ambiguous evidence or a competing task stops the chain. An explicit service failure already recorded on the frozen task remains task-specific evidence. The 2026-10-23 real 503 record was replayed offline; a successful eligibility decision is not a newly generated image or approval to resume a paused run.

A runnable/available model registration does not prove the account has enough balance or that the upstream request works. Equally, absence of success in one task's folder does not prove the whole model family has never generated successfully.
