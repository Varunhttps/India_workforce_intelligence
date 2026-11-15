"""Manager-facing Excel workbook export."""
from pathlib import Path
from copy import copy
import pandas as pd
from .records import FINDING_COLUMNS, SOURCE_COLUMNS, deduplicate_findings

HISTORY_COLUMNS = FINDING_COLUMNS + ["history_status", "first_seen", "last_seen", "occurrences"]

def _style_workbook(writer):
    for sheet in writer.book.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cells in sheet.columns:
            width = min(max(max(len(str(cell.value or "")) for cell in cells) + 2, 12), 55)
            sheet.column_dimensions[cells[0].column_letter].width = width
        for cell in sheet[1]:
            font = copy(cell.font)
            font.bold = True
            font.color = "FFFFFF"
            cell.font = font
            cell.fill = __import__("openpyxl").styles.PatternFill("solid", fgColor="1F4E78")

def export_workbook(findings, sources, output_path, new_findings=None, recurring_findings=None):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f = pd.DataFrame(deduplicate_findings(findings), columns=FINDING_COLUMNS)
    s = pd.DataFrame(sources, columns=SOURCE_COLUMNS)
    new_df = pd.DataFrame(new_findings or [], columns=HISTORY_COLUMNS)
    recurring_df = pd.DataFrame(recurring_findings or [], columns=HISTORY_COLUMNS)
    summary = (f.groupby(["industry", "country", "problem_type"], dropna=False)
                 .size().reset_index(name="finding_count") if not f.empty else
               pd.DataFrame(columns=["industry", "country", "problem_type", "finding_count"]))
    run_summary = pd.DataFrame([
        {"metric": "Findings extracted", "value": len(f)},
        {"metric": "New findings", "value": len(new_df)},
        {"metric": "Recurring findings", "value": len(recurring_df)},
        {"metric": "Sources discovered", "value": len(s)},
        {"metric": "Sources collected", "value": int((s["Collection status"] == "Collected").sum()) if not s.empty else 0},
        {"metric": "Sources with extraction failures", "value": int((s["Relevance status"] == "Extraction failed").sum()) if not s.empty else 0},
    ])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        run_summary.to_excel(writer, sheet_name="Run Overview", index=False)
        f.to_excel(writer, sheet_name="Workforce Findings", index=False)
        new_df.to_excel(writer, sheet_name="New Findings", index=False)
        recurring_df.to_excel(writer, sheet_name="Recurring Findings", index=False)
        s.to_excel(writer, sheet_name="Source Register", index=False)
        summary.to_excel(writer, sheet_name="Research Summary", index=False)
        _style_workbook(writer)
    return path
