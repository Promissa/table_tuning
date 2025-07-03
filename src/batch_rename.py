#!/usr/bin/env python3
"""
Script to traverse directories up to a depth of 2 levels, ignore hidden files,
randomize their order, then rename each PNG along with its two associated JSONs
(`.json` and `_cells.json`) to `table_<id>.<ext>` and move them to the root
directory, deleting the originals. Also updates the `imagePath` field inside
each JSON to match the new PNG filename.
Afterwards, split all PNGs into `train` (80%), `val` (10%), and `test` (10%) folders
with fresh IDs from 1 in each subset.

Usage:
    python rename_tables.py --root /path/to/root_folder
"""
import os
import argparse
import random
import json


def collect_files(base_dir):
    """
    Walk up to depth 2 and collect non-hidden file paths.
    """
    files = []
    for current_root, dirs, filenames in os.walk(base_dir):
        rel_path = os.path.relpath(current_root, base_dir)
        depth = 0 if rel_path == "." else len(rel_path.split(os.sep))
        if depth > 2:
            dirs[:] = []  # don't descend further
            continue
        for fname in filenames:
            if fname.startswith("."):
                continue
            full_path = os.path.join(current_root, fname)
            _, ext = os.path.splitext(fname)
            files.append((full_path, ext.lower()))
    return files


def split_pngs(base_dir):
    """
    After renaming, collect all .png files in base_dir, shuffle, and split into
    train/val/test folders with new sequential IDs per subset.
    """
    pngs = [f for f in os.listdir(base_dir) if f.lower().endswith(".png")]
    random.shuffle(pngs)
    total = len(pngs)
    train_cut = int(total * 0.8)
    val_cut = train_cut + int(total * 0.1)

    splits = {
        "train": pngs[:train_cut],
        "val": pngs[train_cut:val_cut],
        "test": pngs[val_cut:],
    }

    for split, files in splits.items():
        split_dir = os.path.join(base_dir, split)
        os.makedirs(split_dir, exist_ok=True)
        for idx, fname in enumerate(files, 1):
            src = os.path.join(base_dir, fname)
            _, ext = os.path.splitext(fname)
            dst_name = f"table_{idx}{ext}"
            dst = os.path.join(split_dir, dst_name)
            try:
                os.rename(src, dst)
                print(f"Moved to {split}: {src} -> {dst}")
            except OSError as e:
                print(f"Error moving {src} to {dst}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Randomize, rename PNGs and their JSONs, update imagePath, relocate, and split into train/val/test."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to start traversing (default: current directory)",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(args.root)
    all_files = collect_files(base_dir)

    # Filter only PNG entries for grouping with JSONs
    png_entries = [(path, ext) for path, ext in all_files if ext == ".png"]
    random.shuffle(png_entries)

    id_counter = 95  # starting ID
    for old_path, ext in png_entries:
        dirpath, fname = os.path.split(old_path)
        base_name = os.path.splitext(fname)[0]
        new_png = f"table_{id_counter}{ext}"
        new_png_path = os.path.join(base_dir, new_png)

        # Rename PNG
        try:
            os.rename(old_path, new_png_path)
            print(f"Renamed PNG: {old_path} -> {new_png_path}")
        except OSError as e:
            print(f"Error renaming PNG {old_path}: {e}")

        # Rename & update associated JSON files
        for suffix in ["", "_cells"]:
            old_json = os.path.join(dirpath, f"{base_name}{suffix}.json")
            if os.path.exists(old_json):
                new_json_name = f"table_{id_counter}{suffix}.json"
                new_json_path = os.path.join(base_dir, new_json_name)
                try:
                    # Read, update imagePath, then write to new JSON file
                    with open(old_json, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                    data["imagePath"] = new_png
                    with open(new_json_path, "w", encoding="utf-8") as jf:
                        json.dump(data, jf, ensure_ascii=False, indent=4)
                    print(f"Renamed & updated JSON: {old_json} -> {new_json_path}")
                    os.remove(old_json)
                except (OSError, json.JSONDecodeError) as e:
                    print(f"Error processing JSON {old_json}: {e}")

        id_counter += 1

    # Finally, split the renamed PNGs into train/val/test
    # split_pngs(base_dir)


if __name__ == "__main__":
    main()
