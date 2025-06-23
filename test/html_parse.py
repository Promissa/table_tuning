from src.html_parse import *

file_path = "data/sec_samples/aapl-20240928.ht"
output_path = "test/test_output/html_parse/"
parse(file_path, output_path, type="csv")
# print(detect_sec_type(read_html(file_path)))
