import os
import sys
import argparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def parse_args():
    p = argparse.ArgumentParser(
        description="Find HTML (depth≤2), render tables to PNG, and output Pascal-VOC XML for rows/columns"
    )
    p.add_argument("input_dir", help="Root dir to search for HTML files")
    p.add_argument(
        "-o", "--out_root", default="tables_png", help="Root dir to save PNGs + XML"
    )
    return p.parse_args()


def load_html(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_head_content(soup):
    if not soup.head:
        return ""
    return "".join(str(child) for child in soup.head.contents)


def find_html_files(root, max_depth=2):
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.lower().endswith((".html", ".htm")):
                yield dirpath, fn


def make_pascal_voc_xml(folder, filename, img_width, img_height, objects):
    """
    objects is a list of dicts:
      { 'name': str, 'xmin': int, 'ymin': int, 'xmax': int, 'ymax': int }
    """
    ann = ET.Element("annotation")

    ET.SubElement(ann, "folder").text = folder
    ET.SubElement(ann, "filename").text = filename
    ET.SubElement(ann, "path").text = os.path.join(folder, filename)

    # size
    size = ET.SubElement(ann, "size")
    ET.SubElement(size, "width").text = str(img_width)
    ET.SubElement(size, "height").text = str(img_height)
    ET.SubElement(size, "depth").text = "3"

    ET.SubElement(ann, "segmented").text = "0"

    for obj in objects:
        obj_el = ET.SubElement(ann, "object")
        ET.SubElement(obj_el, "name").text = obj["name"]
        ET.SubElement(obj_el, "pose").text = "Frontal"
        ET.SubElement(obj_el, "truncated").text = "0"
        ET.SubElement(obj_el, "difficult").text = "0"
        ET.SubElement(obj_el, "occluded").text = "0"

        bb = ET.SubElement(obj_el, "bndbox")
        ET.SubElement(bb, "xmin").text = str(obj["xmin"])
        ET.SubElement(bb, "ymin").text = str(obj["ymin"])
        ET.SubElement(bb, "xmax").text = str(obj["xmax"])
        ET.SubElement(bb, "ymax").text = str(obj["ymax"])

    # pretty‐print indentation
    def indent(elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

    indent(ann)

    return ET.tostring(ann, encoding="utf-8")


def main():
    args = parse_args()
    os.makedirs(args.out_root, exist_ok=True)

    html_files = list(find_html_files(args.input_dir, max_depth=2))
    if not html_files:
        print("No HTML files found up to 2 levels under", args.input_dir)
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        for dirpath, fname in html_files:
            rel_dir = os.path.relpath(dirpath, args.input_dir)
            name_noext, _ = os.path.splitext(fname)
            out_dir = os.path.join(args.out_root, rel_dir, name_noext)
            os.makedirs(out_dir, exist_ok=True)

            html = load_html(os.path.join(dirpath, fname))
            soup = BeautifulSoup(html, "html.parser")
            head_inner = extract_head_content(soup)
            tables = soup.find_all("table")
            if not tables:
                print(f"🔍 {fname}: no <table>, skipping.")
                continue

            print(f"\n📄 Processing {fname} ({len(tables)} table(s))…")
            for tidx, table in enumerate(tables, start=1):
                # render snippet
                snippet = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {head_inner}
</head>
<body>
  {str(table)}
</body>
</html>"""
                page.set_content(snippet, wait_until="networkidle")
                page.wait_for_timeout(200)

                tbl = page.query_selector("table")
                if not tbl:
                    print(f"  ⚠️ Table #{tidx} not found, skipping.")
                    continue

                tbl_box = tbl.bounding_box()
                if not tbl_box or tbl_box["width"] < 100:
                    w = tbl_box["width"] if tbl_box else 0
                    print(f"  🚫 Table #{tidx} width {w:.0f}px <100px, skipping.")
                    continue

                # compute row boxes
                rows = page.query_selector_all("tr")
                row_boxes = []
                for ridx, row in enumerate(rows):
                    b = row.bounding_box()
                    if not b:
                        continue
                    row_boxes.append(
                        {
                            "name": "table row",
                            "xmin": int(b["x"] - tbl_box["x"]),
                            "ymin": int(b["y"] - tbl_box["y"]),
                            "xmax": int(b["x"] - tbl_box["x"] + b["width"]),
                            "ymax": int(b["y"] - tbl_box["y"] + b["height"]),
                        }
                    )

                # compute column boxes
                row_cells = [r.query_selector_all("th,td") for r in rows]
                max_cols = max((len(c) for c in row_cells), default=0)
                col_boxes = []
                for cidx in range(max_cols):
                    cell_boxes = []
                    for cells in row_cells:
                        if cidx < len(cells):
                            b = cells[cidx].bounding_box()
                            if b:
                                cell_boxes.append(b)
                    if not cell_boxes:
                        continue
                    min_x = min(b["x"] for b in cell_boxes)
                    min_y = min(b["y"] for b in cell_boxes)
                    max_x2 = max(b["x"] + b["width"] for b in cell_boxes)
                    max_y2 = max(b["y"] + b["height"] for b in cell_boxes)
                    col_boxes.append(
                        {
                            "name": "table column",
                            "xmin": int(min_x - tbl_box["x"]),
                            "ymin": int(min_y - tbl_box["y"]),
                            "xmax": int(max_x2 - tbl_box["x"]),
                            "ymax": int(max_y2 - tbl_box["y"]),
                        }
                    )

                # screenshot
                img_path = os.path.join(out_dir, f"table_{tidx}.png")
                tbl.screenshot(path=img_path)
                print(f"  ✔️ table_{tidx}.png")

                # build and save Pascal VOC XML
                objects = row_boxes + col_boxes
                xml = make_pascal_voc_xml(
                    folder=os.path.basename(out_dir),
                    filename=os.path.basename(img_path),
                    img_width=int(tbl_box["width"]),
                    img_height=int(tbl_box["height"]),
                    objects=objects,
                )
                xml_path = os.path.join(out_dir, f"table_{tidx}.xml")
                with open(xml_path, "wb") as xf:
                    xf.write(xml)
                print(f"  ✔️ table_{tidx}.xml")

        browser.close()

    print(f"\n✅ Done! Check outputs under “{args.out_root}/”.\n")


if __name__ == "__main__":
    main()
