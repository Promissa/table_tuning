import json, os, sys


def read_json(file_path: str) -> dict[str, str]:
    with open(file_path, "r") as file:
        data = json.load(file)
    return data


def find_closest(x: float, arr: list[float]) -> float:
    import bisect

    idx = bisect.bisect_left(arr, x)

    if idx == 0:
        return arr[0]
    if idx == len(arr):
        return arr[-1]

    return arr[idx - 1] if abs(arr[idx - 1] - x) < abs(arr[idx - 1] - x) else arr[idx]


row_labels = ["table row", "table column header", "table projected row header"]


def find_json_files(root: str, max_depth: int = 1):
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.lower().endswith(".json") and "cells" not in fn:
                yield dirpath, fn


def adsorp(path: str) -> dict[str, str]:
    data = read_json(path)
    shapes = data["shapes"]
    row_borders = [shapes[0]["points"][0][1]]
    col_borders = [shapes[0]["points"][0][0]]
    for shape in shapes:
        if shape["label"] in row_labels:
            if abs(row_borders[-1] - shape["points"][0][1]) > 2.0:
                row_borders.append(shape["points"][0][1])
            row_borders.append(shape["points"][1][1])
        if shape["label"] == "table column":
            if abs(col_borders[-1] - shape["points"][0][0]) > 2.0:
                col_borders.append(shape["points"][0][0])
            col_borders.append(shape["points"][1][0])
            shape["points"][0][1] = shapes[0]["points"][0][1]
            shape["points"][1][1] = shapes[0]["points"][1][1]
    row_borders.append(shapes[0]["points"][1][1])
    col_borders.append(shapes[0]["points"][1][0])
    for shape in shapes:
        if shape["label"] == "table column":
            shape["points"][0][1] = find_closest(shape["points"][0][1], row_borders)
            shape["points"][1][1] = find_closest(shape["points"][1][1], row_borders)
        if shape["label"] == "table spanning cell":
            shape["points"][0][0] = find_closest(shape["points"][0][0], col_borders)
            shape["points"][1][0] = find_closest(shape["points"][1][0], col_borders)
            shape["points"][0][1] = find_closest(shape["points"][0][1], row_borders)
            shape["points"][1][1] = find_closest(shape["points"][1][1], row_borders)
    data["shapes"] = shapes
    return data


def main():
    folder_path = "data/labeling_data/annotated/"
    json_files = list(find_json_files(folder_path, max_depth=1))
    if not json_files:
        print("No json files found")
        sys.exit(1)
    for json_file in json_files:
        path = os.path.join(json_file[0], json_file[1])
        output_path = os.path.join("test/test_output/json/", json_file[1])
        print(f"Created: {output_path}")
        data = read_json(path)
        data["shapes"] = adsorp(data)
        with open(output_path, "w") as file:
            json.dump(data, file, indent=2)


if __name__ == "__main__":
    main()
