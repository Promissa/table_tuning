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


def find_pstyle_pt(soup, style, loc):
    s = soup.p["style"].strip(";").split(";")
    for item in s:
        if not style in item:
            continue
        pt_values = re.findall(r"([\d.]+)pt", item)
        if pt_values and loc < len(pt_values):
            return float(pt_values[loc])
    return -1


def parse(file_path):
    html_content = read_html(file_path)
    tables = BeautifulSoup(html_content, "html.parser").find_all("table")

    indents_pt = {}
    for table in tables:
        items = BeautifulSoup(str(table), "html.parser").find_all("td")
        for item in items:
            if not item.find("p"):
                continue
            if find_pstyle_pt(item, "margin", -1) != -1:
                indents_pt[item] = find_pstyle_pt(item, "margin", -1)
        indents_pt = dict_sort(indents_pt)
        # print(indents_pt.values())
        # print("-" * 200)


if __name__ == "__main__":
    file_path = "data/htm_input/cvs_Current_Folio_10K.htm"
    parse(file_path)
