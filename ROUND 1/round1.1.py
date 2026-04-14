from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional, Tuple
import json

class Trader:

    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    PEPPER_TARGET_LONG = 50
    PEPPER_BASE_DAILY_DRIFT = 1000.0
    OSMIUM_FAIR_VALUE = 10000
    OSMIUM_TRADE_CLIP = 8

    def _load_state(self, raw: str) -> Dict[str, float]:
        default_state = {
            "pepper_last_mid": 12000.0,
            "pepper_slope_per_ts": self.PEPPER_BASE_DAILY_DRIFT / 1_000_000.0,
            "pepper_last_ts": 0.0,
        }
        if not raw:
            return default_state
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return default_state
            default_state.update(
                {
                    "pepper_last_mid": float(payload.get("pepper_last_mid", default_state["pepper_last_mid"])),
                    "pepper_slope_per_ts": float(payload.get("pepper_slope_per_ts", default_state["pepper_slope_per_ts"])),
                    "pepper_last_ts": float(payload.get("pepper_last_ts", default_state["pepper_last_ts"])),
                }
            )
            return default_state
        except Exception:
            return default_state

    def _best_bid_ask(self, depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
        best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
        return best_bid, best_ask

    def _mid_price(self, depth: OrderDepth, fallback: float) -> float:
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return fallback

    def _position_after(self, position: int, orders: List[Order]) -> int:
        return position + sum(order.quantity for order in orders)

    def _buy_capacity(self, limit: int, effective_position: int) -> int:
        return max(0, limit - effective_position)

    def _sell_capacity(self, limit: int, effective_position: int) -> int:
        return max(0, limit + effective_position)

    def _append_buy(self, orders: List[Order], product: str, price: int, quantity: int, position: int) -> None:
        if quantity <= 0:
            return
        limit = self.POSITION_LIMITS[product]
        effective_position = self._position_after(position, orders)
        cap = self._buy_capacity(limit, effective_position)
        qty = min(quantity, cap)
        if qty > 0:
            orders.append(Order(product, int(price), int(qty)))

    def _append_sell(self, orders: List[Order], product: str, price: int, quantity: int, position: int) -> None:
        if quantity <= 0:
            return
        limit = self.POSITION_LIMITS[product]
        effective_position = self._position_after(position, orders)
        cap = self._sell_capacity(limit, effective_position)
        qty = min(quantity, cap)
        if qty > 0:
            orders.append(Order(product, int(price), int(-qty)))

    def _trade_pepper(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        expected_fair: float,
        target_long: int,
    ) -> List[Order]:
        orders: List[Order] = []

        asks = sorted(depth.sell_orders.items())
        bids = sorted(depth.buy_orders.items(), reverse=True)

        # Aggressive buys when asks are below expected fair value with a bullish bias.
        for ask_price, ask_volume in asks:
            edge = expected_fair - ask_price
            if edge < 1.0:
                continue
            remaining_to_target = max(0, target_long - self._position_after(position, orders))
            if remaining_to_target <= 0:
                break
            ask_qty = max(0, -ask_volume)
            take_qty = min(ask_qty, 18, remaining_to_target)
            self._append_buy(orders, product, ask_price, take_qty, position)

        best_bid, best_ask = self._best_bid_ask(depth)
        live_position = self._position_after(position, orders)

        # Keep a persistent long bias using passive bids until target inventory is reached.
        if live_position < target_long and best_bid is not None:
            passive_bid = min(int(expected_fair - 1), best_bid + 1)
            top_up = min(12, target_long - live_position)
            self._append_buy(orders, product, passive_bid, top_up, position)

        # Defensive profit-taking only when rich vs expected fair and inventory is heavy.
        live_position = self._position_after(position, orders)
        if live_position > target_long and best_ask is not None:
            rich_threshold = int(expected_fair + 2)
            for bid_price, bid_volume in bids:
                if bid_price < rich_threshold:
                    break
                bid_qty = max(0, bid_volume)
                unwind_qty = min(bid_qty, 10, live_position - target_long)
                self._append_sell(orders, product, bid_price, unwind_qty, position)

            # Passive offer to bleed down excess inventory safely.
            live_position = self._position_after(position, orders)
            if live_position > target_long:
                passive_ask = max(int(expected_fair + 2), (best_ask - 1) if best_ask is not None else int(expected_fair + 3))
                self._append_sell(orders, product, passive_ask, min(8, live_position - target_long), position)

        return orders

    def _trade_osmium(self, product: str, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is None and best_ask is None:
            return orders

        fair = self.OSMIUM_FAIR_VALUE

        # Lightweight mean-reversion around a near-fixed fair value.
        if best_ask is not None and best_ask <= fair - 2:
            ask_volume = max(0, -depth.sell_orders[best_ask])
            self._append_buy(orders, product, best_ask, min(self.OSMIUM_TRADE_CLIP, ask_volume), position)

        if best_bid is not None and best_bid >= fair + 2:
            bid_volume = max(0, depth.buy_orders[best_bid])
            self._append_sell(orders, product, best_bid, min(self.OSMIUM_TRADE_CLIP, bid_volume), position)

        # If we are too long/short, bias passive quotes to drift toward neutral.
        live_position = self._position_after(position, orders)
        if live_position > 10 and best_ask is not None:
            self._append_sell(orders, product, max(fair + 1, best_ask - 1), min(6, live_position - 10), position)
        elif live_position < -10 and best_bid is not None:
            self._append_buy(orders, product, min(fair - 1, best_bid + 1), min(6, -10 - live_position), position)

        return orders

    def bid(self):
        return 15
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        state_data = self._load_state(state.traderData)
        result: Dict[str, List[Order]] = {}

        pepper_depth = state.order_depths.get("INTARIAN_PEPPER_ROOT")
        if pepper_depth is not None:
            previous_mid = float(state_data["pepper_last_mid"])
            previous_ts = float(state_data["pepper_last_ts"])
            pepper_mid = self._mid_price(pepper_depth, fallback=previous_mid)
            ts_delta = max(1.0, float(state.timestamp) - previous_ts)
            observed_slope = (pepper_mid - previous_mid) / ts_delta
            slope = 0.85 * float(state_data["pepper_slope_per_ts"]) + 0.15 * observed_slope
            min_slope = self.PEPPER_BASE_DAILY_DRIFT / 1_000_000.0 * 0.5
            max_slope = self.PEPPER_BASE_DAILY_DRIFT / 1_000_000.0 * 1.8
            slope = max(min_slope, min(max_slope, slope))

            expected_fair = pepper_mid + slope * 120.0

            pepper_position = state.position.get("INTARIAN_PEPPER_ROOT", 0)
            pepper_orders = self._trade_pepper(
                product="INTARIAN_PEPPER_ROOT",
                depth=pepper_depth,
                position=pepper_position,
                expected_fair=expected_fair,
                target_long=self.PEPPER_TARGET_LONG,
            )
            result["INTARIAN_PEPPER_ROOT"] = pepper_orders

            state_data["pepper_last_mid"] = pepper_mid
            state_data["pepper_slope_per_ts"] = slope
            state_data["pepper_last_ts"] = float(state.timestamp)

        osmium_depth = state.order_depths.get("ASH_COATED_OSMIUM")
        if osmium_depth is not None:
            osmium_position = state.position.get("ASH_COATED_OSMIUM", 0)
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(
                product="ASH_COATED_OSMIUM",
                depth=osmium_depth,
                position=osmium_position,
            )

        # Ensure output contains all observed products, even if no trade is sent.
        for product in state.order_depths:
            result.setdefault(product, [])

        traderData = json.dumps(state_data)
        conversions = 0
        return result, conversions, traderData