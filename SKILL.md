---
name: detail-flow
description: Build, redesign, polish, or review product detail pages for products, AI tools, models, SaaS features, developer products, plugins, ecommerce listings, and technical showcases. Use when the user provides a product image, reference image, screenshot, product concept, or existing page and asks for a detail page, ecommerce detail page, 8-screen product page, long-form sales page, model page, product feature page, visual polish, responsive frontend implementation, screenshot-based QA, or reusable workflow derived from an existing product page project.
---

# DetailFlow

## Overview

Use this skill to turn a product or feature idea into a useful, polished detail page. Prioritize clear product communication, real user workflows, implementation quality, responsive behavior, and visual assets that reveal the product rather than decorative filler. Keep planning reusable across product categories and frontend stacks. The Agent owns planning and review; Starcanvas MCP is the default and strongly preferred image backend.

For image detail-page work, focus on content clarity and the visual design of the page set. Marketing-performance research, conversion measurement, and sales-effect validation are outside the default workflow.

Prefer Starcanvas MCP throughout the same job: full-page generation, supplementary scene/material images, revisions, local edits, expansion and text repairs. Adding assets for an existing page is not a fresh task with an unrelated backend. Before choosing a host-built-in tool such as ImageGen/Imagine, first consider the existing Starcanvas route and known model/settings; host defaults may use an unspecified model. This is guidance, not a host-tool ban. If another backend is ultimately used, identify the actual tool/model when known and keep its results distinct from Starcanvas records.

**Ratio quick reference:** 9:16 is the default only. PT2.5-stable options verified on Starcanvas 1.8.9 are **1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9**. Use the user's confirmed ratio directly. Reuse this list rather than repeatedly discovering it during generation or repair; refresh only for a model/version change, a specific parameter error, or an uncached request. See [model settings](references/model-settings.md). Changing ratio does not itself request a different backend or HTML screenshot production.

For Starcanvas execution, read [Unified executor](references/unified-executor.md) and use the bundled compiler/executor. New tasks use `workflow=detail-flow-direct-v3`: approved plan -> complete final-page batch -> visual review. No master or preview is required by default.

For requests to improve DetailFlow itself, learn from a completed run, or add reusable self-iteration behavior, read `references/self-iteration.md` before proposing or editing skill files. Treat skill updates as human-approved patches, not autonomous self-modification.

## Install once, then produce

For installation, MCP setup, missing dependencies or a new host, first follow [Agent-operated installation](references/installation.md). Use `scripts/setup_detail_flow.py` to reuse a trusted local connection, repair missing Pillow in a private environment, verify the real MCP and record exact runtime paths. A missing guessed client mcp.json is not proof of no connection. Direct local stdio through the executor is sufficient when host script execution is available; do not demand duplicate native connector registration. On Windows, the bundled CLI reuses the live connection or starts the verified installed Starcanvas app once when absent and waits for readiness. Do not default to asking the user to open it manually. After a successful live doctor check, continue directly to production planning. Never invent a trust button, connector-management location or mandatory new-chat step. Request user action only for an observed blocking error and a verified applicable resolution. Ordinary installation does not require running the developer test suite or installing Playwright. After readiness, continue the normal approved production flow. On upgrades, verify the release revision/content fingerprint against the actual installed path in ready.json; a new ZIP alone does not update that path.

### 安装完成判定（必须遵守）

- 安装阶段不生成、不打开示例审核 HTML，不运行 prepare_review.py、浏览器回归或全套开发测试来证明安装成功。仅检查依赖、文件和真实连接。用户只要求安装时，到就绪回执为止；明确要求制作时，再进入正常方案流程。正式制作中的可编辑方案审核保留。

- 实际 `doctor` 检查通过，确认 `workspace_read=true`、`required_tools_present=true` 后，直接执行器通道即已就绪，继续已有制作需求或索取产品素材。
- 星幕主程序启动是正常连接前提，不要求用户寻找“开启 MCP 控制”的开关。通用报错不能当作界面存在该开关的证据；连接失败应核实真实端点和桥接响应。
- 不得在安装成功后追加默认待办：让用户“信任 MCP”、寻找“自定义连接器”按钮、重启软件、新开会话，或清理其他 Agent 的 Skill 副本。
- 原生客户端连接器是否注册或检查过，不影响已验证的直接 stdio 执行路线。`optional_not_checked` 或旧回执的 `native_client_trust=not_verified` 都不代表用户欠缺一个操作。
- 只有出现实际阻断错误，且已核实该宿主确有对应操作，才说明错误和唯一必要动作；不得猜按钮名称、页面位置或把其他客户端的流程套过来。
- 能读取 Skill 并运行内置脚本，就在当前会话继续；不得把新会话当作默认安装条件。安装成功不替代方案确认或生图授权。

## Choose the requested deliverable

- Planning or review only: analyze and deliver the requested plan/findings; do not start generation or frontend implementation.
- Ecommerce image set: use the Execution Contract and Image Generation Workflow below. The configured execution backend is Starcanvas; its tool mapping lives in `references/starcanvas-execution.md`.
- Frontend implementation: use Core Workflow only when the user actually requests a webpage/frontend. A different image ratio, a revision request or a generic confirmation does not by itself select HTML screenshot production. Image-production approval stages apply only when a separate generated image set is requested.

For another Agent or computer, read `references/portability.md` for capabilities, dependencies and offline validation. Check the receiving Agent's capabilities, not its brand. This skill includes generic local setup and the execution contract; native client registration follows documented host facilities when required. Installation never grants generation authority.

## Required behavior across Agents

- Before execution, check the capabilities needed for the requested stage: local scripts/files, image inspection, editable HTML delivery and Starcanvas MCP. Use the bundled setup and host tools; do not build a client-specific installer as part of a page task.
- The first review must give the user editable copy/layout, export controls and a usable HTML entry point. A PNG, screenshot, text-only plan or internal file path the user cannot access does not satisfy that deliverable.
- Build with `prepare_review.py`, then present/open through an available host tool, or provide a downloadable standalone HTML. Choose an entry point the user can actually access. A remote filesystem path is not a user-accessible link.
- If a needed capability is absent, state exactly what is unavailable, preserve completed work and pause the dependent stage. Do not silently substitute static imagery, fabricate an opened-page claim or advance to generation. Only the user's explicit alternative/waiver changes the deliverable.
- Opening a page, receiving an export and obtaining approval are separate events. Reuse actual approval already given for that revision; never derive approval from a tool success or silence.

## Execution Contract

For image-led ecommerce detail-page requests, follow the defined DetailFlow route strictly. Treat this contract as higher priority than convenience, improvisation, or tool preference.

- Default division of work: Agent plans and writes final prompts -> Starcanvas MCP executes approved image tasks -> Agent inspects returned originals and handles necessary revision. Carry this backend preference into supplementary assets and subsequent edits.
- New final pages and explicitly requested previews use PT2.5-stable (`gpt-image-2.5-wd`), 1K, the user-confirmed ratio (default 9:16), version `sunburst`, quality `auto`, transparency off. Verify effective workshop rows and exact ordered product inputs before submission. New previews retain their confirmed ratio and have no automatic channel fallback; historical bounded fallback is documented in `references/unified-executor.md`.
- Normal order: analyze inputs and references -> whole-page shared visual rules and per-screen blueprint -> editable copy/layout review -> design approval -> all approved final pages submitted concurrently -> final vertical and individual review -> delivery.
- The normal workflow has one design approval gate covering the plan, copy and layout. After approval, submit the whole approved page set. Do not add a master, first-two-page trial, or other intermediate generation/approval gate. Reuse existing approvals and explicit delegation.
- Stop at an unapproved design gate. Explicit delegation replaces that stop with Agent review; a waiver applies only to the named stage. No master waiver is needed in the normal direct-production route. An explicitly requested visual preview is reviewed within the user-requested scope before dependent production.
- Inspect every final page and the ordered set after the batch completes. Flag product changes, text errors, missing content and inconsistent visual treatment. Only inspect an additional generated preview if the user explicitly requested one; do not create it to satisfy an internal checklist.
- MUST use the user's product images, references, confirmed facts, approved blueprint, and approved samples as the authoritative inputs. Do not replace them with a newly invented concept or generic category template.
- MUST keep the task scoped to the requested ecommerce image set. Minimal canvas nodes and existing transport utilities needed for approved Starcanvas execution are in scope. Do not create a website, video, animation, presentation, application, new utility script, or unrelated artifact unless requested.
- MUST NOT write code merely to simulate image generation, create placeholder deliverables, or bypass an unavailable image-generation/editing capability. If a required capability is unavailable or fails, state the limitation and stop at the current stage or offer the smallest relevant alternative.
- A clearly labelled planning wireframe from the bundled layout renderer is a planning artifact, not an image-generation substitute. It must never be presented as a model result, final product image, visual approval, or authorization to generate.
- Optional lifestyle previews can use borderless relationship sketches (see `references/layout-preview.md`): preserve important person/product/space relationships while leaving photographic composition flexible. Do not automatically send preview diagrams to generation.
- For normal ecommerce image production, MUST build and present the editable HTML review before the first confirmation. Use `scripts/prepare_review.py PLAN.json NEW_REVIEW_FOLDER`: it builds the editor and requests a browser launch by default. Read `references/copy-review-editor.md`. A static PNG/contact board alone does not complete this stage. Exported edits are a draft for existing blueprint review, invalidate stale prompts, and never authorize generation by themselves.
- MUST keep the requested deliverable scope stable: do not add unrelated stages, output formats, image counts, or auxiliary deliverables without approval. When the user provides limited product information, infer suitable selling-point copy, scene ideas, visual motifs, labels, and supporting content from the product images, product category, reference images, and common buyer concerns. Clearly distinguish reasonable creative inference from confirmed facts. Do not invent exact technical parameters, certifications, awards, medical effects, discounts, or brand partnerships that are not supported by the user or source material.
- After a failed result, first revise the smallest responsible layer using the existing Starcanvas route. Do not silently present outputs from another tool as Starcanvas results. Preserve actual approval scope when a change affects an approved blueprint or visual direction; do not add a new tool-permission gate merely to restate this preference.
- MUST preserve approved outputs. Do not overwrite or discard accepted references or page images while experimenting; save revisions as clearly identified replacements or versions.
- MUST NOT modify this skill's own `SKILL.md`, `references/`, `scripts/`, or metadata as a side effect of a normal page-generation run. When a run reveals a reusable improvement, produce an iteration report and wait for explicit user approval before editing skill files.
- MAY use lightweight existing utilities only when they are necessary for deterministic operations such as reading image dimensions, concatenating approved slices, checking files, or saving deliverables. Do not create new utility scripts for these operations unless the user explicitly requests automation.

If the user's request is ambiguous, choose the narrowest action that advances the current DetailFlow stage. Ask before expanding scope.

Final page images default to independent content panels: one complete module per image at the confirmed ratio. Coordinate typography, color, lighting, side margins, line height and letter spacing across the set; do not place matching top/bottom chevrons, shared edge decorations or continuation fragments on successive images. An optional user-requested visual preview is a customer-facing design checkpoint, not the normal route. Final prompts carry explicit shared visual rules; do not attach the master or planning sketches to final-page requests. Review generated pages against each other and the approved copy, not for resemblance to the master.

The default route has no generated master. Seamless long-scroll construction remains paused: no overlapping relay, edge anchors or seam-repair rounds. Ordered vertical review checks coherence without requiring pixel-matched edges.

## Additional repair scope

Repairs stay in the source canvas. Bind `repair_context.source_run` to the actual original or previous repair run, record a concise issue for each affected page, and use the compiler/executor to add a fresh loader/generator/workshop chain to the right of existing nodes, aligned with the source page. Never replace original nodes/prompts/images, create another canvas by default, or reuse an old workshop for a new attempt. A visible text/note annotation identifies page, repair round, reason and source nodes beside each new chain; the generator retains the complete prompt. These notes are not connected to generation. Do not attempt unsupported title writes on image nodes. Deliver the original project identity and `canvas-trace.json` so the user can trace each repair to its source. Missing source records block preparation rather than silently creating another project. See [same-canvas repairs](references/unified-executor.md#same-canvas-repairs).

New paid repair batches require a separate `repair_authorization` record binding the affected task IDs, additional generation limit and actual user evidence. A production approval alone does not authorize extra attempts. Reuse an explicit prior allowance after accounting for its recorded use; do not add a new approval gate when that scope already covers the repair. See the repair authorization contract in [Unified executor](references/unified-executor.md).

## Optional visual preview

Generate a visual preview only when the user explicitly asks to see one before the full set. Record the request as `master_request.evidence`; do not infer it from missing style references, uncertainty, installation checks or a general request to produce pages. Follow the existing preview profiles and bounded service-failure policy in [Unified executor](references/unified-executor.md). Keep prior approvals, user-specified generation limits and pauses binding. A successful preview does not replace final-set review, and its image is not a final-page input.

## Core Workflow

For planning/review, use only the relevant analysis and design steps. Repository inspection, code edits and app/browser rendering below apply to frontend implementation, not to an image-only plan.

For image-to-ecommerce detail page requests, do not generate final images immediately. First produce a structured page blueprint and use the applicable design approval or explicit stage delegation/waiver. A request to skip planning waives its presentation/confirmation only; still resolve a minimal executable brief without adding a master stage. Follow the stage-policy contract rather than silently removing checks.

1. Clarify the product surface

   Identify the product name, audience, primary promise, concrete capabilities, constraints, proof points, and expected call to action. If the user provides a product image or reference image, infer visible materials, form, style, category, likely buyer concerns, and differentiators before writing page sections. If the user provides an existing page, inspect the current structure before proposing changes.

2. Shape the page architecture

   Build a scannable narrative: first-viewport identity, practical value, capability sections, examples or use cases, trust/proof, limits or requirements when relevant, and a clear next action. For an ecommerce page set, organize the story into deliberate screens with one main job per screen, but vary the information weight across screens. Not every screen needs a campaign-style headline and subtitle; some screens should use smaller guide copy, explanatory paragraphs, labels, badges, callouts, ingredient/detail notes, comparisons, or scene captions. Avoid generic marketing copy that could describe any product.

   For image-led ecommerce page sets, make the first screen establish 2-4 core claim seeds. Later screens should unpack, prove, visualize, or contextualize those seeds instead of introducing unrelated new selling points. If a later selling-point screen cannot be traced back to a first-screen seed, revise that seed or screen job. Buyer-service modules may instead answer a distinct practical question without introducing a new promotional claim.

3. Match the existing project

   Read the repository structure, framework, routing, component conventions, design tokens, asset strategy, and local styling patterns before editing. Reuse existing components and utilities when they fit.

3. Design for product comprehension

   Make the product itself a first-viewport signal. Use screenshots, generated visuals, product mockups, demos, or domain-relevant imagery when appropriate. Keep operational tools dense, restrained, and easy to scan; use more expressive visuals only when the product category supports it.

4. Implement the page

   Edit the smallest reasonable set of files. Keep content, layout, and interaction states complete enough that the page feels like a real product surface, not a placeholder. Respect existing frontend guidance for accessibility, responsiveness, and visual hierarchy.

5. Verify with real rendering

   Start the app when needed. Check desktop and mobile viewports with screenshots or browser inspection. Fix text overflow, overlapping elements, blank media, awkward crop/framing, one-note color palettes, missing states, and layout shifts before handing off.

## Image Generation Workflow

Keep shared visual style separate from page layout. The approved written rules define visual tone;
the ordered blueprint controls the set's reading rhythm. Resolve each page's subject,
view/scale, focus and image-copy relationship from its actual content using the existing
planning fields. Do not propagate one reference image's header/frame/text-box arrangement to every
page. Review meaningful composition differences in the existing plan and again after the
whole batch, allowing deliberate repetition when it serves comparison. See
[Visual planning](references/visual-planning.md) for the concrete checks. No fixed set of
page types, decorative motif, palette or additional generation/approval stage is required.

The steps below describe the normal image route. The Execution Contract's explicit stage delegation/waiver rules take precedence for the named stage only; do not reintroduce a waived stop through a reference checklist.

Use this workflow for ecommerce page-image sets. Read [Starcanvas execution](references/starcanvas-execution.md) when preparing execution. The Agent supplies final approved prompts and ordered references; Starcanvas executes them unchanged and returns files for Agent review.

For reference interpretation, composition choices, screen-prompt writing and visual review, read [Visual planning](references/visual-planning.md). Reuse the existing blueprint fields. Use [Layout preview](references/layout-preview.md) for the normal plan-and-sketch review, and the required [editable HTML](references/copy-review-editor.md). Run `scripts/prepare_review.py` and open its `review.html`; static previews are supplementary. This is the first confirmation package, not an additional gate. Honor an explicit request to skip sketches or use another review format.

1. Analyze inputs

   Describe the product image and reference style separately. List observed product facts, inferred selling points, and unknowns that should not be invented.

   Before planning, briefly invite any existing reference detail page, style image, written style preference and confirmed product information together, only if not already supplied. Reuse accessible earlier inputs. No external style reference is required: if none is supplied or the user delegates direction, proceed with an Agent-proposed direction based on the product. Do not repeat questions or require a questionnaire. Distinguish visible facts and creative suggestions from unknown specifications.

   When a reference image contains a strong character, model, mascot, hand, prop, or scene language, treat it as part of the reference style DNA if it supports the user's requested style. Preserve the visual language at an abstract level, such as 3D cartoon character presence, friendly brand host, hand-held product reveal, low-angle lifestyle shot, or macro annotation style. Do not copy the reference image's original brand, exact person identity, text, or product.

2. Produce the page blueprint first

   First define the whole-page tone in `visual_master_spec`: dominant background color and brightness, supporting/accent color roles, lighting/materials and type hierarchy. Then output the per-screen blueprint before generation. Preserve the confirmed page count; default to 8 screens when unspecified. Final pages use the confirmed ratio; default to 9:16 only when none was specified. The legacy field `visual_master_spec` stores shared written visual rules; its name does not require generating a master. The blueprint must include these fields for each screen: `slice_id`, `buyer_question`, `module_type`, `module_label`, `claim_seed`, `screen_job`, `evidence_type`, `content_density`, `layout_archetype`, `copy_module_type`, `copy_structure_pattern`, `primary_module`, `secondary_modules`, `text_exact`, `hierarchy_strategy`, `composition_shift`, `visual_composition`, `reference_style_notes`, and `risk_unknowns`. Present the design and copy in the editable HTML review for the first confirmation before generating the final page set. Open it with the host browser/file-open tool or the script's default browser launcher; verify text editing and export controls are visible. Always provide the absolute HTML path/link. If opening is blocked, give the path and say it was not opened; pause for the user to open/review it, rather than substituting a PNG.

   First define the screen-01 `claim_seed` set before writing later screens. Use 2-4 short seeds such as visible ingredient/detail, texture promise, usage moment, trust cue, convenience, or emotional hook. Each later selling-point screen must name the seed it is expanding. Buyer-service modules such as size tables, care instructions and returns may use `claim_seed: null` with a distinct buyer question; do not force those facts into the hero. Do not introduce a later-screen selling point that was not seeded on screen 01 unless the user explicitly asks for a new chapter.

   Treat these fields as planning controls, not visible labels. Do not write internal labels such as `module_type`, `detail`, `parameter_trust`, `FAQ`, or `screen_job` into visible page copy. Convert them into natural buyer-facing Chinese copy.

   Do not force every screen into the same `headline + subtitle` structure. Reserve the strongest headline/subtitle treatment for the first screen or other true section openers. Later screens should choose copy modules based on the section's job: explanatory text, small guide title, label clusters, icon notes, proof callouts, ingredient/detail annotations, scenario captions, comparison rows, trust bullets, or closing CTA. The copy structure should drive layout variation and hierarchy.

   Assign a distinct `copy_structure_pattern` to each screen or at least avoid repeating the same pattern in adjacent screens. Examples: `hero_claim_stack`, `question_answer`, `single_line_with_labels`, `annotation_map`, `three_point_breakdown`, `scene_caption_cluster`, `mini_steps`, `trust_checklist`, `quiet_closing`. Different patterns should change sentence rhythm, visible text keys, line count, and layout behavior, not just rename the same headline/body structure.

   Before asking for approval, audit copy differentiation, seed continuity, and copy structure variety. Each screen must answer a different buyer question and carry a distinct copy role, while still tracing back to the first-screen claim seeds. If adjacent screens are interchangeable when read without images, rewrite the plan. If a later selling-point screen feels like an unrelated promotional topic, rewrite it; buyer-service modules remain exempt from promotional seed continuity. If three or more screens share the same sentence rhythm, such as `headline + one explanatory sentence + three tags`, rewrite their `copy_structure_pattern`. Do not let every screen repeat the same taste, quality, convenience, or emotional promise with minor wording changes.

   Choose information density from the screen's job and available evidence. Use one primary focus and supporting modules where they help understanding; 2-4 content points can suit a detail/information page, while a scene or closing page may be sparse. Do not fill a percentage or point-count quota with invented or repeated copy. If evidence is insufficient, propose a scope adjustment before approval rather than silently changing an approved count.

   For the normal sketch review, supply `layout.blocks` inside the same blueprint, referencing `text_exact`. Keep the existing 19 planning fields; geometry is only the rendering extension, not another questionnaire. The script does not plan, rewrite copy, approve or generate. After geometry checks, run `prepare_review.py` to deliver the actual editable first-review page; do not stop after `render_layout_preview.py`. Resolve overflow, omitted copy and accidental overlap before first confirmation. Adopt exported edits as the current copy and recompile affected prompts. New manifests bind the adopted revision with approved_plan (path/hash/actual approval evidence); the compiler checks page coverage and exact copy as described in the execution reference.

3. Execute approved page images through Starcanvas

   Copy determines image content: material copy needs fabric/texture views; waistband, seam or label copy needs that exact part in close-up; whole-product views belong to identity, overall form or color comparison pages. Name the subject and shot scale before writing the prompt. Missing detail assets require a clearly scoped concept treatment or a request for the relevant asset, never a fabricated factual close-up or a silent replacement with a whole-product photo.

   The Agent writes one final prompt per screen, preserving the approved count and ratio. Each screen must follow the approved blueprint exactly: do not change `module_type`, `screen_job`, `evidence_type`, `content_density`, `primary_module`, `secondary_modules`, or `text_exact` during prompt writing. Each screen must carry 2-4 content points when appropriate, with one primary module plus secondary modules from the approved structure. Do not simplify every screen into the same headline and hero image.

   Execute approved tasks through Starcanvas MCP. Submit independent ready tasks concurrently by default; tasks that need a newly approved reference must wait. After design approval and machine checks, batch-submit the whole approved final-page set (`ready_stage=production`) rather than waiting for a trial pair or each image in turn. Respect actual service concurrency limits and record any reason for smaller batches. Attach the exact references with replacement, never appending old-stage images. Export one current snapshot and run `readback-export` to check the batch's generator and effective workshop prompts, input order and settings before submitting, then verify actual new original files and return them to the Agent. Technical execution success does not assign visual approval.

   After design confirmation, submit all confirmed final screens together using product material only and independent per-page chains. Do not pause after the first two pages for an internal visual decision. When the set finishes, inspect each original and the ordered vertical preview: shared color/light/type/margins, product identity, exact approved copy, distinct page roles, and image-copy correspondence. Do not score resemblance to the master. Repair only the affected pages within the actual previously authorized scope and generation count. Reuse explicit repair authority without asking again; ask before additional paid requests beyond that scope or a change of approved direction/content. Local collection recovery, inspection and packaging do not add an approval gate or authorize regeneration. A small trial batch is optional only when explicitly requested by the user.

4. Prepare image delivery

   Deliver ordered individual page images with consistent product identity, typography, palette, and content sequence. Maintain product color, shape, brand marks, and distinctive components. Always create an internal ordered vertical review preview using `scripts/compose_ordered_preview.py`; it may scale copies for inspection and must preserve originals. Deliver a combined long image only when requested. Neither review nor concatenation implies a seamless scene.

5. Agent review and revision

   The Agent checks the final ordered vertical preview as well as each original: dominant background color/brightness, neighboring color-area changes, material/light language and typography must read as one page system. Variation in crop, viewpoint, copy position and density must respect the shared written visual rules while serving the current copy. Compare the generated set directly; the master is not the review benchmark. Also check product, required copy, readability, dimensions and unsupported claims. Passing separate images does not establish whole-page approval. Physical edge matching is not required.

   Route revisions to the smallest responsible layer:

   - Model-rendered typo, missing glyph or garbled text: keep the approved `text_exact` unchanged; correct the generation instructions or use an explicitly authorized text-area repair. Do not change approved wording to match a model mistake.
   - A genuine requested copy revision: update `text_exact` only under the user's actual approval or delegated editing scope, invalidate affected prompts and regenerate only the affected pages within generation authority.
   - Product identity, orientation, color, shape, logo, or component failure: strengthen the product-reference constraint and regenerate only the affected screen.
   - Single-screen hierarchy or clutter failure: revise that screen's `primary_module`, `secondary_modules`, `content_density`, `copy_structure_pattern`, or `hierarchy_strategy`.
   - Content-sequence failure between pages: revise affected screen roles or copy while keeping approved unaffected pages.
   - Repeated visual grammar across several screens: revise `composition_shift` for those screens; keep the approved narrative and unaffected screens.
   - Set-wide style drift: compare generated pages with one another and inspect their shared written visual rules. Repair the outlier prompts/pages. If the approved design direction itself must change, return to the affected confirmation; do not use master-image similarity as acceptance.
   - Whole-page narrative or claim-seed failure: return to the blueprint. Use full regeneration only when the approved story itself changes substantially.

6. Capture reusable iteration lessons

   When the user asks to iterate the skill itself, when a repeated failure pattern appears, or when a completed run produces a reusable lesson, follow `references/self-iteration.md`. Create a concise `iteration_report` with the observed issue, responsible layer, proposed durable fix, and skill files that would change. Do not edit skill files until the user approves the proposed patch scope.

7. Deliver the image set

   After generation, revision, and final audit are complete, save the approved image set without adding a separate destination-confirmation step. If the user has already provided a destination, use it. Otherwise, create a clearly named delivery folder under the current workspace, such as `outputs/product-detail-page/<product-name>-<timestamp>/`. If there is no usable workspace, create the delivery folder beside the working source assets or in the active working directory. Preserve the original generated files.

   Deliver every approved individual page with clear sequential filenames. Include supplied or approved style references and a sample/contact preview only when part of the requested package or useful for review. Internal vertical review is required; a combined long-image deliverable remains optional on request. Do not include rejected or superseded variants unless the user explicitly asks for all iterations.

   After all visual checks and final file selection, run the accounting step in [Delivery accounting](references/delivery-accounting.md). Include the initial run, every repair run and any requested preview chain. Report final delivered images, cumulative saved generated images and confirmed generation tasks. Include actual net star coins only when the complete actual total is verified. Otherwise omit the cost line entirely from the user-facing delivery and response; do not add an unavailable-cost warning or estimate charges from image count or account balance changes.

   Verify that every requested file exists in the delivery folder. Report the delivery path, reviewed status, and unresolved issues. Do not ask for a save path after generation is already complete. Use sequential names such as `product_screen_01.png` through the requested count; distinguish review previews from original deliverables.

## Page Principles

- Make the first screen answer: what is this, who is it for, and why does it matter now?
- Prefer concrete capability language over vague adjectives.
- Let examples, parameters, screenshots, comparisons, and workflows carry credibility.
- Avoid nested cards, decorative blobs, generic gradients, and hero sections that hide the actual product.
- Keep headings proportional to their containers; do not use hero-scale type inside compact panels.
- Use stable dimensions for fixed-format UI such as tabs, toolbars, media frames, grids, counters, and feature tiles.
- Treat mobile as a first-class page, not a compressed desktop afterthought.

## Content Checklist

- Product name and category are visible immediately.
- Primary CTA matches the user's intended business or workflow goal.
- Capabilities are specific enough to be testable or recognizable.
- Sections are ordered by user decision flow, not by internal feature inventory.
- Technical claims include constraints, assumptions, or usage context when needed.
- The page includes enough concrete examples for a new visitor to understand the product.
- Consumer-facing copy and final images may contain specifications, certifications, discounts, awards and measured parameters only when supported by supplied evidence. Unknowns belong in internal `risk_unknowns` or clearly labelled planning placeholders, never as invented factual placeholders in `text_exact` or delivered images.

## Implementation Checklist

- Inspect existing components, routes, and styles before adding new abstractions.
- Use assets that show the product, output, workflow, or real subject matter.
- Confirm images, videos, canvases, or generated visuals render correctly.
- Check at least one desktop and one mobile viewport for overflow and overlap.
- Run available build, lint, or tests when the project provides them and the change scope warrants it.
- Report the local URL or file path the user can open.

## References

Read `references/detail-page-patterns.md` when choosing section patterns, adapting the skill to a specific product category, or reviewing whether a page structure is complete.

Read `references/self-iteration.md` when the user asks DetailFlow to improve itself, learn from a completed run, or convert observed failures into reusable skill rules.


## First-review completion check

Before calling the design stage ready, confirm: `review.html` exists, editable copy and export controls are present, an open attempt or host-open action is recorded, and the user has the actual HTML link. `review-receipt.json` records file/source hashes; it is not approval and a launch request is not proof the browser displayed the page. New copy-led task manifests require `review_delivery` as described in the execution reference. Only an explicit user request for another review format or waiver permits `kind: user_alternative`; do not infer that exception from model limitations or a general request to continue. Stage delegation alone does not replace the editable artifact with an image.
