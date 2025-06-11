from src.benchmark import read_csv, cal_dis

# file1 = "test/benchmark_sample/parsed_result/sample.csv"
# file2 = "test/benchmark_sample/ground_truth/sample.csv"

file1 = "data/parsed_table/1800_000110465911061064_10-Q_1800_1/table_4_2_a2.csv"
file2 = "data/parsed_table/1800_000110465911061064_10-Q_1800_1/table_4.csv"

print(cal_dis(read_csv(file1), read_csv(file2)))
