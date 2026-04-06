from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Optional

from dealwatch.core.models import AnomalyReason, DealEvent, Offer


#########################################################
# Rules Engine
#########################################################
@dataclass(slots=True)
class RulesEngine:
    min_drop_amount: float = 0.05
    min_drop_pct: float = 1.0
    anomaly_min_samples: int = 8
    anomaly_iqr_multiplier: float = 3.0
    anomaly_zscore_threshold: float = 4.0
    anomaly_zero_var_pct: float = 0.5
    anomaly_zero_var_abs: float = 1.0

    def analyze_drop(
        self,
        current_offer: Offer,
        last_price: Optional[float],
        historical_low: Optional[float] = None,
        anomaly_reason: AnomalyReason | None = None,
    ) -> Optional[DealEvent]:
        if last_price is None:
            return None

        normalized_last = round(last_price, 2)
        if normalized_last <= 0:
            return None
        normalized_current = round(current_offer.price, 2)

        drop_amount = round(normalized_last - normalized_current, 2)
        if drop_amount <= 0:
            return None

        drop_pct = round((drop_amount / normalized_last) * 100.0, 2)
        if drop_amount < self.min_drop_amount or drop_pct < self.min_drop_pct:
            return None

        is_new_low = False
        if historical_low is not None:
            normalized_low = round(historical_low, 2)
            if normalized_low > 0 and normalized_current < normalized_low:
                is_new_low = True

        return DealEvent(
            offer=current_offer,
            last_price=normalized_last,
            drop_amount=drop_amount,
            drop_pct=drop_pct,
            is_new_low=is_new_low,
            anomaly_reason=anomaly_reason,
        )

    def is_anomalous_price(
        self,
        current_price: float,
        history: list[float],
    ) -> tuple[bool, AnomalyReason | None]:
        values = [round(price, 2) for price in history if price and price > 0]
        if len(values) < self.anomaly_min_samples:
            return False, None

        values.sort()
        q1 = self._percentile(values, 0.25)
        q3 = self._percentile(values, 0.75)
        iqr = q3 - q1
        if iqr > 0:
            lower = q1 - self.anomaly_iqr_multiplier * iqr
            upper = q3 + self.anomaly_iqr_multiplier * iqr
            if current_price < lower or current_price > upper:
                return True, AnomalyReason.IQR

        deviation = pstdev(values)
        if deviation > 0:
            score = abs((current_price - mean(values)) / deviation)
            if score >= self.anomaly_zscore_threshold:
                return True, AnomalyReason.ZSCORE
        else:
            baseline = mean(values)
            if baseline > 0:
                delta = abs(current_price - baseline)
                pct_delta = delta / baseline
                if delta >= self.anomaly_zero_var_abs or pct_delta >= self.anomaly_zero_var_pct:
                    return True, AnomalyReason.ZERO_VAR

        return False, None

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        if percentile <= 0:
            return values[0]
        if percentile >= 1:
            return values[-1]
        index = (len(values) - 1) * percentile
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        weight = index - lower
        if upper == lower:
            return values[lower]
        return values[lower] + (values[upper] - values[lower]) * weight
