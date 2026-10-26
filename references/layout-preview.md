# Deterministic planning preview

Purpose: show an Agent-authored page plan before paid generation. The renderer has no
network calls, model calls, automatic planner, editor UI, or generation/approval buttons.
It emits page PNG wireframes, a contact board and `layout_report.json`.
The normal first confirmation requires the HTML copy-editing interface; PNGs alone are not sufficient. After geometry checks run `scripts/prepare_review.py`; read
[Copy review editor](copy-review-editor.md). It uses this same plan and renderer.

Use it for the normal design-plan and sketch package before the first confirmation. Honor
an explicitly waived sketch or alternative review format. It adds no separate approval gate.
The output is not a generated product image, not a long-scroll master, and not a replacement
for the Starcanvas stage. Keep preview files separate from final delivery images.

## Input

Reuse the normal blueprint's `slice_id`, `module_label`, `layout_archetype`, `text_exact`
and other planning fields. Add `layout.blocks` for the normal sketch preview; plans from
legacy runs or an explicitly waived sketch may omit this rendering extension.
The script does not assign layouts based on headings or auto-fill every screen with the
same card template. Agent-selected geometry controls each page.

Root fields:

- `title`: review-board title, not product copy.
- `aspect_ratio`: confirmed default for these pages, fixed `9:16` for final pages.
- `design_width`: coordinate/font design width, normally 720.
- `pages`: normal ordered blueprint entries. A page may override `aspect_ratio`.

Every block has a unique `id`, a `type`, and a normalized `box: [x, y, width, height]`.
All values are relative to that page, within 0..1. Blocks are positioned by the Agent.

| Type | Fields | Meaning |
|---|---|---|
| `text` | `copy_key`, optional `font_size`, `color`, `align` | Exact string from `text_exact`; `copy_key` can be `headline` or `labels.0` |
| `image` | local `path`, optional normalized `crop`, `label` | Existing reference placed proportionally, using contain; no new image is fabricated |
| `placeholder` | optional `label` | Explicit visual region such as person/environment when no source image is available |
| `annotation` | `copy_key`, `target: {block_id, uv: [u,v]}`, optional text style | Label and a leader ending on a visual block; `uv` is relative to its displayed image/crop |
| `sketch` | `components` | Borderless relationship sketch; see below |

`font_size` is in design-width pixels. Rendering at another width scales the preview
proportionally. Optional `overlap_with: [other_block_id]` declares a deliberate overlap,
such as a foreground product over a scene region. Other box intersections are flagged.
This declaration is a planning choice, not proof that final image text will remain readable.

Example block:

```json
{"id":"headline","type":"text","copy_key":"headline","box":[0.08,0.12,0.84,0.18],"font_size":52}
```

All leaf strings in `text_exact` must be placed once. The renderer does not shorten copy,
invent selling points, shrink fonts until they become unreadable, or silently discard text.
An overflow requires a geometry revision or an explicitly approved copy change.

## Run

Requires the existing Pillow dependency and a local font with the needed language glyphs.
Windows defaults to Microsoft YaHei; another environment can pass `--font`.

```text
python scripts/render_layout_preview.py examples/layout-preview.json NEW_OUTPUT_DIRECTORY
```

Optional flags: `--width 720`, `--columns 3`, `--font ABSOLUTE_FONT_PATH`.
Use a new revision folder each time; the script refuses to overwrite an existing output folder.
Relative image paths are resolved beside the input blueprint. Remote image URLs are not fetched.

For ordered vertical inspection of existing sketch PNGs or generated originals, save
`{"images":[{"id":"01","path":"page01.png"},{"id":"02","path":"page02.png"}]}`
as a JSON file and run `python scripts/compose_ordered_preview.py ORDER.json NEW_OUTPUT`.
Paths resolve beside that manifest and the supplied list order is preserved; IDs are not sorted.
The preview is scaled for inspection, originals stay intact, and the report records hashes,
dimensions and vertical positions. Its status requires Agent visual review, not automatic approval.

## Checks and status

- Errors: missing geometry, unsafe/duplicate IDs, out-of-bounds boxes, unplaced or duplicated
  copy, unknown copy keys, missing assets, text overflow, undeclared overlap and invalid targets.
- Warning: identical block geometry across pages. The Agent decides whether this is purposeful.
- Errors produce a report and stop page rendering (exit code 2). A valid preview returns exit 0
  and `layout_ready_for_review`; it never grants visual approval or generation authorization.

The report preserves the exact placed strings and the input file hash. Review the PNGs as well:
font measurements and box checks cannot assess persuasion, true product geometry, photographic
quality, reference interpretation or artistic balance.

## Handoff to Starcanvas

### Scene relationship sketches

For a lifestyle scene, prefer a borderless `sketch` block when boxes would hide the
person/product/environment relationship. See `examples/scene-sketch.json`. Keep actual
copy in ordinary text blocks using `text_exact`; declare intentional overlap with the
scene block. This overlap declaration does not prove the drawing leaves text unobstructed:
the Agent must inspect the PNG. Components can overlap inside a scene and draw in list order.

Each component has a unique `id`, `kind`, and normalized `box` relative to the sketch block.
Available reusable symbols: `person_seated`, `sofa`, `window`, `neck_product`, `polyline`.
`polyline` accepts normalized `points` within its box for floors, tables or custom contours.
Optional `facing: left|right` mirrors the component. These are examples, not mandatory scene
ingredients. Do not force unsupported actions or product types into the seated-neck example.

Instead of a box, a component can use `attach_to: {component: person, anchor: neck}` and
`size: [width,height]`. Its center follows that anchor, including after mirroring. The seated
person exposes `neck` and `hand` anchors. Missing targets, cycles, unknown anchors, and
out-of-bounds components block rendering. Orange neck-product lines are a symbolic wearing
location, never the real product outline. Product photos remain the geometry authority.

The Agent specifies which relationships matter and what remains flexible: wearing/contact,
foreground/background and copy readability may matter; exact pose, furniture shape, camera,
lighting and photographic styling normally remain flexible unless approved otherwise.
Do not translate all sketch coordinates into hard generation constraints. If a sketch and
prompt disagree, resolve them against the approved plan before submission. Never automatically
send the sketch to the model. A user-authorized sketch-reference test must say that guide lines,
orange symbols and placeholder styling must not appear in the finished photograph.

Portability: copy this skill folder with both `scripts/render_layout_preview.py` and
`scripts/scene_sketch.py`, install Pillow in the target Python environment, supply a local
CJK font with `--font` when needed, and adapt asset paths. No Codex SDK or MCP is needed
to render. The receiving Agent's skill loading and Starcanvas connection are separate setup.

### Generation handoff

The Agent uses the reviewed plan to write screen-specific prompts. Final-page Starcanvas image inputs use product material only. Neither an optional approved preview nor the planning sketch is uploaded. Translate the approved geometry and content relationships into each page prompt, alongside shared written visual rules. If the user explicitly wants to test a layout
reference, label its role and forbid copying planning boxes/notes; inspect actual output for
layout drift. No pixel-exact reproduction is promised.

Use `scripts/compose_ordered_preview.py` with sketch PNGs to inspect vertical order when needed.
The three-page bundled example demonstrates hero, annotation and scene layouts. Its copy
and placeholder targets are illustrative, not product facts or required page counts.


An empty `layout.blocks` is an incomplete draft (`EMPTY_PAGE`), distinct from a missing layout schema. It preserves the requested page count and must be completed or explicitly replanned before approval. Text `align` supports `left`, `center`, `right`; unsupported values fail. Opaque Pillow RGB colors are normalized to six-digit hex for the HTML editor; transparent text colors are rejected.
