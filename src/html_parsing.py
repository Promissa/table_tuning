from unstructured.documents.html import HTMLDocument
from unstructured.nlp.partition import is_possible_title
import re, csv, os, multiprocessing, sys, math
import pandas as pd
import io
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from unstructured.documents.elements import Title, Table
from unstructured.cleaners.core import clean_extra_whitespace
from multiprocessing import Pool
from src import html2md
from copy import copy
import chardet

invalid_tags = [("<ix:header", "</ix:header>")]
remove_tags = [
    ("<ix:nonNumeric", ">"),
    ("</ix:nonNumeric", ">"),
    ("<ix:continuation", ">"),
    ("</ix:continuation", ">"),
]


def match_item_title(ptext, rtitle, title):
    ban = ["see ", "“", "”"]
    ftext = rtitle.split(" ")[0]
    if (
        any(elm in rtitle[:25] for elm in ban)
        or (rtitle[:1] == ",")
        or (rtitle[-1:] == ",")
        or (ftext == "and")
        or (ftext == "in")
        or (ftext == "within")
        or (ftext == "of")
        or (ftext == "under")
        or (ptext == "and")
        or (ptext == "in")
        or (ptext == "within")
        or (ptext == "of")
        or (ptext == "under")
    ):
        return None
    title = title.lower().replace(" ", "").replace("otheritems", "")[:10]
    return "Item" if "item" in title else None


def is_10k_item_title(str1, str2):
    str1 = str1.lower().replace(" ", "")
    str2 = str2.lower().replace(" ", "")
    if "continued" in str1[-10:] or "continued" in str2[-10:]:
        return None
    if "business" in str1[:20]:
        return "1", 0
    if "risk" in str1[:15] and "parti" not in str1:
        return "1A", 1
    if "unresolved" in str1[:20] and "parti" not in str1:
        return ("1B", 2)
    if "cybersecurity" in str1[:30] and "parti" not in str1:
        return ("1C", 3)
    if "properties" in str1[:25] and "parti" not in str1:
        return ("2", 4)
    if "legalproceedings" in str1[:25] and "parti" not in str1:
        return ("3", 5)
    if "min" in str1[:25] and "safety" in str1[:25] and "parti" not in str1:
        return ("4", 6)
    if "submission" in str1[:25] and "parti" not in str1:
        return ("4", 6)
    if "executiveofficers" in str1[:25] and "parti" not in str1:
        return ("4", 6)
    if "marketfor" in str1[:25]:
        return ("5", 7)
    if "marketprice" in str1[:25]:
        return ("5", 7)
    if (
        "selectedfinancial" in str1.replace("consolidated", "")[:50]
        and "part" not in str1
    ):
        return ("6", 8)
    if "reserved" in str1[:30] and "partii" not in str1:
        return ("6", 8)
    if ("management" in str1 and "sdiscussion" in str1[:100]) and "partii" not in str1:
        return ("7", 9)
    if (
        "quantitativeandqualitative" in str1[:40]
        or "qualitativeandquantitative" in str1[:40]
    ) and "partii" not in str1:
        return ("7A", 10)
    if "financialstatements" in str1[:30] and "partii" not in str1:
        return ("8", 11)
    if "changesinanddisagreements" in str1[:35] and "partii" not in str1:
        return ("9", 12)
    if "controlsandprocedures" in str1[:30] and "partii" not in str1:
        return ("9A", 13)
    if "otherinfo" in str1[:20] and "partii" not in str1:
        return ("9B", 14)
    if "disclosureregarding" in str1[:40] and "partii" not in str1:
        return ("9C", 15)
    if (
        ("directors" in str1[:50]) or ("trustees" in str1[:50])
    ) and "executive" in str1[:50]:
        return ("10", 16)
    if "executivecompensation" in str1[:35] and "partiii" not in str1:
        return ("11", 17)
    if "securityownership" in str1[:30] and "partiii" not in str1:
        return ("12", 18)
    if "certainrelationships" in str1[:30] and "partiii" not in str1:
        return ("13", 19)
    if "principala" in str1[:25] and "partiii" not in str1:
        return ("14", 20)
    if "business" in str2[:20]:
        return "1", 0
    if "risk" in str2[:15] and "parti" not in str2:
        return "1A", 1
    if "unresolved" in str2[:20] and "parti" not in str2:
        return ("1B", 2)
    if "cybersecurity" in str2[:25] and "parti" not in str2:
        return ("1C", 3)
    if "properties" in str2[:25] and "parti" not in str2:
        return ("2", 4)
    if "legalproceedings" in str2[:25] and "parti" not in str2:
        return ("3", 5)
    if "min" in str2[:25] and "safety" in str2[:25] and "parti" not in str2:
        return ("4", 6)
    if "submission" in str2[:25] and "parti" not in str2:
        return ("4", 6)
    if "executiveofficers" in str2[:25] and "parti" not in str2:
        return ("4", 6)
    if "marketfor" in str2[:25]:
        return ("5", 7)
    if "marketprice" in str2[:25]:
        return ("5", 7)
    if (
        "selectedfinancial" in str2.replace("consolidated", "")[:50]
        and "partii" not in str2
    ):
        return ("6", 8)
    if "reserved" in str2[:30] and "partii" not in str2:
        return ("6", 8)
    if ("management" in str2 and "sdiscussion" in str2[:100]) and "partii" not in str2:
        return ("7", 9)
    if (
        "quantitativeandqualitative" in str2[:40]
        or "qualitativeandquantitative" in str2[:40]
    ) and "partii" not in str2:
        return ("7A", 10)
    if "financialstatement" in str2[:30] and "partii" not in str2:
        return ("8", 11)
    if "changesinanddisagreements" in str2[:35] and "partii" not in str2:
        return ("9", 12)
    if "controlsandprocedures" in str2[:30] and "partii" not in str2:
        return ("9A", 13)
    if "otherinfo" in str2[:20] and "partii" not in str2:
        return ("9B", 14)
    if "disclosureregarding" in str2[:40] and "partii" not in str2:
        return ("9C", 15)
    if (
        ("directors" in str2[:50]) or ("trustees" in str2[:50])
    ) and "executive" in str2[:50]:
        return ("10", 16)
    if "executivecompensation" in str2[:35] and "partiii" not in str2:
        return ("11", 17)
    if "securityownership" in str2[:30] and "partiii" not in str2:
        return ("12", 18)
    if "certainrelationships" in str2[:30] and "partiii" not in str2:
        return ("13", 19)
    if "principala" in str2[:25] and "partiii" not in str2:
        return ("14", 20)


def is_10q_part1_item_title(str1, str2):
    str1 = str1.lower().replace(" ", "")
    str2 = str2.lower().replace(" ", "")
    if (
        "financialstatement"
        in str1.replace("condensed", "").replace("consolidated", "")[:30]
    ):
        return ("1.1", 4)  ### Item 1 can sometimes go behind item 2-4
    if "management" in str1 and "sdiscussion" in str1[:40]:
        return ("1.2", 4)
    if (
        "quantitativeandqualitative" in str1[:35]
        or "qualitativeandquantitative" in str1[:35]
    ):
        return ("1.3", 4)
    if "controlsandprocedures" in str1[:30] or "controlsprocedures" in str1[:30]:
        return ("1.4", 4)
    if (
        "financialstatement"
        in str2.replace("condensed", "").replace("consolidated", "")[:30]
    ):
        return ("1.1", 4)  ### Item 1 can sometimes go behind item 2-4
    if "management" in str2 and "sdiscussion" in str2[:40]:
        return ("1.2", 4)
    if (
        "quantitativeandqualitative" in str2[:35]
        or "qualitativeandquantitative" in str2[:35]
    ):
        return ("1.3", 4)
    if "controlsandprocedures" in str2[:30] or "controlsprocedures" in str2[:30]:
        return ("1.4", 4)
    return None


def is_10q_part2_item_title(str1, str2):
    str1 = str1.lower().replace(" ", "")
    str2 = str2.lower().replace(" ", "")
    if "legalproceedings" in str1[:25]:
        return ("2.1", 5)
    if "riskfactors" in str1.replace("legal", "")[:20]:
        return ("2.1A", 6)
    if "useofproceeds" in str1[:70] or "unregisteredsales" in str1[:70]:
        return ("2.2", 7)
    if "repurchase" in str1[:40]:
        return ("2.2", 7)
    if "defaults" in str1:
        return ("2.3", 8)
    if "submission" in str1[:20]:
        return ("2.4", 9)
    if "minesafety" in str1[:20]:
        return ("2.4", 9)
    if "reserved" in str1[:40]:
        return ("2.4", 9)
    if (
        ("part" not in str1)
        and ("otherinformation" in str1[:25])
        or ("otheritems" in str1[:25])
    ):
        return ("2.5", 10)
    if "legalproceedings" in str2[:25]:
        return ("2.1", 5)
    if "riskfactors" in str2.replace("legal", "")[:20]:
        return ("2.1A", 6)
    if "repurchase" in str2[:40]:
        return ("2.2", 7)
    if "useofproceeds" in str2[:70] or "unregisteredsales" in str2[:70]:
        return ("2.2", 7)
    if "defaults" in str2:
        return ("2.3", 8)
    if "minesafety" in str2[:20]:
        return ("2.4", 9)
    if "submission" in str2[:20]:
        return ("2.4", 9)
    if "reserved" in str2[:40]:
        return ("2.4", 9)
    if (
        ("part" not in str2)
        and ("otherinformation" in str2[:25])
        or ("otheritems" in str2[:25])
    ):
        return ("2.5", 10)
    return None


def is_sorted(seq):
    seq_iter = iter(seq)
    cur = next(seq_iter, None)
    return all((prev := cur) <= (cur := nxt) for nxt in seq_iter)


def parse_html(html, debug=False):
    # Read the raw HTML content from the file
    if debug:
        raw = open(html, "rb").read()
    else:
        raw = html

    table_soup = BeautifulSoup(raw, "html.parser")

    if table_soup.find_all("10k"):
        form = "10-K"
    else:
        form = "10-Q"

    for p_tag in table_soup.find_all("p"):
        style = p_tag.get("style", "")
        margin_left_match = re.search(r"margin-left:(\d+)pt;", style)
        if margin_left_match:
            margin_left_value = int(margin_left_match.group(1))
            if margin_left_value < 12:
                continue
            spaces = "&nbsp;" * ((margin_left_value - 12) // 12 * 4)
            p_tag.insert(0, spaces)
    for div_tag in table_soup.find_all("div"):
        style = div_tag.get("style", "")
        margin_left_match = re.search(r"text-indent:([\d.]+)pt", style)
        if margin_left_match:
            margin_left_value = float(margin_left_match.group(1))
            spaces = "&nbsp;" * (math.floor(margin_left_value / 6.75) * 4)
            div_tag.insert(0, spaces)
            # print(margin_left_value)

    raw = str(table_soup)

    # Remove invalid tags
    for it in invalid_tags:
        while it[0] in raw:
            id0 = raw.index(it[0])
            id1 = raw.index(it[1]) + len(it[1])
            raw = raw[:id0] + raw[id1:]
    for it in remove_tags:
        while it[0] in raw:
            id0 = raw.index(it[0])
            id1 = raw[id0:].index(it[1]) + len(it[1])
            raw = raw[:id0] + raw[id0 + id1 :]

    # Parse html part from the file
    id0 = raw.lower().index("<html")
    id1 = raw.lower().index("</html>")
    raw_parse = raw[id0 : id1 + 7]
    raw_disp = copy(raw_parse)

    # offsets = []
    # for i in re.finditer("<table", raw_parse.lower()):
    #     offset = i.span()[0]
    #     offset = offset + raw_parse[offset:].lower().index("<tr")
    #     offsets.append(offset)
    # for i in range(len(offsets)):
    #     id = offsets[-i - 1]
    #     raw_parse = (
    #         raw_parse[:id]
    #         + "<tr><td>[*table"
    #         + str(len(offsets) - i)
    #         + "]</td></tr>"
    #         + raw_parse[id:]
    #     )

    offsets = []
    table_ids = {}  # Track table IDs
    for i in re.finditer("<table", raw_parse.lower()):
        offset = i.span()[0]
        offset = offset + raw_parse[offset:].lower().index("<tr")
        offsets.append(offset)

    for i in range(len(offsets)):
        id = offsets[-i - 1]
        table_num = len(offsets) - i
        table_ids[id] = str(table_num)  # Store the mapping
        raw_parse = (
            raw_parse[:id]
            + "<tr><td>[*table"
            + str(table_num)
            + "]</td></tr>"
            + raw_parse[id:]
        )

    html_document = HTMLDocument.from_string(raw_parse).doc_after_cleaners(
        skip_headers_and_footers=True, inplace=True
    )

    for element in html_document.elements:
        # print(element.text[:30])
        element.text = clean_extra_whitespace(element.text)
        # text = element.text.lower()[:30]
        # if (("tableofcontents" in text) or ("index" in text)) and element.links:
        #     element.text = ""
        # if element.category == "Table":
        #     print(element.text_as_html[:60])
        #     element.text = element.text[element.text.rindex("]") + 1 :]
        #     id = element.text_as_html[
        #         element.text_as_html.rindex("[") + 7 : element.text_as_html.rindex("]")
        #     ]
        #     element.text_as_html = (
        #         "<table>"
        #         + element.text_as_html[element.text_as_html.rindex("]") + 11 :]
        #     )
        #     element.tid = id
        #     # print(id)
        if element.category == "Table":
            # Find the table ID from the placeholder text
            if "[*table" in element.text:
                start = element.text.rfind("[*table") + 7
                end = element.text.find("]", start)
                element.tid = element.text[start:end] if end != -1 else "unknown"
            else:
                element.tid = "unknown"

            # Remove the placeholder
            if "]" in element.text:
                element.text = element.text[element.text.rindex("]") + 1 :]

            element.text_as_html = (
                "<table>"
                + element.text_as_html[element.text_as_html.rindex("]") + 11 :]
            )

    # look at text only after table of content
    idtoc = 0
    if len(html_document.pages) > 5:
        for p in [0, 1, 2, 3, 4, 5, 6]:
            f = list(
                filter(
                    lambda p: (
                        p.category != "Table"
                        and "exhibit" in p.text.lower().replace(" ", "")[:20]
                    )
                    or (
                        p.category == "Table"
                        and "exhibit" in p.text.lower().replace(" ", "")
                    ),
                    html_document.pages[p].elements,
                )
            ) + list(
                filter(
                    lambda p: (
                        p.category != "Table"
                        and "signature" in p.text.lower().replace(" ", "")[:20]
                    )
                    or (
                        p.category == "Table"
                        and "signature" in p.text.lower().replace(" ", "")
                    ),
                    html_document.pages[p].elements,
                )
            )
            if f:
                idtoc = html_document.elements.index(f[-1]) + 1
                break

    # Tagging html
    tagid = 0
    anchorid = {}
    anchor_texts = []
    ids = list(map(lambda p: p.id, html_document.elements))
    unique_ids = list(filter(lambda p: ids.count(p) == 1, ids))
    for i in range(0, len(html_document.elements), 6):
        if html_document.elements[i].category != "Table":
            key = ">" + " ".join(html_document.elements[i].text.split(" ")[:10])
            # todo: ignoring some tags now
            if (
                (html_document.elements[i].text not in anchor_texts)
                and (key in raw_disp)
                and (html_document.elements[i].id in unique_ids)
            ):
                id = raw_disp.index(key)
                if "<" + html_document.elements[i].tag in raw_disp[:id]:
                    id = (
                        raw_disp[:id].rindex("<" + html_document.elements[i].tag)
                        + len(html_document.elements[i].tag)
                        + 1
                    )
                    anchor_texts.append(html_document.elements[i].text)
                    anchorid[html_document.elements[i].id] = tagid
                    raw_disp = (
                        raw_disp[:id] + ' id="tag' + str(tagid) + '"' + raw_disp[id:]
                    )
                    tagid += 1

    index = {}
    index["0"] = {"id": 0, "guid": "", "order": 0}
    for element in html_document.elements[idtoc:-2]:
        offset = idtoc if len(index) == 1 else index[list(index)[-1]]["id"] + 1
        id = html_document.elements[offset:].index(element) + offset
        rtext = element.text.lower()
        text = element.text.lower()
        nexttext = html_document.elements[id + 1].text.lower()
        nextelm = html_document.elements[id + 1]
        ptext = html_document.elements[id - 1].text.lower().split(" ")[-1]
        match = match_item_title(ptext, rtext, text)
        if match and (idtoc == 0 or ((not element.links) and (not nextelm.links))):
            if form == "10-Q":
                p1 = is_10q_part1_item_title(text, nexttext)
                p2 = is_10q_part2_item_title(text, nexttext)
                p = p1 or p2
            else:
                p = is_10k_item_title(element.text, nexttext)
            if p and (p[1] >= index[list(index)[-1]]["order"]):
                index[p[0]] = {"id": id, "guid": element.id, "order": p[1]}
        # print(element.text)

    if form == "10-Q" and "1.1" not in index:
        lst = list(
            filter(
                lambda p: "consolidated" in p.text.lower().replace(" ", "")
                and "statements" in p.text.lower().replace(" ", ""),
                html_document.elements[idtoc:],
            )
        )
        if lst:
            id = html_document.elements.index(lst[0])
            index["1.1"] = {"id": id, "guid": "", "order": 1}
            index = dict(sorted(index.items(), key=lambda item: item))

    ids = [index[i]["id"] for i in index]
    guids = [index[i]["guid"] for i in index]
    titles = [i for i in index]

    output = ""
    for i in range(len(ids)):
        for element in html_document.elements[
            ids[i] : ids[i + 1] if i < len(ids) - 1 else -1
        ]:
            if element.id != guids[i] and isinstance(element, Table):
                if (
                    not element.text_as_html.replace("<td></td>", "")
                    .replace("<tr></tr>", "")
                    .replace("<table></table>", "")
                ):
                    continue
                markdown = html2md.process(
                    io.StringIO(element.text_as_html), element.tid
                )
                if markdown:
                    output += element.tid + "," + element.text_as_html + "\n"

    return output


if __name__ == "__main__":
    with open("table_parsing/sample_output.htm", "w", encoding="utf-8") as f:
        f.write(parse_html("table_parsing/htm_input/cvs_Current_Folio_10K.htm", True))
