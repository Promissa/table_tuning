#!/usr/bin/env python3
"""
Script to traverse directories up to a depth of 2 levels, ignore hidden files,
randomize their order, then rename each to 'table_<id><original_extension>'
and move them to the root directory, deleting the originals. Afterwards,
split all PNG files into 'train' (80%), 'val' (10%), and 'test' (10%) folders
with fresh IDs from 1 in each subset.

Usage:
    python rename_tables.py --root /path/to/root_folder
"""
import os
import argparse
import random


def collect_files(base_dir):
    """
    Walk up to depth 2 and collect non-hidden file paths.
    """
    files = []
    for current_root, dirs, filenames in os.walk(base_dir):
        rel_path = os.path.relpath(current_root, base_dir)
        depth = 0 if rel_path == "." else len(rel_path.split(os.sep))
        if depth > 2:
            dirs[:] = []
            continue
        for fname in filenames:
            if fname.startswith("."):
                continue
            old_path = os.path.join(current_root, fname)
            _, ext = os.path.splitext(fname)
            files.append((old_path, ext.lower()))
    return files


def split_pngs(base_dir):
    """
    After renaming, collect all .png files in base_dir, shuffle, and split into
    train/val/test folders with new sequential IDs per subset.
    """
    # Collect PNG filenames
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
        description="Randomize, rename, relocate, and split PNGs into train/val/test."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to start traversing (default: current directory)",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(args.root)
    all_files = collect_files(base_dir)

    # Randomize processing order
    random.shuffle(all_files)

    # Rename and move all files to base_dir
    id_counter = 1
    for old_path, ext in all_files:
        new_name = f"table_{id_counter}{ext}"
        new_path = os.path.join(base_dir, new_name)
        try:
            os.rename(old_path, new_path)
            print(f"Moved: {old_path} -> {new_path}")
            id_counter += 1
        except OSError as e:
            print(f"Error moving {old_path} to {new_path}: {e}")

    # Split PNGs into train/val/test
    split_pngs(base_dir)


if __name__ == "__main__":
    main()
