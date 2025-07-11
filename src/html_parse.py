import re, csv, os
import pandas as pd
import numpy as np
from tqdm import tqdm
from bs4 import BeautifulSoup
from unstructured.cleaners.core import clean_extra_whitespace


def dict_sort(dict: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in sorted(dict.items(), key=lambda item: item[1])}


def read_html_utf8(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def write_csv(file_path: str, data: list[list[str]]):
    with open(file_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(data)


def get_style_attr(soup: BeautifulSoup, attr: str) -> str | None:
    def parse_style(style_str: str) -> dict[str, str]:
        styles: dict[str, str] = {}
        for decl in style_str.split(";"):
            if ":" in decl:
                prop, val = decl.split(":", 1)
                prop = prop.strip().lower()
                val = val.strip()
                if prop:
                    styles[prop] = val
        return styles

    merged_styles: dict[str, str] = {}

    for tag in ["p", "td"]:
        for item in soup.find_all(tag):
            style_str = item.get("style")
            if not style_str:
                continue
            props = parse_style(style_str)
            merged_styles.update(props)

    top_level_divs = [d for d in soup.find_all("div") if d.find_parent("div") is None]
    if top_level_divs:
        current_div = top_level_divs[0]
        while current_div:
            style_str = current_div.get("style", "")
            if style_str:
                merged_styles.update(parse_style(style_str))
            children = [child for child in current_div.find_all("div", recursive=False)]
            current_div = children[0] if children else None

    try:
        return merged_styles[attr]
    except:
        return None


def get_indent(soup: BeautifulSoup) -> float:
    res_pt = 0.0
    for attr in ["margin-left", "margin", "text-indent"]:
        indent_str = get_style_attr(soup, attr)
        if indent_str is None:
            continue
        indent_value = float(
            indent_str.replace("pt", "").replace("em", "").replace("px", "")
        )
        if "em" in indent_str:
            indent_value *= 16
        elif "pt" in indent_str and os.name == "nt":
            indent_value = indent_value * 4 / 3
        res_pt += indent_value
    return res_pt


def remove_empty_col(
    table_contents: list[list[str]], row_ignored: list[int]
) -> list[list[str]]:
    df = pd.DataFrame(table_contents).replace("", np.nan)
    mask = ~df.index.isin(row_ignored)
    if mask.any():
        empty_cols = df[mask].isna().all(axis=0)
        df = df.loc[:, ~empty_cols]
    empty_rows = df.isna().all(axis=1)
    df = df[~empty_rows]
    table_contents = df.replace(np.nan, "").to_numpy().tolist()


def detect_sec_type(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text_to_search = soup.get_text().upper()
    candidates = set(re.findall(r"<TYPE>\s*([^\s<]+)", html.upper()))
    known_forms = ["10K", "10Q", "S1", "S3", "20F"]

    for form in known_forms:
        if form in text_to_search:
            return form

    return "UNKNOWN"


invalid_tags = [("<ix:header", "</ix:header>")]
remove_tags = [
    ("<ix:nonNumeric", ">"),
    ("</ix:nonNumeric", ">"),
    ("<ix:continuation", ">"),
    ("</ix:continuation", ">"),
]


def parse(file_path: str, output_path: str, type: str = "md", min_row: int = 3):
    tables = BeautifulSoup(read_html_utf8(file_path), "html.parser").find_all("table")

    for it in invalid_tags:
        while it[0] in tables:
            id0 = tables.index(it[0])
            id1 = tables.index(it[1]) + len(it[1])
            tables = tables[:id0] + tables[id1:]
    for it in remove_tags:
        while it[0] in tables:
            id0 = tables.index(it[0])
            id1 = tables[id0:].index(it[1]) + len(it[1])
            tables = tables[:id0] + tables[id0 + id1 :]

    prev_table_contents = None
    table_idx = 0
    prefix = "&nbsp;" if type == "md" else " "

    for table in tqdm(tables, desc="Parsing", unit="table"):
        rows = BeautifulSoup(str(table), "html.parser").find_all("tr")
        if len(rows) < min_row:
            continue
        table_contents = []
        indents_pt = []
        row_ignored = []
        for i, row in enumerate(rows):
            items = BeautifulSoup(str(row), "html.parser").find_all("td")
            table_contents.append([])
            indents_pt.append([])
            for item in items:
                # save contents
                item_str = (
                    " ".join(item.stripped_strings)
                    .replace("&nbsp;", " ")
                    .replace("<br>", " ")
                )
                item_str = item_str.replace("( ", "(").replace("’", "'")
                item_str = re.sub(r"(?<=\d),(?=\d)", "", item_str)  # 1,234 => 1234
                item_str = clean_extra_whitespace(item_str)

                # save bold/italic
                if item_str != "":
                    if get_style_attr(item, "font-weight") == "bold":
                        item_str = "**" + item_str + "**"
                        # print(item_str)
                    if get_style_attr(item, "font-style") == "italic":
                        item_str = "*" + item_str + "*"
                    if get_style_attr(item, "text-transform") == "uppercase":
                        item_str = item_str.upper()
                    elif get_style_attr(item, "text-transform") == "lowercase":
                        item_str = item_str.lower()

                if get_style_attr(item, "text-align") != "right":
                    table_contents[i].append(item_str)

                # colspan
                if item.get("colspan"):
                    row_ignored.append(i)
                    for _ in range(int(item.get("colspan")) - 1):
                        table_contents[i].append(item_str)
                        indents_pt[i].append(get_indent(item))

                if get_style_attr(item, "text-align") == "right":
                    table_contents[i].append(item_str)

                indents_pt[i].append(get_indent(item))

        indents_pt = list(map(list, zip(*indents_pt)))  # transposed

        # add indent
        for j, row_pt in enumerate(indents_pt):
            pt_set = sorted(list(set(row_pt)))
            # print(table_idx, pt_set)
            if len(pt_set) == 1:
                continue
            for i in range(len(table_contents)):
                indent_str = prefix * 2 * pt_set.index(indents_pt[j][i])
                table_contents[i][j] = indent_str + table_contents[i][j]

        # add column headers to row_ignored list
        for i in range(len(table_contents)):
            if table_contents[i][0] == "":
                row_ignored.append(i)
            else:
                break

        row_ignored = list(set(row_ignored))

        remove_empty_col(table_contents, row_ignored)

        for i in range(len(table_contents)):
            for j in range(1, len(table_contents[i])):
                # pre sign
                if table_contents[i][j - 1].strip("*") in []:
                    tmp = table_contents[i][j - 1].rstrip("*")
                    table_contents[i][j] = tmp + table_contents[i][j].lstrip("*")
                    table_contents[i][j - 1] = ""
                # post sign
                if table_contents[i][j].strip("*") in [")", "%"]:
                    tmp = table_contents[i][j - 1].rstrip("*")
                    table_contents[i][j - 1] = tmp + table_contents[i][j].lstrip("*")
                    table_contents[i][j] = ""
                # (a) index case
                if (
                    re.match(r"\(.\)", table_contents[i][j].strip(" ").strip("*"))
                    and len(table_contents[i][j - 1]) > 1
                ):
                    starcount = 0
                    if table_contents[i][j - 1][0] == "*":
                        starcount += 1
                    if table_contents[i][j - 1][1] == "*":
                        starcount += 1
                    table_contents[i][j - 1] = (
                        (
                            table_contents[i][j - 1][:-starcount]
                            + table_contents[i][j].strip(" ").strip("*")
                            + "*" * starcount
                        )
                        if starcount > 0
                        else table_contents[i][j - 1][:-1] + table_contents[i][j]
                    )
                    table_contents[i][j] = ""
            for j in range(1, len(table_contents[i]) - 1):
                # connection sign
                if table_contents[i][j].strip("*") in ["-"]:
                    table_contents[i][j] = ""
                    table_contents[i][j + 1] = (
                        table_contents[i][j - 1].rstrip("*")
                        + table_contents[i][j].strip("*")
                        + table_contents[i][j + 1].lstrip("*")
                    )
                    table_contents[i][j - 1] = ""

        # remove_empty_col(table_contents, row_ignored)
        keep_indices = []
        for col in range(len(table_contents[0])):
            has_value = any(
                table_contents[row][col] not in (None, "")
                for row in [
                    x for x in range(len(table_contents)) if x not in row_ignored
                ]
            )
            if has_value:
                keep_indices.append(col)

        # Build new matrix with only kept columns
        table_contents = [[row[col] for col in keep_indices] for row in table_contents]

        if prev_table_contents is None:
            prev_table_contents = table_contents
        elif (
            len(table_contents) == 1
            and prev_table_contents
            and (
                re.match(r"\(.\)", table_contents[0][0])
                or table_contents[0][0].strip() == "*"
            )
        ):
            prev_table_contents = prev_table_contents + table_contents
        else:
            df = pd.DataFrame(prev_table_contents).replace(float("NaN"), "")
            df.replace("", np.nan, inplace=True)
            df.dropna(how="all", inplace=True)
            df.replace(np.nan, "", inplace=True)
            prev_table_contents = table_contents
            table_idx += 1
            if type == "md":
                df = df.replace({"\$": r"\$"}, regex=True)
                df.to_markdown(
                    os.path.join(output_path, f"table_{table_idx}.md"), index=False
                )
            elif type == "csv":
                df.to_csv(
                    os.path.join(output_path, f"table_{table_idx}.csv"), index=False
                )
    if prev_table_contents:
        df = pd.DataFrame(prev_table_contents).replace(float("NaN"), "")
        if type == "md":
            df = df.replace({"\$": r"\$"}, regex=True)
            df.to_markdown(
                os.path.join(output_path, f"table_{table_idx + 1}.md"), index=False
            )
        elif type == "csv":
            df.to_csv(
                os.path.join(output_path, f"table_{table_idx + 1}.csv"), index=False
            )
