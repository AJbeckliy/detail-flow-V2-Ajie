# Starcanvas execution only

Use [the unified executor](unified-executor.md) for submission/wait/collection instead of an Agent-authored runner. It integrates unpaid preparation on Starcanvas 1.8.8; do not bypass preparation or readback checks.

The Agent owns design and review; Starcanvas executes approved prompts. Normal order: editable plan/copy/layout approval -> all approved final pages submitted concurrently -> final vertical and individual review. No generated master or trial pair is required. New tasks use detail-flow-direct-v4; frozen v2/v3 contracts are retained. Seamless construction, edge anchors and seam repair remain paused. A visual master is not a long-scroll chapter or a crop source.

## Input boundary

The Agent completes the original workflow through the current approval gate and writes final per-image prompts. The executor receives ready_tasks.json containing IDs, prompt files, ordered local references, selected model/resolution/ratio and ready stage. It never generates or rewrites prompts, translates copy, adds style constraints, alters counts or supplies a second canvas planning model. It preserves approved copy and internal UTF-8 text exactly. During new copy-led compilation only terminal CR/LF characters are removed for native transport; record the normalization policy and transport hash while keeping the original file and source hash. Leading whitespace, internal line breaks and all other characters remain unchanged.

Use scripts/starcanvas_adapter.py compile READY_TASKS NEW_PACKAGE to produce native node operations and task mappings. This is preparation, not a model call. New copy-led manifests require approved_plan with path, sha256 and approval_evidence for the adopted revision. The compiler checks page IDs and required text_exact against the supplied prompts; it does not interpret or convert visual fields. See Review revision binding in unified-executor.md.

Before submitting, compare both the generator and actual workshop execution row with the package. The row must use the correct stage model/resolution, version sunburst, approved prompt/inputs/ratio, quality=auto and transparency off; generator fields alone are insufficient. Missing quality is unverified, not an assumed match; obtain the actual value before submission. A mismatch stops execution. References must be attached in the supplied order with `canvas_attach_local_images replace:true`. Never append to a reused loader. New packages include `reference_attachments` with the exact paths and replacement flag; resolve its `load_ref` through the committed idMap when calling the tool. New output folders keep approved images intact.
Readback JSON contains generators, workshops and references keyed by task ID. References are the actual loader path list; workshops contain actual `rows` and `autoSaveEnabled` from the same exported project snapshot. Both order and file hashes are checked, including frozen planning sources. Save it into the committed state; reconcile requires it rather than inventing an unchanged-prompt claim. Save pre-submit output paths and task start/end timestamps. Returned files must be new for this attempt and not predate the task (2-second timestamp precision tolerance).
In 1.8.0 canvas_get_node omits loader image data and canvas_list_outputs may be empty before execution. Use the supported project_export snapshot, read canvas.nodes, and extract the loader images[].path in exact order. Do not fabricate the reference readback from the requested list. Export after generation too when checking actual workshop row inputs/prompts. Keep exports local.

## Current batch chain

Read canvas://guide/workflow and workspace_get_context first. Latest unpaid preparation check: 2026-10-21, Starcanvas 1.8.8.

Each task gets its own image/load-image-grid → ai-image/gpt-image → image/workshop chain. Loader output is imageGroup, generator image output is ai-image, workshop image input consumes it. Run the workshop via canvas_run_node, not the generator. The Agent imports actual saved files for inspection.

Create an isolated project for initial production. For repairs, bind the original run and add new chains in that same project as specified in unified-executor.md; never overwrite original nodes. Do not apply a visual template merely to obtain nodes: template row parameters can carry a model/style preset. Master and final tasks use separate loaders/workshops by default. workflow_apply_patch dryRun then commit with current expectedRevision and per-batch idempotencyKey; at most 80 operations, with complete page chains and durable acknowledgements. Preparation batches do not impose staged visual approval or serial generation. Only the committed idMap maps client references to real nodes. Use canvas_attach_local_images for ordered references and the workshop save folder, first dryRun then commit. Read back every target. Run preflight for all scheduled workshops; severity=error stops submission.

## Concurrency without changing planning

Batch-submit independent ready workshops with canvas_run_node nodeIds. Record the individual task IDs returned by the service. Two running requests and overlapping task intervals support a concurrency observation; they do not prove a specific acceleration factor or parallel inference inside the provider.

Any reference required by a task must exist and be reviewed before dependent pages are ready. Final pages wait for design approval. Optional user-requested preview evidence is not a final-page image reference. Independent ready pages must be submitted together by default, within known service limits; do not batch the master with pages that depend on its output. The full approved final-page set uses `ready_stage=production`; no `sample_review` is required and no initial pair blocks the rest. No previous-edge dependency is required.

## Fixed production profile

New tasks use profile `pt25-stable-sunburst-v4`. The user-approved UI settings are:

| Task kind | UI model | Manifest model_id | Resolution | Version / gptStyle | Ratio | Quality | Transparent |
|---|---|---|---|---|---|---|---|
| optional requested master | PT2.5-稳定 | gpt-image-2.5-wd | 1K | sunburst | confirmed ratio (default 9:16) | auto | false |
| slice | PT2.5-稳定 | gpt-image-2.5-wd | 1K | sunburst | confirmed ratio (default 9:16) | auto | false |

The same stable 1K profile with the confirmed ratio applies to repairs and requested previews. Do not switch new tasks to enterprise models. For a correctly configured stage node, set only its required aspect ratio; do not change its version, quality or transparency, or switch new tasks away from stable. Historical tier recovery is described separately in unified-executor.md. Prompts, approved input files and save directories remain task-specific.

Compilation records `gpt_style=sunburst`, `transparent=false` and explicit `workshop_settings` for each task. Generator `modelType` is the registered UI model ID. Actual workshop `params.model` may retain that ID or encode the same sunburst version in an internal alias; the checker accepts only that stage's model family and matching resolution/version suffixes, while independently checking `gptStyle`, resolution, quality and transparency. A different tier, provider or style is not an alias. Unrecognized mappings stop for diagnosis rather than triggering a paid probe.

If the required stage profile is unavailable, report the blocker. New requested previews use stable 1K and the confirmed ratio with automatic fallback disabled. Only historical enterprise-profile packages retain their old tiers; unexpected returned dimensions do not authorize a ratio/profile change. Higher resolution is intended to help text rendering, not to waive exact-copy and visual checks.

At setup, inspect the exact model's live availability and relevant node fields once. Reuse that evidence for unchanged tasks within the same run; refresh after a relevant version/config change or a specific contradiction, not before every image. No paid model-discovery probe is part of setup. Inspect actual returned pixels separately; fixed request settings do not guarantee a model will obey them.

## One snapshot, batch verification

After final attachments, row configuration and preflight, export one current project snapshot and save the committed idMap. Run:

```text
python scripts/starcanvas_adapter.py readback-export PACKAGE.json PROJECT_SNAPSHOT.json ID_MAP.json NEW_READBACK.json
```

This reads the actual `canvas.nodes`, maps each task's loader/generator/workshop and checks all tasks locally. It does not call MCP or generate images. `ID_MAP.json` is the raw committed clientRef-to-nodeId mapping, not a hand-invented map. New packages require `execution_profile=pt25-stable-sunburst-v4`; missing workshop rows or unverified fields fail, rather than being inferred from the requested values. Do not submit a package whose readback fails.

For the current schema, a workshop exposes one `rows[]` entry per task with `prompt`, `images`, `params`, `saveDir`, `saveFilled`, plus node-level `autoSaveEnabled`. Native top-level and nested `data` exports are supported. Keep these values from the snapshot; never manufacture actual readback by copying expected package settings. If rows are not yet materialized, use the documented local preparation/preflight path; do not run a paid task simply to discover or populate them.

When the snapshot reveals a mismatch, correct only the observed layer through documented supported operations. Starcanvas 1.8.8 accepts generator `gptStyle` and `transparent`. Set these explicitly, then call `canvas_prepare_run`; do not send entire copied rows or assume partial row-array writes preserve bindings. Missing rows or unsupported required corrections block submission. Do not guess unrelated fields or enumerate styles. Replace loader inputs with the exact approved list (`replace:true`), then export and recheck once. Recheck after any input/prompt/parameter mutation. The readback is a snapshot, not a lock over future external edits; submit without further configuration mutations.

For final pages, loader images and workshop rows[].images must equal the approved task references in exact order. Current v4 supports product/model roles in text_only mode and selected style/composition roles in mixed mode; see reviewed-workflow.md. Unrelated long references, generated masters, sketches, duplicates and stale inputs stay excluded. Never relabel a visual reference as product to pass validation.

## Durable submission and return

Before submission save an intent identifying round, task ID, prompt hash, input reference hashes and output directory. Immediately save returned remote task IDs. After timeout/reconnection query recorded tasks before any new submission; unknown status does not authorize retries. Tests and retries stay within user-authorized rounds. A ready package itself does not authorize spending.

Save task snapshots and canvas_list_outputs from the specific workshop. Require source=generated, a new file for this attempt, actual decode and dimensions. Deduplicate repeated records pointing to the same physical file; do not confuse inputs or old files with a new generation. status=done only means scheduling ended; error with endedAt and concrete workshop error is a terminal failure.

Use scripts/starcanvas_adapter.py reconcile PACKAGE COMMITTED_STATE RESULT_SNAPSHOT RETURN_DIR to create the Agent return manifest. It binds outputs to node/task/input hashes, checks unique files and ratio, and makes inspection-size previews. It never marks visual approval. Return status is needs_agent_review. After the full batch, the Agent opens originals and uses compose_ordered_preview.py for final-set review. Check perceptual coherence, not pixel-matched seams. Keep technical execution success separate from visual acceptance.

Wrong-ratio or undecodable candidates are preserved with rejection reasons, while other valid candidates continue to collection/selection. Foreign task/node/path or stale-file evidence is not filtered away. Use the normal recollect/collect path to persist the selected file and task status; a manual delivery copy alone does not close a failed run. New paid repairs additionally require `repair_authorization` as specified in unified-executor.md; first-round production authority alone is insufficient.

## Production stage and completion

Execution validation should reuse final ready prompts and approved product-material references without prompt edits. Report submitted task intervals, unique files and read-back match. If outputs fail Agent visual review, keep the original plan and route only the necessary correction; do not change planning or start main images.

Normal user approval covers the plan/copy/layout; a preview gate exists only when explicitly requested. Full-set inspection follows concurrent production and adds no third normal confirmation. Prior explicit delegation remains valid and must be recorded. A full-page claim requires all confirmed pages and final review; a transport test does not establish visual quality.

## Stage vocabulary compatibility

The transport script uses `master` and `slice` kinds. Normal stages are `production` -> optional `repair`; `master` is an explicitly requested preview branch only; `sample`/`remaining` remain only for historical inspection or an explicitly requested staged trial. New `master` and `slice` tasks use stable 1K and the confirmed ratio (9:16 by default). Historical untagged v1 packages remain readable for inspection; new untagged or master-v1 compilations require explicit `legacy_experiment: {evidence: "actual authorization and scope"}`. Omitting `workflow` alone is an error, not a fallback.

For every new normal-flow manifest, set `workflow: "detail-flow-direct-v4"` and
`design_approval` to a concise reference to the actual plan approval or explicit delegation.
Normal final-page tasks need no `visual_master`, `master_request` or `stage_policy.master` waiver. A generated preview uses `kind=master` only with actual user `master_request: {evidence}`. A retained preview request or explicit master gate on a later final-page manifest requires its `visual_master: {path, sha256, approval_evidence}`, unless the user explicitly waives that requested gate. Supplied bindings are still checked; do not carry optional request metadata into ordinary direct-production manifests.
The first reference of each task is `role: "product"`. Current v4 final tasks declare product/model roles and, in selected mixed mode, matched style/composition fragments. Never attach a generated master or a layout sketch as a substitute for planning. The `visual_master` metadata binds approval evidence only and is not added to node inputs. Normal `production` contains the whole approved page set and does not require `sample_review`. New `sample`/`remaining` compilations require `staged_review_authority` pointing to the user's explicit request; the optional `remaining` stage additionally needs `sample_review`.
Repairs can contain final-page tasks without a master. A preview repair belongs to the explicitly requested preview branch. Any supplied optional master binding remains immutable until the corresponding revision is approved.

These checks verify metadata and files, not human permission: never treat a fabricated string
or `approved: true` as approval. The Agent must verify authority in the conversation and keep
evidence in project records. An explicitly requested experimental deviation can use the legacy
manifest contract with its scope stated in `authority` and `legacy_experiment.evidence`; do not silently drop the workflow tag
to bypass a failed check. Use examples/reviewed-workflow.json for current task shapes; copy-led-workflow.json is historical compatibility material. `detail-flow-master-v1` and its older example remain compatibility fixtures; do not select v1 or omit the workflow tag to bypass the current reference policy. Use the current selected mixed-reference policy for A/B tests; legacy contracts are not a shortcut around current plan/reference binding.

## Planning-preview boundary

The layout renderer supports the normal first-confirmation package. Its PNGs and status are planning artifacts, not model output or payment authority. Do not automatically add sketches to generation inputs. An explicitly requested visual preview is a different, generated and user-confirmed artifact; it is retained only as approval evidence and is not attached to final-page tasks. Transport the compiled prompt exactly under its recorded terminal-CR/LF policy and review actual originals.

Review return files by copy-image correspondence, exact template text and consistency within the generated page set, not by matching the master image. Submit independent ready workshops together with `nodeIds`; preserve all real reference dependencies without an initial-pair review barrier. Report overlapping task intervals as concurrency evidence, not a guaranteed speedup.


## Paths, candidates and stage exceptions

CLI `compile` resolves prompt paths, reference paths, master paths and frozen-planning paths relative to the input manifest's directory, never the shell working directory. New packages retain absolute paths. Python callers may pass `base_dir` to `compile_tasks`; otherwise it captures the current directory at compilation. Historical packages with relative paths must be resolved with their original known base before readback; do not guess or rewrite archived evidence. On another computer, remap assets and recompile.

`reconcile` deduplicates repeated records of the same path and verifies every distinct candidate. `candidates` contains all technically verified images; `images` contains at most one chosen image per task. If a task returns multiple candidates, its ID appears in `selection_required` and none is silently selected. Review the originals, then supply `state.selected_candidates[task_id] = {path, sha256, evidence}` and reconcile to a new return folder. A selection is not visual approval. Do not submit another paid task just because selection is pending. Missing, stale or wrong-ratio files still fail technical checks.

Normal manifests keep `design_approval` and `approved_plan` approval evidence. `visual_master.approval_evidence` is used only for an explicitly chosen preview gate. Optional `stage_policy` entries for `design` or `master` have exactly `{mode, evidence}`: `approved` records actual user approval, `delegated` records explicit authority for Agent decision plus the completed internal review, and `waived` records the user's explicit waiver of that named stage. These strings bind records; they cannot establish permission by themselves.

Skipping sketches does not waive design approval. Keep an executable brief with exact copy, confirmed count/ratio and product facts even if presentation is waived. Current direct-workflow final pages do not need a master waiver. If the user explicitly requested and retained a preview gate, that request and any supplied approval/hash binding remain binding. Historical `detail-flow-copy-led-v2` packages keep their original master/waiver requirements; do not rewrite archived packages or invent a waiver to migrate them. Declared role-bound references, full-set checks and generation authority remain required. A pause is never revoked by upgrading the skill.

Example of a separately authorized design-stage delegation (illustrative, not authority):

```json
{"stage_policy":{"design":{"mode":"delegated","evidence":"Reference the user's explicit delegation and the completed internal brief review"}}}
```


## Required editable review handoff for new tasks

Run `prepare_review.py` during first review. Before new copy-led compilation, include:

```json
{"review_delivery":{"kind":"editable_html","receipt_path":"review/review-receipt.json","receipt_sha256":"SHA256 of the receipt file","presentation_evidence":"Actual opened review page or user-visible HTML link"}}
```

The adapter verifies receipt, HTML/source hashes and editable/export controls. It rejects static-only or missing review delivery, but these checks do not prove human approval or a visible popup. Obtain actual design approval separately. Keep the referenced source and HTML unchanged; adopted exports are new revisions. A user's explicit alternative/waiver uses `review_delivery: {kind: "user_alternative", evidence: "actual user's instruction and scope"}`. Host inconvenience and general delegation do not imply an alternative review format. Historical packages without this new field remain inspectable, but new compilation must satisfy it.


## Ready batches and input echoes

For 8, 10 or 12 approved final pages, submit all 8, 10 or 12 after design approval and machine validation, using `ready_stage=production`. Do not hold back pages 3+ for a visual review of pages 1-2. Service concurrency limits may govern queue submission, but do not introduce a manual/internal-review barrier between those submissions. Each task has its own workshop and output directory. Use `canvas_run_node` with the ready `nodeIds`; do not submit one image and wait for it before submitting the next independent image. If service limits require smaller batches, state the actual limit/reason and keep the permitted slots filled. Batch submission is not proof of backend parallel inference; verify returned task IDs and intervals. No extra paid concurrency probe is required.

A workshop may copy an input image into its output directory. A new path and timestamp do not establish new image content. Reconciliation checks each candidate's SHA256 against the task's verified input-reference hashes before ratio validation. Exact byte copies are recorded in `echoes` and excluded from selection; originals remain untouched. If every candidate is an input echo, the task fails without authorizing a retry. This detects byte-identical copies, not every visually similar or re-encoded image; Agent visual review remains required.

New previews and final pages use stable 1K and the confirmed ratio (9:16 by default). Only historical enterprise-profile masters retain 9:21. Do not treat an unexpected output as permission to change the request or bypass exact readback. Layout previews remain neutral wireframes for copy and structure; page-background design controls are not added.


## Bounded recovery and fewer model round-trips

- On a configuration or output anomaly, do one focused diagnosis round: collect the current task result/log, effective workshop row and output dimensions together; compare locally. Do not repeatedly query the full model catalog, enumerate style values, inspect app binaries, recreate projects or run comparison probes as part of ordinary production.
- If no concrete cause is identified after that round, stop the affected branch and report expected versus actual values. Do not keep generating to see whether it changes. Other already-authorized independent tasks may finish; do not duplicate them.
- If a cause is identified and existing user authority covers a retry, permit one targeted correction attempt for the same error, then inspect it. If the same error recurs, stop and report. The documented three-channel master service-failure chain is a separate bounded exception; otherwise further probes/retries require the user's explicit scope. Changing task IDs or project names does not reset either limit. Known pending tasks must be queried instead of resubmitted.
- Compile the complete final-page set directly from the approved blueprint and shared visual rules. Only an explicitly requested preview may delay dependent compilation. Local wording changes invalidate only affected prompts and checks.
- Batch independent file reads and metadata checks. Use existing scripts for deterministic extraction, hashes, dimensions and exact comparisons; do not ask the LLM to re-derive or re-check each small field in a separate round. Keep creative judgment and visual acceptance with the Agent.
- Use the existing task wait/query mechanism with bounded intervals and small status summaries, rather than tight polling plus repeated full context. These are efficiency rules, not permission to skip approval, output review or a failed check.

Historical `pt25-1k-enterprise-v1` packages retain their original inspection contract only. New compilations always use the two-stage sunburst profile; do not reuse an old compiled package as the new production configuration.

## Native prepared save configuration (1.8.8)

Prepared rows may omit saveDir/saveFilled. Read the actual node autoSavePath and autoSaveEnabled, its runPreparation id/digest/goal, and the prepare response effectiveRequest.saveDir. All destinations must match this attempt; explicit contradictory legacy fields still fail. The executor also binds actual row IDs, prompts, images and parameters to the preparation response. No expected values may be substituted for missing actual evidence.

## Repair authority and collection errors

Before a paid repair, check existing user authority and its page/count limits. Reuse explicit authority already granted; ask only for additional paid requests beyond it or changed approved direction/content. Do not ask for permission merely to collect existing files or finish packaging. A rendered typo does not authorize modifying text_exact. Keep approved copy and target its rendering. Local image editing requires the corresponding actual authority. Collection errors never authorize regenerating a completed task.
