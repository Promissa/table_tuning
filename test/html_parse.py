from src.html_parse import *

file_path = "data/sec_samples/10-K/tsla-20241231.html"
output_path = "test/test_output/html_parse/"
parse(file_path, output_path, type="markdown")
# print(detect_sec_type(read_html(file_path)))
