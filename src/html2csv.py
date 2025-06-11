import asyncio
import math
import glob, sys, re
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)
import pandas as pd
from src import html_parsing


def extract_table_title(p):
    lst = []
    for r in range(p.shape[0]):
        lst0 = []
        for c in range(p.shape[1]):
            if p.iat[r, c]:
                lst0.append(p.iat[r, c])
        if len(lst0) == 1 and ("ended" not in str(lst0[0]).lower()):
            lst.append(str(lst0[0]))
        else:
            break
    return lst


def debug_output(i, p):
    if i == 35:
        print(p)


def process(html_content, debug=False):
    html = html_parsing.parse_html(html_content) if debug else html_content
    rows = html.strip().split("\n")
    table_map = [0]
    for r in rows:
        tid = r.split(",")[0]
        if re.compile(r"^\d+$").match(tid):
            table_map.append(int(tid))

    tables = pd.read_html(html, flavor="lxml", displayed_only=False)

    csv_outputs = []
    for i, p in enumerate(tables):
        if (p.shape[0] < 2) or (p.shape[1] < 2):
            continue

        # debug_output(i, p)

        p.dropna(how="all", axis=1, inplace=True)
        p.dropna(how="all", axis=0, inplace=True)
        p = p.fillna("")

        # debug_output(i, p)

        allow_empty = True
        flag_st = 1
        for r in range(p.shape[0]):
            offset = 1 if p.iat[r, 0] else 0
            for c in range(1, p.shape[1]):
                p.iat[r, c] = str(p.iat[r, c]).replace("$", "")
                if p.iat[r, c][:1] == ")":
                    p.iat[r, c - 1] += p.iat[r, c]
                    p.iat[r, c] = ""
                if p.iat[r, c][:1] == "%":
                    p.iat[r, c - 1] += p.iat[r, c]
                    p.iat[r, c] = ""
                if p.iat[r, c] == "–":
                    if c + 1 < p.shape[1]:
                        if not p.iat[r - 1, c] and flag_st <= c - 2:
                            it = r - 1
                            flag_st = c
                            while it > 0:
                                if p.iat[it, c] or not p.iat[it, c + 1]:
                                    break
                                p.iat[it, c - 1] += "- " + str(p.iat[it, c + 1])
                                p.iat[it, c] = ""
                                p.iat[it, c + 1] = ""
                                it -= 1
                        p.iat[r, c - 1] += str(" - ")
                        p.iat[r, c - 1] += str(p.iat[r, c + 1])
                        p.iat[r, c] = ""
                        p.iat[r, c + 1] = ""
                    else:
                        p.iat[r, c - 1] += p.iat[r, c]
                        p.iat[r, c] = ""
                if ".0" in p.iat[r, c][-2:]:
                    p.iat[r, c] = p.iat[r, c].replace(".0", "")
                if "( " in p.iat[r, c]:
                    p.iat[r, c] = p.iat[r, c].replace("( ", "(")
                if re.compile(r"^\d+$").match(
                    p.iat[r, c].replace("(", "").replace(")", "").replace(",", "")
                ):
                    p.iat[r, c] = p.iat[r, c].replace(",", "")
                if re.compile(r"\(\w\)").match(p.iat[r, c]):
                    p.iat[r, c - 1] += p.iat[r, c]
                    p.iat[r, c] = ""
                else:
                    if re.compile(r"\w\)").match(p.iat[r, c]) and c + 1 < p.shape[1]:
                        p.iat[r, c] += " " + p.iat[r, c + 1]
                        for it in range(c + 1, p.shape[1] - 1):
                            p.iat[r, it] = p.iat[r, it + 1]
                        p.iat[r, p.shape[1] - 1] = ""
                if p.iat[r, c] and offset == 0:
                    offset = c + 1

        # debug_output(i, p)

        p.replace("", float("NaN"), inplace=True)
        p.dropna(how="all", axis=1, inplace=True)
        p.replace(float("NaN"), "", inplace=True)
        if (p.shape[0] < 2) or (p.shape[1] < 2):
            continue

        for r in range(3):
            if r >= p.shape[0] or (p.iat[r, 0] and r > 0):
                continue
            values = []
            for c in range(offset, p.shape[1]):
                if p.iat[r, c]:
                    values.append(p.iat[r, c])
            for c in range(offset, p.shape[1]):
                vid = int(math.floor((c - 1.0) * len(values) / (p.shape[1] - 1)))
                if len(values):
                    p.iat[r, c] = values[vid]

        # debug_output(i, p)

        c = 0
        while c < p.shape[1]:
            isEmpty = True
            for r in range(3, p.shape[0]):
                if p.iat[r, c]:
                    isEmpty = False
            if isEmpty and p.shape[0] > 3:
                p.drop(columns=p.columns[c], inplace=True)
            else:
                c += 1

        # debug_output(i, p)
        # print(table_map[i])

        csv_output = p.to_csv(index=False).replace("&nbsp;", " ")
        csv_output = re.sub(r" +", " ", csv_output)
        csv_lines = csv_output.split("\n")
        csv_outputs.append("\n".join(csv_lines[1:-1]))

    return csv_outputs, table_map


if __name__ == "__main__":
    html_file = "./htm_input/msft-10q_20220331.htm"
    with open(html_file, "r") as file:
        html_content = file.read()
    csv_results, table_map = process(html_content, True)
    if csv_results:
        for i, csv_result in enumerate(csv_results):
            with open(f"./test_output/output_table_{i+1}.csv", "w") as output_file:
                output_file.write(csv_result)
    else:
        print("No valid table found in the HTM file.")
