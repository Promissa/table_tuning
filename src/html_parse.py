from unstructured.documents.html import HTMLDocument
from unstructured.nlp.partition import is_possible_title
import re, csv, os, multiprocessing, sys, math
import pandas as pd
import io
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from unstructured.documents.elements import Title, Table
from unstructured.cleaners.core import clean_extra_whitespace
from multiprocessing import Pool
from src import html2md
from copy import copy
import chardet


def dict_sort(dict):
    return {k: v for k, v in sorted(dict.items(), key=lambda item: item[1])}


def read_html(file_path):
    with open(file_path, "rb") as file:
        rawdata = file.read()
        result = chardet.detect(rawdata)
        encoding = result["encoding"]
        return rawdata.decode(encoding)


def write_csv(file_path, data):
    with open(file_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(data)


def get_pstyle_pt(soup, style, loc):
    s = soup.p["style"].strip(";").split(";")
    for item in s:
        if not style in item:
            continue
        pt_values = re.findall(r"([\d.]+)pt", item)
        if pt_values and loc < len(pt_values):
            return float(pt_values[loc])
    return -1


def get_pstyle_attr(soup, attr):
    s = soup.p["style"].strip(";").split(";")
    for item in s:
        if not attr in item:
            continue
        return str(item).split(":")[1].strip()
    return None


def parse(file_path, output_path, type="markdown"):
    html_content = read_html(file_path)
    tables = BeautifulSoup(html_content, "html.parser").find_all("table")

    # find the indent of each table
    for table_idx, table in enumerate(tables):
        rows = BeautifulSoup(str(table), "html.parser").find_all("tr")
        table_contents = []
        indents_pt = []
        for i, row in enumerate(rows):
            items = BeautifulSoup(str(row), "html.parser").find_all("td")
            table_contents.append([])
            indents_pt.append([])
            for item in items:
                # save contents
                item_str = " ".join(item.stripped_strings).replace("&nbsp;", " ")
                item_str = item_str.replace("( ", "(")
                item_str = re.sub(r"(?<=\d),(?=\d)", "", item_str)
                item_str = clean_extra_whitespace(item_str)
                # print(i, j)
                
                
                if not item.find("p"):
                    table_contents[i].append(item_str)
                    continue

                # save bold/italic
                if item_str != "":
                    if get_pstyle_attr(item, "text-transform") == "uppercase":
                        item_str = item_str.upper()
                    elif get_pstyle_attr(item, "text-transform") == "lowercase":
                        item_str = item_str.lower()
                    if get_pstyle_attr(item, "font-weight") == "bold":
                        item_str = "**" + item_str + "**"
                    if get_pstyle_attr(item, "font-style") == "italic":
                        item_str = "*" + item_str + "*"

                if (
                    get_pstyle_attr(item, "text-align") != "right"
                    and get_pstyle_attr(item, "text-align") != "center"
                ):
                    table_contents[i].append(item_str)

                if item.get("colspan") is not None:
                    for _ in range(int(item["colspan"]) - 1):
                        table_contents[i].append("")
                        indents_pt[i].append(0.0)

                if (
                    get_pstyle_attr(item, "text-align") == "right"
                    or get_pstyle_attr(item, "text-align") == "center"
                ):
                    table_contents[i].append(item_str)

                indents_pt[i].append(0.0)
                j = len(indents_pt[i]) - 1

                # save indent(pt)
                if get_pstyle_pt(item, "margin", -1) != -1:
                    indents_pt[i][j] = get_pstyle_pt(item, "margin", -1)
                if get_pstyle_pt(item, "margin-left", -1) != -1:
                    indents_pt[i][j] = get_pstyle_pt(item, "margin-left", -1)

                if get_pstyle_attr(item, "text-indent") is not None:
                    txt_indent = float(
                        get_pstyle_attr(item, "text-indent").split(":")[-1].strip()[:-2]
                    )
                    if indents_pt[i][j] != 0.0:
                        # e.g. "margin-left: 24pt, text-indent: -12pt"
                        indents_pt[i][j] += txt_indent
                    else:
                        indents_pt[i][j] = txt_indent

        indents_pt = list(map(list, zip(*indents_pt)))  # transposed

        for j, row_pt in enumerate(indents_pt):
            pt_set = sorted(list(set(row_pt)))
            if len(pt_set) == 1:
                continue
            for i in range(len(table_contents)):
                if type == "markdown":
                    prefix = "&nbsp;&nbsp;"
                elif type == "csv":
                    prefix = " "
                table_contents[i][j] = (
                    prefix * 2 * pt_set.index(indents_pt[j][i]) + table_contents[i][j]
                )

        df = pd.DataFrame(table_contents).replace("", float("NaN"))
        df.dropna(how="all", axis=0, inplace=True)
        df.dropna(how="all", axis=1, inplace=True)
        table_contents = df.replace(float("NaN"), "").to_numpy().tolist()

        for i in range(len(table_contents)):
            for j in range(1, len(table_contents[i])):
                if table_contents[i][j].strip("*") == ")":
                    table_contents[i][j - 1] = table_contents[i][j - 1].rstrip(
                        "*"
                    ) + table_contents[i][j].lstrip("*")
                    table_contents[i][j] = ""
                if re.match(r"\(.\)", table_contents[i][j].strip(" ").strip("*")):
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
                if table_contents[i][j].strip("*") == "–":
                    table_contents[i][j] = ""
                    table_contents[i][j + 1] = (
                        table_contents[i][j - 1].rstrip("*")
                        + "–"
                        + table_contents[i][j + 1].lstrip("*")
                    )
                    table_contents[i][j - 1] = ""

        df = pd.DataFrame(table_contents).replace("", float("NaN"))
        df.dropna(how="all", axis=0, inplace=True)
        df.dropna(how="all", axis=1, inplace=True)

        table_contents = df.to_numpy().tolist()
        if table_idx == 0:
            prev_table_contents = table_contents
        if len(table_contents) == 1 and table_idx > 0 and re.match(r"\(.\)", table_contents[0][0]):
            prev_table_contents = prev_table_contents + table_contents
        else:
            df = pd.DataFrame(prev_table_contents).replace(float("NaN"), "")
            prev_table_contents = table_contents
            if type == "markdown":
                df.to_markdown(os.path.join(output_path, f"table_{table_idx + 1}.md"))
            elif type == "csv":
                df.to_csv(os.path.join(output_path, f"table_{table_idx + 1}.csv"), index=False)


if __name__ == "__main__":
    file_path = "data/htm_input/sec_sample.html"
    output_path = "test/test_output/html_parse/"
    parse(file_path, output_path)
    print("Parsing completed. CSV files saved to", output_path)
    test = BeautifulSoup(
        """<td style="background-color: #e5e5e5; width: 40.42%" valign="top">
<p style="
                                        line-height: 11pt;
                                        margin-bottom: 0pt;
                                        margin-top: 0pt;
                                        margin-left: 12pt;
                                        text-indent: -12pt;
                                        font-family: Arial;
                                        font-size: 10pt;
                                        font-weight: normal;
                                        font-style: normal;
                                        text-transform: none;
                                        font-variant: normal;
                                    ">
                                    Operating lease cost
                                </p>
                                <p>123</p>
</td>""",
        "html.parser",
    )
    # print(get_pstyle_pt(test, "margin-left", -1))
