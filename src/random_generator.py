import json
import random as rd
import string
import argparse
import pandas as pd
import os
from typing import List, Dict, Any, Union

def generate_random_operations(csv_path, num_operations, max_table_index) -> List[Dict[str, Any]]:
    """
    Generate a list of random operations for CSV editing.
    
    Args:
        num_operations: Number of operations to generate
        max_table_index: Maximum table index for filenames (1-61)
        
    Returns:
        List of operation dictionaries
    """
    operations = []
    
    # Define possible actions
    actions = ["edit", "remove_row", "remove_col", "add_row", "add_col", "merge"]

    for _ in range(num_operations):
        # Pick a random table index
        if max_table_index == -1:
            max_table_index = 0
            for file in os.listdir(csv_path):
                if file.endswith(".csv"):
                    max_table_index += 1
            if max_table_index == 0:
                raise ValueError("No CSV files found in the specified directory.")
        table_index = rd.randint(1, max_table_index)
        filename = f"output_table_{table_index}.csv"
        
        # Pick a random action
        action = rd.choice(actions)
        
        # Create the base operation
        operation = {
            "fileName": filename,
            "tableIndex": table_index,
            "action": action,
            "range": None,
            "details": {}
        }

        df = pd.read_csv(csv_path + filename, dtype=str)
        max_rows, max_cols = df.shape
        row = 0 if max_rows == 1 else rd.randint(1, max_rows - 1)
        col = 0 if max_cols == 1 else rd.randint(0, max_cols - 1)

        if action == "edit":  
            if rd.random() < 0.2:
                new_val = None
            else:
                new_val = rd.choice([
                    str(rd.randint(-100, 100)),
                    f"{rd.randint(0, 100)}.{rd.randint(0, 99)}",
                    ''.join(rd.choices(string.ascii_letters, k=rd.randint(3, 8)))
                ])
            
            operation["details"] = {
                "row": row,
                "col": col,
                "oldVal": df.iat[row - 1, col],
                "newVal": new_val
            }
            
        elif action == "remove_row":
            operation["details"] = {
                "index": row,
                "amount": rd.randint(1, min(3, max_rows - row))
            }
            
        elif action == "remove_col":
            operation["details"] = {
                "index": col,
                "amount": rd.randint(1, min(2, max_cols - col))
            }
            
        elif action == "add_row":
            operation["details"] = {
                "index": row,
                "amount": rd.randint(1, 3)
            }
            
        elif action == "add_col":
            operation["details"] = {
                "index": col,
                "amount": rd.randint(1, 2)
            }
            
        elif action == "merge":
            is_row = rd.choice([True, False])
            index = row if is_row else col
            operation["details"] = {
                "index": index,
                "isRow": is_row
            }
        
        operations.append(operation)
    
    return operations

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate random JSON operations for CSV editing")
    parser.add_argument("--csv_path", "-p", type=str, default="./test/test_input/msft-10q_20220331/",
                        help="Path to the CSV files")   
    parser.add_argument("--output", "-o", type=str, default="./test/test_inst/", 
                        help="Output JSON file path")
    parser.add_argument("--num", "-n", type=int, default=50,
                        help="Number of JSONs to generate")
    parser.add_argument("--max-table", "-t", type=int, default=-1,
                        help="Maximum table index")
    
    args = parser.parse_args()
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    for i in range(args.num):
        operations = generate_random_operations(args.csv_path, 50, args.max_table)
        # Write to a JSON file
        with open(os.path.join(args.output, f"random_inst_{i}.json"), 'w') as f:
            json.dump(operations, f, indent=4)
    
    print(f"Generated {len(operations)} random operations and saved to {args.output}")