from src.html_parse import *

file_path = "data/sec_samples/20-F/000119312524187406:d759422d20f.html"
output_path = "test/test_output/html_parse/"
parse(file_path, output_path, type="csv")
# print(detect_sec_type(read_html(file_path)))
