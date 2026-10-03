"""Transaction cost model for Indian equity markets."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CostBreakdown:
    brokerage_bps: float
    exchange_tx_charge_bps: float
    stt_buy_bps: float
    stt_sell_bps: float
    stamp_duty_bps: float
    slippage_bps: float
    total_round_trip_bps: float


class TransactionCostModel:
    """Multi-tier cost model for NSE Indian equity trades.

    Defaults based on SEBI regulations:
    - Brokerage: 0.05% max (configurable)
    - Exchange transaction charge: 0.00325% (NSE)
    - STT: 0.1% on sell (equity delivery), 0.025% on sell (intraday)
    - Stamp duty: 0.015% (buy) + 0.015% (sell)
    - GST: 18% on brokerage + exchange charges
    - Slippage: configurable
    """

    def __init__(
        self,
        brokerage_rate_bps: float = 5.0,
        exchange_tx_bps: float = 0.325,
        stt_sell_bps: float = 10.0,
        stamp_duty_bps: float = 1.5,
        slippage_bps: float = 5.0,
    ):
        self.brokerage_bps = brokerage_rate_bps
        self.exchange_tx_bps = exchange_tx_bps
        self.stt_sell_bps = stt_sell_bps
        self.stamp_duty_bps = stamp_duty_bps
        self.slippage_bps = slippage_bps

    def cost_per_trade(self, turnover: float) -> CostBreakdown:
        """Calculate cost components for a single-direction trade."""
        brokerage = turnover * self.brokerage_bps / 10000
        exchange_tx = turnover * self.exchange_tx_bps / 10000
        stt = turnover * self.stt_sell_bps / 10000
        stamp = turnover * self.stamp_duty_bps / 10000
        slippage = turnover * self.slippage_bps / 10000
        gst = (brokerage + exchange_tx) * 0.18
        total = brokerage + exchange_tx + stt + stamp + slippage + gst
        return CostBreakdown(
            brokerage_bps=self.brokerage_bps,
            exchange_tx_charge_bps=self.exchange_tx_bps,
            stt_buy_bps=0.0,
            stt_sell_bps=self.stt_sell_bps,
            stamp_duty_bps=self.stamp_duty_bps,
            slippage_bps=self.slippage_bps,
            total_round_trip_bps=round(total / turnover * 10000, 2) if turnover > 0 else 0.0,
        )

    def round_trip_cost_bps(self) -> float:
        """Total round-trip cost in basis points (buy + sell)."""
        one_way = (
            self.brokerage_bps
            + self.exchange_tx_bps
            + self.stt_sell_bps
            + self.stamp_duty_bps
            + self.slippage_bps
            + 0.18 * (self.brokerage_bps + self.exchange_tx_bps)
        )
        return round(one_way * 2, 2)  # buy + sell (STT only on sell, stamp on both)


def get_default_cost_model() -> TransactionCostModel:
    return TransactionCostModel()
