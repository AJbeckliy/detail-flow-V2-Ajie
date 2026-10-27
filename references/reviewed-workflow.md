# Current-product planning and reference contract

New jobs use `workflow=detail-flow-direct-v4`. Frozen v2/v3 jobs retain their existing contract for inspection and recovery. Do not downgrade a new job merely to skip the checks below. These records are filled by the Agent within the existing design-review step; they do not add user questionnaires or approval gates.

## Start each product independently

Use `scripts/product_brief.py NAME NEW_PLAN.json --assets PRODUCT_IMAGES --pages N --language LANGUAGE`. It produces a draft seed, not an approved plan. Without a current request, aspect ratio defaults to 9:16. An explicit ratio needs `--ratio 16:9 --ratio-evidence "current product request or actual reusable preference"`. Never copy another product's temporary ratio, count, language or folders.

Fill the normal blueprint into this draft. `product_context` records a fresh product_id, name, page_count, language, aspect_ratio, ratio_source and current product asset paths/hashes. The manifest repeats only `product_id`; the compiler binds the approved full plan, count, language, ratios and product sources. Language and evidence are declarations of the actual request, not proof supplied by a nonempty string. Do not manufacture approval or reuse an old product_id for a new product.

## Resolve the page before writing its prompt

Reuse `visual_composition`, `composition_shift`, `reference_style_notes`, `primary_module` and `secondary_modules`. State the actual subject, view/shot scale, visual focus and image-copy relationship. Add only one small display choice per page:

| product_display | Prompt instruction |
|---|---|
| primary | 本屏以商品为主视觉。 |
| secondary | 本屏商品仅作辅助识别，不得压过本屏主题。 |
| absent | 本屏不展示完整商品或包装，产品图仅用于身份核对。 |

Place the exact approved `visual_composition` and the corresponding display instruction in the prompt. They sit alongside the approved copy and shared visual rules. Do not prepend a large-packaging command to every page. Providing a product photo does not require displaying the entire product; detail pages may show only the named part, and ingredient pages may omit packaging.

For a numeric grid, draw independent numeric groups. For steps, draw separate step blocks. For a table, place headers and rows/cells so their relationships can be reviewed. Preserve exact copy when reorganizing text keys; do not rewrite claims. Use the existing text/layout blocks rather than implementing another editor. A neutral wireframe remains a composition plan, not a photographic promise.

## Resolve concrete planning warnings

Run `python scripts/planning_checks.py plan PLAN.json`. The HTML editor also shows initial planning warnings; exports must be checked again after edits. Checks flag repeated geometry, undivided multi-part copy, numeric/table/step pages without meaningful text blocks and generic identical reference notes.

Revise the plan, or record a specific reason for intentional repetition in `planning_review.decisions`:

```json
{"planning_review":{"decisions":{"repeated_geometry:02":{"action":"keep","reason":"Two product variants deliberately use matched positions for comparison"}}}}
```

A warning still present cannot be dismissed with `action: revised`. Revision removes the finding on the next audit; a valid remaining exception uses `keep` with its real reason. These checks detect concrete structural risks, not artistic quality. Do not report design or generation quality as passed merely because geometry is valid.

## Text-only and selected mixed references

Every page declares its actual ordered reference_images, including sha256 for each image and source_sha256 when a crop has a source_path. Freeze these before reviewing the plan; tasks must use the same paths, roles and purposes, and changed reference bytes invalidate that approval binding. First input is current product authority. Keep product, model identity and visual references distinct:

- `product`: genuine product source or a recorded crop of one of this product's sources.
- `model`: the supplied person/animal identity, only on pages needing that identity; include `purpose`.
- `style`: palette/material/light/type character; include `purpose` and an `exclude` list.
- `composition`: framing, scale, relative placement or visual focus; include `purpose` and an `exclude` list.

Default `reference_policy={mode: "text_only"}` accepts product and necessary model references. Style is translated to page-specific text, not a shared adjective repeated on every page. Optional `reference_policy={mode: "mixed"}` additionally permits the selected style/composition references already included in that page's approved plan. It does not require attaching them to every page.

Select complete visual modules from a long reference instead of one repeated long image or arbitrary fixed-height strips. For a crop, preserve `source_path`, normalized `crop_box: [x,y,width,height]` and the resulting image path; the compiler freezes both original and crop hashes. Hashes prove stable files, not that the crop was meaningful. Inspect the actual crop. Full-frame reference images do not need artificial crop coordinates.

Example reference entry, repeated in the approved page and task:

```json
{"role":"composition","path":"ingredient-reference.png","source_path":"long-reference.jpg","crop_box":[0,0.2,1,0.15],"purpose":"只借鉴食材近景的尺度与分组关系","exclude":["不迁移参考品牌、猫、配方、功效或百分比"]}
```

Put every non-product purpose and exclusion into the actual prompt. These are metadata and prompt constraints, not provider-enforced roles or weights. Do not invent weight/strength parameters. Record exact image order and verify the actual workshop inputs. Legacy product-only contracts remain unchanged; do not relabel visual references as product to bypass them.

Direct reference images are an optional strategy, not a proven universal improvement. For a comparison, keep product, copy, ratio, model, composition target and number of attempts equal; add only the selected reference and its role explanation. Preserve all outcomes. Do not generalize success rates from a few samples, or turn this experiment into a new mandatory trial stage.

## Readable visual review and repeated errors

Keep the ordered long preview for overall rhythm. `compose_ordered_preview.py` also writes groups of up to four pages in a two-column layout. Compare those groups, then inspect every original and zoom into critical text/parts. Do not rely on a long image reduced to a thin strip.

Use one review record for all layers: per page `technical`, `copy`, `product_identity`, `composition` are `pass`, `needs_revision` or `unverified`; include image_path, sha256 and concrete issues. `set_coherence` records the whole set separately. `user_accepted` plus actual user_evidence is separate from the Agent's review. Run `python scripts/planning_checks.py visual REVIEW.json` to check record consistency. It never approves an image or authorizes spending itself.

Inspect brand/model/specification numbers, visible key components and readable packaging text against supplied sources. Missing close-up evidence is not permission to invent hidden structure. A leaf-shaped clasp with new holes or dense veins is not a match just because it remains a leaf.

For a repeated issue, retain a stable issue code (for example `headline:睛->晴`), set `repeated: true`, and record `next_strategy` and `strategy_reason`. Options are `targeted_text_edit`, `prompt_or_layout_change`, `request_better_asset`, or `defer`. Repeating the same full-page prompt is not a new strategy. Confirm that the selected editing method actually exists; do not pretend a prompt-only edit guarantees unchanged pixels outside the text. Recheck the entire revised page and unaffected areas. Preserve approved wording; do not replace 点睛 with 点晴 to accept a bad render. Existing repair authority, page limits and same-canvas tracing remain in force.

Known defects keep the review at needs_revision. A user's choice to accept a test with notes remains separately recorded; it does not erase the defects or authorize another generation.
