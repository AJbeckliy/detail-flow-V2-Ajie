# Final delivery counts

Run after reviewing originals, the ordered set, repairs and final selections. This reports quantities, not visual acceptance or generation authority.

Report final delivered images, cumulative saved generated images, confirmed generation tasks, repair/preview task counts and unknown submission outcomes. Candidates and unsuccessful attempts are not hidden merely because fewer final pages are delivered. Missing or unreadable files make image counts incomplete.

Currency consumption and billing are outside this step. Do not calculate, return or request them, and do not append an explanation about unavailable cost data. Existing generation authorization and repair-attempt limits still apply; those govern actions, not financial reporting.

Create a final selection manifest with ordered images containing id, path and sha256, using selected originals or byte-identical delivery copies. Include all initial, repair and preview runs:

```text
PYTHON -X utf8 scripts/delivery_summary.py --runs INITIAL_RUN REPAIR_RUN --delivery FINAL_SELECTION.json --output NEW_SUMMARY_FOLDER
```

The command writes `交付统计.txt` and `usage-summary.json`. There is no billing argument or cost field. Include the text in delivery and summarize its counts in the final response.

Bound repair ancestors and recorded fallback children are included automatically and deduplicated. List separate sibling repair runs explicitly. Sharing a canvas does not mean an attempt can be omitted. No unrelated projects are scanned and no generation is submitted.

Example: **交付16张；累计保存生成图片18张；确认生成任务18次，其中返修2次。** Keep unknown submissions separate. Per-run report.json usage is provisional; the final summary uses all relevant runs and selected files.
