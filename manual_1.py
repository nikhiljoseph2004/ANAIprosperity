import numpy as np

def clearing_price(potential_clearing_prices, bids, asks):
    best_price, best_volume = 0, 0
    for price in potential_clearing_prices:
        # we need to find the clearing price that maximizes the total volume of trades
        # if there are multiple clearing prices with the same total volume, we choose the one the highest clearing price
        sum_bid = sum(volume for bid_price, volume in bids if bid_price >= price)
        sum_ask = sum(volume for ask_price, volume in asks if ask_price <= price)
        total_volume = min(sum_bid, sum_ask)
        if total_volume > best_volume or (total_volume == best_volume and price > best_price):
            best_price, best_volume = price, total_volume
    return best_price, best_volume



def my_bid_fill(order_price, order_size, cp, stale_bids, stale_asks):
    """Volume I get filled if I place a bid at order_price/order_size."""
    if order_price < cp:
        return 0
    total_ask = sum(vol for p, vol in stale_asks if p <= cp)
    stale_bid = sum(vol for p, vol in stale_bids if p >= cp)
    return max(0, min(order_size, total_ask - stale_bid))


def my_ask_fill(order_price, order_size, cp, stale_bids, stale_asks):
    """Volume I get filled if I place an ask at order_price/order_size."""
    if order_price > cp:
        return 0
    total_bid = sum(vol for p, vol in stale_bids if p >= cp)
    stale_ask = sum(vol for p, vol in stale_asks if p <= cp)
    return max(0, min(order_size, total_bid - stale_ask))


def main():
    stale_bids = [(30, 30_000), (29, 5_000), (28, 12_000), (27, 28_000)]
    stale_asks = [(28, 40_000), (31, 20_000), (32, 20_000), (33, 30_000)]
    closing_price = 30

    potential_clearing_prices = np.arange(25, 36)

    # Baseline clearing price (no participant order)
    base_cp, base_vol = clearing_price(potential_clearing_prices, stale_bids, stale_asks)
    print(f"Baseline clearing price: {base_cp}, volume: {base_vol:,}")

    order_prices = np.arange(25, 36)
    order_sizes = np.arange(5_000, 120_000, 5_000)

    best_pnl = 0
    best_order = None

    for order_size in order_sizes:
        for order_price in order_prices:
            # --- Try as a BID ---
            new_bids = stale_bids + [(order_price, order_size)]
            cp, _ = clearing_price(potential_clearing_prices, new_bids, stale_asks)
            fill = my_bid_fill(order_price, order_size, cp, stale_bids, stale_asks)
            pnl = fill * (closing_price - cp)
            if pnl > best_pnl:
                best_pnl = pnl
                best_order = ("BID", order_price, order_size, cp, fill, pnl)

            # --- Try as an ASK ---
            new_asks = stale_asks + [(order_price, order_size)]
            cp, _ = clearing_price(potential_clearing_prices, stale_bids, new_asks)
            fill = my_ask_fill(order_price, order_size, cp, stale_bids, stale_asks)
            pnl = fill * (cp - closing_price)
            if pnl > best_pnl:
                best_pnl = pnl
                best_order = ("ASK", order_price, order_size, cp, fill, pnl)

    if best_order:
        side, op, os, cp, fill, pnl = best_order
        print(f"\nBest order: {side} {os:,} @ {op}")
        print(f"  Clearing price : {cp}")
        print(f"  Fill           : {fill:,}")
        print(f"  PnL            : {pnl:,}")
    else:
        print("\nNo profitable order found.")


if __name__ == '__main__':
    main()

    