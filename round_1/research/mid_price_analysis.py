from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean, pstdev

import matplotlib.pyplot as plt


def load_mid_prices(
    csv_path: Path, drop_nonpositive: bool = True
) -> tuple[dict[str, list[tuple[int, float]]], dict[str, int]]:
    by_product: dict[str, list[tuple[int, float]]] = {}
    dropped: dict[str, int] = {}

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            product = row["product"].strip()
            ts_raw = row["timestamp"].strip()
            mid_raw = row["mid_price"].strip()

            if not product or not ts_raw or not mid_raw:
                continue

            timestamp = int(ts_raw)
            mid_price = float(mid_raw)

            if drop_nonpositive and mid_price <= 0:
                dropped[product] = dropped.get(product, 0) + 1
                continue

            by_product.setdefault(product, []).append((timestamp, mid_price))

    for product, points in by_product.items():
        points.sort(key=lambda x: x[0])

    return by_product, dropped


def rolling_mean(values: list[float], window: int) -> list[float]:
    out: list[float] = []
    running_sum = 0.0
    for i, v in enumerate(values):
        running_sum += v
        if i >= window:
            running_sum -= values[i - window]
        denom = min(i + 1, window)
        out.append(running_sum / denom)
    return out


def rolling_std(values: list[float], window: int) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        out.append(pstdev(chunk) if len(chunk) > 1 else 0.0)
    return out


def first_diff(values: list[float]) -> list[float]:
    if len(values) < 2:
        return []
    return [values[i] - values[i - 1] for i in range(1, len(values))]


def lag1_autocorr(values: list[float]) -> float:
    if len(values) < 3:
        return float("nan")

    x = values[:-1]
    y = values[1:]
    mx = mean(x)
    my = mean(y)

    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    var_x = sum((a - mx) ** 2 for a in x)
    var_y = sum((b - my) ** 2 for b in y)

    if var_x == 0 or var_y == 0:
        return float("nan")

    return cov / math.sqrt(var_x * var_y)


def series_by_product(
    points: list[tuple[int, float]],
) -> tuple[list[int], list[float], list[float], list[float], list[float]]:
    timestamps = [t for t, _ in points]
    mids = [m for _, m in points]

    if not mids:
        return timestamps, mids, [], [], []

    base = mids[0]
    pct_from_start = [((m / base) - 1.0) * 100.0 for m in mids]
    d_mids = first_diff(mids)
    d_mids_vol = rolling_std(d_mids, window=20) if d_mids else []
    d_mids_avg = rolling_mean(d_mids, window=20) if d_mids else []

    return timestamps, mids, pct_from_start, d_mids_avg, d_mids_vol


def build_spread(
    product_a: list[tuple[int, float]],
    product_b: list[tuple[int, float]],
) -> tuple[list[int], list[float]]:
    map_a = {t: m for t, m in product_a}
    map_b = {t: m for t, m in product_b}

    common_ts = sorted(set(map_a).intersection(map_b))
    spread = [map_b[t] - map_a[t] for t in common_ts]
    return common_ts, spread


def print_summary(by_product: dict[str, list[tuple[int, float]]]) -> None:
    print("Mid-price summary")
    print("=" * 60)

    for product, points in sorted(by_product.items()):
        mids = [m for _, m in points]
        d_mids = first_diff(mids)
        ac = lag1_autocorr(mids)

        print(f"{product}:")
        print(f"  observations: {len(mids)}")
        print(f"  min/max mid: {min(mids):.2f} / {max(mids):.2f}")
        print(f"  mean mid: {mean(mids):.4f}")
        print(f"  std mid: {pstdev(mids):.4f}")
        if d_mids:
            print(f"  mean delta(mid): {mean(d_mids):.6f}")
            print(f"  std delta(mid): {pstdev(d_mids):.6f}")
        else:
            print("  mean delta(mid): n/a")
            print("  std delta(mid): n/a")
        print(f"  lag-1 autocorr(mid): {ac:.6f}" if not math.isnan(ac) else "  lag-1 autocorr(mid): n/a")
        print("-" * 60)


def plot_mid_prices(by_product: dict[str, list[tuple[int, float]]], out_path: Path, show: bool) -> None:
    if len(by_product) < 2:
        raise ValueError("Expected at least 2 products for comparative analysis.")

    products = sorted(by_product.keys())

    fig, ax = plt.subplots(1, 1, figsize=(12, 6), constrained_layout=True)

    for product in products:
        points = by_product[product]
        timestamps = [t for t, _ in points]
        mids = [m for _, m in points]
        ax.scatter(timestamps, mids, s=8, alpha=0.55, label=product)

    ax.set_title("Mid Price Dots by Asset")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Mid Price")
    ax.grid(alpha=0.25)
    ax.legend()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    print(f"Saved plot: {out_path}")

    if show:
        plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze and plot mid-price patterns for all products in a prices file."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/ROUND_1/prices_round_1_day_0.csv"),
        help="Path to semicolon-delimited prices CSV.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("research/output/mid_price_patterns_day0.png"),
        help="Path to output plot image.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figure window in addition to saving it.",
    )
    parser.add_argument(
        "--keep-nonpositive",
        action="store_true",
        help="Keep non-positive mid prices instead of filtering them out.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.csv.exists():
        raise FileNotFoundError(f"CSV not found: {args.csv}")

    by_product, dropped = load_mid_prices(
        args.csv,
        drop_nonpositive=not args.keep_nonpositive,
    )

    if not by_product:
        raise ValueError("No valid rows found in CSV.")

    if dropped and not args.keep_nonpositive:
        print("Filtered non-positive mid prices")
        print("=" * 60)
        for product, count in sorted(dropped.items()):
            print(f"{product}: dropped {count} rows")
        print("=" * 60)

    print_summary(by_product)
    plot_mid_prices(by_product, out_path=args.out, show=args.show)


if __name__ == "__main__":
    main()
