# Final delivery and star-coin accounting

Run this step after the Agent has reviewed every original, the ordered set and any repairs, and selected the final delivery images. It reports quantities and actual billing; it does not approve visuals or authorize generation.

## Required final report

- Final delivered images: the final ordered, selected page files.
- Cumulative saved generated images: include initial candidates, preview images and repair images; exclude exact input echoes and duplicate output records. This is not the number of billed requests. Missing/unreadable files make the image count incomplete.
- Confirmed generation tasks: include unsuccessful attempts and repairs. Report unknown submission outcomes separately; do not assume a refund.
- Actual net star coins: actual charges minus evidenced refunds, across all included attempts. A failed task is not automatically free. No verified total is emitted until all confirmed tasks and submission outcomes are reconciled.

Include costs in the user-facing delivery only when the complete actual total is verified. Otherwise omit the entire cost item, including placeholders, explanations and partial subtotals. Do not invent a field or derive actual cost from model pricing, output count or account balance changes. Internal accounting can retain its reconciliation state without exposing an unknown-cost notice.

## Local command

Create a final selection manifest after visual review, using existing original files or byte-identical delivery copies:

```json
{"images":[{"id":"01","path":"delivery/screen-01.png","sha256":"ACTUAL_FILE_SHA256"}]}
```

Pass every initial, repair and requested-preview run for this deliverable. The script expands recorded fallback children and bound same-canvas repair ancestors, and deduplicates repeated run paths and task IDs. Separate sibling repair runs must still be listed; sharing a canvas does not make them free or automatically discoverable. It never searches unrelated projects or submits generation.

```text
PYTHON -X utf8 scripts/delivery_summary.py --runs INITIAL_RUN REPAIR_RUN --delivery FINAL_SELECTION.json --output NEW_SUMMARY_FOLDER
```

The new folder contains `交付统计.txt` and internal `usage-summary.json`; when an actual total is verified, the text file is named `费用统计.txt` and includes that amount. Include the text in the final delivery and copy its concise counts into the final response. This creates no additional approval gate. Ordinary report.json usage is provisional and cannot replace this cumulative final step. Do not omit repair runs to make the total look smaller.

## Actual bills when available

When actual transaction details are available through a supported UI/export or a user-provided bill, reconcile each charge/refund to the remote task ID. Without reliable attribution, omit the user-facing cost item; do not delay ordinary image delivery for it.

Create a normalized local ledger referencing the original bill evidence; the numbers must be transcribed from that source, never fabricated:

```json
{
  "kind":"actual_platform_bill",
  "currency":"star_coin",
  "evidence":{"path":"original-platform-bill.json","sha256":"ACTUAL_EVIDENCE_SHA256"},
  "records":[{"task_id":"ACTUAL_REMOTE_TASK_ID","charged_star_coins":"12.5","refunded_star_coins":"0"}]
}
```

The numbers above are schema examples, not prices. An original platform export or screenshot can be evidence; do not use the normalized ledger itself as its own source. Aggregate multiple real billing rows for one task into one net calculation while retaining the original evidence. Zero is accepted only when the actual bill supports zero. Wrong currency, negative values, duplicate task IDs, unknown tasks, missing/changed evidence and refunds exceeding charges are rejected.

Append `--billing NORMALIZED_LEDGER.json` to the final command. A hash establishes source stability, not authenticity or correctness of transcription; the Agent must inspect the actual bill. Do not manufacture an allocation when attribution is unavailable. Do not expose payment credentials or unrelated transactions in the delivery package.

The final user-facing format is: **交付 X 张；累计生成 Y 张，确认生成任务 Z 次（含返修 R 次）。** Append **实际净消耗 N 星币** only with a verified complete total. Note incomplete image counts or unknown submissions explicitly. No pricing cache or shared billing database is introduced.
