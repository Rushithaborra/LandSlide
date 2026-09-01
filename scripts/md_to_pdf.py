"""One-off conversion of docs/datasets.md to a styled PDF for the team.
Pure-Python (markdown + xhtml2pdf) -- avoids pandoc/weasyprint's native
dependencies, which this machine's Application Control policy has been
unreliable with for other native-DLL packages this session."""
import pathlib
import sys

import markdown
from xhtml2pdf import pisa

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

CSS = """
<style>
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.4; color: #1a1a1a; }
h1 { font-size: 20pt; margin-top: 0; margin-bottom: 4pt; }
h2 { font-size: 14pt; margin-top: 18pt; margin-bottom: 6pt; border-bottom: 1pt solid #ccc; padding-bottom: 3pt; }
h3 { font-size: 11pt; margin-top: 12pt; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9pt; }
th, td { border: 0.5pt solid #999; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background-color: #e8e8e8; font-weight: bold; }
code { font-family: Courier, monospace; background-color: #f0f0f0; padding: 1pt 3pt; font-size: 8.5pt; }
pre { background-color: #f0f0f0; padding: 6pt; font-size: 8pt; }
a { color: #1a5fb4; text-decoration: none; }
hr { border: none; border-top: 0.5pt solid #ccc; margin: 12pt 0; }
</style>
"""


def convert(md_path: pathlib.Path, pdf_path: pathlib.Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    full_html = f"<html><head>{CSS}</head><body>{body_html}</body></html>"

    with open(pdf_path, "wb") as f:
        result = pisa.CreatePDF(full_html, dest=f)
    if result.err:
        sys.exit(f"PDF generation failed with {result.err} error(s)")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    convert(REPO_ROOT / "docs" / "datasets.md", REPO_ROOT / "docs" / "datasets.pdf")
