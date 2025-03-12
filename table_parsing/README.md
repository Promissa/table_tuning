# CSV Table Editor with Flask and Handsontable

## Features

- Upload HTML files: Users can upload HTML files which are then processed to extract tables.

- Edit CSV tables: The extracted tables are displayed and can be edited using Handsontable.

- Save changes: All edits are automatically saved to the server and cached locally.

- Table navigation: Navigate through multiple tables and ensure that edits are preserved when switching between tables.

    > This function may cause an error that will navigate to a neighboring table of the selected one.
    
- Download CSV files: Edited tables can be downloaded as CSV files compressed in a `.zip` file.

## Installation

```
pip install -r requirements.txt
```

## Running

```
python app.py
```

### Steps

1. Click `Import Files` at the footer, select all raw `.htm` files that needed to be parsed. Files should be directly saved from SEC.

2. Edit the tables. Originally draw 5 tables randomly, use `Draw` button to draw 5 more.

3. Use `Download CSV` to download parsed `.csv` tables compressed in `tables_{fileName}.zip`.
   
   Use `Export Log` to download editting log `log_{fileName}.json`.

4. Use `Previous File` `Next File` to switch between different `.htm` files.

Notice that parsed `csv` tables and logs are only for the current displayed `.htm` file.

### Keyboard shortcuts

- Bold (Add `<b></b>`): `Ctrl + B`

- Add indent (4 spaces): `Ctrl + G`

- Cut: `Ctrl + X`

- Copy: `Ctrl + C`

- Paste: `Ctrl + V`

All the preceding functions support batch processing.

Shortcuts could be changed [Here](/templates/index.html) at line 202. 