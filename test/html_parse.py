from src.html_parse import *

file_path = "data/sec_samples/20-F/000119312524187406:d759422d20f.html"
output_path = "test/test_output/html_parse/"
parse(file_path, output_path, type="md")


# print(detect_sec_type(read_html(file_path)))
html_sample = """
<td colspan="13" style="vertical-align: bottom; white-space: nowrap">
                                    <ix:nonnumeric name="us-gaap:LesseeOperatingLeaseDescription" contextref="P04_01_2023To03_31_2024" id="ixv-36781">Refer to note 28— “Commitments and
                                        contingencies—Lease<br>commitments” for more
                                        information and balances as at March 31, 2024.<br></ix:nonnumeric>
                                </td>
"""
item = BeautifulSoup(html_sample, "html.parser").find_all("td")
# print(item[0]["colspan"])
# print(get_indent(BeautifulSoup(html_sample, "html.parser")))
# print(item.find("div"))
