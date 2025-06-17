import os
from bs4 import BeautifulSoup


def fix_html(html_content: str) -> str:
    """Fix malformed HTML using BeautifulSoup."""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.prettify()


def fix_html_files_in_folder(folder_path: str, output_dir: str = None) -> None:
    """
    Recursively fix all HTML files in a directory.

    Args:
        folder_path (str): The root folder to start searching for HTML files.
        output_dir (str): Optional. If provided, save fixed files to this path instead of overwriting.
    """
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith((".html", ".htm")):
                full_path = os.path.join(root, file)

                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    html_content = f.read()

                fixed_content = fix_html(html_content)

                # Determine output path
                if output_dir:
                    relative_path = os.path.relpath(full_path, folder_path)
                    output_path = os.path.join(output_dir, relative_path)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                else:
                    output_path = full_path  # overwrite

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)

                print(f"Fixed: {output_path}")


# Example usage:
# fix_html_files_in_folder("/path/to/html/folder")                     # Overwrite
if __name__ == "__main__":
    fix_html_files_in_folder(
        "data/sec_samples", "data/sec_samples_fixed"
    )  # Save to new folder
