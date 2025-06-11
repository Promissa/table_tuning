import asyncio
import math
import glob, sys
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)
import pandas as pd

# pd.set_option('future.no_silent_downcasting', True)


# Note: One HTML at a time
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


def process(html, tid=0):
    # p = pd.read_html(html, flavor='bs4')[0]
    p = pd.read_html(html, flavor="lxml", displayed_only=False)[0]
    if (p.shape[0] < 2) or (p.shape[1] < 2):
        return None
    p.dropna(how="all", axis=1, inplace=True)
    p.dropna(how="all", axis=0, inplace=True)
    p = p.fillna("")
    lst = extract_table_title(p)
    p = p[len(lst) :]
    p.replace("", float("NaN"), inplace=True)
    p.dropna(how="all", axis=1, inplace=True)
    p.dropna(how="all", axis=0, inplace=True)
    p.replace(float("NaN"), "", inplace=True)

    # m = p.to_markdown()
    # print(m)
    allow_empty = True
    for r in range(p.shape[0]):
        for c in range(1, p.shape[1]):
            p.iat[r, c] = str(p.iat[r, c]).replace("$", "")
            if p.iat[r, c][:1] == ")":
                p.iat[r, c - 1] += p.iat[r, c]
                p.iat[r, c] = ""
            if p.iat[r, c][:1] == "%":
                p.iat[r, c - 1] += p.iat[r, c]
                p.iat[r, c] = ""

        if r == 0 or (not p.iat[r, 0] and allow_empty):
            offset = 1
        else:
            allow_empty = False
            offset = 0

        values = []
        for c in range(offset, p.shape[1]):
            if p.iat[r, c]:
                values.append(str(p.iat[r, c]))
        for c in range(offset, p.shape[1]):
            if values:
                v = values.pop(0)
                if ".0" in v[-2:]:
                    v = v.replace(".0", "")
                p.iat[r, c] = v
            else:
                p.iat[r, c] = ""

    p.replace("", float("NaN"), inplace=True)
    p.dropna(how="all", axis=1, inplace=True)
    p.replace(float("NaN"), "", inplace=True)
    if (p.shape[0] < 2) or (p.shape[1] < 2):
        return None

    for r in range(3):
        if r >= p.shape[0] or (p.iat[r, 0] and r > 0):
            continue
        values = []
        for c in range(1, p.shape[1]):
            if p.iat[r, c]:
                values.append(p.iat[r, c])
        for c in range(1, p.shape[1]):
            vid = int(math.floor((c - 1.0) * len(values) / (p.shape[1] - 1)))
            if len(values):
                p.iat[r, c] = values[vid]

    # new_header = p.iloc[0]
    # p = p[1:]
    # p.columns = new_header
    m = "\n".join(lst) + "\n" if len(lst) else ""
    m += '<markdown tid="' + str(tid) + '">\n' + p.to_markdown() + "\n</markdown>"
    return m


# if __name__ == '__main__':
# #for f in glob.glob('/mnt/d/FinAI/parsed/ADBE/10-Q*/1.1.txt'):
#     print(process('/mnt/d/FinAI/parsed/XOM/10-Q_000003408812000050/3.html'))
