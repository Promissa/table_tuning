import os
import json
import pandas as pd
import argparse
import glob
from pathlib import Path

def process_edits(csv_folder_path, json_path, output_folder=None):
    # Verify paths exist
    if not os.path.exists(csv_folder_path):
        print(f"CSV folder not found at {csv_folder_path}")
        return
        
    if not os.path.exists(json_path):
        print(f"JSON file not found at {json_path}")
        return

    if not os.path.exists(output_folder) and output_folder is not None:
        os.makedirs(output_folder, exist_ok=True)
        print(f"Output folder created at {output_folder}")

    with open(json_path, 'r') as f:
        instructions = json.load(f)

    file_instructions = {}
    for instruction in instructions:
        file_name = instruction.get("fileName")
        if not file_name:
            print(f"Instruction missing fileName, skipping: {instruction}")
            continue
        
        if file_name not in file_instructions:
            file_instructions[file_name] = []
        
        file_instructions[file_name].append(instruction)

    for file_name, instr_list in file_instructions.items():
        csv_path = os.path.join(csv_folder_path, file_name)
        if not os.path.exists(csv_path):
            base_name = Path(file_name).stem
            possible_files = glob.glob(os.path.join(csv_folder_path, f"{base_name}*.csv"))
            
            if not possible_files:
                print(f"No CSV file found for {file_name}. Skipping.")
                continue
            
            csv_path = possible_files[0]
            # print(f"Using {csv_path} for instructions related to {file_name}")

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"Error loading CSV file {csv_path}: {e}")
            continue

        for instruction in instr_list:
            action = instruction.get("action")
            details = instruction.get("details", {})

            if action == "edit":
                apply_edit(df, details)
            elif action == "remove_row":
                apply_remove_row(df, details)
            elif action == "remove_col":
                apply_remove_col(df, details)
            elif action == "add_col":
                apply_add_col(df, details)
            elif action == "add_row":
                apply_add_row(df, details)
            elif action == "merge":
                apply_merge(df, details)
            else:
                print(f"Unknown action: {action}. Skipping.")

        if output_folder:
            os.makedirs(output_folder, exist_ok=True)
            base_name = Path(csv_path).stem
            output_path = os.path.join(output_folder, f"{base_name}_edited.csv")
        else:
            base_path = Path(csv_path)
            output_path = str(base_path.parent / f"{base_path.stem}_edited{base_path.suffix}")

        df.to_csv(output_path, index=False)
        # print(f"Updated CSV saved to {output_path}")

def apply_edit(df, details):
    row = details.get("row") - 1
    col = details.get("col")
    old_val = details.get("oldVal")
    new_val = details.get("newVal")
    
    if row >= len(df) or col >= len(df.columns):
        print(f"Invalid row or column index: row={row}, col={col}. Skipping edit.")
        return

    current_val = str(df.iloc[row, col])
    # if old_val is not None and current_val != str(old_val.split('.')[0]):
        # print(f"Value mismatch at row={row}, col={col}. Expected '{old_val}', found '{current_val}'. Proceeding anyway.")
    
    if new_val is None:
        df.iloc[row, col] = ""
    else:
        df.iloc[row, col] = new_val

def apply_remove_row(df, details):
    start_index = details.get("index") - 1
    amount = details.get("amount", 1)

    if start_index is None and "row" in details:
        start_index = details.get("row")
        amount = 1

    if start_index >= len(df) or start_index < 0:
        print(f"Invalid starting row index: {start_index}. Skipping row removal.")
        return

    if start_index + amount > len(df):
        print(f"Adjusting removal amount from {amount} to {len(df) - start_index} to avoid going beyond DataFrame bounds.")
        amount = len(df) - start_index

    rows_to_remove = list(range(start_index, start_index + amount))
    df.drop(index=rows_to_remove, inplace=True)

    df.reset_index(drop=True, inplace=True)
    
    # print(f"Removed {amount} rows starting at position {start_index}")

def apply_remove_col(df, details):
    start_index = details.get("index")
    amount = details.get("amount", 1)

    if start_index is None and "col" in details:
        start_index = details.get("col")
        amount = 1

    if start_index >= len(df.columns):
        print(f"Invalid starting column index: {start_index}. Skipping column removal.")
        return

    if start_index + amount > len(df.columns):
        print(f"Adjusting removal amount from {amount} to {len(df.columns) - start_index} to avoid going beyond DataFrame bounds.")
        amount = len(df.columns) - start_index

    cols_to_remove = [df.columns[i] for i in range(start_index, start_index + amount)]

    df.drop(columns=cols_to_remove, inplace=True)
    
    # print(f"Removed {amount} columns starting at position {start_index}")
   
def apply_add_col(df, details):
    start_index = details.get("index", 0)  # Starting pos
    amount = details.get("amount", 1)  # Number of columns to add
    
    if start_index > len(df.columns):
        print(f"Invalid starting column index: {start_index}. Will append at the end.")
        start_index = len(df.columns)

    for i in range(amount):
        col_index = start_index + i
        df.insert(col_index, "", "", allow_duplicates=True)
        # print(f"Added new column at position {col_index}")

def apply_add_row(df, details):
    start_index = details.get("index", 0) - 1  # Starting pos to insert rows
    amount = details.get("amount", 1)  # Number of rows to add

    if start_index > len(df):
        print(f"Invalid starting row index: {start_index}. Will append at the end.")
        start_index = len(df)

    empty_rows = pd.DataFrame(
        {col: [""] * amount for col in df.columns},
        columns=df.columns
    )

    df_before = df.iloc[:start_index].copy()
    df_after = df.iloc[start_index:].copy()

    new_df = pd.concat([df_before, empty_rows, df_after], ignore_index=True)

    df.drop(df.index, inplace=True)
    df.reset_index(drop=True, inplace=True)
    for col in new_df.columns:
        df[col] = new_df[col]
    
    # print(f"Added {amount} new rows starting at position {start_index}")

def apply_merge(df, details):
    index = details.get("index")
    is_row = details.get("isRow", True)

    if index is None:
        print("Missing 'index' parameter in merge operation. Skipping.")
        return
    
    if is_row:
        if index >= len(df) - 1:
            # print(f"Invalid row index {index} for merging. Need at least two rows to merge. Skipping.")
            return

        for col_idx in range(len(df.columns)):
            val1 = str(df.iloc[index, col_idx])
            val2 = str(df.iloc[index + 1, col_idx])
            
            # Handle NaN values
            if val1 == "nan" or val1 == "NaN":
                val1 = ""
            if val2 == "nan" or val2 == "NaN":
                val2 = ""
            
            merged_val = val1 + val2
            
            df.iloc[index, col_idx] = merged_val

        df.drop(index=index + 1, inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        # print(f"Merged rows {index} and {index + 1} by concatenating their content")
        
    else:
        if index >= len(df.columns) - 1:
            # print(f"Invalid column index {index} for merging. Need at least two columns to merge. Skipping.")
            return

        col1_name = df.columns[index]
        col2_name = df.columns[index + 1]

        if col1_name and col2_name:
            merged_col_name = col1_name + "_" + col2_name
        else:
            merged_col_name = col1_name + col2_name
        
        merged_col_values = []
        for row_idx in range(len(df)):
            val1 = str(df.iloc[row_idx, index])
            val2 = str(df.iloc[row_idx, index + 1])
            
            # Handle NaN values
            if val1 == "nan":
                val1 = ""
            if val2 == "nan":
                val2 = ""

            if val1 and val2:
                merged_val = val1 + " " + val2
            else:
                merged_val = val1 + val2
            
            merged_col_values.append(merged_val)

        new_columns = list(df.columns)

        df.drop(columns=[col2_name], inplace=True)

        df.rename(columns={col1_name: merged_col_name}, inplace=True)
        df[merged_col_name] = merged_col_values
        
        # print(f"Merged columns {index} ({col1_name}) and {index + 1} ({col2_name}) into {merged_col_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edit a CSV file based on JSON instructions")
    parser.add_argument("csv_path", help="Path to the CSV file to edit")
    parser.add_argument("json_path", help="Path to the JSON file with edit instructions")
    parser.add_argument("-o", "--output", help="Path to save the edited CSV file (optional)")
    
    args = parser.parse_args()
    json_files = glob.glob(os.path.join(args.json_path, "*.json"))
    
    if not json_files:
        print(f"No JSON files found in {args.json_path}")
        pass
    
    print(f"Found {len(json_files)} JSON files in {args.json_path}")
    
    for json_file in json_files:
        print(f"Processing {json_file}...")
        output_path = os.path.join(args.output, os.path.basename(json_file).split('_')[-1].split('.')[0])
        try:
            process_edits(args.csv_path, json_file, output_path)
            print(f"Successfully processed {json_file}\n")
        except Exception as e:
            print(f"Error processing {json_file}: {str(e)}")

    print("Processing complete.")