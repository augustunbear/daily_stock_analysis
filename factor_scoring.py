"""
Factor scoring module.

Provides a lightweight, extensible scoring system that can be used
alongside AI analysis. Scores are designed to be explainable and
robust to missing data.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_percent(value: Any) -> Optional[float]:
    numeric = _to_float(value)
    if numeric is None:
        return None
    if abs(numeric) <= 1:
        numeric *= 100
    return numeric


def _default_signal(score: float) -> str:
    if score >= 70:
        return "bullish"
    if score >= 55:
        return "neutral"
    return "bearish"


@dataclass
class FactorDefinition:
    name: str
    weight: float
    scorer: Callable[[Dict[str, Any]], Optional[float]]
    signaler: Callable[[float], str] = _default_signal


class FactorScorer:
    def __init__(self, factors: List[FactorDefinition]):
        self._factors = list(factors)

    def add_factor(self, factor: FactorDefinition) -> None:
        self._factors.append(factor)

    def score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        scores: Dict[str, float] = {}
        signals: Dict[str, str] = {}
        weights: Dict[str, float] = {}

        total_weight = 0.0
        weighted_sum = 0.0

        for factor in self._factors:
            raw_score = factor.scorer(context)
            if raw_score is None:
                continue
            score = _clamp(raw_score)
            scores[factor.name] = round(score, 2)
            signals[factor.name] = factor.signaler(score)
            weights[factor.name] = factor.weight
            weighted_sum += score * factor.weight
            total_weight += factor.weight

        total_score = None
        if total_weight > 0:
            total_score = round(weighted_sum / total_weight, 2)

        if total_score is not None:
            signals["overall"] = _default_signal(total_score)

        return {
            "total_score": total_score,
            "scores": scores,
            "signals": signals,
            "weights": weights,
            "order": [f.name for f in self._factors],
        }


def _score_trend(context: Dict[str, Any]) -> Optional[float]:
    ma_status = (context.get("ma_status") or "").strip()
    today = context.get("today") or {}

    if "多头" in ma_status:
        return 80.0
    if "空头" in ma_status:
        return 20.0
    if "短期向好" in ma_status:
        return 65.0
    if "短期走弱" in ma_status:
        return 35.0
    if "震荡" in ma_status:
        return 50.0

    close = _to_float(today.get("close"))
    ma5 = _to_float(today.get("ma5"))
    ma10 = _to_float(today.get("ma10"))
    ma20 = _to_float(today.get("ma20"))
    if close is None or ma5 is None or ma10 is None or ma20 is None:
        return None

    if close > ma5 > ma10 > ma20:
        return 80.0
    if close < ma5 < ma10 < ma20:
        return 20.0
    if close > ma5 and ma5 > ma10:
        return 60.0
    if close < ma5 and ma5 < ma10:
        return 40.0
    return 50.0


def _score_momentum(context: Dict[str, Any]) -> Optional[float]:
    today = context.get("today") or {}
    trend = context.get("trend_analysis") or {}
    pct_chg = _to_float(today.get("pct_chg"))
    bias_ma5 = _to_float(trend.get("bias_ma5"))

    score = 50.0
    has_data = False

    if pct_chg is not None:
        has_data = True
        if 0 <= pct_chg <= 3:
            score += 15
        elif 3 < pct_chg <= 5:
            score += 5
        elif pct_chg > 5:
            score -= 10
        elif -3 <= pct_chg < 0:
            score -= 5
        elif -5 <= pct_chg < -3:
            score -= 10
        elif pct_chg < -5:
            score -= 15

    if bias_ma5 is not None:
        has_data = True
        if bias_ma5 < 2:
            score += 10
        elif bias_ma5 > 5:
            score -= 15

    return score if has_data else None


def _score_volume(context: Dict[str, Any]) -> Optional[float]:
    realtime = context.get("realtime") or {}
    volume_ratio = _to_float(realtime.get("volume_ratio"))
    turnover_rate = _to_float(realtime.get("turnover_rate"))
    volume_change_ratio = _to_float(context.get("volume_change_ratio"))

    score = 50.0
    has_data = False

    if volume_ratio is not None:
        has_data = True
        if volume_ratio < 0.5:
            score -= 15
        elif volume_ratio < 0.8:
            score -= 8
        elif volume_ratio < 1.2:
            score += 5
        elif volume_ratio < 2.0:
            score += 10
        elif volume_ratio < 3.0:
            score += 5
        else:
            score -= 5

    if turnover_rate is not None:
        has_data = True
        if turnover_rate > 8:
            score += 5
        elif turnover_rate < 1:
            score -= 5

    if volume_change_ratio is not None:
        has_data = True
        if volume_change_ratio > 1.5:
            score += 5
        elif volume_change_ratio < 0.7:
            score -= 5

    return score if has_data else None


def _score_valuation(context: Dict[str, Any]) -> Optional[float]:
    realtime = context.get("realtime") or {}
    pe_ratio = _to_float(realtime.get("pe_ratio"))
    pb_ratio = _to_float(realtime.get("pb_ratio"))

    score = 50.0
    has_data = False

    if pe_ratio is not None:
        has_data = True
        if 10 <= pe_ratio <= 30:
            score += 10
        elif 30 < pe_ratio <= 60:
            score += 2
        elif pe_ratio < 5:
            score -= 10
        elif pe_ratio > 80:
            score -= 15

    if pb_ratio is not None:
        has_data = True
        if 1 <= pb_ratio <= 4:
            score += 5
        elif pb_ratio > 10:
            score -= 5
        elif pb_ratio < 0.5:
            score -= 5

    return score if has_data else None


def _score_size(context: Dict[str, Any]) -> Optional[float]:
    realtime = context.get("realtime") or {}
    total_mv = _to_float(realtime.get("total_mv"))
    if total_mv is None:
        return None

    if total_mv < 5e9:
        return 35.0
    if total_mv < 5e10:
        return 50.0
    if total_mv < 2e11:
        return 65.0
    return 75.0


def _score_value(context: Dict[str, Any]) -> Optional[float]:
    return _score_valuation(context)


def _score_low_volatility(context: Dict[str, Any]) -> Optional[float]:
    today = context.get("today") or {}
    high = _to_float(today.get("high"))
    low = _to_float(today.get("low"))
    close = _to_float(today.get("close"))
    if high is None or low is None or close is None or close == 0:
        return None

    intraday_range = (high - low) / close
    if intraday_range < 0.02:
        return 80.0
    if intraday_range < 0.05:
        return 65.0
    if intraday_range < 0.08:
        return 50.0
    if intraday_range < 0.12:
        return 35.0
    return 20.0


def _score_quality(context: Dict[str, Any]) -> Optional[float]:
    fundamentals = context.get("fundamentals") or {}
    roe = _to_percent(fundamentals.get("roe"))
    profit_margin = _to_percent(fundamentals.get("profit_margin"))
    debt_to_equity = _to_percent(fundamentals.get("debt_to_equity"))

    score = 50.0
    has_data = False

    if roe is not None:
        has_data = True
        if roe >= 15:
            score += 15
        elif roe >= 8:
            score += 8
        elif roe < 5:
            score -= 10

    if profit_margin is not None:
        has_data = True
        if profit_margin >= 15:
            score += 10
        elif profit_margin >= 8:
            score += 5
        elif profit_margin < 3:
            score -= 8

    if debt_to_equity is not None:
        has_data = True
        if debt_to_equity <= 50:
            score += 8
        elif debt_to_equity <= 100:
            score += 4
        elif debt_to_equity > 200:
            score -= 10
        elif debt_to_equity > 150:
            score -= 6

    return score if has_data else None


def _score_profitability(context: Dict[str, Any]) -> Optional[float]:
    fundamentals = context.get("fundamentals") or {}
    profit_margin = _to_percent(fundamentals.get("profit_margin"))
    operating_margin = _to_percent(fundamentals.get("operating_margin"))
    gross_margin = _to_percent(fundamentals.get("gross_margin"))

    score = 50.0
    has_data = False

    if profit_margin is not None:
        has_data = True
        if profit_margin >= 15:
            score += 10
        elif profit_margin >= 8:
            score += 5
        elif profit_margin < 3:
            score -= 8

    if operating_margin is not None:
        has_data = True
        if operating_margin >= 12:
            score += 8
        elif operating_margin < 2:
            score -= 6

    if gross_margin is not None:
        has_data = True
        if gross_margin >= 30:
            score += 6
        elif gross_margin < 10:
            score -= 6

    return score if has_data else None


def _score_investment(context: Dict[str, Any]) -> Optional[float]:
    fundamentals = context.get("fundamentals") or {}
    asset_growth = _to_percent(fundamentals.get("asset_growth"))
    revenue_growth = _to_percent(fundamentals.get("revenue_growth"))

    score = 50.0
    has_data = False

    if asset_growth is not None:
        has_data = True
        if asset_growth < 0:
            score += 5
        elif asset_growth <= 5:
            score += 10
        elif asset_growth <= 15:
            score += 5
        elif asset_growth > 30:
            score -= 10

    if asset_growth is None and revenue_growth is not None:
        has_data = True
        if 0 <= revenue_growth <= 15:
            score += 5
        elif revenue_growth > 25:
            score -= 5
        elif revenue_growth < 0:
            score -= 5

    return score if has_data else None


def _score_liquidity(context: Dict[str, Any]) -> Optional[float]:
    realtime = context.get("realtime") or {}
    volume_ratio = _to_float(realtime.get("volume_ratio"))
    turnover_rate = _to_float(realtime.get("turnover_rate"))

    score = 50.0
    has_data = False

    if volume_ratio is not None:
        has_data = True
        if volume_ratio < 0.6:
            score -= 15
        elif volume_ratio < 0.9:
            score -= 8
        elif volume_ratio < 1.5:
            score += 8
        elif volume_ratio < 2.5:
            score += 12
        else:
            score += 5

    if turnover_rate is not None:
        has_data = True
        if turnover_rate > 8:
            score += 8
        elif turnover_rate < 1:
            score -= 8

    return score if has_data else None


def _score_dividend_yield(context: Dict[str, Any]) -> Optional[float]:
    fundamentals = context.get("fundamentals") or {}
    dividend_yield = fundamentals.get("dividend_yield")
    if dividend_yield is None:
        realtime = context.get("realtime") or {}
        dividend_yield = realtime.get("dividend_yield")

    dividend_yield = _to_percent(dividend_yield)
    if dividend_yield is None:
        return None

    if dividend_yield >= 5:
        return 70.0
    if dividend_yield >= 2:
        return 62.0
    if dividend_yield >= 0.5:
        return 55.0
    return 45.0


def _score_earnings_revisions(context: Dict[str, Any]) -> Optional[float]:
    fundamentals = context.get("fundamentals") or {}
    eps_estimate = _to_float(fundamentals.get("eps_estimate"))
    eps_actual = _to_float(fundamentals.get("eps_actual"))
    trailing_eps = _to_float(fundamentals.get("trailing_eps"))
    forward_eps = _to_float(fundamentals.get("forward_eps"))

    if eps_estimate not in (None, 0) and eps_actual is not None:
        surprise = (eps_actual - eps_estimate) / abs(eps_estimate)
        if surprise >= 0.05:
            return 70.0
        if surprise > 0:
            return 60.0
        if surprise <= -0.05:
            return 40.0
        return 50.0

    if trailing_eps not in (None, 0) and forward_eps is not None:
        revision = (forward_eps - trailing_eps) / abs(trailing_eps)
        if revision >= 0.05:
            return 68.0
        if revision > 0:
            return 58.0
        if revision <= -0.05:
            return 40.0
        return 50.0

    return None


def _score_chip(context: Dict[str, Any]) -> Optional[float]:
    chip = context.get("chip") or {}
    realtime = context.get("realtime") or {}
    today = context.get("today") or {}

    profit_ratio = _to_float(chip.get("profit_ratio"))
    concentration_90 = _to_float(chip.get("concentration_90"))
    avg_cost = _to_float(chip.get("avg_cost"))
    current_price = _to_float(realtime.get("price"))
    if current_price is None:
        current_price = _to_float(today.get("close"))

    score = 50.0
    has_data = False

    if profit_ratio is not None:
        has_data = True
        if 0.4 <= profit_ratio <= 0.8:
            score += 10
        elif profit_ratio > 0.9:
            score -= 10
        elif profit_ratio < 0.2:
            score -= 10

    if concentration_90 is not None:
        has_data = True
        if concentration_90 < 0.15:
            score += 10
        elif concentration_90 > 0.35:
            score -= 10

    if avg_cost is not None and current_price is not None:
        has_data = True
        if current_price > avg_cost * 1.03:
            score += 5
        elif current_price < avg_cost * 0.97:
            score -= 5

    return score if has_data else None


def _score_risk(context: Dict[str, Any]) -> Optional[float]:
    today = context.get("today") or {}
    trend = context.get("trend_analysis") or {}

    pct_chg = _to_float(today.get("pct_chg"))
    bias_ma5 = _to_float(trend.get("bias_ma5"))
    high = _to_float(today.get("high"))
    low = _to_float(today.get("low"))
    close = _to_float(today.get("close"))

    score = 60.0
    has_data = False

    if bias_ma5 is not None:
        has_data = True
        if bias_ma5 > 8:
            score -= 30
        elif bias_ma5 > 5:
            score -= 20
        elif bias_ma5 < 2:
            score += 10

    if pct_chg is not None:
        has_data = True
        if abs(pct_chg) > 10:
            score -= 25
        elif abs(pct_chg) > 7:
            score -= 15

    if high is not None and low is not None and close:
        has_data = True
        intraday_range = (high - low) / close if close else 0
        if intraday_range > 0.08:
            score -= 10

    return score if has_data else None


def build_default_factor_scorer() -> FactorScorer:
    factors = [
        FactorDefinition(name="size", weight=0.08, scorer=_score_size),
        FactorDefinition(name="value", weight=0.1, scorer=_score_value),
        FactorDefinition(name="momentum", weight=0.12, scorer=_score_momentum),
        FactorDefinition(name="low_volatility", weight=0.1, scorer=_score_low_volatility),
        FactorDefinition(name="quality", weight=0.1, scorer=_score_quality),
        FactorDefinition(name="profitability", weight=0.1, scorer=_score_profitability),
        FactorDefinition(name="investment", weight=0.08, scorer=_score_investment),
        FactorDefinition(name="liquidity", weight=0.12, scorer=_score_liquidity),
        FactorDefinition(name="dividend_yield", weight=0.1, scorer=_score_dividend_yield),
        FactorDefinition(name="earnings_revisions", weight=0.1, scorer=_score_earnings_revisions),
        FactorDefinition(name="trend", weight=0.25, scorer=_score_trend),
        FactorDefinition(name="volume", weight=0.2, scorer=_score_volume),
        FactorDefinition(name="chip", weight=0.1, scorer=_score_chip),
        FactorDefinition(name="risk", weight=0.1, scorer=_score_risk),
    ]
    return FactorScorer(factors)


_DEFAULT_SCORER: Optional[FactorScorer] = None


def get_factor_scorer() -> FactorScorer:
    global _DEFAULT_SCORER
    if _DEFAULT_SCORER is None:
        _DEFAULT_SCORER = build_default_factor_scorer()
    return _DEFAULT_SCORER
