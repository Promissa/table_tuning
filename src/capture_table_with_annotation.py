import os
import sys
import argparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw


def parse_args():
    p = argparse.ArgumentParser(
        description="Extract tables from HTML, save images, generate Pascal VOC XML, and annotate images based on XML."
    )
    p.add_argument("input_dir", help="Root directory for HTML files (depth ≤2)")
    p.add_argument(
        "-o",
        "--out_root",
        default="tables_output",
        help="Directory to save images, XML, and annotations",
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


def make_pascal_voc_xml(folder, filename, img_w, img_h, objects):
    ann = ET.Element("annotation")
    ET.SubElement(ann, "folder").text = folder
    ET.SubElement(ann, "filename").text = filename
    size = ET.SubElement(ann, "size")
    ET.SubElement(size, "width").text = str(img_w)
    ET.SubElement(size, "height").text = str(img_h)
    ET.SubElement(size, "depth").text = "3"
    ET.SubElement(ann, "segmented").text = "0"
    for obj in objects:
        o = ET.SubElement(ann, "object")
        ET.SubElement(o, "name").text = obj["name"]
        ET.SubElement(o, "pose").text = "Frontal"
        ET.SubElement(o, "truncated").text = "0"
        ET.SubElement(o, "difficult").text = "0"
        ET.SubElement(o, "occluded").text = "0"
        bb = ET.SubElement(o, "bndbox")
        ET.SubElement(bb, "xmin").text = str(obj["xmin"])
        ET.SubElement(bb, "ymin").text = str(obj["ymin"])
        ET.SubElement(bb, "xmax").text = str(obj["xmax"])
        ET.SubElement(bb, "ymax").text = str(obj["ymax"])

    def indent(el, lvl=0):
        sp = "\n" + lvl * "  "
        if len(el):
            if not el.text or not el.text.strip():
                el.text = sp + "  "
            for c in el:
                indent(c, lvl + 1)
            if not c.tail or not c.tail.strip():
                c.tail = sp
        if lvl and (not el.tail or not el.tail.strip()):
            el.tail = sp

    indent(ann)
    return ET.tostring(ann, encoding="utf-8")


def annotate_image_with_xml(image_path, xml_path, out_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    im = Image.open(image_path)
    draw = ImageDraw.Draw(im)
    for obj in root.findall("object"):
        bb = obj.find("bndbox")
        xmin = int(bb.find("xmin").text)
        ymin = int(bb.find("ymin").text)
        xmax = int(bb.find("xmax").text)
        ymax = int(bb.find("ymax").text)
        draw.rectangle([xmin, ymin, xmax, ymax], outline="red", width=2)
    im.save(out_path)


def main():
    args = parse_args()
    os.makedirs(args.out_root, exist_ok=True)
    htmls = list(find_html_files(args.input_dir, max_depth=2))
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

            html = load_html(os.path.join(dirpath, fname))
            soup = BeautifulSoup(html, "html.parser")
            head = extract_head(soup)
            tables = soup.find_all("table")
            if not tables:
                continue

            snippet_head = f"<!DOCTYPE html>\n<html>\n{head}\n<body>"
            snippet_tail = "\n</body>\n</html>"

            for tidx, tbl in enumerate(tables, start=1):
                tmp = BeautifulSoup(str(tbl), "html.parser").table
                for tr in tmp.find_all("tr"):
                    if not any(
                        c.get_text(strip=True) for c in tr.find_all(["td", "th"])
                    ):
                        tr.decompose()
                snippet = snippet_head + str(tmp) + snippet_tail
                page.set_content(snippet, wait_until="networkidle")
                el = page.query_selector("table")
                if not el:
                    continue
                box = el.bounding_box()
                if not box or box["width"] < 100 or box["height"] < 50:
                    continue
                x0, y0 = box["x"], box["y"]
                img_w, img_h = int(box["width"]), int(box["height"])

                # screenshot
                img_path = os.path.join(outd, f"table_{tidx}.png")
                el.screenshot(path=img_path)

                # collect objects
                rows = page.query_selector_all("tr")
                objs = []
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
                cells = [r.query_selector_all("th,td") for r in rows]
                maxc = max((len(c) for c in cells), default=0)
                for cidx in range(maxc):
                    boxes = []
                    for cl in cells:
                        if cidx < len(cl):
                            b = cl[cidx].bounding_box()
                            if b and cl[cidx].inner_text().strip():
                                boxes.append(b)
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

                # write XML
                xml_path = os.path.join(outd, f"table_{tidx}.xml")
                xml_bytes = make_pascal_voc_xml(
                    folder=os.path.basename(outd),
                    filename=f"table_{tidx}.png",
                    img_w=img_w,
                    img_h=img_h,
                    objects=objs,
                )
                with open(xml_path, "wb") as xf:
                    xf.write(xml_bytes)

                # annotate image from XML
                annotated_path = os.path.join(outd, f"table_{tidx}_annotated.png")
                annotate_image_with_xml(img_path, xml_path, annotated_path)

                print(f"Created: {img_path}, {xml_path}, {annotated_path}")

        browser.close()


if __name__ == "__main__":
    main()
