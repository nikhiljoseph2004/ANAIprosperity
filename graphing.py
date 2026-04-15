import pandas as pd

def main():
    data_dir = "data/ROUND_1/"
    instrument1 = ""
    instrument2 = "ASH_COATED_OSMIUM"
    for i in range(-2, 1):
        price_data = pd.read_csv(f"{data_dir}prices_round_1_day_{i}.csv", sep=";")


if __name__ == "__main__":
    main()