"""Manager-facing Excel workbook export."""
from pathlib import Path
import pandas as pd
from .records import FINDING_COLUMNS,SOURCE_COLUMNS,deduplicate_findings
def export_workbook(findings,sources,output_path):
    path=Path(output_path); path.parent.mkdir(parents=True,exist_ok=True)
    f=pd.DataFrame(deduplicate_findings(findings),columns=FINDING_COLUMNS); s=pd.DataFrame(sources,columns=SOURCE_COLUMNS)
    summary=(f.groupby(["industry","country","problem_type"],dropna=False).size().reset_index(name="finding_count") if not f.empty else pd.DataFrame(columns=["industry","country","problem_type","finding_count"]))
    with pd.ExcelWriter(path,engine="openpyxl") as writer:
        f.to_excel(writer,sheet_name="Workforce Findings",index=False); s.to_excel(writer,sheet_name="Source Register",index=False); summary.to_excel(writer,sheet_name="Research Summary",index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes="A2"; sheet.auto_filter.ref=sheet.dimensions
            for cells in sheet.columns: sheet.column_dimensions[cells[0].column_letter].width=min(max(max(len(str(c.value or "")) for c in cells)+2,12),55)
    return path
