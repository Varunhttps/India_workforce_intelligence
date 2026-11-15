"""Excel export for findings and source traceability."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .records import FINDING_COLUMNS, SOURCE_COLUMNS, deduplicate_findings


def export_workbook(
    findings: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    output_path: str | Path,
) -> Path:
    """Write a manager-ready workbook without Evidence/Confidence/HR Category columns."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_findings = deduplicate_findings(findings)
    findings_df = pd.DataFrame(clean_findings, columns=FINDING_COLUMNS)
    sources_df = pd.DataFrame(sources, columns=SOURCE_COLUMNS)
    summary_df = (
        findings_df.groupby(["industry", "country", "problem_type"], dropna=False)
        .size().reset_index(name="finding_count")
        if not findings_df.empty else
        pd.DataFrame(columns=["industry", "country", "problem_type", "finding_count"])
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        findings_df.to_excel(writer, sheet_name="Workforce Findings", index=False)
        sources_df.to_excel(writer, sheet_name="Source Register", index=False)
        summary_df.to_excel(writer, sheet_name="Research Summary", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column_cells in sheet.columns:
                width = min(max(max(len(str(c.value or "")) for c in column_cells) + 2, 12), 55)
                sheet.column_dimensions[column_cells[0].column_letter].width = width
    return path
