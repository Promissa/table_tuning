import csv
import numpy as np


def read_csv(file_path):
    table = []
    with open(file_path, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            table.append(row)
    return table


def print_table(t):
    for i in range(len(t)):
        print(t[i])


def cal_lev(r1, r2):
    n, m = len(r1), len(r2)
    f = np.zeros((n + 1, m + 1), dtype=int)

    for i in range(n + 1):
        f[i][0] = i
    for j in range(m + 1):
        f[0][j] = j

    def judge(s1, s2, ignoreComma=False):
        # `ignoreComma`: "123,456.789" "123456.789" will be taken equally when True
        if s1 == s2:
            return True
        if ignoreComma == False:
            return False

        if s1 == "" or s2 == "":
            return False
        if not all(char.isdigit() or char == "," or char == "." for char in s1):
            return False
        if not all(char.isdigit() or char == "," or char == "." for char in s2):
            return False
        return float(s1.replace(",", "")) == float(s2.replace(",", ""))

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if judge(r1[i - 1], r2[j - 1]):
                f[i][j] = f[i - 1][j - 1]
            else:
                f[i][j] = min(f[i - 1][j] + 1, f[i][j - 1] + 1, f[i - 1][j - 1] + 1)
    return f[n][m]


def cal_2d_lev(t1, t2):
    n, m = len(t1), len(t2)
    f = np.zeros((n + 1, m + 1), dtype=int)

    for i in range(n + 1):
        f[i][0] = i
    for j in range(m + 1):
        f[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = cal_lev(t1[i - 1], t2[j - 1])
            f[i][j] = min(f[i - 1][j] + 1, f[i][j - 1] + 1, f[i - 1][j - 1] + cost)

    # print_table(f)
    return f[n][m]


def cal_teds(t1, t2):
    pass


if __name__ == "__main__":
    file1 = "parsedtable/1800_000110465911061064_10-Q_1800_1/table_4_2_a2.csv"
    file2 = "parsedtable/1800_000110465911061064_10-Q_1800_1/table_4.csv"
    # print_table(read_csv("parsedtable/1800_000110465911061064_10-Q_1800_1/table_4_1.csv"))
    # file1, file2 = "parsed_result/sample.csv", "ground_truth/sample.csv"
    print(cal_2d_lev(read_csv(file1), read_csv(file2)))
