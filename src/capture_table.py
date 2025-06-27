import os
import sys
import argparse
import xml.etree.ElementTree as ET
from tqdm import tqdm
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


def main():
    args = parse_args()
    os.makedirs(args.out_root, exist_ok=True)

    html_files = list(find_html_files(args.input_dir, max_depth=1))
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
            for it, table in tqdm(enumerate(tables, start=1), total=len(tables)):
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
                if not box:
                    continue
                height = box["height"]
                if height < 50:
                    # print(f"  🚫  Table #{it} height {height:.0f}px < 50px, skipping.")
                    continue

                # original table bounds
                tbl_x, tbl_y = box["x"], box["y"]
                orig_w, orig_h = int(box["width"]), int(box["height"])

                # add padding
                padding = 30
                pad_x = max(tbl_x - padding, 0)
                pad_y = max(tbl_y - padding, 0)
                img_w = orig_w + padding * 2
                img_h = orig_h + padding * 2

                # screenshot with padding
                img_path = os.path.join(out_dir, f"table_{idx}.png")
                page.screenshot(
                    path=img_path,
                    clip={"x": pad_x, "y": pad_y, "width": img_w, "height": img_h},
                )

                # print(f"  ✔️  table_{idx}.png ({height:.0f}px high with padding)")
                idx += 1

        browser.close()

    print(f"\n✅  Done! Outputs under '{args.out_root}/'.")


if __name__ == "__main__":
    main()
