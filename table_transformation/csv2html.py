from __future__ import annotations
import argparse, random, re, textwrap
from pathlib import Path
import pandas as pd

STYLE_POOL: list[str] = [
    "border-collapse:collapse;width:100%;border:2pt double #000;",
    "border-collapse:collapse;width:95%;border:1pt solid #666;border-top:3pt solid #000;",
    "border-collapse:collapse;width:100%;border:0.75pt solid #888;background:#fafafa;",
    "border-collapse:collapse;width:90%;border:0.5pt solid #444;border-left:none;border-right:none;",
    "border-collapse:collapse;width:100%;border:0.5pt dashed #999;",
    "border-collapse:collapse;width:100%;border:0.75pt solid transparent;border-top:2pt double #000;",
]

NBSP = "\u00a0"  # non‑breaking space to keep blank cells narrow


def _unique_col(existing: set[str], base: str) -> str:
    i = 0
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"


def add_glue_cols(df: pd.DataFrame, every: int = 2) -> None:
    """Insert a thin NBSP column every *every* data columns."""
    offset = 0
    for pos in range(every, df.shape[1] + offset, every + 1):
        name = _unique_col(set(df.columns), "_sep")
        df.insert(pos, name, [NBSP] * len(df))
        offset += 1
    df.rename(
        columns={c: " " for c in df.columns if c.startswith("_sep")}, inplace=True
    )


def add_spare_cols(df: pd.DataFrame, how_many: int) -> None:
    """Randomly insert *how_many* extra blank columns inside the DataFrame."""
    if how_many <= 0:
        return
    positions = sorted(random.sample(range(df.shape[1] + 1), how_many))
    inserted = 0
    for pos in positions:
        try:
            df.insert(pos + inserted, "", [NBSP] * len(df), allow_duplicates=True)
        except TypeError:  # pandas < 1.5
            tmp = _unique_col(set(df.columns), "_sp")
            df.insert(pos + inserted, tmp, [NBSP] * len(df))
            df.rename(columns={tmp: " "}, inplace=True)
        inserted += 1


def decorate_newlines(txt: str, mode: str) -> str:
    txt = str(txt).replace("\r\n", "\n")
    if mode == "br":
        return txt.replace("\n\n", "<br><br>").replace("\n", "<br>")
    if mode == "blankp":
        return txt.replace("\n\n", '<p style="line-height:4pt;">&nbsp;</p>').replace(
            "\n", "<br>"
        )
    return txt  # "none"


def add_percentage_widths(html: str, df: pd.DataFrame) -> str:
    widths: list[int] = []
    for idx in range(df.shape[1]):
        col_series = df.iloc[:, idx]
        numeric = pd.to_numeric(col_series, errors="coerce").notna().all()
        blank = (col_series == NBSP).all() or (col_series == " ").all()
        widths.append(3 if blank else (8 if numeric else 35))
    total = sum(widths) or 1
    ratios = [round(w * 100 / total, 1) for w in widths]
    html = html.replace(
        "<table", "<table><colgroup>" + "<col>" * len(ratios) + "</colgroup>", 1
    )
    for pct in ratios:
        html = html.replace("<col", f'<col style="width:{pct}%;&#x200B;"', 1)
    return html


def zebra_and_rules(html: str) -> str:
    html = re.sub(
        r"border-bottom:[^;]+;", "border-bottom:0.75pt solid transparent;", html
    )
    html = re.sub(
        r"(<tr[^>]*>(?:.*?(Total|Subtotal|Net).*)?)transparent;",
        r"\1#000;",
        html,
        flags=re.I | re.S,
    )
    return html


def csv_to_html(csv_path: Path) -> str:
    df = pd.read_csv(csv_path, dtype=str)

    newline_mode = random.choice(["none", "br", "blankp"])
    glue_cols = random.choice([True, False])
    perc_widths = random.choice([True, False])
    fancy_rules = random.choice([True, False])
    spare_cols = random.choice([0, 1, 2])

    df = df.applymap(lambda x: decorate_newlines(x, newline_mode))
    if glue_cols:
        add_glue_cols(df, every=random.randint(2, 4))
    if spare_cols:
        add_spare_cols(df, spare_cols)

    base_style = random.choice(STYLE_POOL)
    white_space = "pre-line" if newline_mode in ("br", "blankp") else "normal"

    html = df.to_html(index=False, escape=False, border=0, col_space=2)
    html = re.sub(
        r"<table([^>]*)>",
        rf'<table\1 style="{base_style}white-space:{white_space};">',
        html,
        1,
    )

    if perc_widths:
        html = add_percentage_widths(html, df)
    if fancy_rules:
        html = zebra_and_rules(html)

    caption = (
        f"<caption style='font-weight:bold;margin-bottom:6pt'>{csv_path.name}</caption>"
    )
    return caption + html


# ═══════════════  DOCUMENT / I‑O  ════════════════


def wrap_document(tables: list[str]) -> str:
    css = textwrap.dedent(
        """
        <style>
          body{font-family:Times New Roman,serif;margin:24px}
          table{margin:24px auto}
          th,td{padding:4pt;border:0.5pt solid #888}
          tr:nth-child(even){background:#f9f9f9}
        </style>"""
    )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>\n"
        + css
        + "\n</head><body>\n"
        + "\n\n".join(tables)
        + "\n</body></html>"
    )


def collect_csv_files(folder: Path, recursive: bool = False) -> list[Path]:
    pattern = "**/*.csv" if recursive else "*.csv"
    return sorted(folder.glob(pattern))


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch CSV → one random‑styled HTML")
    parser.add_argument(
        "--path",
        default="test/test_input/msft-10q_20220331",
        help="Folder containing CSVs",
    )
    parser.add_argument(
        "-o", "--output", default="test_output.html", help="Output merged html file"
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=False,
        help="Search for CSVs recursively",
    )
    args = parser.parse_args()

    csv_files = collect_csv_files(Path(args.path), args.recursive)
    if not csv_files:
        print("No CSV files found.")
        return

    tables = [csv_to_html(csv) for csv in csv_files]
    Path(args.output).write_text(wrap_document(tables), encoding="utf-8")

    # Duplicate pass (kept from earlier spec; can be removed if undesired)
    csvs = collect_csv_files(Path(args.path), args.recursive)
    if not csvs:
        print("No CSV files found.")
        return
    tables = [csv_to_html(f) for f in csvs]
    Path(args.output).write_text(wrap_document(tables), "utf-8")
    print(f"Merged {len(csvs)} CSVs into {args.output}")


if __name__ == "__main__":
    main()
