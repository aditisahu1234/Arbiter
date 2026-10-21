import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
import yfinance as yf
from app.core.config import settings
from app.core.logging import get_logger
from app.data.providers.base import MarketDataProvider

logger = get_logger("yahoo_provider")


class YahooFinanceProvider(MarketDataProvider):
    """Yahoo Finance market data provider implementation with raw persistence and resilient retry."""

    def __init__(
        self,
        raw_base_dir: Optional[Path] = None,
        request_delay: float = settings.YAHOO_REQUEST_DELAY_SECONDS,
        max_retries: int = 3,
    ):
        self.raw_base_dir = raw_base_dir or settings.DATA_RAW_DIR / "yahoo"
        self.raw_base_dir.mkdir(parents=True, exist_ok=True)
        self.request_delay = request_delay
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "yahoo"

    def _persist_raw_payload(
        self, provider_symbol: str, raw_data: Dict[str, Any], date_folder: str
    ) -> Path:
        """Preserve raw provider payload for data provenance and auditability."""
        target_dir = self.raw_base_dir / date_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        sanitized_symbol = provider_symbol.replace("^", "").replace(".", "_")
        target_file = target_dir / f"{sanitized_symbol}.json"
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, default=str, indent=2)
        return target_file

    def get_asset_metadata(self, provider_symbol: str) -> Dict[str, Any]:
        """Fetch asset fundamental profile and metadata."""
        ticker = yf.Ticker(provider_symbol)
        try:
            info = ticker.info or {}
            # Persist raw info
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self._persist_raw_payload(provider_symbol, {"type": "metadata", "info": info}, today_str)

            return {
                "symbol": provider_symbol.split(".")[0],
                "provider_symbol": provider_symbol,
                "name": info.get("longName") or info.get("shortName") or provider_symbol,
                "currency": info.get("currency", "INR"),
                "country": info.get("country", "IN"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "exchange": info.get("exchange", "NSE"),
                "market_cap": info.get("marketCap"),
            }
        except Exception as e:
            logger.warning("Failed to fetch asset metadata from Yahoo", symbol=provider_symbol, error=str(e))
            return {
                "symbol": provider_symbol.split(".")[0],
                "provider_symbol": provider_symbol,
                "name": provider_symbol,
                "exchange": "NSE",
            }

    def get_historical_ohlcv(
        self,
        provider_symbol: str,
        start_date: datetime | str,
        end_date: datetime | str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical daily OHLCV from Yahoo Finance."""
        start_str = (
            start_date.strftime("%Y-%m-%d")
            if isinstance(start_date, datetime)
            else str(start_date)
        )
        end_str = (
            end_date.strftime("%Y-%m-%d")
            if isinstance(end_date, datetime)
            else str(end_date)
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                time.sleep(self.request_delay)
                ticker = yf.Ticker(provider_symbol)
                # auto_adjust=False gives us both Close and Adj Close
                df = ticker.history(
                    start=start_str,
                    end=end_str,
                    interval=interval,
                    auto_adjust=False,
                    actions=True,
                )

                if df.empty:
                    logger.warning("Empty OHLCV received from Yahoo", symbol=provider_symbol, start=start_str, end=end_str)
                    return pd.DataFrame()

                # Preserve raw response as JSON/CSV
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                raw_records = df.reset_index().to_dict(orient="records")
                self._persist_raw_payload(
                    provider_symbol,
                    {
                        "symbol": provider_symbol,
                        "query_start": start_str,
                        "query_end": end_str,
                        "records_count": len(raw_records),
                        "data": raw_records,
                    },
                    today_str,
                )

                # Reset index to extract Date column
                df = df.reset_index()

                # Normalize column names
                # Date or Datetime
                date_col = "Date" if "Date" in df.columns else "Datetime"
                df["timestamp"] = pd.to_datetime(df[date_col]).dt.tz_localize(None)

                # Map price columns
                df["open"] = df["Open"].astype(float)
                df["high"] = df["High"].astype(float)
                df["low"] = df["Low"].astype(float)
                df["close"] = df["Close"].astype(float)
                df["adjusted_close"] = (
                    df["Adj Close"].astype(float)
                    if "Adj Close" in df.columns
                    else df["close"]
                )
                df["volume"] = df["Volume"].fillna(0).astype("int64")

                ordered = df[["timestamp", "open", "high", "low", "close", "adjusted_close", "volume"]]
                ordered = ordered.sort_values("timestamp").reset_index(drop=True)
                return ordered

            except Exception as e:
                wait_time = attempt * 1.5
                logger.warning(
                    "Yahoo download retry",
                    symbol=provider_symbol,
                    attempt=attempt,
                    wait_seconds=wait_time,
                    error=str(e),
                )
                if attempt == self.max_retries:
                    logger.error("Yahoo download failed after max retries", symbol=provider_symbol, error=str(e))
                    return pd.DataFrame()
                time.sleep(wait_time)

        return pd.DataFrame()

    def get_latest_ohlcv(self, provider_symbol: str) -> pd.DataFrame:
        """Fetch the most recent OHLCV bar."""
        ticker = yf.Ticker(provider_symbol)
        try:
            df = ticker.history(period="5d", interval="1d", auto_adjust=False)
            if df.empty:
                return pd.DataFrame()

            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else "Datetime"
            df["timestamp"] = pd.to_datetime(df[date_col]).dt.tz_localize(None)
            df["open"] = df["Open"].astype(float)
            df["high"] = df["High"].astype(float)
            df["low"] = df["Low"].astype(float)
            df["close"] = df["Close"].astype(float)
            df["adjusted_close"] = (
                df["Adj Close"].astype(float)
                if "Adj Close" in df.columns
                else df["close"]
            )
            df["volume"] = df["Volume"].fillna(0).astype("int64")

            ordered = df[["timestamp", "open", "high", "low", "close", "adjusted_close", "volume"]]
            return ordered.tail(1).reset_index(drop=True)
        except Exception as e:
            logger.error("Failed to fetch latest OHLCV from Yahoo", symbol=provider_symbol, error=str(e))
            return pd.DataFrame()

    def get_live_quote(self, provider_symbol: str) -> Dict[str, Any]:
        """Fetch a bounded, clearly-labelled live/delayed intraday quote.

        This does NOT modify or corrupt completed daily candles. It returns the
        most recent verified price with its timestamp and a data_state that
        indicates whether the value is live, delayed, or unavailable. When no
        usable intraday value is exposed by the provider, data_state is
        "unavailable" and the caller must fall back to the last completed
        daily candle.
        """
        out: Dict[str, Any] = {
            "symbol": provider_symbol.split(".")[0],
            "provider_symbol": provider_symbol,
            "price": None,
            "price_timestamp": None,
            "data_state": "unavailable",
            "is_intraday": False,
            "note": "No usable current-session price from provider.",
        }
        ticker = yf.Ticker(provider_symbol)
        try:
            fi = ticker.fast_info
            price = None
            try:
                price = float(fi["last_price"])
            except Exception:
                try:
                    price = float(fi["last_close"])
                except Exception:
                    price = None
            ts = None
            try:
                raw_ts = fi.get("last_market_time") or fi.get("last_date")
                if raw_ts is not None:
                    ts = pd.to_datetime(raw_ts).to_pydatetime() if isinstance(raw_ts, str) else raw_ts
            except Exception:
                ts = None
            if price is not None and ts is not None:
                now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
                ts_aware = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                age_min = (now_ist.astimezone(timezone.utc) - ts_aware).total_seconds() / 60.0
                out.update(
                    price=round(price, 4),
                    price_timestamp=ts_aware.astimezone(timezone.utc).isoformat(),
                    data_state="live" if age_min <= 15 else "delayed",
                    is_intraday=age_min <= 15,
                    note=(
                        "Current intraday quote (live)." if age_min <= 15
                        else "Last verified quote is delayed; treat as a reference, not a live market value."
                    ),
                )
                return out
        except Exception as e:
            logger.warning("Yahoo fast_info unavailable", symbol=provider_symbol, error=str(e))

        try:
            df = ticker.history(period="1d", interval="5m", auto_adjust=False)
            if df is not None and not df.empty:
                last_ts = df.index[-1]
                out.update(
                    price=round(float(df.iloc[-1]["Close"]), 4),
                    price_timestamp=last_ts.isoformat() if hasattr(last_ts, "isoformat") else str(last_ts),
                    data_state="delayed",
                    is_intraday=True,
                    note="Most recent intraday bar (delayed reference); not a live market value.",
                )
                return out
        except Exception as e:
            logger.warning("Yahoo intraday history unavailable", symbol=provider_symbol, error=str(e))

        return out
