import numpy as np

def clearing_price(potential_clearing_prices, bids, asks):
    best_price=0
    best_volume = 0
    for price in potential_clearing_prices:
        bid_volume = sum(volume for bid_price, volume in bids if bid_price >= price)
        ask_volume = sum(volume for ask_price, volume in asks if ask_price <= price)
        clearing_volume = min(bid_volume, ask_volume)

        if clearing_volume > best_volume:
            best_volume = clearing_volume
            best_price = price
    return best_price, best_volume


def simulate_order(side, price, volume, bids, asks, potential_clearing_prices, fair_value=30):
    """
    side: "bid" or "ask"
    price: order limit price
    volume: order size
    """
    if side not in {"bid", "ask"}:
        raise ValueError("side must be 'bid' or 'ask'")

    new_bids = list(bids)
    new_asks = list(asks)

    if side == "bid":
        new_bids.append((price, volume))
    else:
        new_asks.append((price, volume))

    cp, cv = clearing_price(potential_clearing_prices, new_bids, new_asks)

    if volume == 0:
        return {
            "side": side,
            "price": price,
            "order_volume": volume,
            "clearing_price": cp,
            "clearing_volume": cv,
            "filled_volume": 0,
            "fill_price": None,
            "pnl_vs_30": 0,
        }

    if side == "bid":
        # Not marketable at the auction clearing price.
        if price < cp:
            filled = 0
        else:
            # Existing bids ahead of us (better price, or same price queue already there).
            ahead = sum(
                v for p, v in bids
                if p >= cp and (p > price or p == price)
            )
            filled = max(0, min(volume, cv - ahead))
        pnl = (fair_value - price) * filled
    else:
        # Not marketable at the auction clearing price.
        if price > cp:
            filled = 0
        else:
            # Existing asks ahead of us (better price, or same price queue already there).
            ahead = sum(
                v for p, v in asks
                if p <= cp and (p < price or p == price)
            )
            filled = max(0, min(volume, cv - ahead))
        pnl = (price - fair_value) * filled

    fill_price = cp if filled > 0 else None

    return {
        "side": side,
        "price": price,
        "order_volume": volume,
        "clearing_price": cp,
        "clearing_volume": cv,
        "filled_volume": filled,
        "fill_price": fill_price,
        "pnl_vs_30": pnl,
    }


bids = [(30, 30_000), (29, 5_000), (28, 12_000), (27, 28_000)]
asks = [(28, 40_000), (31, 20_000), (32, 20_000), (33, 30_000)]
potential_clearing_prices = np.arange(26, 35)


results = []
for side in ["bid", "ask"]:
    for price in potential_clearing_prices:
        for volume in range(0, 110_001, 5_000):
            outcome = simulate_order(
                side=side,
                price=int(price),
                volume=volume,
                bids=bids,
                asks=asks,
                potential_clearing_prices=potential_clearing_prices,
                fair_value=30,
            )
            results.append(outcome)


for r in results:
    print(
        f"side={r['side']:>3} price={r['price']:>2} vol={r['order_volume']:>6} "
        f"cp={r['clearing_price']:>2} cv={r['clearing_volume']:>6} "
        f"fill={r['filled_volume']:>6} fill_px={str(r['fill_price']):>4} pnl={r['pnl_vs_30']:>8}"
    )


