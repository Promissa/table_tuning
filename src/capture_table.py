import os
import sys
import argparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def parse_args():
    p = argparse.ArgumentParser(
        description="Find HTML files up to 2 levels deep, extract tables, and render each to PNGs"
    )
    p.add_argument("input_dir", help="Root directory to search for HTML files")
    p.add_argument(
        "-o", "--out_root", default="tables_png", help="Root directory to save all PNGs"
    )
    return p.parse_args()


def load_html(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_head(soup):
    return str(soup.head) if soup.head else ""


def find_html_files(root, max_depth=2):
    """Yield (dirpath, filename) for .html/.htm files up to max_depth beneath root."""
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            # don't recurse any deeper
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.lower().endswith((".html", ".htm")):
                yield dirpath, fn


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
                # page.wait_for_timeout(200)

                el = page.query_selector("table")
                if not el:
                    print(f"  ⚠️  Table #{it} not in DOM, skipping.")
                    continue

                box = el.bounding_box()
                height = box["height"] if box else 0
                if height < 50:
                    print(f"  🚫  Table #{it} width {height:.0f}px < 50px, skipping.")
                    continue

                out_path = os.path.join(out_dir, f"table_{idx}.png")
                el.screenshot(path=out_path)
                print(f"  ✔️  table_{idx}.png ({height:.0f}px high)")
                idx += 1

        browser.close()

    print(f"\n✅  Done! Check your screenshots under “{args.out_root}/”.")


if __name__ == "__main__":
    main()
