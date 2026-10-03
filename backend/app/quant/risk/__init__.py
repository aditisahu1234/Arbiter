"""Risk analysis: CAPM and Fama-French 3-Factor regression."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class CAPMResult:
    alpha: float
    beta: float
    r_squared: float
    alpha_se: float
    alpha_t_stat: float
    alpha_p_value: float
    observations: int


@dataclass
class FamaFrenchResult:
    alpha: float
    beta_market: float
    beta_size: float
    beta_value: float
    r_squared: float
    alpha_se: float
    alpha_t_stat: float
    alpha_p_value: float
    observations: int


class CAPMEngine:
    """CAPM: R_i - Rf = alpha + beta*(Rm - Rf) + epsilon"""

    @staticmethod
    def compute(
        asset_returns: pd.Series,
        market_returns: pd.Series,
        risk_free_daily: float = 0.000183,  # ~6.68% annualized / 252
    ) -> CAPMResult:
        excess_asset = asset_returns - risk_free_daily
        excess_market = market_returns - risk_free_daily

        valid = pd.DataFrame({
            "excess_asset": excess_asset,
            "excess_market": excess_market,
        }).dropna()

        if len(valid) < 30:
            raise ValueError(f"Insufficient observations: {len(valid)}")

        x = valid["excess_market"].values
        y = valid["excess_asset"].values

        # OLS regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        return CAPMResult(
            alpha=intercept,
            beta=slope,
            r_squared=float(r_value ** 2),
            alpha_se=float(std_err),
            alpha_t_stat=intercept / std_err if std_err > 0 else 0.0,
            alpha_p_value=float(p_value),
            observations=len(valid),
        )


class FamaFrenchEngine:
    """Fama-French 3-Factor: Ri - Rf = alpha + beta_m*(Rm-Rf) + beta_s*SMB + beta_h*HML"""

    @staticmethod
    def compute(
        asset_returns: pd.Series,
        market_excess: pd.Series,
        smb: pd.Series,
        hml: pd.Series,
        risk_free_daily: float = 0.000183,
    ) -> FamaFrenchResult:
        excess = asset_returns - risk_free_daily

        df = pd.DataFrame({
            "excess": excess,
            "mkt": market_excess,
            "smb": smb,
            "hml": hml,
        }).dropna()

        if len(df) < 30:
            raise ValueError(f"Insufficient observations: {len(df)}")

        X = df[["mkt", "smb", "hml"]].values
        y = df["excess"].values

        # OLS with statsmodels-style manual computation
        X_with_const = np.column_stack([np.ones(len(X)), X])
        beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]

        y_pred = X_with_const @ beta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        n = len(y)
        k = X_with_const.shape[1]
        mse = ss_res / max(n - k, 1)
        var_beta = mse * np.linalg.inv(X_with_const.T @ X_with_const).diagonal()
        se = np.sqrt(np.maximum(var_beta, 0))

        t_stat = beta[0] / se[0] if se[0] > 0 else 0
        p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - k))

        return FamaFrenchResult(
            alpha=float(beta[0]),
            beta_market=float(beta[1]),
            beta_size=float(beta[2]),
            beta_value=float(beta[3]),
            r_squared=float(r_squared),
            alpha_se=float(se[0]),
            alpha_t_stat=float(t_stat),
            alpha_p_value=float(p_val),
            observations=n,
        )
