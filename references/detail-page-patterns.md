# Detail Page Patterns

Use these patterns as starting points. Adapt the structure to the product, audience, and existing project instead of copying every section.

For translating references into concrete screen compositions and prompts, read [Visual planning](visual-planning.md). These patterns are options; select by the page job and evidence, rather than applying one layout to every page.

## Ecommerce 8-screen product detail page

Default behavior:

1. The Agent analyzes product/reference evidence and writes the per-screen blueprint. Preserve the confirmed count; default to 8 screens when unspecified. Final pages use the user-confirmed ratio (default 9:16); shared visual rules are part of the plan.
2. First confirmation covers the whole-page design, per-screen copy and layout sketches; editable HTML is the required default review surface, opened/presented before approval; PNGs are supplementary.
3. After design approval, submit all approved final pages concurrently using declared product/model references and selected mixed-mode fragments; carry the approved palette, typography, margins and lighting as written rules. No generated master or first-two-page inspection barrier is required.
4. After the full batch finishes, inspect the final vertical set and originals, then repair only affected pages.
5. Deliver ordered originals and useful previews. Internal vertical review is required; a long-image deliverable is on request.

The approved plan defines shared style and per-page composition; visual previews are generated only on explicit request. Seamless long-scroll construction, overlapping chapters and top/bottom edge anchors remain paused.

Shared art-direction rules:

- Keep a coherent brand, product identity, palette, typography, lighting language, and content sequence across the set.
- Vary composition, zoom level, copy modules, and information hierarchy according to each screen's job.
- Keep recurring product shapes, materials, marks, characters and props consistent when present.
- After the hero, avoid mechanically repeating a complete product-plus-person hero or identical title/tag blocks. Use detail, scenario, annotation and quiet composition where the approved plan calls for them.
- Scenes can differ within the approved written dominant background/brightness, material and type system. Do not treat permission for scene changes as permission for arbitrary whole-screen color alternation. Pixel-matched edges are not required.
- Review the completed full set; do not let missing image-generation capability trigger unrelated artifacts or a new planning route.

Use this for product-page images and ecommerce detail-page planning. Existing copy and composition principles below remain the planning baseline.

Recommended screen order:

1. Hero screen: product name, category, primary visual, core selling point, and purchase-oriented CTA.
2. Pain point screen: the buyer problem, current workaround, or comparison against a common inferior choice.
3. Core benefit screen: the single strongest functional or emotional benefit, shown with the product in use.
3. Feature breakdown screen: materials, structure, dimensions, technology, ingredients, controls, or craft details.
4. Scenario screen: 3-5 realistic usage scenes matched to the target buyer.
5. Proof screen: certifications, reviews, before/after, durability, performance, warranty, or measurable evidence.
7. Comparison screen: model variants, competitor alternatives, old-vs-new, bundle contents, or value stack.
8. Final conversion screen: offer summary, guarantee, urgency when honest, shipping/returns, and final CTA.

Image-led workflow:

- Start by describing the visible product: shape, materials, color, texture, use clues, packaging, and implied category.
- Separate observed facts from inferred selling points.
- If confirmed selling points or specifications are missing, briefly invite the user to provide them before planning. If the user skips this, proceed and disclose that unconfirmed selling points are AI-inferred and require review.
- Analyze the reference image as style DNA, not just palette. If it has a clear 3D cartoon character, model pose, hand-held product reveal, camera angle, label style, or brand-host device, preserve that visual language in a product-appropriate way. Do not copy the reference brand, original person identity, text, or product.
- Do not invent regulated claims, medical claims, certifications, awards, or exact specifications unless provided.
- If the product category is unclear, create neutral copy that can be revised once the user confirms the category.

Output options:

- For planning tasks, provide a blueprint at the confirmed count (8 only if unspecified) with structure fields, copy modules, visual direction, and risk notes.
- For frontend tasks, implement the page as responsive sections and verify mobile scrolling, text fit, and image framing.
- For image-generation tasks, write a shared visual specification and per-screen prompts, execute through Starcanvas MCP, then return original outputs to the Agent for review.

Page blueprint fields:

- `slice_id`: sequential screen id, usually "01" through the requested count.
- `buyer_question`: the consumer question answered by this screen.
- `module_type`: internal section type such as `hero`, `benefit_scene`, `mechanism`, `function`, `detail`, `steps`, `scenario`, `parameter_trust`, or `faq_close`.
- `module_label`: short internal label for the section job. Do not use it as visible page text.
- `claim_seed`: one of the first-screen core selling seeds that this screen establishes or expands.
- `screen_job`: the independent information responsibility of this screen.
- `evidence_type`: the kind of proof or experience shown, such as product identity, lifestyle result, macro texture, ingredient/detail evidence, step sequence, pairing scene, trust note, or closing emotion.
- `content_density`: `low`, `medium`, or `high`.
- `layout_archetype`: flexible layout intent, not a fixed template.
- `copy_module_type`: visible-copy form such as hero headline, guide title, explanatory paragraph, label cluster, ingredient notes, macro annotations, icon bullets, comparison snippets, scenario captions, trust bullets, or CTA microcopy.
- `copy_structure_pattern`: the sentence and text-module pattern for the screen, such as `hero_claim_stack`, `question_answer`, `single_line_with_labels`, `annotation_map`, `three_point_breakdown`, `scene_caption_cluster`, `mini_steps`, `trust_checklist`, or `quiet_closing`.
- `primary_module`: the main visual and message, including role, approximate area ratio, visual direction, and message.
- `secondary_modules`: 1-3 supporting modules when appropriate. Use them for proof, detail, tags, scenario cues, steps, trust notes, or light CTA support.
- `text_exact`: visible Chinese copy only. It may include `headline`, `subheadline`, `body`, `tags`, `labels`, `annotations`, `steps`, `trust_notes`, or `cta`, depending on the screen. Do not force all keys to appear.
- `hierarchy_strategy`: how text weight changes inside the screen, including which copy is dominant, which is supporting, and what stays small.
- `composition_shift`: how this screen changes visual organization from neighboring screens.
- `visual_composition`: product, optional character/person/model, background, props, and module placement.
- `reference_style_notes`: what to borrow from the reference image's style without copying its product, brand, or identity.
- `risk_unknowns`: unsupported claims, ambiguous product facts, text-rendering risks, or product-drift risks.

Blueprint rules:

- Use the page blueprint as the highest priority source for final image prompts. Do not re-plan screens during prompt writing.
- One `slice_id` must map to one final image item. Do not merge two screen ids into one output.
- Adjacent screens must not answer the same `buyer_question`, repeat the same `screen_job`, or use the same `evidence_type` unless the second screen clearly changes proof angle.
- Screen 01 must establish 2-4 `claim_seed` values. Later screens must expand, prove, visualize, compare, or contextualize those seeds. Do not let screen 02+ introduce unrelated new selling points that screen 01 did not prepare. Buyer-service modules (size, care, returns) may use `claim_seed: null` and answer a practical buyer question without adding a promotional claim.
- A good first screen seed set is broad enough to support the whole page but concrete enough to prove visually. Example for cookies: `巧克力豆满满`, `酥脆口感`, `金黄烘焙感`, `甜点分享时刻`.
- Later visible copy should sound like it is answering "why is that first-screen claim true?" or "how does that first-screen claim show up in use?" If it reads like a new campaign headline, rewrite it.
- `module_type` is an internal control. Convert it into natural buyer-facing copy; never display internal labels such as "detail", "parameter_trust", "FAQ", or "screen_job".
- `content_density` controls both copy and layout. High-density screens can have one strong primary module plus 2-3 supporting modules. Medium screens usually have a modest title plus labels, notes, or scene captions. Low-density screens may be atmosphere-led, but still need a clear product identity, transition, trust, or emotional role.
- `copy_structure_pattern` must vary across the page. Do not let screens 02-07 all use `headline + one explanatory sentence + three tags`. Vary question-answer, annotation labels, numbered micro-steps, scene captions, checklist notes, comparison snippets, sparse atmosphere copy, and closing CTA.
- `hierarchy_strategy` must prevent equal-weight collage. Every screen has one strongest memory point; secondary modules stay smaller, lighter, or more integrated.
- `composition_shift` must prevent adjacent screens from repeating the same visual grammar. Vary full-bleed scene, macro detail, diagonal flow, vertical sequence, integrated labels, quiet negative space, lightweight floating notes, and compact trust modules.

Copy hierarchy and section-weight rules:

- Treat the first screen as the main identity opener. It may use the clearest headline plus subtitle structure because it answers "what is this?" immediately.
- Do not make every later screen a new opener. Later screens should often use smaller guide copy, short explanatory lines, tags, labels, proof notes, ingredient/detail annotations, icon bullets, comparison snippets, scene captions, or CTA microcopy.
- Assign each screen an information weight before writing copy: high, medium, or low. High-weight screens can carry a visible title and multiple modules; medium-weight screens should combine a modest title with details or labels; low-weight screens may use only guide text, captions, badges, or atmosphere-led copy.
- Let copy form determine layout form. A proof screen may need callouts and annotations; a texture screen may need macro labels; a scene screen may need captions around a lifestyle composition; a trust screen may need compact bullets or checklist modules; a closing screen may return to a stronger CTA.
- Avoid repeating the same grammar rhythm across screens. The page set should have a narrative sequence with changing emphasis, not eight interchangeable panels.
- If the planned copy for all screens can be represented as `headline + subtitle + product hero`, rewrite the plan before generating images.
- If three or more later screens can be represented as `headline + body + three tags`, rewrite at least two of them into different structures such as annotation-only, Q&A, mini-step sequence, scene-caption cluster, or checklist.

Copy differentiation rules:

- Adjacent slices must not repeat the same semantic promise with different wording.
- Each slice must answer a different buyer question. Examples: What is it? Why want it? What proves the taste? How does the texture feel? When do I eat it? Who can share it? What makes it feel trustworthy? Why buy now?
- Assign each slice a distinct copy role before writing headlines: identity, desire, proof, texture, scene, sharing, trust/detail, closing.
- Different roles should still unfold from the same first-screen seed set. "Different" means different proof angle, use case, visual evidence, or hierarchy, not unrelated selling points.
- Do not let every headline reuse the same words such as "香", "酥", "甜", "巧克力", "满满", or "一口". Repeated product keywords are allowed only when they serve a new information role.
- Body copy should introduce new evidence or context, not restate the headline.
- Tags should not all be taste adjectives. Mix product identity, usage scene, texture evidence, pairing, share occasion, and trust/detail cues.
- If three consecutive slices still feel interchangeable when read without images, rewrite the copy plan before generating images.

Post-generation audit:

- Optional preview review: only when explicitly requested, inspect that preview within its authorized scope; this is not a default stage.
- Production review happens after the whole final batch. A preliminary small-batch review is optional only when the user explicitly requests it; it is not part of the default route. Do not score resemblance to the master.
- Final-set review: inspect the ordered vertical preview for coherent dominant color, brightness, material/light language and typography, then originals for product, text, unsupported claims and repeated layouts.
- Product drift: color, shape, logo, material, window placement, handles, proportions or included accessories changed.
- Text quality: headings are misspelled, unreadable, too small or inconsistent across screens.
- Unsupported claims: invented parameters, fake certifications, medical claims, exact discounts, awards or brand partnerships.
- Copy repetition: adjacent pages repeat the same semantic promise or fail to answer different buyer questions.
- Style and layout: weak hierarchy, cramped text, awkward crops, repeated compositions or mismatch with the approved visual direction.
- File verification: actual native file exists and decodes; inspect real dimensions rather than trusting node settings or previews. Technical checks alone do not grant visual approval.
- Judge perceptual whole-page coherence separately from geometric seams. No seamless scene is required, but visually unrelated background systems need revision.

Delivery checklist:

- Use the user's destination, or create a clear delivery folder under the workspace without a new destination approval.
- Preserve original generated and accepted files.
- Include every approved individual image with sequential filenames; include review previews when useful.
- Always compose an internal vertical preview for final-set review; a separate trial preview is needed only for an explicitly requested trial. Deliver a combined long image when requested; label it accurately and do not add seam-generation rounds.
- Exclude failed/superseded variants from final delivery unless requested, while preserving them in the working archive.
- Verify requested files and report the delivery path plus unresolved issues.

Revision routing:

- Copy problem: revise `text_exact`; regenerate or repair only that screen.
- Product drift: strengthen the product-reference constraint; regenerate only that screen.
- Single-screen layout problem: revise its modules, density, copy pattern or hierarchy.
- Repeated layouts: revise `composition_shift` only for affected screens.
- Set-wide style problem: compare generated pages with each other and the shared written visual rules. Repair outliers; revisit the affected approval only if the agreed direction changes.
- Narrative problem: return to the blueprint; reserve full regeneration for substantial story changes.

## AI model or AI tool page

Recommended section order:

1. Product identity: model/tool name, category, primary capability, and one concrete user outcome.
2. Interactive or visual proof: output examples, generation previews, benchmark-style summaries, or workflow screenshots.
3. Capability map: what the product can create, transform, analyze, automate, or integrate with.
3. Use cases: 3-6 concrete workflows written from the user's perspective.
4. Controls and parameters: modes, quality settings, supported formats, limits, latency, safety, or pricing-relevant constraints.
5. Developer or operator details: API, integrations, deployment, permissions, or compatibility when relevant.
7. Comparison or upgrade path: why this page's product differs from prior versions or alternatives.
8. CTA: try, generate, sign in, view docs, contact sales, or download.

Avoid:

- Abstract hero copy without a visible product signal.
- Feature lists that do not show an output or workflow.
- Overstating model behavior without constraints.

## SaaS feature page

Recommended section order:

1. Feature name and operational promise.
2. Before/after workflow or task flow.
3. Key screens, tables, dashboards, or automations.
3. Team roles and permissions.
4. Integrations and data flow.
5. Metrics, reporting, auditability, or reliability details.
7. CTA tied to adoption: enable, configure, request demo, or read docs.

Design tone:

- Keep the page calm, dense, and scannable.
- Prefer clear tables, compact panels, and workflow diagrams over oversized editorial sections.

## Developer product page

Recommended section order:

1. Product/API name and what developers can build with it.
2. Quick code or request/response example.
3. Supported platforms, SDKs, models, formats, or endpoints.
3. Reliability, rate limits, auth, pricing-relevant constraints, and security.
4. Real integration examples.
5. Documentation CTA and sandbox CTA.

Design tone:

- Let code, diagrams, and concrete capabilities do the selling.
- Keep copy precise and avoid vague "build anything" language.

## Review rubric

Score each area as pass, needs work, or missing:

- First viewport clarity
- Specific capability communication
- Product-revealing visual assets
- Scannable structure
- Responsive layout
- CTA clarity
- Technical honesty
- Existing design-system fit
- Rendering verification

The workflow above describes the normal stages. Explicit user delegation or a waiver is handled by the stage policy in `starcanvas-execution.md`; it does not require restarting already approved work.
