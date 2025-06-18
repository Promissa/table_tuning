import os
import sys
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def extract_tables(html_content):
    """提取所有 <table>，只保留行数 > 1 的列表"""
    soup = BeautifulSoup(html_content, "html.parser")
    tables = []
    for tbl in soup.find_all("table"):
        if len(tbl.find_all("tr")) > 1:
            tables.append(str(tbl))
    return tables


def render_and_screenshot(table_html, output_path, index):
    """渲染 table 并截图，带 20px 留白"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("window-size=1200x800")
    driver = webdriver.Chrome(options=chrome_options)

    html = f"""
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body, html {{ margin:0; padding:0; }}
          #wrapper {{ padding: 20px; }}
          table {{ border-collapse: collapse; display: table; }}
          table, th, td {{ border: 1px solid #333; padding: 4px; }}
        </style>
      </head>
      <body>
        <div id="wrapper">{table_html}</div>
      </body>
    </html>
    """

    tmp_file = f"tmp_table_{index}.html"
    with open(tmp_file, "w", encoding="utf-8", errors="replace") as f:
        f.write(html)

    driver.get("file://" + os.path.abspath(tmp_file))
    time.sleep(0.5)

    wrapper = driver.find_element(By.ID, "wrapper")
    rect = driver.execute_script(
        "const r=arguments[0].getBoundingClientRect();"
        "return {width:r.width,height:r.height};",
        wrapper,
    )

    w = max(int(rect["width"]) + 20, 840)
    h = max(int(rect["height"]) + 20, 640)
    driver.set_window_size(w, h)
    time.sleep(0.2)

    os.makedirs(output_path, exist_ok=True)
    screenshot_path = os.path.join(output_path, f"table_{index}.png")
    wrapper.screenshot(screenshot_path)

    driver.quit()
    os.remove(tmp_file)
    print(f"Screenshot saved: {screenshot_path}")


def process_file(html_path, input_base, output_base):
    """
    处理单个 HTML 文件：
    - 计算相对路径
    - 在相对路径下，再创建一个以文件名为名的子文件夹
    - 将截图输出到该子文件夹
    """
    # 相对父目录路径
    rel_parent = os.path.relpath(os.path.dirname(html_path), input_base)
    # HTML 文件名（无扩展名）
    name = os.path.splitext(os.path.basename(html_path))[0]
    # 最终输出目录：output_base/rel_parent/name
    target_dir = os.path.join(output_base, rel_parent, name)

    # 读取并解码
    with open(html_path, "rb") as f:
        raw = f.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")

    tables = extract_tables(content)
    if not tables:
        print(f"[Skipped] {html_path}（无符合条件的表格）")
        return

    for idx, tbl_html in enumerate(tables, 1):
        render_and_screenshot(tbl_html, target_dir, idx)


def main(input_path, output_base):
    if not os.path.exists(input_path):
        print(f"Error: 输入路径不存在: {input_path}")
        sys.exit(1)
    os.makedirs(output_base, exist_ok=True)

    # 单文件模式
    if os.path.isfile(input_path):
        process_file(input_path, os.path.dirname(input_path), output_base)
        return

    # 目录模式：两层深度递归
    for root, dirs, files in os.walk(input_path):
        depth = os.path.relpath(root, input_path).count(os.sep)
        if depth > 2:
            dirs[:] = []  # 阻止更深层遍历
            continue
        for fname in files:
            if fname.lower().endswith((".html", ".htm")):
                html_file = os.path.join(root, fname)
                print(f"Processing: {html_file}")
                process_file(html_file, input_path, output_base)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python screenshot_tables.py <input_file_or_dir> <output_dir>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
