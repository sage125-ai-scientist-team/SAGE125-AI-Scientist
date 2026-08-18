# Export Consistency and PDF QA

状态：`PASS_SYNTHETIC_FIXTURE / PRODUCTION_WAIT`

Source:

```text
tests/api/fixtures/canonical_report.json
truth_status=planned
actual_execution=false
```

Generated artifacts:

- `pdf_qa/representative_report.json`
- `pdf_qa/representative_report.md`
- `pdf_qa/representative_report.pdf`
- `pdf_qa/page-1.png`
- `pdf_qa/pdf_qa.json`

Automated result:

```text
formats=JSON,Markdown,PDF
page_count=1
blank_page_count=0
link_count=1
contains_truth_status_planned=true
contains_actual_execution_no=true
contains_raw_markdown_heading=false
pdf_size_bytes=39778
```

Manual page inspection:

- no clipping or overlap;
- no blank page;
- no abnormal character spacing observed;
- Chinese warning and limitation text are visible;
- planned and ACTUAL EXECUTION: NO are prominent;
- DOI link is visible.

This proves renderer behavior for a planned synthetic canonical report only.
Production export remains WAIT until owner composition and production browser E2E complete.
