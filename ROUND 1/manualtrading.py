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
        


bids = [(30, 30_000), (29, 5_000), (28, 12_000), (27, 28_000)]
asks = [(28, 40_000), (31, 20_000), (32, 20_000), (33, 30_000)]
potential_clearing_prices = np.arange(26, 35)


best_price, best_volume = clearing_price(potential_clearing_prices, bids, asks)



print(best_price, best_volume)


