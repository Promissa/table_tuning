import os
import time
import math
from urllib.parse import quote
from jinja2 import Template
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Jinja2 HTML template for rendering table with padding and single bottom border
tmpl_html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body { margin:0; padding:0; overflow:visible; }
    #wrapper {
      position: relative;
      width: {{ total_size }}px;
      height: {{ total_size }}px;
      padding: {{ pad }}px;
      box-sizing: border-box;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      background: #fff;
      overflow: visible;
    }
    table {
      width: 100%;
      height: auto;
      table-layout: fixed;
      border-collapse: collapse;
      border: 1px solid #333;
      border-bottom: none;
    }
    th, td {
      border: 1px solid #333;
      border-bottom: none;
      padding: 4px;
      box-sizing: border-box;
    }
    /* single bottom border under entire table */
    #wrapper::after {
      content: "";
      position: absolute;
      left: {{ pad }}px;
      right: {{ pad }}px;
      bottom: {{ pad }}px;
      border-bottom: 1px solid #333;
    }
  </style>
</head>
<body>
  <div id="wrapper">
    {{ table_html | safe }}
  </div>
</body>
</html>
"""


def extract_tables(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return [str(tbl) for tbl in soup.find_all("table") if len(tbl.find_all("tr")) > 1]


def probe_table_size(table_html, index):
    """
    Render a minimal HTML via Jinja2 to measure table dimensions without manual f-strings.
    """

    # Define a simple Jinja template
    probe_tmpl = Template(
        """
<html><head><meta charset='utf-8'><style>
  html, body { margin:0; padding:0; overflow:visible; }
  table { border-collapse: collapse; display: table; width:auto; height:auto; }
  table, th, td { border:1px solid #333; padding:4px; }
</style></head><body>{{ table_html | safe }}</body></html>
"""
    )
    # Render probe HTML
    probe_html = probe_tmpl.render(table_html=table_html)
    fn = f"probe_{index}.html"
    with open(fn, "w", encoding="utf-8", errors="replace") as f:
        f.write(probe_html)

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opts)
    driver.get("file://" + os.path.abspath(fn))
    time.sleep(0.2)
    elem = driver.find_element(By.TAG_NAME, "table")
    rect = driver.execute_script(
        "const r=arguments[0].getBoundingClientRect(); return {w:r.width,h:r.height};",
        elem,
    )
    driver.quit()
    os.remove(fn)
    return rect["w"], rect["h"]


def render_and_screenshot(table_html, output_dir, index):
    # 1) Probe original table size
    orig_w, orig_h = probe_table_size(table_html, index)
    area = orig_w * orig_h

    # 2) Compute square of equal area (1:1 aspect)
    side = math.sqrt(area)

    # 3) Clamp so table fits (ensures side >= max dimension)
    side = max(side, orig_w, orig_h)

    # 4) Add padding and ensure square container fits all rows
    pad = 20
    # initial square size from area
    total_size = math.ceil(side + pad * 2)
    # if table height needs more space, expand square to fit height
    min_height = math.ceil(side + pad * 2)
    if min_height > total_size:
        total_size = min_height

    # 5) Render final HTML via Jinja2
    template = Template(tmpl_html)
    final_html = template.render(total_size=total_size, pad=pad, table_html=table_html)

    # 6) Load HTML via data URI and screenshot
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(total_size, total_size)
    data_uri = "data:text/html;charset=utf-8," + quote(final_html)
    driver.get(data_uri)
    time.sleep(0.5)
    wrapper = driver.find_element(By.ID, "wrapper")

    os.makedirs(output_dir, exist_ok=True)
    out_png = os.path.join(output_dir, f"table_{index}.png")
    wrapper.screenshot(out_png)

    driver.quit()
    print(f"Saved {out_png}: {total_size}×{total_size}")


def process_html_file(html_path, base_input, base_output):
    rel = os.path.relpath(os.path.dirname(html_path), base_input)
    name = os.path.splitext(os.path.basename(html_path))[0]
    output_dir = os.path.join(base_output, rel, name)

    with open(html_path, "rb") as f:
        raw = f.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")

    tables = extract_tables(content)
    for idx, tbl in enumerate(tables, 1):
        render_and_screenshot(tbl, output_dir, idx)


def main(input_path, output_base):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found")
        return
    os.makedirs(output_base, exist_ok=True)
    html_files = []
    base_in = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
    if os.path.isfile(input_path):
        html_files = [input_path]
    else:
        for root, dirs, files in os.walk(input_path):
            if os.path.relpath(root, input_path).count(os.sep) > 2:
                dirs[:] = []
                continue
            for f in files:
                if f.lower().endswith((".html", ".htm")):
                    html_files.append(os.path.join(root, f))
    for path in html_files:
        print(f"Processing {path}")
        process_html_file(path, base_in, output_base)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python script.py <input> <output>")
    else:
        main(sys.argv[1], sys.argv[2])
