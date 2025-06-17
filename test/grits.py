from src.grits import *
from src.html_parse import read_html
import numpy as np

file_path = "data/htm_input/sec_sample.html"
output_path = "test/test_output/html_parse/"
cells = html_to_cells(read_html(file_path))
for i in range(len(cells)):
    cells[i]["cell_text"] = cells[i]["cell_text"].strip()
grid = cells_to_grid(cells, key="cell_text")
