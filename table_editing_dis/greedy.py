import pandas as pd
import numpy as np
import csv
from Levenshtein import distance as levenshtein_distance
import re
import math
from itertools import permutations
import copy
import os
from collections import defaultdict

class DataPoint:
    def __init__(self, coords, value, value_type=None, place_type=None, rp=None, middle_place_type=None, mrp=None):
        self.coords = coords
        self.value = value
        self.value_type = value_type
        self.place_type = place_type
        self.rp = rp
        self.middle_place_type = middle_place_type
        self.mrp = mrp


    def __repr__(self):
        return (f"DataPoint(coords={self.coords}, value={self.value}, "
                f"value_type={self.value_type}, place_type={self.place_type}, right_place={self.rp}, middle_place_type={self.middle_place_type}, mrp={self.mrp})")

def read_and_adjust_csv(file_path):
    rows = []
    max_cols = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
            max_cols = max(max_cols, len(row))
    adjusted_rows = [row + [''] * (max_cols - len(row)) for row in rows]
    df = pd.DataFrame(adjusted_rows)
    row_num = len(adjusted_rows)
    column_num = max_cols
    return df, row_num, column_num

def convert_element(value):
    # Check if the value is a string and follows the pattern of parentheses-wrapped negative numbers
    if isinstance(value, str) and value.startswith("(") and value.endswith(")"):
        inner_value = value[1:-1]  # Extract the content inside the parentheses
        if inner_value.isdigit():  # Check if the inner content is purely numeric
            return f"-{inner_value}"  # Return the negative representation as a string
        else:
            return value  # Return the original value as is if the inner content is not numeric
    # Convert the value to a string and return
    return str(value)

def clean_data_points_for_merge_split(data_points):
    for dp in data_points:
        # print(f"Original value: {dp.value}, Type: {type(dp.value)}")
        dp.value = str(dp.value)
        dp.value = re.sub(r'\.0\b', '', dp.value)
        dp.value = re.sub(r'[^\w\s\.]', '', dp.value)
        dp.value = dp.value.replace(' ', '')
    return data_points

def edit_distance_similarity(text1, text2):
    text1 = str(text1)
    text2 = str(text2)
    edit_distance = levenshtein_distance(text1, text2)
    max_len = max(len(text1), len(text2))
    similarity = 1 - edit_distance / max_len if max_len > 0 else 1
    return similarity

def find_and_remove_reconstructable(values1, values2):
    values1 = clean_data_points_for_merge_split(values1)
    values2 = clean_data_points_for_merge_split(values2)
    # print("groundtruth_point_left:")
    # print(values1)
    # print("generate_point_left:")
    # print(values2)

    merge_split_mistake = []

    # Use a flag to indicate the source of the data
    for source_values, target_values, source_list_name, target_list_name in [
        (values1, values2, "groundtruth_point", "generate_point"),
        (values2, values1, "generate_point", "groundtruth_point")
    ]:
        for source in list(source_values):
            possible_reconstruction = []
            possible_reconstruction_item = []

            for target in target_values:
                # Compare based on value of the DataPoint object, not the whole object
                if target.value in source.value and target.value not in possible_reconstruction:
                    possible_reconstruction_item.append(target)
                    possible_reconstruction.append(target.value)

            a = 0
            fragments_used = []

            for perm_item in permutations(possible_reconstruction_item):
                perm = [frag.value for frag in perm_item]
                x_coords = [frag.coords[0] for frag in perm_item]
                if all(x == x_coords[0] for x in x_coords):
                    p = ''.join(perm)
                    p_replace = p.replace(" ", "")
                    source_replace = source.value.replace(" ", "")

                    if p_replace == source_replace:
                        a = 1
                        merge_split_mistake.append({
                            source_list_name: source,  # Store the full source DataPoint object
                            target_list_name: possible_reconstruction_item,  # Store the full target DataPoint object
                        })
                        fragments_used.extend([frag for frag in perm_item])
                        # print("fragments_used1111")
                        # print(fragments_used)

                        if source in source_values:
                            source_values.remove(source)

                        for fragment in fragments_used:
                            target_values.remove(fragment)
                        
            if a == 0:
                for r in range(1, len(possible_reconstruction) + 1):
                    for perm_item in permutations(possible_reconstruction_item, r): 
                        perm = [frag.value for frag in perm_item]
                        x_coords = [frag.coords[0] for frag in perm_item]
                        if all(x == x_coords[0] for x in x_coords):
                            value_to_datapoint = [dp for dp in possible_reconstruction_item if dp.value in perm]
                            p = ''.join(perm)
                            p_replace = p.replace(" ", "")
                            source_replace = source.value.replace(" ", "")

                            if p_replace == source_replace:
                                merge_split_mistake.append({
                                    source_list_name: source,
                                    target_list_name: value_to_datapoint,
                                })
                                fragments_used.extend([frag for frag in perm_item])
                                # print("fragments_used")
                                # print(fragments_used)

                                if source in source_values:
                                    source_values.remove(source)

                                for fragment in fragments_used:
                                    target_values.remove(fragment)
                                break

    return merge_split_mistake, values1, values2

def match_closest0(one_to_one, matching_coords):
    for group in one_to_one:
        generate_points = group[0]
        groundtruth_points = group[1]
        matching_coords.append({
            "generate_point": generate_points[0],
            "groundtruth_point": groundtruth_points[0]
        })

def match_closest1(one_to_many, matching_coords):
    for group in one_to_many:
        generate_points = group[0]
        groundtruth_points = group[1]
        for generate_point in generate_points:
            closest_groundtruth = min(groundtruth_points,
                                      key=lambda gt: euclidean_distance(generate_point.coords, gt.coords))
            groundtruth_points.remove(closest_groundtruth)
            matching_coords.append({
                "generate_point": generate_point,
                "groundtruth_point": closest_groundtruth
            })
def match_closest(many_to_one, matching_coords):
    for group in many_to_one:
        generate_points = group[0]
        groundtruth_points = group[1]
        for gt_point in groundtruth_points:
            closest_generate_point = min(generate_points,
                                         key=lambda generate: euclidean_distance(generate.coords, gt_point.coords))
            generate_points.remove(closest_generate_point)
            matching_coords.append({
                "generate_point": closest_generate_point,
                "groundtruth_point": gt_point
            })
def handle_many_to_many(many_to_many, matching_coords):
    for group in many_to_many:
        generate_points = group[0]
        groundtruth_points = group[1]
        if len(generate_points) < len(groundtruth_points):
            for generate_point in generate_points:
                closest_groundtruth = min(groundtruth_points,
                                          key=lambda gt: euclidean_distance(generate_point.coords, gt.coords))
                groundtruth_points.remove(closest_groundtruth)
                matching_coords.append({
                    "generate_point": generate_point,
                    "groundtruth_point": closest_groundtruth
                })
        else:
            for gt_point in groundtruth_points:
                closest_generate_point = min(generate_points,
                                             key=lambda generate: euclidean_distance(generate.coords, gt_point.coords))
                generate_points.remove(closest_generate_point)
                matching_coords.append({
                    "generate_point": closest_generate_point,
                    "groundtruth_point": gt_point
                })

def euclidean_distance(point1, point2):
    return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2)

def edit_distance(str1, str2):
    len_str1 = len(str1)
    len_str2 = len(str2)
    dp = np.zeros((len_str1 + 1, len_str2 + 1), dtype=int)

    for i in range(len_str1 + 1):
        for j in range(len_str2 + 1):
            if i == 0:
                dp[i][j] = j
            elif j == 0:
                dp[i][j] = i
            elif str1[i - 1] == str2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])

    return dp[len_str1][len_str2]

def find_matching_groundtruth_from_pairs(generate_point, a):
    for pair in a:
        if pair['generate_point'] == generate_point:
            return pair['groundtruth_point']

        elif isinstance(pair['generate_point'], list):
            if generate_point in pair['generate_point']:
                return pair['groundtruth_point']

    return None
def analyze_differences(matching_coords):
    value_match_different_coords = sum(1 for match in matching_coords if match['generate_point'].coords != match['groundtruth_point'].coords)
    return value_match_different_coords

def calculate_score(matching_coords, match_count, groundtruth_num):
    value_match_different_coords = analyze_differences(matching_coords)
    score = (match_count * 2 + value_match_different_coords) / (groundtruth_num * 2)
    # print("Analysis Results:")
    # print("Number of completely matched points:", match_count)
    # print("Number of value-matched but coordinate-mismatched points:", value_match_different_coords)
    # print("Groundtruth_num:", groundtruth_num)
    # print(len(matching_coords))
    # print("Score:", score)
    return score

def clear(point):
    point.value = " "
    point.value_type = "N"
    point.place_type = None

def move(point, target_dp):
    point.value, target_dp.value = " ", point.value
    point.value_type, target_dp.value_type = "N", point.value_type
    point.place_type = None
    if point.rp == target_dp.coords:
        target_dp.place_type = "T"
    else:
        target_dp.place_type = "F"
    point.rp, target_dp.rp = None, point.rp

def merge(points):
    point = points[0]
    values = []
    for p in points:
        values.append(p.value)
    merged_value = " ".join(map(str, values))
    point.value = merged_value
    point.value_type = "N"
    point.place_type = None
    for point_to_clear in points[1:]:
        point_to_clear.value = " "
        point_to_clear.value_type = "N"
        point_to_clear.place_type = None
        point_to_clear.rp = None

def split(points, refer):
    for dp in points:
        dp.value = " "
        dp.value_type = "N"
        dp.place_type = None
        dp.rp = None
        for r in refer:
            if r.coords == dp.coords:
                dp.value = r.value
def modify_minor_num_mistake(data_point):
    correct_value = str(data_point.place_type)
    steps = edit_distance(str(data_point.value), correct_value)
    data_point.value = correct_value
    data_point.value_type = "matching_values"
    matching_groundtruth_point = find_matching_groundtruth_from_pairs(data_point, minor_num_mistake)

def add_value_in_empty_cell(p, target_dp):
    target_dp.value = p.value
    target_dp.rp = p.rp
    target_dp.middle_place_type = "T"

def add_row(data_points, row_index):
    for dp in data_points:
        if dp.coords[0] >= row_index:
            dp.coords[0] += 1
    for col in range(max_column_num0):
            data_points.append(
                DataPoint(
                    coords=[row_index, col],
                    value=" ",
                    value_type="N",
                    place_type=None,
                    rp=None,
                )
            )
    data_points.sort(key=lambda dp: (dp.coords[0], dp.coords[1]))

def add_column(data_points, col_index):
    for dp in data_points:
        if dp.coords[1] >= col_index:
            dp.coords[1] += 1
    for row in range(max_row_num0):
            data_points.append(
                DataPoint(
                    coords=[row, col_index],
                    value=" ",
                    value_type="N",
                    place_type=None,
                    rp=None,
                )
            )
    data_points.sort(key=lambda dp: (dp.coords[0], dp.coords[1]))

def delete_row(data_points, row_index):
    data_points[:] = [dp for dp in data_points if dp.coords[0] != row_index]
    for dp in data_points:
        if dp.coords[0] > row_index:
            dp.coords[0] -= 1
    for col in range(max_column_num0):
        data_points.append(
            DataPoint(
                coords=[max_row_num0 - 1, col],
                value=" ",
                value_type="N",
                place_type=None,
                rp=None,
            )
        )
    data_points.sort(key=lambda dp: (dp.coords[0], dp.coords[1]))


def delete_column(data_points, col_index):
    data_points[:] = [dp for dp in data_points if dp.coords[1] != col_index]
    for dp in data_points:
        if dp.coords[1] > col_index:
            dp.coords[1] -= 1
    for row in range(max_row_num0):
        for col in range((max_column_num0 - 1), max_column_num0):
            data_points.append(
                DataPoint(
                    coords=[row, col],
                    value=" ",
                    value_type="N",
                    place_type=None,
                    rp=None,
                )
            )
    data_points.sort(key=lambda dp: (dp.coords[0], dp.coords[1]))

def calculate_matching_points(generate_data_points, groundtruth_data_points):
    one_to_one = []
    one_to_many = []
    many_to_one = []
    many_to_many = []
    matching_coords = []
    generate_group = defaultdict(list)
    groundtruth_group = defaultdict(list)

    for generate_point in generate_data_points:
        if generate_point.value not in (" ", ' ', '', None) and len(generate_point.value) != 0:
            generate_group[generate_point.value].append(generate_point)

    for groundtruth_point in groundtruth_data_points:
        if groundtruth_point.value not in (" ", ' ', '', None) and len(groundtruth_point.value) != 0:
            groundtruth_group[groundtruth_point.value].append(groundtruth_point)

    generate_group_many = [{key: value} for key, value in generate_group.items() if len(value) > 1]
    groundtruth_group_many = [{key: value} for key, value in groundtruth_group.items() if len(value) > 1]
    generate_group_one = [{key: value} for key, value in generate_group.items() if len(value) == 1]
    groundtruth_group_one = [{key: value} for key, value in groundtruth_group.items() if len(value) == 1]

    for group in generate_group_many:
        for key, value in group.items():  # Each group is a dictionary
            for group1 in groundtruth_group_many:  # Loop over the list
                for key1, value1 in group1.items():  # Now loop over the dictionary items
                    if key == key1:
                        many_to_many.append([value, value1])
                        del group
                        del group1

    if generate_group_many:
        for group in generate_group_many:
            for key, value in group.items():
                for group1 in groundtruth_group_one:
                    for key1, value1 in group1.items():
                        if key == key1:
                            many_to_one.append([value, value1])
                            del group
                            del group1

    if groundtruth_group_many:
        for group in groundtruth_group_many:
            for key, value in group.items():
                for group1 in generate_group_one:
                    for key1, value1 in group1.items():
                        if key == key1:
                            one_to_many.append([value1, value])
                            del group
                            del group1

    for group in generate_group_one:
        for key, value in group.items():
            for group1 in groundtruth_group_one:
                for key1, value1 in group1.items():
                    if key == key1:
                        one_to_one.append([value, value1])
                        del group
                        del group1

    match_closest0(one_to_one, matching_coords)
    match_closest1(one_to_many, matching_coords)
    match_closest(many_to_one, matching_coords)
    handle_many_to_many(many_to_many, matching_coords)

    return matching_coords

def calculate_match_count(generate_data_points, groundtruth_data_points):
    # Create a set of tuples (coords, value) for ground truth data points
    groundtruth_set = {(tuple(dp.coords), dp.value) for dp in groundtruth_data_points}

    # Count how many generated data points match coords and value in the ground truth set
    match_count = sum(
        (tuple(dp.coords), dp.value) in groundtruth_set for dp in generate_data_points
    )

    return match_count

def clear_data_point_attributes(data_points):
    """
    Clear all attributes of DataPoint objects except 'coords' and 'value'.

    Parameters:
        data_points (list): List of DataPoint objects.
    """
    for dp in data_points:
        dp.value_type = None
        dp.place_type = None
        dp.right_place = None
        dp.middle_place_type = None
        dp.mrp = None

def generate_valid_operations(data_points):
    """
    Traverse all DataPoints and determine executable operations based on value_type and place_type.
    """
    operations = []

    if merge_mistake:
        for item in merge_mistake:
            generate_point = item['generate_point']
            groundtruth_points = item['groundtruth_point']
            all_empty = True  # Assume all values are empty initially

            # Iterate over each coordinate in generate_point.right_place
            for coord in generate_point.rp:
                # Iterate over each DataPoint in generate_points
                for point in data_points:
                    # Check if the current DataPoint's coords match the current coord
                    if point.coords == coord and point.coords != generate_point.coords:
                        # If they match, check if the value of this DataPoint is not empty
                        if point.value not in (" ", '', None):
                            # If any DataPoint has a non-empty value, set all_empty to False
                            all_empty = False
                            break  # Break out of the inner loop since we've found a non-empty value
                # If we found a non-empty value, break out of the outer loop as well
                if not all_empty:
                    break
            matching_points = [point for point in data_points if point.coords in generate_point.rp]
            if all_empty:
                operations.append({
                    "operation": "split",
                    "params": {"points": matching_points, "refer": groundtruth_points}
                })
            else:
                operations.append({
                    "operation": "clear",
                    "params": {"point": generate_point}
                })

    if split_mistake:
        for item in split_mistake:
            generate_points = item['generate_point']
            all_values_not_empty = all(point.value not in (" ", ' ', '', None) for point in generate_points)
            if all_values_not_empty:
                operations.append({
                    "operation": "merge",
                    "params": {"points": generate_points}
                })
            else:
                for point in generate_points:
                    if point.value not in (" ", ' ', '', None):
                        operations.append({
                            "operation": "clear",
                            "params": {"point": point}
                        })

    # Add value operation: Fill empty cells with the correct value
    if groundtruth_point_left:
        # print("3333")
        # print(groundtruth_point_left)
        for p in groundtruth_point_left:
            target_dp = next((dp for dp in data_points if dp.coords == p.coords), None)
            # print("121212222")
            # print(target_dp)
            if target_dp.value in (" ", ' ', '', None):
                operations.append({
                    "operation": "add_value_in_empty_cell",
                    "params": {"point": p, "target_dp": target_dp}
                })

    for point in data_points:

        # 1. Clear operation: Remove unnecessary generate_added_values
        if point.value_type == "generate_added_values":
            operations.append({
                "operation": "clear",
                "params": {"point": point}
            })

        # 2. Move operation: Move a point to its correct position if the target cell is empty
        if point.value_type == "matching_values" and point.place_type == "F" and point.rp:
            target_dp = next((dp for dp in data_points if dp.coords == point.rp), None)
            if target_dp and target_dp.value == " ":
                operations.append({
                    "operation": "move",
                    "params": {"point": point, "target_dp": target_dp}
                })

        # 3. Modify operation: Fix minor numerical mistakes
        if point.value_type == "minor_num_mistake":
            operations.append({
                "operation": "modify_minor_num_mistake",
                "params": {"point": point}
            })
    # Add/delete row/column  operation
    if rows_to_delete:
        for r in rows_to_delete:
            operations.append({
                "operation": "delete_row",
                "params": {"row_index": r}
            })
    if columns_to_delete:
        for c in columns_to_delete:
            operations.append({
                "operation": "delete_column",
                "params": {"column_index": c}
            })
    if rows_to_add:
        for r in rows_to_add:
            operations.append({
                "operation": "add_row",
                "params": {"row_index": r}
            })
    if columns_to_add:
        for c in columns_to_add:
            operations.append({
                "operation": "add_column",
                "params": {"row_index": c}
            })

    # print(operations)
    return operations

def apply_try_operation(data_points, operation):
    if operation['operation'] == 'add_row':
        add_row(data_points, operation['params']['row_index'])
        temp_rows_to_add.remove(operation['params']['row_index'])
    if operation['operation'] == 'add_column':
        add_column(data_points, operation['params']['column_index'])
        temp_columns_to_add.remove(operation['params']['column_index'])
    if operation['operation'] == 'delete_row':
        delete_row(data_points, operation['params']['row_index'])
        temp_rows_to_delete.remove(operation['params']['row_index'])
    if operation['operation'] == 'delete_column':
        delete_column(data_points, operation['params']['column_index'])
        temp_columns_to_delete.remove(operation['params']['column_index'])
    if operation['operation'] == 'clear':
        clear(operation['params']['point'])
    if operation['operation'] == 'modify_minor_num_mistake':
        modify_minor_num_mistake(operation['params']['point'])
    if operation['operation'] == 'move':
        move(operation['params']['point'], operation['params']['target_dp'])
    if operation['operation'] == 'add_value_in_empty_cell':
        add_value_in_empty_cell(operation['params']['point'], operation['params']['target_dp'])
    if operation['operation'] == 'merge':
        # print("aaaaa")
        # print(operation['params']['points'])
        merge(operation['params']['points'])
        # print("bbbbb")
        # print(operation['params']['points'])
        for item in temp_split_mistake:
            if item['generate_point'] == operation['params']['points']:
                temp_split_mistake.remove(item)
    if operation['operation'] == 'split':
        split(operation['params']['points'], operation['params']['refer'])
        for item in temp_merge_mistake:
            if item['generate_point'] == operation['params']['points']:
                temp_merge_mistake.remove(item)


def apply_operation(data_points, operation):
    global columns_to_delete
    global rows_to_add
    global columns_to_add
    global rows_to_delete
    global split_mistake
    if operation['operation'] == 'add_row':
        add_row(data_points, operation['params']['row_index'])
        rows_to_add.remove(operation['params']['row_index'])
        rows_to_add = {x + 1 if x >= operation['params']['row_index'] else x for x in rows_to_add}
    if operation['operation'] == 'add_column':
        add_column(data_points, operation['params']['column_index'])
        columns_to_add.remove(operation['params']['column_index'])
        columns_to_add = {x + 1 if x >= operation['params']['column_index'] else x for x in columns_to_add}
    if operation['operation'] == 'delete_row':
        delete_row(data_points, operation['params']['row_index'])
        rows_to_delete.remove(operation['params']['row_index'])
        rows_to_delete = {x - 1 if x > operation['params']['row_index'] else x for x in rows_to_delete}
    if operation['operation'] == 'delete_column':
        delete_column(data_points, operation['params']['column_index'])
        # print(operation['params']['column_index'])
        columns_to_delete.remove(operation['params']['column_index'])
        # print(columns_to_delete)
        columns_to_delete = {x - 1 if x > operation['params']['column_index'] else x for x in columns_to_delete}
        # print(columns_to_delete)

    if operation['operation'] == 'clear':
        clear(operation['params']['point'])
    if operation['operation'] == 'modify_minor_num_mistake':
        modify_minor_num_mistake(operation['params']['point'])
    if operation['operation'] == 'move':
        move(operation['params']['point'], operation['params']['target_dp'])
    if operation['operation'] == 'add_value_in_empty_cell':
        add_value_in_empty_cell(operation['params']['point'], operation['params']['target_dp'])
    if operation['operation'] == 'merge':
        merge(operation['params']['points'])
        for item in split_mistake:
            if item['generate_point'] == operation['params']['points']:
                split_mistake.remove(item)
    if operation['operation'] == 'split':
        split(operation['params']['points'], operation['params']['refer'])
        for item in temp_merge_mistake:
            if item['generate_point'] == operation['params']['points']:
                temp_merge_mistake.remove(item)

results = []

folder_path = r'parsedtable/1800_000110465912034444_10-Q_1800_2'
for i in range(1, 26):
    groundtruth_file = f'table_{i}.csv'
    groundtruth_path = os.path.join(folder_path, groundtruth_file)
    if os.path.exists(groundtruth_path):
        for j in range(1, 4):
            generate_file = f'table_{i}_{j}.csv'
            generate_path = os.path.join(folder_path, generate_file)
            operation_log = []
            print(f"Processing table_{i}_{j}.csv...")
            if os.path.exists(generate_path):
                # groundtruth_path = r"/Users/yiruizhang/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/71856bc484f827c6fac68942ae248e55/Message/MessageTemp/9e20f478899dc29eb19741386f9343c8/File/1800_000110465912034444_10-Q_1800_2/table_4.csv"
                # generate_path = r"/Users/yiruizhang/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/71856bc484f827c6fac68942ae248e55/Message/MessageTemp/9e20f478899dc29eb19741386f9343c8/File/1800_000110465912034444_10-Q_1800_2/table_4_3.csv"
                df_groundtruth, groundtruth_row_num, groundtruth_column_num = read_and_adjust_csv(groundtruth_path)
                df_generate, generate_row_num, generate_column_num = read_and_adjust_csv(generate_path)
                # print(df_groundtruth)
                # print(df_generate)

                df_groundtruth_values = df_groundtruth.values.flatten()
                df_generate_values = df_generate.values.flatten()
                groundtruth_coords_values = []
                generate_coords_values = []

                for row in range(df_groundtruth.shape[0]):
                    for col in range(df_groundtruth.shape[1]):
                        value = df_groundtruth.iloc[row, col]
                        groundtruth_coords_values.append([[row, col], value])

                for row in range(df_generate.shape[0]):
                    for col in range(df_generate.shape[1]):
                        value = df_generate.iloc[row, col]
                        generate_coords_values.append([[row, col], value])
                # print(generate_coords_values)
                # print(groundtruth_coords_values)

                generate_data_points = [DataPoint(coords=d[0], value=d[1]) for d in generate_coords_values]
                groundtruth_data_points = [DataPoint(coords=d[0], value=d[1]) for d in groundtruth_coords_values]
                # print("qqqqq")
                # print(generate_data_points)
                # print(groundtruth_data_points)

                generate_data_points = [DataPoint(coords=d.coords, value=convert_element(d.value)) for d in generate_data_points]
                groundtruth_data_points = [DataPoint(coords=d.coords, value=convert_element(d.value)) for d in groundtruth_data_points]
                clean_data_points_for_merge_split(generate_data_points)
                clean_data_points_for_merge_split(groundtruth_data_points)
                # print("Generate Data Points:")
                # print(generate_data_points)
                # print("Groundtruth Data Points:")
                # print(groundtruth_data_points)

                matching_coords = calculate_matching_points(generate_data_points, groundtruth_data_points)
                minor_num_mistake = []
                generate_point_left = []
                groundtruth_point_left = []
                for generate_point in generate_data_points:
                    if not any(entry['generate_point'] == generate_point for entry in matching_coords):
                        if generate_point.value not in ["", " ", None]:
                            generate_point_left.append(generate_point)

                for groundtruth_point in groundtruth_data_points:
                    if not any(entry['groundtruth_point'] == groundtruth_point for entry in matching_coords):
                        if groundtruth_point.value not in ["", " ", None]:
                            groundtruth_point_left.append(groundtruth_point)

                # print("Matching Coordinates:")
                # print(matching_coords)
                # print("\nGenerate Points Left:")
                # print(generate_point_left)
                # print("\nGroundtruth Points Left:")
                # print(groundtruth_point_left)
                merge_split_mistake, groundtruth_point_left, generate_point_left = find_and_remove_reconstructable(groundtruth_point_left, generate_point_left)
                # print("\nMerge Split Mistake:")
                # print(merge_split_mistake)
                merge_mistake = []
                split_mistake = []
                for pair in merge_split_mistake:
                    if isinstance(pair['generate_point'], list):
                        split_mistake.append(pair)
                    else:
                        merge_mistake.append(pair)
                # print("\nMerge Mistake:")
                # print(merge_mistake)
                # print("\nSplit Mistake:")
                # print(split_mistake)
                to_remove_groundtruth = []
                to_remove_generate = []

                used_generate_left = set()

                for groundtruth_left in groundtruth_point_left:
                    best_match = None  # To store the best matching generate_left for the current groundtruth_left
                    best_score = 0     # To store the highest similarity score for the current groundtruth_left

                    for generate_left in generate_point_left:
                        # Skip if generate_left has already been used
                        if generate_left in used_generate_left:
                            continue
                        
                        # Compute similarity score (edit distance)
                        edit_dist = edit_distance_similarity(generate_left.value, groundtruth_left.value)
                        
                        # Update the best match if the current score is higher
                        if edit_dist > best_score:
                            best_match = generate_left
                            best_score = edit_dist

                    # If a valid match is found (score > 0.7), record it and mark generate_left as used
                    if best_score > 0.7 and best_match:
                        # Append the best match to the list of minor mistakes
                        minor_num_mistake.append({
                            "generate_point": best_match,
                            "groundtruth_point": groundtruth_left
                        })
                        # Add the current groundtruth_left and generate_left to removal lists
                        to_remove_groundtruth.append(groundtruth_left)
                        to_remove_generate.append(best_match)
                        # Mark the best match as used
                        used_generate_left.add(best_match)

                for item in to_remove_groundtruth:
                    groundtruth_point_left.remove(item)
                for item in to_remove_generate:
                    generate_point_left.remove(item)

                # print("\nMinor Num Mistake:")
                # print(minor_num_mistake)

                # print("\nGenerate Points Left:")
                # print(generate_point_left)

                # print("\nGroundtruth Points Left:")
                # print(groundtruth_point_left)

                generate = []
                groundtruth = []

                for pair in matching_coords:
                    pair['generate_point'].rp = pair['groundtruth_point'].coords
                    if pair['generate_point'].coords == pair['groundtruth_point'].coords:
                        pair['generate_point'].place_type = "T"
                    else:
                        pair['generate_point'].place_type = "F"
                    pair['generate_point'].value_type = "matching_values"
                    pair['groundtruth_point'].value_type = "matching_values"
                    generate.append(pair['generate_point'])
                    groundtruth.append(pair['groundtruth_point'])

                for pair in split_mistake:
                    split1 = []
                    for gt_point in pair['generate_point']:
                        split1.append(gt_point.coords)
                    for gt_point in pair['generate_point']:
                        gt_point.value_type = "splitting_problem"
                        gt_point.rp = pair['groundtruth_point'].coords
                        gt_point.place_type = split1
                        generate.append(gt_point)
                    groundtruth.append(pair['groundtruth_point'])

                for pair in merge_mistake:
                    split2 = []
                    for gt_point in pair['groundtruth_point']:
                        split2.append(gt_point.coords)
                        groundtruth.append(gt_point)
                    pair['generate_point'].value_type = "merging_problem"
                    pair['generate_point'].rp = split2
                    generate.append(pair['generate_point'])

                for pair in minor_num_mistake:
                    pair['generate_point'].rp = pair['groundtruth_point'].coords
                    pair['generate_point'].value_type = "minor_num_mistake"
                    pair['generate_point'].place_type = pair['groundtruth_point'].value
                    pair['groundtruth_point'].value_type = "minor_num_mistake"
                    generate.append(pair['generate_point'])
                    groundtruth.append(pair['groundtruth_point'])

                for point in generate_point_left:
                    point.value_type = "generate_added_values"
                    generate.append(point)

                for point in groundtruth_point_left:
                    point.value_type = "groundtruth_added_values"
                    groundtruth.append(point)

                # print("\nMerge Mistake:")
                # print(merge_mistake)
                pair = []

                for entry in minor_num_mistake:
                    groundtruth_coords = entry['groundtruth_point'].coords
                    generate_coords = entry['generate_point'].coords
                    pair.append((groundtruth_coords, generate_coords))
                for entry in merge_mistake:
                    generate_coords = entry['generate_point'].coords
                    for gro_point in entry['groundtruth_point']:
                        groundtruth_coords = gro_point.coords
                        pair.append((groundtruth_coords, generate_coords))
                for entry in split_mistake:
                    groundtruth_coords = entry['groundtruth_point'].coords
                    generate_coords = entry['generate_point'][0].coords
                    pair.append((groundtruth_coords, generate_coords))
                for entry in matching_coords:
                    groundtruth_coords = entry['groundtruth_point'].coords
                    generate_coords = entry['generate_point'].coords
                    pair.append((groundtruth_coords, generate_coords))

                row_mapping = defaultdict(list)
                col_mapping = defaultdict(list)

                for right_place, coords in pair:
                    coord_row, coord_col = coords
                    right_row, right_col = right_place
                    row_mapping[right_row].append(coord_row)
                    col_mapping[right_col].append(coord_col)
                row_mapping = {key: row_mapping[key] for key in sorted(row_mapping)}
                col_mapping = {key: col_mapping[key] for key in sorted(col_mapping)}

                row_analysis = {}
                last_selected_row = -1
                for right_row, rows in row_mapping.items():
                    row_counts = defaultdict(int)
                    for row in rows:
                        row_counts[row] += 1
                    sorted_rows = sorted(row_counts.items(), key=lambda x: (-x[1], x[0]))
                    for row, _ in sorted_rows:
                        if row > last_selected_row:
                            row_analysis[right_row] = row
                            last_selected_row = row
                            break
                    else:
                        row_analysis[right_row] = last_selected_row + 1
                    if 0 not in row_analysis and 0 not in row_analysis.values():
                        row_analysis[0] = 0



                col_analysis = {}
                last_selected_col = -1

                for right_col, cols in col_mapping.items():
                    col_counts = defaultdict(int)
                    for col in cols:
                        col_counts[col] += 1

                    sorted_cols = sorted(col_counts.items(), key=lambda x: (-x[1], x[0]))
                    for col, _ in sorted_cols:
                        if col > last_selected_col:
                            col_analysis[right_col] = col
                            last_selected_col = col
                            break
                    else:
                        col_analysis[right_col] = last_selected_col + 1
                    if 0 not in col_analysis and 0 not in col_analysis.values():
                        col_analysis[0] = 0

                # print("row_analysis")
                # print(row_analysis)
                # print("col_analysis")
                # print(col_analysis)
                # print("\nMapping of Right Place rows to Coords rows:")
                # for right_row, coord_row in row_analysis.items():
                #     print(f"Right Place row {right_row} -> Coords row {coord_row}")
                # print("\nMapping of Right Place columns to Coords columns:")
                # for right_col, coord_col in col_analysis.items():
                #     print(f"Right Place column {right_col} -> Coords column {coord_col}")


                mapped_coords_cols = set(col_analysis.values())
                all_coords_cols = set(range(max(col_analysis.values()) + 1))
                columns_to_delete = all_coords_cols - mapped_coords_cols
                mapped_coords_rows = set(row_analysis.values())
                all_coords_rows = set(range(max(row_analysis.values()) + 1))
                rows_to_delete = all_coords_rows - mapped_coords_rows
                # print("rows_to_delete")
                # print(rows_to_delete)
                # print("columns_to_delete")
                # print(columns_to_delete)
                mapped_coords_rows = set(row_analysis.keys())
                all_coords_rows = set(range(max(row_analysis.keys()) + 1))
                rows_to_add = all_coords_rows - mapped_coords_rows
                mapped_coords_cols = set(col_analysis.keys())
                all_coords_cols = set(range(max(col_analysis.keys()) + 1))
                columns_to_add = all_coords_cols - mapped_coords_cols
                seen = set()
                duplicates = set()
                for value in row_analysis.values():
                    if value in seen:
                        duplicates.add(value)
                    else:
                        seen.add(value)
                rows_to_add.update(duplicates)
                # print("rows_to_add")
                # print(rows_to_add)
                # print("columns_to_add")
                # print(columns_to_add)

                max_row_num = max(generate_row_num, groundtruth_row_num)
                max_column_num = max(generate_column_num, groundtruth_column_num)
                max_row_num0 = max_row_num
                max_column_num0 = max_column_num
                existing_coords = set(tuple(dp.coords) for dp in generate)
                for row in range(max_row_num):
                    for col in range(max_column_num):
                        if (row, col) not in existing_coords:
                            # Create a new DataPoint for missing coordinates
                            # print(row, col)
                            new_dp = DataPoint(coords=[row, col], value=" ", value_type="N", place_type=None)
                            generate.append(new_dp)

                existing_coords = set(tuple(dp.coords) for dp in groundtruth)
                for row in range(max_row_num):
                    for col in range(max_column_num):
                        if (row, col) not in existing_coords:
                            # Create a new DataPoint for missing coordinates
                            new_dp = DataPoint(coords=[row, col], value=" ", value_type="N", place_type=None)
                            groundtruth.append(new_dp)

                sorted_generate_data_points = sorted(generate, key=lambda dp: dp.coords)
                # print("Sorted Generate Data Points:")
                # for dp in sorted_generate_data_points:
                #     print(dp)
                sorted_groundtruth_data_points = sorted(groundtruth, key=lambda dp: dp.coords)
                # print("\nSorted Groundtruth Data Points:")
                # for dp in sorted_groundtruth_data_points:
                #     print(dp)

                groundtruth_num = len(sorted_groundtruth_data_points)

                best_score = float('-inf')
                best_operation = None
                current_data_points = sorted_generate_data_points
                # print("qqqqq")
                # for n in current_data_points:
                #     print(n)
                # print("qqqqq")
                current_groundtruth_data_points = sorted_groundtruth_data_points
                # i = 0
                best_score = float('-inf')
                best_score_all = float('-inf')
                exit_while_loop = False
                # while best_score_all < 1 and i <= 2:
                while best_score_all < 1:
                    # i += 1
                    # Generate valid operations
                    operations = generate_valid_operations(current_data_points)

                    if not operations:
                        print("No more operations possible.")
                        break

                    best_score = float('-inf')

                    best_operation = None

                    # Evaluate each operation
                    for operation in operations:
                        # Step 1: Deep copy the data points
                        temp_data_points = copy.deepcopy(current_data_points)
                        temp_groundtruth_data_points = copy.deepcopy(current_groundtruth_data_points)
                        temp_rows_to_add = copy.deepcopy(rows_to_add)
                        temp_rows_to_delete = copy.deepcopy(rows_to_delete)
                        temp_columns_to_add = copy.deepcopy(columns_to_add)
                        temp_columns_to_delete = copy.deepcopy(columns_to_delete)
                        temp_split_mistake = copy.deepcopy(split_mistake)
                        temp_merge_mistake = copy.deepcopy(merge_mistake)

                        # Step 2: Create a mapping from original data points to copied data points
                        data_point_mapping = {id(dp): new_dp for dp, new_dp in zip(current_data_points, temp_data_points)}

                        reverse_data_point_mapping = {id(temp_dp): orig_dp for temp_dp, orig_dp in zip(temp_data_points, current_data_points)}

                        # Step 3: Replace operations' data points with those in temp_data_points
                        def map_data_point(operation, mapping):
                            """Replace data points in the operation with their corresponding deep copies."""
                            if 'params' in operation:
                                # Replace 'point' if it exists
                                if 'point' in operation['params']:
                                    original_point = operation['params']['point']
                                    if id(original_point) in mapping:
                                        operation['params']['point'] = mapping[id(original_point)]
                                # Replace 'target_dp' if it exists
                                if 'target_dp' in operation['params']:
                                    original_target_dp = operation['params']['target_dp']
                                    if id(original_target_dp) in mapping:
                                        operation['params']['target_dp'] = mapping[id(original_target_dp)]
                                if 'points' in operation['params']:
                                    original_points = operation['params']['points']
                                    for i, p in enumerate(original_points):
                                        if id(p) in mapping:
                                            operation['params']['points'][i] = mapping[id(p)]


                        def reverse_map_data_point(operation, reverse_mapping):
                            """Replace data points in the operation with their original references."""
                            if 'params' in operation:
                                # Replace 'point' if it exists
                                if 'point' in operation['params']:
                                    temp_point = operation['params']['point']
                                    if id(temp_point) in reverse_mapping:
                                        operation['params']['point'] = reverse_mapping[id(temp_point)]
                                # Replace 'target_dp' if it exists
                                if 'target_dp' in operation['params']:
                                    temp_target_dp = operation['params']['target_dp']
                                    if id(temp_target_dp) in reverse_mapping:
                                        operation['params']['target_dp'] = reverse_mapping[id(temp_target_dp)]
                                if 'points' in operation['params']:
                                    temp_points = operation['params']['points']
                                    for i, p in enumerate(temp_points):
                                        if id(p) in reverse_mapping:
                                            operation['params']['points'][i] = reverse_mapping[id(p)]


                        map_data_point(operation, data_point_mapping)

                        # Step 4: Apply operation and calculate the score
                        apply_try_operation(temp_data_points, operation)
                        matching_coords = calculate_matching_points(temp_data_points, temp_groundtruth_data_points)
                        match_count = calculate_match_count(temp_data_points, temp_groundtruth_data_points)
                        score = calculate_score(matching_coords, match_count, groundtruth_num)

                        reverse_map_data_point(operation, reverse_data_point_mapping)

                        if score > best_score:
                            best_score = score
                    if best_score >= best_score_all:
                        best_operation = operation
                    else:
                        exit_while_loop = True

                    # If best operation is found, apply it to the original data points
                    if best_operation:
                        operation_log.append(str(best_operation))
                        apply_operation(current_data_points, best_operation)
                        print(f"Applying operation: {best_operation}")
                        # print(current_data_points)
                        max_row_num0 = max(dp.coords[0] for dp in current_data_points) + 1
                        max_column_num0 = max(dp.coords[1] for dp in current_data_points) + 1
                        matching_coords = calculate_matching_points(current_data_points, current_groundtruth_data_points)
                        match_count = calculate_match_count(temp_data_points, temp_groundtruth_data_points)
                        best_score_all = calculate_score(matching_coords, match_count, groundtruth_num)
                        print(f"Updated Score: {best_score_all}")
                        clear_data_point_attributes(current_data_points)
                        minor_num_mistake = []
                        generate_point_left = []
                        groundtruth_point_left = []
                        for generate_point in current_data_points:
                            if not any(entry['generate_point'] == generate_point for entry in matching_coords):
                                if generate_point.value not in ["", " ", None]:
                                    generate_point_left.append(generate_point)

                        for groundtruth_point in current_groundtruth_data_points:
                            if not any(entry['groundtruth_point'] == groundtruth_point for entry in matching_coords):
                                if groundtruth_point.value not in ["", " ", None]:
                                    groundtruth_point_left.append(groundtruth_point)
                        merge_split_mistake, groundtruth_point_left, generate_point_left = find_and_remove_reconstructable(
                            groundtruth_point_left, generate_point_left)
                        merge_mistake = []
                        split_mistake = []
                        for pair in merge_split_mistake:
                            if isinstance(pair['generate_point'], list):
                                split_mistake.append(pair)
                            else:
                                merge_mistake.append(pair)
                        # print("\nMerge Mistake:")
                        # print(merge_mistake)
                        # print("\nSplit Mistake:")
                        # print(split_mistake)
                        to_remove_groundtruth = []
                        to_remove_generate = []

                        used_generate_left = set()

                        for groundtruth_left in groundtruth_point_left:
                            best_match = None  # To store the best matching generate_left for the current groundtruth_left
                            best_score = 0     # To store the highest similarity score for the current groundtruth_left

                            for generate_left in generate_point_left:
                                # Skip if generate_left has already been used
                                if generate_left in used_generate_left:
                                    continue
                                
                                # Compute similarity score (edit distance)
                                edit_dist = edit_distance_similarity(generate_left.value, groundtruth_left.value)
                                
                                # Update the best match if the current score is higher
                                if edit_dist > best_score:
                                    best_match = generate_left
                                    best_score = edit_dist

                            # If a valid match is found (score > 0.7), record it and mark generate_left as used
                            if best_score > 0.7 and best_match:
                                # Append the best match to the list of minor mistakes
                                minor_num_mistake.append({
                                    "generate_point": best_match,
                                    "groundtruth_point": groundtruth_left
                                })
                                # Add the current groundtruth_left and generate_left to removal lists
                                to_remove_groundtruth.append(groundtruth_left)
                                to_remove_generate.append(best_match)
                                # Mark the best match as used
                                used_generate_left.add(best_match)

                        for item in to_remove_groundtruth:
                            groundtruth_point_left.remove(item)
                        for item in to_remove_generate:
                            generate_point_left.remove(item)

                        generate = []
                        groundtruth = []

                        for pair in matching_coords:
                            pair['generate_point'].rp = pair['groundtruth_point'].coords
                            if pair['generate_point'].coords == pair['groundtruth_point'].coords:
                                pair['generate_point'].place_type = "T"
                            else:
                                pair['generate_point'].place_type = "F"
                            pair['generate_point'].value_type = "matching_values"
                            pair['groundtruth_point'].value_type = "matching_values"
                            generate.append(pair['generate_point'])
                            groundtruth.append(pair['groundtruth_point'])

                        for pair in split_mistake:
                            split3 = []
                            for gt_point in pair['generate_point']:
                                split3.append(gt_point.coords)
                            for gt_point in pair['generate_point']:
                                gt_point.value_type = "splitting_problem"
                                gt_point.rp = pair['groundtruth_point'].coords
                                gt_point.place_type = split3
                                generate.append(gt_point)
                            groundtruth.append(pair['groundtruth_point'])

                        for pair in merge_mistake:
                            split0 = []
                            for gt_point in pair['groundtruth_point']:
                                split0.append(gt_point.coords)
                                groundtruth.append(gt_point)
                            pair['generate_point'].value_type = "merging_problem"
                            pair['generate_point'].rp = split0
                            generate.append(pair['generate_point'])

                        for pair in minor_num_mistake:
                            pair['generate_point'].rp = pair['groundtruth_point'].coords
                            pair['generate_point'].value_type = "minor_num_mistake"
                            pair['generate_point'].place_type = pair['groundtruth_point'].value
                            pair['groundtruth_point'].value_type = "minor_num_mistake"
                            generate.append(pair['generate_point'])
                            groundtruth.append(pair['groundtruth_point'])

                        for point in generate_point_left:
                            point.value_type = "generate_added_values"
                            generate.append(point)

                        for point in groundtruth_point_left:
                            point.value_type = "groundtruth_added_values"
                            groundtruth.append(point)

                    if best_score_all == 1:
                        # print("Reached optimal solution with score 1.")
                        break

                    if exit_while_loop:
                        break
                    # for n in current_data_points:
                    #     print(n)

                # print("operation_log:")
                # for o in operation_log:
                #     print(o)
                # for n in current_data_points:
                #     print(n)
                # print("groundtruth")
                # for n in current_groundtruth_data_points:
                #     print(n)
                # for n in matching_coords:
                #     print(n)
                result = {
                    'generate_file': generate_file,
                    'best_score_all': best_score_all,
                    'operation_log': operation_log
                }
                results.append(result)

# Create a DataFrame from the results list
df_results = pd.DataFrame(results)

# Write the DataFrame to a CSV or Excel file
df_results.to_excel("comparison_results.xlsx", index=False)# You can also use .to_excel() if needed

# print("Results have been written to comparison_results.csv")