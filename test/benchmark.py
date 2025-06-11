from src.benchmark import *
import argparse

# file1 = "test/benchmark_sample/parsed_result/sample.csv"
# file2 = "test/benchmark_sample/ground_truth/sample.csv"

parser = argparse.ArgumentParser(
    description="Benchmark Test\n1 - 2D Levenshtein\n2 - TEDS"
)

parser.add_argument(
    "--type",
    "-t",
    type=int,
    default=1,
    help="Type of benchmark test: 1 for 2D Levenshtein, 2 for TEDS",
)

csv_file1 = "data/parsed_table/1800_000110465911061064_10-Q_1800_1/table_4_2_a2.csv"
csv_file2 = "data/parsed_table/1800_000110465911061064_10-Q_1800_1/table_4.csv"

args = parser.parse_args()

if args.type == 1:
    print(cal_2d_lev(read_csv(csv_file1), read_csv(csv_file2)))
elif args.type == 2:
    print(cal_teds(read_csv(file1), read_csv(file2)))
