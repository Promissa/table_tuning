import xml.etree.ElementTree as ET
from collections import defaultdict

# Load and parse the XML
xml_path = "/Users/bytedance/projects/table_tuning/data/PMC493271_table_2.xml"
tree = ET.parse(xml_path)
root = tree.getroot()

# Dictionary to store results
bbox_dict = defaultdict(list)

# Iterate over each object in the XML
for obj in root.findall("object"):
    name = obj.find("name").text.strip()
    bndbox = obj.find("bndbox")
    if bndbox is not None:
        xmin = float(bndbox.find("xmin").text)
        xmax = float(bndbox.find("xmax").text)
        ymin = float(bndbox.find("ymin").text)
        ymax = float(bndbox.find("ymax").text)
        bbox_dict[name].append((xmin, xmax, ymin, ymax))

import pandas as pd

# Convert to DataFrame for display
result_df = pd.DataFrame(
    [(k, *bbox) for k, v in bbox_dict.items() for bbox in v],
    columns=["object_name", "xmin", "xmax", "ymin", "ymax"],
)

print(result_df)
