# Offline copy and layout review

Required by default for the first design/copy confirmation in ecommerce image production; users do not need to separately ask for an editor. This is a
copy-and-layout editing interface for the normal plan-and-sketch confirmation, not another approval gate.

Build from the same plan used by the PNG renderer:

```text
python scripts/prepare_review.py PLAN.json NEW_REVIEW_FOLDER
```

Uses Python, Pillow, the existing renderer and its font discovery (`--font` supported).
The resulting HTML embeds the background images and plan; opening it needs only a modern
browser with JavaScript and download support. No server, SDK, model or network is involved.
The entrypoint requests a default-browser launch. Also use the host browser/file-open tool when appropriate and verify the page is visible; preserve existing HTML versions. Always provide its absolute HTML path. Do not claim it opened merely because launch was requested. The lower-level `build_review_editor.py` only builds HTML; it does not launch. The editor
template is `references/review-editor.html` and is not opened directly without a payload.

## User interaction

- Click copy to edit; drag its Move handle to reposition or its corner handle to resize. The inspector supports numeric position, size and font size. Arrow keys on the Move handle nudge; Shift increases the step.
- Select any block on the page or in the current-page module list, then Delete Selected Module. Text, image, placeholder, sketch and annotation blocks are deletable; undo restores them. Deleting a visual also removes annotations targeting it. Deleted text keys are removed without renumbering nested copy paths; same-source older exports remain importable.
- Add ordinary text with New Copy. Auto-height expands a box when copy grows, bounded by the page; Fit Content also permits shrinking. Existing imagery can be selected and deleted; its geometry stays fixed.
- Add a numbered comment by clicking Add Annotation then a page position. Move the pin if needed; comments live in `page.review_annotations` and are not consumer copy or generation authority.
- Undo/redo covers copy, geometry, added copy and comments. Overflow and overlaps are advisory, never prevent editing or export, and still require Agent review.
- Export creates a dated JSON download, not an overwrite or automatic project save. Confirm
  the browser has saved it. There is no automatic persistence: export before closing.
- Load exports from the same source hash. Text box geometry/font changes, new `user_text_N` blocks/copy keys, and `review_annotations` are allowed. Existing page metadata and retained source-image paths/non-text geometry remain fixed; original blocks may be deleted together with their copy. Invalid coordinates, duplicate IDs, changed source paths and foreign plans are rejected.
- Old copy-only exports of the same source still load. A revised source plan has a different hash: preserve old exports and ask the Agent to merge desired changes, rather than loading them blindly.
- Reset asks before discarding edits. Leaving with edits triggers the browser's unload warning
  where supported. Browser download completion cannot be confirmed by this offline page.

## Agent handoff: one authoritative copy

When the user supplies an exported JSON, read `review_state`, inspect its diff against the
source plan and verify the original source bytes match `source_plan_sha256`. The browser
guard is a convenience, not proof that an externally supplied file is trustworthy.
Review copy, geometry, new blocks and comments against the source plan. Comments remain review requests, not automatic instructions to execute or publish.
Confirm which changes the user wants adopted through the existing blueprint approval;
reuse explicit approval if already provided. Do not treat exporting as approval to generate.

Save an adopted revision separately. Its `text_exact` becomes the sole current copy source.
Update related blueprint fields when adopting new copy/geometry; do not leave prompts or secondary_modules pointing to the old arrangement.
Regenerate the PNG preview using `render_layout_preview.py` to check the saved JSON and
look at the output. Browser font metrics can differ from Pillow; neither proves final model
layout. If copy overflows, revise geometry or discuss copy, never silently truncate/shrink.

`prompts_require_recompile: true` invalidates previously compiled screen prompts. Rebuild
the affected prompts from the adopted copy, checking for old text in other planning fields.
Do not submit stale task manifests or prompts just because they remain in the JSON/project.
`generation_authorized: false` and `draft_needs_agent_review` are the export defaults.
After plan/copy/layout confirmation, compile and submit the complete final-page set directly. A later copy edit requires fit checking and prompt recompilation. A change to the agreed visual direction/hierarchy returns to the affected design decision; it does not automatically add a master or sample stage.
No transport utility is called by this editor.

For compilation, bind the adopted JSON as `approved_plan` with its exact SHA256 and actual approval/delegation evidence. Keep exported lineage metadata; export-time `generation_authorized:false` remains an export default, not a replacement for the external approval record. New compiled packages bind this revision and check approved page coverage and visible copy against the prompts. See `unified-executor.md` for task page IDs and representative master copy. Never generate this approval record by merely treating an export as user consent.

Original product asset paths are made absolute in exported JSON so a download in another
folder can be rendered on the same computer. Moving to another computer requires remapping
those paths; the embedded HTML previews still display independently of source asset paths.

## Checks

`test_review_builder.py` checks embedding, asset paths, literal script-like text, invalid
layouts and preservation. `test_review_editor.cjs` uses an existing Playwright installation
and browser executable to check the SKG demo in a real browser (it does not install packages):

```text
node scripts/test_review_editor.cjs REVIEW.html NEW_TEST_OUTPUT BROWSER_EXECUTABLE
```

The browser fixture expects the bundled three-screen demo with screen 03 `headline`; reset is checked against its actual initial value.
It exports test JSON and screenshots to the specified new folder. Use the JSON for a renderer
roundtrip. No generated product imagery is validated by these checks.

## Editor v2 checks

`node scripts/test_review_model.cjs [PLAN.json] [EXPORT.json]` tests bounded moves/resizes, new text, comment separation, source-bound import/export, invalid/immutable edits and script syntax without a browser. It does not verify real pointer events, CSS layout or downloads. Run the browser fixture only where browser access is permitted; never bypass a denied file URL policy. `test_review_builder.py` checks live annotation target metadata as well as embedded assets.


## Empty drafts and canonical display values

Deleting a block also removes retained `overlap_with` links to deleted blocks. Import can clean those links from same-source older exports, but cannot change live overlap targets or image paths. Deleting every block leaves the page in place as an incomplete draft: the editor warns and exports `review_state.empty_page_ids`; the renderer reports `EMPTY_PAGE` and does not produce approval-ready PNGs. Add content or obtain explicit approval to remove/replan the page; never silently reduce the confirmed count.

The builder converts supported opaque color names/short hex into six-digit RGB in its embedded plan. This is representation normalization, not a copy change; retain the source hash when reviewing the diff. Existing same-source editors can import their unchanged retained color values, while added text uses six-digit hex. Left, center and right alignment are shared with the PNG renderer.

When switching to another page or entering annotation-placement mode, the inspector clears its old text selection. Edits always belong to the selected module's page.


## Default delivery and blocked browser behavior

`prepare_review.py` produces `review.html` and `review-receipt.json`; the HTML contains the editable plan and export/import controls. Static PNGs can supplement but cannot replace it. On a headless host use `--no-open` only to avoid an impossible server-side popup, then deliver/open the HTML through the user's client. A remote server opening its own browser is not a popup on the user's computer.

If the host rejects opening local HTML, retain the file, provide its path/link and stop for the user to review. Do not work around a browser safety denial. Do not describe a PNG as editable or proceed to generation before actual design approval. Explicit user-selected alternative formats remain supported; record that authority instead of fabricating a receipt.

If the host cannot read MCP resources, do not claim `canvas://guide/workflow` was read. Report that capability gap and use an available current server guide with its source identified; a tool list alone is not the guide. Do not add client-specific installation or configuration steps to the creative workflow.

For remote Agents, provide a downloadable HTML or a host-supported interactive preview; a server-local absolute path alone is not delivery to the user. If no accessible editable entry point is possible, stop the dependent stage rather than silently presenting a PNG.
