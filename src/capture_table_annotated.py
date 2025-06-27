import os
import sys
import json
import argparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw


def parse_args():
    p = argparse.ArgumentParser(
        description="Extract tables from HTML, save images, generate JSON annotations for AnyLabeling, and annotate images based on JSON."
    )
    p.add_argument("input_dir", help="Root directory for HTML files (depth ≤2)")
    p.add_argument(
        "-o",
        "--out_root",
        default="tables_output",
        help="Directory to save images, JSON annotations, and annotated images",
    )
    return p.parse_args()


def load_html(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_head(soup):
    # preserve original head for CSS
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


def write_json_annotation(out_path, image_filename, img_w, img_h, objects):
    data = {"image": image_filename, "width": img_w, "height": img_h, "annotations": []}
    for obj in objects:
        # bbox as [xmin, ymin, xmax, ymax]
        data["annotations"].append(
            {
                "label": obj["name"],
                "bbox": [obj["xmin"], obj["ymin"], obj["xmax"], obj["ymax"]],
            }
        )
    with open(out_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    os.makedirs(args.out_root, exist_ok=True)
    htmls = list(find_html_files(args.input_dir, max_depth=1))
    # htmls = args.input_dir
    if not htmls:
        print("No HTML files found.")
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        for dirpath, fname in htmls:
            rel = os.path.relpath(dirpath, args.input_dir)
            base, _ = os.path.splitext(fname)
            outd = os.path.join(args.out_root, rel, base)
            os.makedirs(outd, exist_ok=True)

            # load and parse HTML
            html = load_html(os.path.join(dirpath, fname))
            soup = BeautifulSoup(html, "html.parser")
            head = extract_head(soup)
            tables = soup.find_all("table")
            if not tables:
                continue

            snippet_head = f"<!DOCTYPE html>\n<html>\n{head}\n<body>"
            snippet_tail = "\n</body>\n</html>"

            for tidx, tbl in enumerate(tables, start=1):
                # remove empty rows
                tmp = BeautifulSoup(str(tbl), "html.parser").table
                for tr in tmp.find_all("tr"):
                    if not any(
                        c.get_text(strip=True) for c in tr.find_all(["td", "th"])
                    ):
                        tr.decompose()

                # render snippet
                snippet = snippet_head + str(tmp) + snippet_tail
                page.set_content(snippet, wait_until="networkidle")
                el = page.query_selector("table")
                if not el:
                    continue
                box = el.bounding_box() or {}
                # skip too small
                if box.get("width", 0) < 100 or box.get("height", 0) < 50:
                    continue
                x0, y0 = box["x"], box["y"]
                img_w, img_h = int(box["width"]), int(box["height"])

                # screenshot raw table
                img_path = os.path.join(outd, f"table_{tidx}.png")
                el.screenshot(path=img_path)

                # collect annotations
                rows = page.query_selector_all("tr")
                objs = []
                # rows
                for r in rows:
                    txt = r.inner_text().strip()
                    if not txt:
                        continue
                    br = r.bounding_box()
                    if not br:
                        continue
                    objs.append(
                        {
                            "name": "table row",
                            "xmin": int(br["x"] - x0),
                            "ymin": int(br["y"] - y0),
                            "xmax": int(br["x"] - x0 + br["width"]),
                            "ymax": int(br["y"] - y0 + br["height"]),
                        }
                    )
                # columns
                cells = [r.query_selector_all("th,td") for r in rows]
                maxc = max((len(c) for c in cells), default=0)
                for cidx in range(maxc):
                    boxes = []
                    for cl in cells:
                        if cidx < len(cl):
                            bb = cl[cidx].bounding_box()
                            if bb and cl[cidx].inner_text().strip():
                                boxes.append(bb)
                    if not boxes:
                        continue
                    minx = min(b["x"] for b in boxes)
                    miny = min(b["y"] for b in boxes)
                    maxx2 = max(b["x"] + b["width"] for b in boxes)
                    maxy2 = max(b["y"] + b["height"] for b in boxes)
                    objs.append(
                        {
                            "name": "table column",
                            "xmin": int(minx - x0),
                            "ymin": int(miny - y0),
                            "xmax": int(maxx2 - x0),
                            "ymax": int(maxy2 - y0),
                        }
                    )

                # write JSON annotation
                json_path = os.path.join(outd, f"table_{tidx}.json")
                write_json_annotation(
                    json_path, os.path.basename(img_path), img_w, img_h, objs
                )

                # annotate image
                annotated_path = os.path.join(outd, f"table_{tidx}_annotated.png")
                im = Image.open(img_path)
                draw = ImageDraw.Draw(im)
                for o in objs:
                    draw.rectangle(
                        [o["xmin"], o["ymin"], o["xmax"], o["ymax"]],
                        outline="red",
                        width=2,
                    )
                im.save(annotated_path)

                print(f"Created: {img_path}, {json_path}, {annotated_path}")

        browser.close()


if __name__ == "__main__":
    main()
