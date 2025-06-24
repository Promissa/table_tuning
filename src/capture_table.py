import os
import sys
import argparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def parse_args():
    p = argparse.ArgumentParser(
        description="Find HTML files up to 2 levels deep, extract tables, render PNGs, and output Pascal VOC XML."
    )
    p.add_argument("input_dir", help="Root directory to search for HTML files")
    p.add_argument(
        "-o",
        "--out_root",
        default="tables_png",
        help="Root directory to save PNGs + XML",
    )
    return p.parse_args()


def load_html(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_head(soup):
    return str(soup.head) if soup.head else ""


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
    ann = ET.Element("annotation")
    ET.SubElement(ann, "folder").text = folder
    ET.SubElement(ann, "filename").text = filename
    ET.SubElement(ann, "path").text = os.path.join(folder, filename)

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

    # indent
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
        print("No HTML files found up to 2 levels deep under", args.input_dir)
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        for dirpath, fname in html_files:
            rel_dir = os.path.relpath(dirpath, args.input_dir)
            name_noext, _ = os.path.splitext(fname)
            out_dir = os.path.join(args.out_root, rel_dir, name_noext)
            os.makedirs(out_dir, exist_ok=True)

            html_path = os.path.join(dirpath, fname)
            html = load_html(html_path)
            soup = BeautifulSoup(html, "html.parser")
            head_html = extract_head(soup)
            tables = soup.find_all("table")

            if not tables:
                print(f"🔍  {html_path}: no <table> tags, skipping.")
                continue

            print(f"\nProcessing {html_path}, found {len(tables)} table(s)...")
            idx = 0
            for it, table in enumerate(tables, start=1):
                snippet = f"""<!DOCTYPE html>
                            <html>
                            {head_html}
                            <body>
                                {str(table)}
                            </body>
                            </html>"""
                page.set_content(snippet, wait_until="networkidle")

                el = page.query_selector("table")
                if not el:
                    print(f"  ⚠️  Table #{it} not in DOM, skipping.")
                    continue

                box = el.bounding_box()
                height = box["height"] if box else 0
                if height < 50:
                    print(f"  🚫  Table #{it} height {height:.0f}px < 50px, skipping.")
                    continue

                # compute boxes
                tbl_x, tbl_y = box["x"], box["y"]
                img_w, img_h = int(box["width"]), int(box["height"])

                rows = page.query_selector_all("tr")
                row_objs = []
                for ridx, row in enumerate(rows):
                    b = row.bounding_box()
                    if not b:
                        continue
                    row_objs.append(
                        {
                            "name": "table row",
                            "xmin": int(b["x"] - tbl_x),
                            "ymin": int(b["y"] - tbl_y),
                            "xmax": int(b["x"] - tbl_x + b["width"]),
                            "ymax": int(b["y"] - tbl_y + b["height"]),
                        }
                    )

                cells_per_row = [r.query_selector_all("th,td") for r in rows]
                max_cols = max((len(c) for c in cells_per_row), default=0)
                col_objs = []
                for cidx in range(max_cols):
                    boxes = []
                    for cells in cells_per_row:
                        if cidx < len(cells):
                            b = cells[cidx].bounding_box()
                            if b:
                                boxes.append(b)
                    if not boxes:
                        continue
                    min_x = min(b["x"] for b in boxes)
                    min_y = min(b["y"] for b in boxes)
                    max_x2 = max(b["x"] + b["width"] for b in boxes)
                    max_y2 = max(b["y"] + b["height"] for b in boxes)
                    col_objs.append(
                        {
                            "name": "table column",
                            "xmin": int(min_x - tbl_x),
                            "ymin": int(min_y - tbl_y),
                            "xmax": int(max_x2 - tbl_x),
                            "ymax": int(max_y2 - tbl_y),
                        }
                    )

                # screenshot and save xml
                img_path = os.path.join(out_dir, f"table_{idx}.png")
                el.screenshot(path=img_path)
                objects = row_objs + col_objs
                xml = make_pascal_voc_xml(
                    folder=os.path.basename(out_dir),
                    filename=os.path.basename(img_path),
                    img_width=img_w,
                    img_height=img_h,
                    objects=objects,
                )
                xml_path = os.path.join(out_dir, f"table_{idx}.xml")
                with open(xml_path, "wb") as xf:
                    xf.write(xml)

                print(f"  ✔️  table_{idx}.png + table_{idx}.xml ({height:.0f}px high)")
                idx += 1

        browser.close()

    print(f"\n✅  Done! Outputs under '{args.out_root}/'.")


if __name__ == "__main__":
    main()
