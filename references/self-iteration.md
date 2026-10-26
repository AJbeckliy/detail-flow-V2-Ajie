# DetailFlow Self-Iteration

Use this reference when a user asks DetailFlow to improve itself, learn from a completed detail-page run, make the workflow more reliable, or turn observed failures into reusable rules.

## Operating Model

Treat self-iteration as a human-approved improvement loop, not autonomous self-modification.

Default loop:

1. Observe the run: collect the approved blueprint, prompts, generated outputs, audits, user corrections, and final files.
2. Diagnose failures: classify issues by responsible layer instead of blaming the whole workflow.
3. Propose the smallest durable improvement: update prompt rules, audit checks, blueprint fields, or a reference note.
4. Produce an `iteration_report`: summarize what worked, what failed, which layer should change, and the proposed patch.
5. Wait for explicit user approval before editing `SKILL.md`, files under `references/`, scripts, or agents metadata.
6. Apply the approved change, validate the skill folder, and report the changed files.

Never silently rewrite the skill after a normal delivery. A generated detail page is evidence for possible improvement, not permission to change the skill.

## Improvement Layers

Route each lesson to the smallest responsible layer:

- `blueprint`: narrative gaps, repeated buyer questions, missing first-screen seeds, unsupported claims, weak screen roles.
- `copy`: garbled text, repeated sentence rhythm, copy too generic, claim wording stronger than evidence.
- `visual_master`: set-wide style drift, repeated hero motifs, weak reference-style transfer.
- `slice_prompt`: one screen changes product identity, misses copy, or repeats adjacent composition.
- `audit`: a recurring defect was not caught before delivery.
- `delivery`: missing requested files, wrong names, unusable previews, unclear output path.
- `skill_reference`: a reusable heuristic or checklist should be available for future jobs.
- `skill_core`: only use when the mandatory route, approval gates, or triggering behavior must change.

Prefer updating a reference file over expanding `SKILL.md` unless the rule is mandatory for every DetailFlow run.

## Iteration Report Format

When self-iteration is requested or materially useful, include this compact report:

```markdown
iteration_report:
  task_summary: "<product/page type and requested style>"
  final_status: "passed | passed_with_notes | needs_revision | blocked"
  successful_patterns:
    - "<specific reusable pattern>"
  observed_failures:
    - issue: "<specific issue>"
      layer: "blueprint | copy | visual_master | slice_prompt | audit | delivery | skill_reference | skill_core"
      evidence: "<file/slice/prompt/user correction>"
      proposed_fix: "<smallest durable fix>"
  reusable_rules_to_add:
    - "<candidate rule>"
  suggested_files_to_change:
    - path: "<skill-relative path>"
      reason: "<why this file, not a larger rewrite>"
  requires_user_approval: true
```

Keep the report concise. It should help a later Codex instance improve the workflow without reading the entire conversation.

## Patch Proposal Rules

Before editing the skill, state:

- The files to change.
- Whether the change affects mandatory behavior or only a reference heuristic.
- Why the change should generalize beyond the current product.
- Any risks, such as overfitting to one style, adding too much context, or making approval gates heavier.

Only apply the patch after the user clearly approves the proposed change. If the user asks to "use this to upgrade the skill" or equivalent, that is sufficient approval for the described patch scope.

## Evaluation Checks

After applying an approved self-iteration patch:

1. Run the skill validation script when available.
2. Re-read the modified snippets to verify the new rule is discoverable from `SKILL.md`.
3. Confirm the update did not add duplicate instructions or conflict with the existing execution contract.
4. If the change came from one image-generation run, mark it as a heuristic unless it is broadly true.

## Common Detail-Page Lessons

Use these as examples of how to convert failures into reusable rules:

- If a generated animal, mascot, or character becomes too human, add a reference-style constraint that preserves body structure, action vocabulary, and forbidden anthropomorphic cues.
- If a product's visible brand conflicts with the supplied product name, require an explicit identity decision before visual generation.
- If generated pages drift from the approved art direction or repeat the same layout, revise the shared visual specification or affected screen composition while preserving approved copy.
- If a regulated or technical claim is overextended, revise `text_exact` and the claim boundary, then regenerate only affected slices.
- If a requested plain combined preview exceeds a utility limit, use an existing deterministic image utility and preserve original page files. This does not activate seamless-scene repair.

## Boundaries

Do not:

- Create a hidden memory store or modify the skill without user approval.
- Treat one user's preference as universal unless the user asks for that preference to become a rule.
- Add large examples, changelogs, or project diaries to the skill.
- Rewrite the entire skill when a reference note or prompt heuristic is enough.
- Delete generated outputs or previous accepted files while iterating.
