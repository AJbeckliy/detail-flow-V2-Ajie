# Visual decisions and prompt writing

Use this during Agent planning, prompt preparation, and review of returned images.
Starcanvas generates final pages directly from the approved plan. A visual preview is generated only when explicitly requested. Seamless long-scroll construction remains paused.

## 1. Interpret evidence and references

Keep the product photo, confirmed product facts, and style references in separate roles.
Product geometry, components, marks, colors and visible materials come from the product
source. A style reference does not establish specifications, effects or certifications.

Reuse accessible references already supplied in the task. Inspect the full-page overview for
sequence and rhythm, then enlarge relevant sections for composition, materials and typography;
filenames alone are not evidence. For an explicitly requested preview, select only useful references or excerpts and identify their roles. For final-page generation, attach product material only and translate style decisions into written rules. Ask for missing files
only when the existing source cannot be accessed.

For each useful reference, extract only decisions that can affect this page set:

- Subject scale and camera distance: complete product, macro, person/product relationship.
- Text hierarchy and placement: dominant title, guide copy, annotations, body or captions.
- Information density and empty space: what occupies the page and what gets room to breathe.
- Light and materials: direction, softness, contrast, surface texture and shadow behavior.
- Composition and depth: asymmetry, foreground/background relationships and visual focus.
- Palette and type character: useful shared traits, not a copy of the reference's brand.

Connect each observation to a screen and a decision. For example: "The reference's large
product and short title suit the hero; its dense body text is not needed on the scene page."
Reuse `reference_style_notes`, `visual_composition`, `hierarchy_strategy` and
`layout_archetype`; do not add a second mandatory planning schema.

If no style reference is supplied, propose a direction from the product, buyer and content.
Mark it as an Agent proposal, not a reference-backed observation. Include it in the normal
blueprint confirmation rather than creating another approval stage.

## 2. Choose composition from the screen's job

Resolve the buyer question and evidence first, then choose a composition. The families
below are options, not three templates that every product must use.

| Family | Useful for | Decisions to make | Common failure |
|---|---|---|---|
| Product hero | Identity and the first reason to look | Full product or focal presentation; one dominant title; amount and position of support copy | Every page repeats the same centered product and headline |
| Detail / annotation | Explaining visible parts or a specific physical detail | Which source-visible area to crop; where labels fit; exact annotation endpoints; guide-title weight | Wrong target, invented hidden geometry, or a second generic hero |
| Scenario / editorial | A believable use moment or human context | Person/product/environment relationship; camera distance; where light copy is readable | Product pasted in without purpose, distorted wearing, or a repeated portrait pose |

Other approved page jobs can use other layouts. Do not turn a requested comparison,
instruction or specification page into one of these families merely to fit a preview tool.
Only include comparisons, steps and data for which the user has supplied adequate facts.

For every screen, settle one primary visual focus and its supporting information.
Choose density according to the job: a scene may be sparse; a detail page may need labels;
a proof page may need more information. Do not invent or repeat copy to meet a percentage
or point-count quota. If evidence cannot support the requested scope, propose a smaller
scope at the planning stage; never silently reduce an already approved page count.

Define one whole-page baseline before per-screen layouts: dominant background color and brightness, supporting/accent color roles, material/light treatment and type hierarchy. Record these in the existing `visual_master_spec`. A list of colors is insufficient; say where each is used. Routine variation changes framing and density, not the entire dominant background every screen. Any strong color chapter shift must be designed in the whole-page plan and confirmed. This is not a universal ban on contrast or a fixed beige palette. Use the
existing `composition_shift` and `visual_composition` fields to vary subject scale, camera
distance, text placement and density where the content calls for it. A detail page should
show the relevant part close enough to explain it; a scene should give the environment a
meaningful role rather than replace the hero's backdrop. A closing page can lower density.
These are design options, not a required four-screen sequence, color scheme or prop kit.

### Separate shared style from page-specific composition

Shared rules define palette roles, type character/hierarchy, product identity and the
photographic/material language. They do not prescribe one repeated header, image frame,
text-box position, subject size or mascot placement. A recurring character can identify
a chapter or explain an action; its presence on every page is not a default requirement.
Likewise, borderless imagery and left-aligned headings are options, not a replacement template.

Resolve each screen's visual task before its decorative treatment. In the existing
`visual_composition` field, identify what must be seen, the useful view/scale, the dominant
subject position and how copy relates to the image. Use `hierarchy_strategy` for the
reading order and `composition_shift` to explain a meaningful change from neighboring
screens, or why a deliberate repeat helps comparison. Do not add mandatory fields or quotas.

Read the ordered plan as a sequence inside the existing editable review: can the viewer
distinguish page purposes without reading every title? A change of heading, photograph or
background tint alone does not establish a different composition. Compare subject scale,
visual center, image/text relationship, information density and scene/action where relevant.
Similar products, variants and step comparisons may intentionally share a layout. Change
only repetition that weakens the current content; do not force arbitrary variety.

When interpreting a reference, extract both its shared visual traits and its variation:
where it moves between environment, detail, action, diagram and information, and why.
Recurring decorations are not its entire style. Transfer the reasoning to the current
product's evidence and copy, not the reference's story, claims, variant count or page order.

Review the set together. When two screens remain visually interchangeable, revise the
responsible composition, not just its heading or background. Use crop, viewpoint, spatial
depth or reserved copy space to make the content clearer. Keep a deliberate repeat when
it serves the task; variation is not a quota or a reason to add ornamental clutter.

## 3. Approve shared visual rules, then compile final pages

The approved plan carries the palette, typography, materials/light and margins in the existing `visual_master_spec` field. This is written art direction; the legacy field name does not require generating an image. Once plan/copy/layout approval is recorded, compile all final-page prompts directly, retaining each page's distinct composition and exact copy.

A generated visual preview is optional only when the user explicitly requests one. In that branch, inspect the preview within the agreed scope, record its approval and translate useful decisions into written rules; do not attach it to final-page requests or clone its layout across the set. Do not introduce a paid preview or first-two-page gate as a default quality check.

An adopted copy change invalidates affected prompts and requires fit checking. A material change in agreed direction returns to the affected design decision, without automatically creating a master.

## 4. Compile a screen prompt from resolved decisions

Write a compact task-specific prompt in this order:

1. Current screen job and output format.
2. Actual input-image roles: final pages use product-material references only; style references are analyzed during planning; attaching them is reserved for an explicitly requested preview or experiment.
3. Main subject, camera distance, relative position and intended scale.
4. Supporting modules, text hierarchy and space reserved for copy.
5. Relevant lighting, material and style decisions.
6. Verbatim `text_exact`, limited to the current screen.
7. Necessary product, claim and layout constraints for this task.

Use geometry only where it materially constrains the design. A rough bounding region is
guidance, not a promise of pixel-exact generation. Do not paste every planning field,
alternative layout, whole-page copy, or unrelated prohibition into every screen prompt.
Resolve conflicting instructions before submission. Do not mix a multi-page overview task
with instructions to generate only one final page.

For every prompt first state the copy-to-image mapping: the named part/material, required view/scale, composition and copy location. Then add shared palette/type/spacing/light rules. Do not let a material or detail page fall back to a full-product hero. Preserve layout edits from the review export as composition instructions; comments remain review input, not automatic execution authority.

Keep shared-style instructions separate from the current screen's composition instructions.
Do not copy a successful page's full layout paragraph into every prompt. A detail explanation
may need a source-visible close-up and accurate labels; a use scene may need a different
view, action or environmental relationship; information may be clearest as a table or diagram.
These are examples of matching presentation to evidence, not mandatory page families.
Changing the scenery while keeping an almost identical pose and crop may still look repetitive.

Use concrete instructions rather than adjective lists. For a detail page:
"Show the source-visible contact plate and circular side control in close-up. Reserve
separate readable label areas; each leader terminates on its named part. Use a smaller
guide title than the hero. Keep the product's real component positions."

Confirmed copy is not rewritten while compiling prompts. If it cannot fit legibly, return
the specific layout/copy issue to the Agent planning step and respect existing approval scope.
The execution adapter transports the final prompt and ordered references unchanged.

## 5. Review the design intent in actual output

Open the returned original file. File existence or a preview diagram is not visual acceptance.

After the full batch finishes, check whether the intended composition differences survived
generation. A set can be consistent in palette yet monotonous in layout. Compare adjacent
pages and repeated page families in the ordered preview; record the actual repeated structure
and its effect, not just a score or a generic instruction to "make it richer". Keep successful
pages; revise only the responsible composition within existing authority. This review does
not introduce a first-two-page gate or authorize additional generation.

Hard checks: exact required copy, source-faithful product and marks, reasonable anatomy or
wearing, correct labels/targets, no unsupported claims, real output dimensions and usable files.

Visual review: dominant focus is clear; copy is readable at intended viewing size; the
selected reference traits are visible; and materials, lighting and spatial depth feel
intentional. Inspect an ordered vertical preview after the complete set; do not delay remaining submissions for a first-two-page visual check in the default route. Check adjacent background brightness, color-area balance, materials,
lighting and type across the generated set; a four-up contact sheet alone is insufficient. Do not compare the pages to the master for acceptance.
No pixel-matched seams are required. Also inspect originals: composition should add information
or context rather than repeat another page. Revise only the weak screen while keeping the
shared direction and accepted pages. In visual-framework tests, record unclear tiny source
markings as input limitations; do not turn them into a separate repair project unless requested.

Use `pass`, `needs_revision`, or `blocked`, with observed evidence and the smallest repair.
For example: "The product consumes the intended label space" or "The scene repeats the
hero's composition" is useful; "make it more premium" is not a sufficient correction.
An annotation coordinate in a diagram only expresses intent; verify the target on the final
generated product independently. A renderer cannot verify product truth or artistic quality.

## Layout sketches within the first confirmation

Before using a preview as a generation reference, inspect the actual subject size inside
its image box. Source-image whitespace and contain scaling can make the visible product
much smaller than the planned region. Crop only irrelevant source margins when appropriate,
then remap annotation targets to the displayed crop. Compare the rendered preview with the
prompt before submission; an error-free geometry report does not prove they agree.

For annotation pages, separate required targets from flexible label placement. The named
component and leader endpoint must agree; a label may sit beside its target to avoid crossing
important markings unless its position is explicitly required. Do not simultaneously require
all labels on one side and routing that cannot reach the opposite-side component cleanly.

Use explicit type family, weight and title/label size relationships as planning guidance,
then inspect the generated type; this does not guarantee an exact font. Verify output pixel
ratio independently of the requested setting. Keep any repaired output separate from original
A/B results when a comparison was requested; one pair does not establish a general advantage
or isolate the cause of a model failure. A/B testing is not a required production stage.

For the normal plan-and-sketch package, read [Layout preview](layout-preview.md). Honor an
explicitly waived sketch or alternative review format. The Agent supplies the boxes; the bundled script
draws them and flags geometric problems. Include this preview in blueprint confirmation.
For lifestyle content, use the optional borderless relationship sketch to express people,
product contact and space. Keep exact contours and photographic execution flexible; inspect
text clearance and physical plausibility visually. Symbolic product outlines are not facts.
It belongs to the first approval and does not itself authorize generation. Preserve already
approved work; do not restart a live task just to retroactively insert a new step.

## Independent content panels

For standard final images, complete each content module inside its own frame. Use one shared type scale, consistent side margins, line height and letter spacing; verify these perceptually in generated images rather than claiming pixel-exact typography. A reference/master chapter divider is not a requirement to repeat top and bottom borders on every page. Whole-page review checks style and reading rhythm, not edge continuity. In the current independent-panel workflow, omit matching chevrons and cross-frame continuations; keep any explicitly requested and approved preview as planning evidence only. Translate the confirmed style into prompt text, not an attached image.

## Copy-led shot choices

- Brand/overall form: complete product.
- Fabric/material/feel: fabric macro, weave at a supportable scale, drape and light.
- Waistband/stitching/printed label: that component close enough to understand it, with restrained annotations if useful.
- Cut/fit: the angle or clearly distinguished diagram that explains the specified structure.
- Color range: product color comparison.
- Size/specification: readable table or information layout.

Vary framing and text location across adjacent modules, not the shared type/color system. Review exact template copy for omissions, additions, duplicated headings promoted to selling points, and incorrect numbers. Check image-copy correspondence separately from set-wide style. A coherent palette does not excuse an unrelated picture.
