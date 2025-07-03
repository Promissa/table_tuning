import os
import sys
import json
import argparse
from tqdm import tqdm
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def parse_args():
    p = argparse.ArgumentParser(
        description="Find HTML files up to 2 levels deep, extract tables, render full table PNGs with padding via wrapper, output LabelMe-style JSON for rows, and JSON for cells with content using integer coordinates."
    )
    p.add_argument("input_dir", help="Root directory to search for HTML files")
    p.add_argument(
        "-o",
        "--out_root",
        default="tables_output",
        help="Root directory to save outputs",
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


def write_labelme_json(path, image_file, width, height, table_bbox, row_bboxes):
    data = {
        "version": "0.4.30",
        "flags": {},
        "shapes": [],
        "imagePath": image_file,
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
    }
    x0, y0, x1, y1 = table_bbox
    data["shapes"].append(
        {
            "label": "table",
            "text": "",
            "points": [[x0, y0], [x1, y1]],
            "group_id": None,
            "shape_type": "rectangle",
            "flags": {},
        }
    )
    for ymin, ymax in row_bboxes:
        data["shapes"].append(
            {
                "label": "table row",
                "text": "",
                "points": [[x0, ymin], [x1, ymax]],
                "group_id": None,
                "shape_type": "rectangle",
                "flags": {},
            }
        )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_cells_json(path, image_file, width, height, cell_objs):
    data = {
        "imagePath": image_file,
        "imageWidth": width,
        "imageHeight": height,
        "cells": [],
    }
    for obj in cell_objs:
        data["cells"].append(
            {"text": obj["text"], "bbox": [obj["x0"], obj["y0"], obj["x1"], obj["y1"]]}
        )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    os.makedirs(args.out_root, exist_ok=True)
    html_files = list(find_html_files(args.input_dir, max_depth=1))
    if not html_files:
        print("No HTML files found.")
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for dirpath, fname in html_files:
            rel = os.path.relpath(dirpath, args.input_dir)
            base, _ = os.path.splitext(fname)
            outd = os.path.join(args.out_root, rel, base)
            os.makedirs(outd, exist_ok=True)

            html = load_html(os.path.join(dirpath, fname))
            soup = BeautifulSoup(html, "html.parser")
            head = extract_head(soup)
            # inject border and no-wrap styles
            style_injection = "<style>table, th, td { border: 1px solid black !important; border-collapse: collapse; white-space: nowrap; }</style>"
            head_section = f"<head>{style_injection}{head}</head>"
            tables = soup.find_all("table")
            if not tables:
                continue

            print(f"\nProcessing {fname}: {len(tables)} tables...")
            idx = 0
            for tbl in tqdm(tables, total=len(tables)):
                tmp = BeautifulSoup(str(tbl), "html.parser").table
                for tr in tmp.find_all("tr"):
                    if not any(
                        td.get_text(strip=True) for td in tr.find_all(["td", "th"])
                    ):
                        tr.decompose()

                pad = 30
                snippet = f"""<!DOCTYPE html>
<html>
{head}
<body>
<div id='wrapper' style='padding:{pad}px; display:inline-block'>
{str(tmp)}
</div>
</body>
</html>"""
                page.set_content(snippet, wait_until="networkidle")

                wrapper = page.query_selector("#wrapper")
                if not wrapper:
                    continue
                wrapper_box = wrapper.bounding_box()
                if not wrapper_box:
                    continue

                img_file = f"table_{idx}.png"
                img_path = os.path.join(outd, img_file)
                wrapper.screenshot(path=img_path)

                table_el = page.query_selector("table")
                table_box = table_el.bounding_box()
                if (
                    not table_box
                    or table_box["width"] < 100
                    or table_box["height"] < 50
                ):
                    continue

                # integer coordinates
                rel_x0 = int(table_box["x"] - wrapper_box["x"])
                rel_y0 = int(table_box["y"] - wrapper_box["y"])
                rel_x1 = rel_x0 + int(table_box["width"])
                rel_y1 = rel_y0 + int(table_box["height"])
                table_bbox = [rel_x0, rel_y0, rel_x1, rel_y1]

                rows = page.query_selector_all("tr")
                row_bboxes = []
                for r in rows:
                    if not r.inner_text().strip():
                        continue
                    b = r.bounding_box()
                    if not b:
                        continue
                    ymin = int(b["y"] - wrapper_box["y"])
                    ymax = ymin + int(b["height"])
                    row_bboxes.append([ymin, ymax])

                cells = page.query_selector_all("td")
                cell_objs = []
                for c in cells:
                    text = c.inner_text().strip()
                    if not text:
                        continue
                    b = c.bounding_box()
                    if not b:
                        continue
                    x0 = int(b["x"] - wrapper_box["x"])
                    y0 = int(b["y"] - wrapper_box["y"])
                    x1 = x0 + int(b["width"])
                    y1 = y0 + int(b["height"])
                    cell_objs.append(
                        {"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
                    )

                img_w = int(wrapper_box["width"])
                img_h = int(wrapper_box["height"])

                json_file = f"table_{idx}.json"
                json_path = os.path.join(outd, json_file)
                write_labelme_json(
                    json_path, img_file, img_w, img_h, table_bbox, row_bboxes
                )

                cells_file = f"table_{idx}_cells.json"
                cells_path = os.path.join(outd, cells_file)
                write_cells_json(cells_path, img_file, img_w, img_h, cell_objs)

                print(f"Created: {img_path}, {json_path}, {cells_path}")
                idx += 1

        browser.close()


if __name__ == "__main__":
    main()
