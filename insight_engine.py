from datetime import datetime

import pandas as pd

from utils import COUNTRY_DISPLAY_MAP, METRIC_DISPLAY_MAP
from config import (
    ANOMALY_MIN_PCT_CHANGE,
    ANOMALY_EXTREME_THRESHOLD,
    ANOMALY_HIGH_SEVERITY_PCT,
    ANOMALY_BRUSCA_THRESHOLD,
    TREND_MIN_TOTAL_DELTA_PCT,
    BENCHMARK_MIN_PP_GAP,
    BENCHMARK_MIN_REL_GAP_PCT,
    BENCHMARK_MIN_ABS_GAP,
    BENCHMARK_HIGH_SEVERITY_PP,
    BENCHMARK_HIGH_SEVERITY_REL,
)


class InsightEngine:
    """
    Genera insights automáticos rule-based a partir de un analytical_result
    y también puede producir un reporte ejecutivo sobre el dataset completo.
    """

    WEEK_ORDER = {
        "L8W": 0,
        "L7W": 1,
        "L6W": 2,
        "L5W": 3,
        "L4W": 4,
        "L3W": 5,
        "L2W": 6,
        "L1W": 7,
        "L0W": 8,
    }

    LOWER_IS_BETTER = {
        "Late Orders",
        "Defects",
        "Cancellations",
        "Restaurants Markdowns / GMV",
    }

    WEEK_SHORT_DISPLAY = {
        "L0W": "sem. actual",
        "L1W": "hace 1 sem.",
        "L2W": "hace 2 sem.",
        "L3W": "hace 3 sem.",
        "L4W": "hace 4 sem.",
        "L5W": "hace 5 sem.",
        "L6W": "hace 6 sem.",
        "L7W": "hace 7 sem.",
        "L8W": "hace 8 sem.",
    }

    def __init__(self, metrics_df: pd.DataFrame | None = None, orders_df: pd.DataFrame | None = None):
        self.metrics_df = metrics_df.copy() if metrics_df is not None else None
        self.orders_df = orders_df.copy() if orders_df is not None else None

    def _is_percentage_metric(self, metric_name: str | None) -> bool:
        if not metric_name:
            return False

        percentage_metrics = {
            "Perfect Orders",
            "Late Orders",
            "Defects",
            "Cancellations",
            "Lead Penetration",
            "Pro Adoption",
            "Pro Adoption (Last Week Status)",
            "Turbo Adoption",
            "Non-Pro PTC > OP",
            "Restaurants SS > ATC CVR",
            "Restaurants SST > SS CVR",
            "Retail SST > SS CVR",
            "Restaurants Markdowns / GMV",
            "% PRO Users Who Breakeven",
            "% Restaurants Sessions With Optimal Assortment",
            "MLTV Top Verticals Adoption",
        }
        return metric_name in percentage_metrics

    def _is_lower_better(self, metric_name: str | None) -> bool:
        return metric_name in self.LOWER_IS_BETTER

    def _metric_display(self, metric_name: str) -> str:
        return METRIC_DISPLAY_MAP.get(metric_name, metric_name)

    def _week_display(self, week: str) -> str:
        return self.WEEK_SHORT_DISPLAY.get(week, week)

    def _zone_display(self, zone: str) -> str:
        """Convert ALL_CAPS_UNDERSCORE zone names to readable Title Case."""
        if not zone:
            return zone
        normalized = zone.replace("_", "").replace("-", "").replace(" ", "")
        if normalized and normalized.isupper():
            return zone.replace("_", " ").title()
        return zone

    def _fmt(self, value, metric_name: str | None = None):
        if value is None:
            return "N/A"

        try:
            numeric_value = float(value)
            if self._is_percentage_metric(metric_name):
                # Values already in percentage form (> 1) should not be multiplied
                if abs(numeric_value) <= 1:
                    return f"{numeric_value * 100:,.2f}%"
                return f"{numeric_value:,.2f}%"
            return f"{numeric_value:,.2f}"
        except Exception:
            return str(value)

    def _safe_float(self, value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    def _make_insight(
        self,
        title: str,
        message: str,
        category: str = "operational_readout",
        severity: str = "medium",
        recommendation: str | None = None,
    ) -> dict:
        payload = {
            "title": title,
            "message": message,
            "category": category,
            "severity": severity,
        }
        if recommendation:
            payload["recommendation"] = recommendation
        return payload

    def _trend_strength_label(self, delta_pct):
        if delta_pct is None:
            return "stable"

        abs_delta = abs(delta_pct)
        if abs_delta >= 15:
            return "strong"
        if abs_delta >= 5:
            return "moderate"
        if abs_delta > 0:
            return "slight"
        return "stable"

    def _with_sorting(self, df: pd.DataFrame) -> pd.DataFrame:
        ordered = df.copy()
        ordered["week_order"] = ordered["week"].map(self.WEEK_ORDER)
        return ordered.sort_values("week_order")

    def _latest_week(self, df: pd.DataFrame) -> str | None:
        weeks = [w for w in df["week"].dropna().unique() if w in self.WEEK_ORDER]
        if not weeks:
            return None
        return max(weeks, key=lambda w: self.WEEK_ORDER[w])

    def _generate_trend_insights(self, result: dict) -> list[dict]:
        insights = []

        first_value = self._safe_float(result.get("first_value"))
        last_value = self._safe_float(result.get("last_value"))
        delta_abs = self._safe_float(result.get("delta_abs"))
        delta_pct = self._safe_float(result.get("delta_pct"))
        metric = result.get("metric", "Metric")
        first_week = result.get("first_week")
        last_week = result.get("last_week")

        if first_value is None or last_value is None:
            return [
                self._make_insight(
                    "Tendencia no disponible",
                    "El análisis de tendencia no está disponible porque la serie temporal está incompleta.",
                    category="trend_watch",
                    severity="medium",
                )
            ]

        if delta_abs is None:
            delta_abs = last_value - first_value

        strength = self._trend_strength_label(delta_pct)

        if delta_abs > 0:
            insights.append(
                self._make_insight(
                    "Dirección de la tendencia",
                    f"{metric} aumentó desde {self._fmt(first_value, metric)} en {first_week} hasta {self._fmt(last_value, metric)} en {last_week}.",
                    category="trend_watch",
                    severity="medium",
                )
            )
        elif delta_abs < 0:
            insights.append(
                self._make_insight(
                    "Dirección de la tendencia",
                    f"{metric} disminuyó desde {self._fmt(first_value, metric)} en {first_week} hasta {self._fmt(last_value, metric)} en {last_week}.",
                    category="trend_watch",
                    severity="high" if abs(delta_pct or 0) >= 10 else "medium",
                    recommendation="Revisá los principales drivers operativos detrás de la última caída y aislá si es un fenómeno general o concentrado en pocas zonas.",
                )
            )
        else:
            insights.append(
                self._make_insight(
                    "Dirección de la tendencia",
                    f"{metric} se mantuvo estable entre {first_week} y {last_week}, alrededor de {self._fmt(last_value, metric)}.",
                    category="trend_watch",
                    severity="low",
                )
            )

        if delta_pct is not None:
            if delta_abs > 0:
                insights.append(
                    self._make_insight(
                        "Magnitud del cambio",
                        f"La mejora total en el período seleccionado fue de {self._fmt(delta_abs, metric)} ({float(delta_pct):,.2f}%).",
                        category="trend_watch",
                        severity="medium",
                    )
                )
            elif delta_abs < 0:
                insights.append(
                    self._make_insight(
                        "Magnitud del cambio",
                        f"La caída total en el período seleccionado fue de {self._fmt(abs(delta_abs), metric)} ({abs(float(delta_pct)):,.2f}%).",
                        category="trend_watch",
                        severity="high" if abs(delta_pct) >= 10 else "medium",
                    )
                )

        interpretation_map = {
            "strong": (
                "Interpretación",
                "Parece un movimiento fuerte y podría justificar una investigación operativa más profunda.",
                "high",
            ),
            "moderate": (
                "Interpretación",
                "Parece un movimiento relevante, más allá del ruido normal entre semanas.",
                "medium",
            ),
            "slight": (
                "Interpretación",
                "El cambio es claro en dirección, pero todavía es relativamente pequeño en magnitud.",
                "low",
            ),
            "stable": (
                "Interpretación",
                "La serie se ve bastante estable dentro de la ventana temporal seleccionada.",
                "low",
            ),
        }
        title, message, severity = interpretation_map[strength]
        insights.append(
            self._make_insight(
                title,
                message,
                category="trend_watch",
                severity=severity,
            )
        )

        return insights

    def _generate_comparison_insights(self, result: dict) -> list[dict]:
        latest_snapshot = result.get("latest_snapshot", [])
        metric = result.get("metric", "Metric")
        group_by = result.get("group_by", "dimension")
        latest_week = result.get("latest_week")

        if not latest_snapshot:
            return [
                self._make_insight(
                    "Comparación no disponible",
                    "No se pudo generar el insight de comparación porque no hay un snapshot reciente disponible.",
                    category="benchmarking",
                    severity="medium",
                )
            ]

        ordered = sorted(latest_snapshot, key=lambda x: float(x.get("value", 0)), reverse=True)
        top = ordered[0]
        bottom = ordered[-1]
        top_name = top.get(group_by, "Top entity")
        bottom_name = bottom.get(group_by, "Bottom entity")
        top_value = self._safe_float(top.get("value"))
        bottom_value = self._safe_float(bottom.get("value"))

        insights = [
            self._make_insight(
                "Líder vs rezagado",
                f"En {latest_week}, {top_name} lideró {metric} con {self._fmt(top_value, metric)}, mientras que {bottom_name} tuvo el valor más bajo con {self._fmt(bottom_value, metric)}.",
                category="benchmarking",
                severity="medium",
            )
        ]

        if top_value is not None and bottom_value is not None:
            gap = top_value - bottom_value
            rel_gap_pct = None if bottom_value == 0 else (gap / abs(bottom_value)) * 100
            insights.append(
                self._make_insight(
                    "Brecha de performance",
                    f"La brecha entre el mejor y el peor {group_by} fue de {self._fmt(gap, metric)}.",
                    category="benchmarking",
                    severity="high" if (rel_gap_pct or 0) >= 20 else "medium",
                    recommendation=f"Usá a {top_name} como referencia y compará las prácticas operativas contra {bottom_name}.",
                )
            )

            if rel_gap_pct is not None:
                if rel_gap_pct >= 20:
                    spread_text = f"La dispersión entre {group_by}s es amplia y sugiere diferencias operativas materiales."
                    severity = "high"
                elif rel_gap_pct >= 8:
                    spread_text = f"Hay una dispersión visible entre {group_by}s, aunque no extrema."
                    severity = "medium"
                else:
                    spread_text = f"La performance entre {group_by}s es relativamente pareja en el snapshot más reciente."
                    severity = "low"

                insights.append(
                    self._make_insight(
                        "Spread",
                        spread_text,
                        category="benchmarking",
                        severity=severity,
                    )
                )

        return insights

    def _generate_ranking_insights(self, result: dict) -> list[dict]:
        top_rows = result.get("top_n") or result.get("top_10", [])
        group_by = result.get("group_by", "dimension")
        metric = result.get("metric", "Metric")

        if not top_rows:
            return [
                self._make_insight(
                    "Ranking no disponible",
                    "No se pudo generar el insight de ranking porque la salida del ranking está vacía.",
                    category="opportunity",
                    severity="medium",
                )
            ]

        ordered = sorted(top_rows, key=lambda x: float(x.get("value", 0)), reverse=True)
        leader = ordered[0]
        trailer = ordered[-1]
        leader_name = leader.get(group_by, "Leader")
        trailer_name = trailer.get(group_by, "Bottom entity")
        leader_value = self._safe_float(leader.get("value"))
        trailer_value = self._safe_float(trailer.get("value"))

        insights = [
            self._make_insight(
                "Mejor performer",
                f"{leader_name} ocupa el primer lugar en {metric} con {self._fmt(leader_value, metric)}.",
                category="opportunity",
                severity="medium",
            ),
            self._make_insight(
                "Parte baja del ranking mostrado",
                f"Dentro del ranking mostrado, {trailer_name} está actualmente al final con {self._fmt(trailer_value, metric)}.",
                category="opportunity",
                severity="medium",
                recommendation=f"Revisá si {trailer_name} necesita un plan específico de recuperación o si la brecha de performance es estructural.",
            ),
        ]

        if len(ordered) >= 2:
            second = ordered[1]
            second_name = second.get(group_by, "Second entity")
            second_value = self._safe_float(second.get("value"))
            if leader_value is not None and second_value is not None:
                insights.append(
                    self._make_insight(
                        "Ventaja del líder",
                        f"El líder está por delante de {second_name} por {self._fmt(leader_value - second_value, metric)}.",
                        category="opportunity",
                        severity="medium",
                    )
                )

        if len(ordered) >= 3:
            values = [self._safe_float(item.get("value")) for item in ordered]
            values = [v for v in values if v is not None]
            if values and sum(values) != 0:
                top3_share = sum(values[:3]) / sum(values) * 100
                insights.append(
                    self._make_insight(
                        "Concentración del top 3",
                        f"El top 3 explica {top3_share:,.2f}% del valor total mostrado en el ranking.",
                        category="opportunity",
                        severity="medium" if top3_share >= 50 else "low",
                    )
                )

        return insights

    def _generate_distribution_insights(self, result: dict) -> list[dict]:
        metric = result.get("metric", "Metric")
        secondary_metric = result.get("secondary_metric", "Secondary metric")
        group_by = result.get("group_by", "dimension")
        matched_entities = result.get("matched_entities", [])

        if not matched_entities:
            return [
                self._make_insight(
                    "Sin oportunidades detectadas",
                    f"Ningún {group_by} combina hoy {metric} alto con {secondary_metric} bajo en el scope seleccionado.",
                    category="opportunity",
                    severity="low",
                )
            ]

        top_match = matched_entities[0]
        top_name = top_match.get(group_by, "Top opportunity")
        top_primary = self._safe_float(top_match.get("primary_value"))
        top_secondary = self._safe_float(top_match.get("secondary_value"))
        matched_count = result.get("matched_count", len(matched_entities))

        return [
            self._make_insight(
                "Cluster de oportunidad",
                f"Encontré {matched_count} {group_by}s con {metric} por encima de la mediana y {secondary_metric} por debajo de la mediana.",
                category="opportunity",
                severity="medium",
            ),
            self._make_insight(
                "Candidato más fuerte",
                f"{top_name} se destaca con {metric} en {self._fmt(top_primary, metric)} y {secondary_metric} en {self._fmt(top_secondary, secondary_metric)}.",
                category="opportunity",
                severity="high",
                recommendation=f"Investigá por qué {top_name} convierte una demanda fuerte en una ejecución más débil aguas abajo.",
            ),
        ]

    def _generate_lookup_insights(self, result: dict) -> list[dict]:
        metric = result.get("metric", "Metric")
        latest_week = result.get("latest_week")
        latest_value = result.get("latest_value")
        aggregation_method = result.get("aggregation_method")

        message = f"El último valor disponible de {metric} es {self._fmt(latest_value, metric)} en {latest_week}."
        if aggregation_method:
            message += f" Este resultado está agregado usando {aggregation_method}."

        return [
            self._make_insight(
                "Último valor",
                message,
                category="operational_readout",
                severity="low",
            )
        ]

    def _generate_anomaly_insights(self, result: dict) -> list[dict]:
        metric = result.get("metric", "Metric")
        group_by = result.get("group_by", "dimension")
        top_rows = result.get("top_n", [])

        if not top_rows:
            return [
                self._make_insight(
                    "Sin líderes de anomalía",
                    f"No se encontraron resultados rankeados de anomalías para {metric}.",
                    category="anomalies",
                    severity="low",
                )
            ]

        leader = top_rows[0]
        entity_name = leader.get(group_by, "Top entity")
        delta_pct = self._safe_float(leader.get("delta_pct"))

        return [
            self._make_insight(
                "Mayor movimiento",
                f"{entity_name} muestra el movimiento más fuerte en {metric}, con un cambio de {delta_pct:,.2f}%.",
                category="anomalies",
                severity="high" if abs(delta_pct or 0) >= 10 else "medium",
                recommendation="Validá si este movimiento refleja un cambio operativo real o un evento aislado.",
            )
        ]

    def _build_summary(self, findings: list[dict], limit: int = 5) -> list[dict]:
        severity_rank = {"high": 0, "medium": 1, "low": 2}
        ordered = sorted(
            findings,
            key=lambda item: (severity_rank.get(item.get("severity", "medium"), 1), item["title"]),
        )

        # First pass: pick the best (highest-severity) item per category
        seen_categories: set[str] = set()
        selected: list[dict] = []
        remainder: list[dict] = []
        for item in ordered:
            cat = item.get("category", "")
            if cat not in seen_categories:
                seen_categories.add(cat)
                selected.append(item)
            else:
                remainder.append(item)

        # Second pass: fill remaining slots from leftovers (still severity-ordered)
        combined = selected + remainder
        return combined[:limit]

    def _generate_anomaly_findings(self) -> list[dict]:
        if self.metrics_df is None or self.metrics_df.empty:
            return []

        findings = []
        group_cols = ["country", "city", "zone", "metric"]
        for _, group in self.metrics_df.groupby(group_cols):
            ordered = self._with_sorting(group)
            if len(ordered) < 2:
                continue

            last = ordered.iloc[-1]
            prev = ordered.iloc[-2]
            prev_value = self._safe_float(prev["value"])
            last_value = self._safe_float(last["value"])
            if prev_value in [None, 0] or last_value is None:
                continue

            pct_change = ((last_value - prev_value) / abs(prev_value)) * 100
            if abs(pct_change) < ANOMALY_MIN_PCT_CHANGE:
                continue

            metric = last["metric"]
            metric_display = self._metric_display(metric)
            zone = self._zone_display(last["zone"])
            city = last["city"]
            is_deterioration = pct_change > 0 if self._is_lower_better(metric) else pct_change < 0
            is_extreme = abs(pct_change) > ANOMALY_EXTREME_THRESHOLD

            prev_fmt = self._fmt(prev_value, metric)
            last_fmt = self._fmt(last_value, metric)

            if is_extreme:
                # For extreme swings (|Δ| > 100%), showing the % change confuses business users.
                # Use absolute change instead so the magnitude is clear without arithmetic gymnastics.
                abs_change = last_value - prev_value
                body = (
                    f"{zone} en {city}: {metric_display} pasó de {prev_fmt} ({self._week_display(prev['week'])}) "
                    f"a {last_fmt} ({self._week_display(last['week'])}). "
                    f"Cambio absoluto: {abs_change:+,.2f}."
                )
                title = f"{metric_display}: variaci\u00f3n extrema en {zone}"
                severity = "high"
                recommendation = (
                    f"Un movimiento de esta magnitud suele reflejar un problema de datos. "
                    f"Verificá la fuente antes de actuar sobre {zone}."
                )
            else:
                if not self._is_percentage_metric(metric) and prev_value < 0:
                    # Relative % change is confusing when the base is negative — show absolute change instead
                    abs_change = last_value - prev_value
                    body = (
                        f"{zone} en {city}: {metric_display} pasó de {prev_fmt} ({self._week_display(prev['week'])}) "
                        f"a {last_fmt} ({self._week_display(last['week'])}). "
                        f"Cambio absoluto: {abs_change:+,.2f}."
                    )
                else:
                    body = (
                        f"{zone} en {city} registró {pct_change:+,.2f}% en {metric_display} "
                        f"de {prev_fmt} ({self._week_display(prev['week'])}) a {last_fmt} ({self._week_display(last['week'])})."
                    )
                direction = "ca\u00edda" if pct_change < 0 else "alza"
                qualifier = "brusca" if abs(pct_change) >= ANOMALY_BRUSCA_THRESHOLD else "moderada"
                title = f"{metric_display}: {direction} {qualifier} en {zone}"
                severity = "high" if (is_deterioration and abs(pct_change) >= ANOMALY_HIGH_SEVERITY_PCT) else "medium"
                if is_deterioration:
                    recommendation = (
                        f"Priorizá {zone} para investigar los drivers operativos detr\u00e1s de esta ca\u00edda en {metric_display}."
                    )
                else:
                    recommendation = (
                        f"Analiz\u00e1 qu\u00e9 impuls\u00f3 esta mejora en {zone} - si es reproducible, escal\u00e1la a otras zonas."
                    )

            findings.append(
                self._make_insight(title, body, category="anomalies", severity=severity, recommendation=recommendation)
            )

        return findings[:8]

    def _generate_trend_findings(self) -> list[dict]:
        if self.metrics_df is None or self.metrics_df.empty:
            return []

        findings = []
        group_cols = ["country", "city", "zone", "metric"]
        for _, group in self.metrics_df.groupby(group_cols):
            ordered = self._with_sorting(group)
            if len(ordered) < 4:
                continue

            values = ordered["value"].astype(float).tolist()
            deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
            recent_deltas = deltas[-3:]
            metric = ordered.iloc[-1]["metric"]
            metric_display = self._metric_display(metric)
            if self._is_lower_better(metric):
                deteriorating = all(delta > 0 for delta in recent_deltas)
            else:
                deteriorating = all(delta < 0 for delta in recent_deltas)

            if not deteriorating:
                continue

            start_row = ordered.iloc[-4]
            end_row = ordered.iloc[-1]
            start_float = self._safe_float(start_row["value"])
            end_float = self._safe_float(end_row["value"])

            # Require a minimum total change to avoid flagging negligible drifts
            if start_float is not None and end_float is not None and start_float != 0:
                total_delta_pct = abs((end_float - start_float) / abs(start_float)) * 100
                if total_delta_pct < TREND_MIN_TOTAL_DELTA_PCT:
                    continue

            zone = self._zone_display(ordered.iloc[-1]["zone"])
            city = ordered.iloc[-1]["city"]
            start_val = self._fmt(start_float, metric)
            end_val = self._fmt(end_float, metric)

            findings.append(
                self._make_insight(
                    f"{metric_display}: deterioro persistente en {zone}",
                    (
                        f"{zone} en {city} acumula 3 semanas consecutivas de deterioro en {metric_display}: "
                        f"de {start_val} ({self._week_display(start_row['week'])}) a {end_val} ({self._week_display(end_row['week'])})."
                    ),
                    category="trend_deterioration",
                    severity="high",
                    recommendation=(
                        f"El deterioro sostenido en {metric_display} sugiere un problema estructural, no ruido puntual. "
                        f"Priorizá {zone} para an\u00e1lisis de causa ra\u00edz."
                    ),
                )
            )

        return findings[:8]

    def _generate_benchmark_findings(self) -> list[dict]:
        if self.metrics_df is None or self.metrics_df.empty:
            return []

        latest_week = self._latest_week(self.metrics_df)
        if latest_week is None:
            return []

        snapshot = self.metrics_df[self.metrics_df["week"] == latest_week].copy()
        findings = []

        for (country, zone_type, metric), group in snapshot.groupby(["country", "zone_type", "metric"]):
            if len(group) < 2:
                continue

            ordered = group.sort_values("value", ascending=False)
            top = ordered.iloc[0]
            bottom = ordered.iloc[-1]
            bottom_value = self._safe_float(bottom["value"])
            top_value = self._safe_float(top["value"])
            if bottom_value in [None, 0] or top_value is None:
                continue

            rel_gap_pct = ((top_value - bottom_value) / abs(bottom_value)) * 100
            metric_display = self._metric_display(metric)
            top_val_str = self._fmt(top_value, metric)
            bot_val_str = self._fmt(bottom_value, metric)

            gap_verb = "brecha"
            if self._is_percentage_metric(metric):
                # Use absolute pp gap to avoid inflation when denominator is tiny
                top_pct = top_value * 100 if abs(top_value) <= 1 else top_value
                bot_pct = bottom_value * 100 if abs(bottom_value) <= 1 else bottom_value
                abs_gap_pp = top_pct - bot_pct
                if abs_gap_pp < BENCHMARK_MIN_PP_GAP:
                    continue
                gap_label = f"{abs_gap_pp:,.1f} pp"
                severity = "high" if abs_gap_pp >= BENCHMARK_HIGH_SEVERITY_PP else "medium"
            elif bottom_value > 0:
                # Non-percentage, positive base: relative gap is meaningful
                if rel_gap_pct < BENCHMARK_MIN_REL_GAP_PCT:
                    continue
                gap_label = f"{rel_gap_pct:,.1f}%"
                severity = "high" if rel_gap_pct >= BENCHMARK_HIGH_SEVERITY_REL else "medium"
            else:
                # Non-percentage, negative base: relative gap is misleading — use absolute difference
                abs_diff = top_value - bottom_value
                if abs_diff < BENCHMARK_MIN_ABS_GAP:
                    continue
                gap_label = f"{abs_diff:,.2f}"
                gap_verb = "diferencia"
                severity = "high" if abs_diff >= 5 else "medium"

            top_zone = self._zone_display(top["zone"])
            bot_zone = self._zone_display(bottom["zone"])
            country_display = COUNTRY_DISPLAY_MAP.get(country, country)
            findings.append(
                self._make_insight(
                    f"{metric_display}: {gap_verb} de {gap_label} en {zone_type}",
                    (
                        f"En {country_display} / {zone_type}, {top_zone} ({top_val_str}) supera a {bot_zone} ({bot_val_str}) "
                        f"en {metric_display} ({self._week_display(latest_week)}) - {gap_verb} de {gap_label}."
                    ),
                    category="benchmarking",
                    severity=severity,
                    recommendation=(
                        f"Investigá qu\u00e9 hace diferente a {top_zone} en {metric_display}. "
                        f"Sus pr\u00e1cticas podr\u00edan replicarse en {bot_zone} y otras zonas del segmento."
                    ),
                )
            )

        return findings[:8]

    def _generate_correlation_findings(self) -> list[dict]:
        if self.metrics_df is None or self.metrics_df.empty:
            return []

        latest_week = self._latest_week(self.metrics_df)
        if latest_week is None:
            return []

        snapshot = self.metrics_df[self.metrics_df["week"] == latest_week].copy()
        pivot = snapshot.pivot_table(index="zone", columns="metric", values="value", aggfunc="mean")
        candidate_pairs = [
            ("Lead Penetration", "Perfect Orders"),
            ("Lead Penetration", "Orders"),
            ("Pro Adoption", "Perfect Orders"),
            ("Pro Adoption", "MLTV Top Verticals Adoption"),
            ("Non-Pro PTC > OP", "Perfect Orders"),
            ("Restaurants SS > ATC CVR", "Orders"),
            ("% Restaurants Sessions With Optimal Assortment", "Restaurants SS > ATC CVR"),
            ("Turbo Adoption", "Orders"),
        ]

        findings = []
        for left, right in candidate_pairs:
            if left not in pivot.columns or right not in pivot.columns:
                continue
            pair_df = pivot[[left, right]].dropna()
            if len(pair_df) < 3:
                continue

            corr = pair_df[left].corr(pair_df[right])
            if corr is None or abs(corr) < 0.5:
                continue

            direction = "positiva" if corr > 0 else "negativa"
            left_display = self._metric_display(left)
            right_display = self._metric_display(right)
            findings.append(
                self._make_insight(
                    f"Correlaci\u00f3n {direction}: {left_display} y {right_display}",
                    (
                        f"Hay una correlaci\u00f3n {direction} ({corr:,.2f}) entre {left_display} y {right_display} "
                        f"entre zonas ({self._week_display(latest_week)})."
                    ),
                    category="correlations",
                    severity="medium",
                    recommendation=(
                        f"Us\u00e1 {left_display} como se\u00f1al temprana al priorizar una revisi\u00f3n m\u00e1s profunda de {right_display}."
                    ),
                )
            )

        return findings[:6]

    def _generate_opportunity_findings(self) -> list[dict]:
        if self.metrics_df is None or self.metrics_df.empty:
            return []

        latest_week = self._latest_week(self.metrics_df)
        if latest_week is None:
            return []

        snapshot = self.metrics_df[self.metrics_df["week"] == latest_week].copy()
        pivot = snapshot.pivot_table(index=["country", "city", "zone"], columns="metric", values="value", aggfunc="mean")
        if "Lead Penetration" not in pivot.columns or "Perfect Orders" not in pivot.columns:
            return []

        pivot = pivot.dropna(subset=["Lead Penetration", "Perfect Orders"]).reset_index()
        if pivot.empty:
            return []

        lp_threshold = pivot["Lead Penetration"].median()
        po_threshold = pivot["Perfect Orders"].median()
        matches = pivot[
            (pivot["Lead Penetration"] >= lp_threshold)
            & (pivot["Perfect Orders"] < po_threshold)
        ].sort_values(["Lead Penetration", "Perfect Orders"], ascending=[False, True])

        lp_med_str = self._fmt(lp_threshold, "Lead Penetration")
        po_med_str = self._fmt(po_threshold, "Perfect Orders")

        findings = []
        for _, row in matches.head(5).iterrows():
            zone_name = self._zone_display(row["zone"])
            lp_val = self._fmt(row["Lead Penetration"], "Lead Penetration")
            po_val = self._fmt(row["Perfect Orders"], "Perfect Orders")
            findings.append(
                self._make_insight(
                    f"Demanda lista, ejecuci\u00f3n pendiente: {zone_name}",
                    (
                        f"{zone_name} en {row['city']} tiene Penetraci\u00f3n de Leads en {lp_val} "
                        f"(mediana: {lp_med_str}) pero \u00d3rdenes Perfectas en {po_val} "
                        f"(mediana: {po_med_str}) ({self._week_display(latest_week)})."
                    ),
                    category="opportunities",
                    severity="high",
                    recommendation=(
                        f"Alta cobertura de tiendas pero calidad de \u00f3rdenes bajo la mediana - "
                        f"revis\u00e1 tiempo de entrega, cancelaciones y defectos en {zone_name}."
                    ),
                )
            )

        return findings

    def _generate_cross_country_benchmark_findings(self) -> list[dict]:
        """Compara el mismo metric entre países, agregando por country dentro de cada zone_type."""
        if self.metrics_df is None or self.metrics_df.empty:
            return []

        latest_week = self._latest_week(self.metrics_df)
        if latest_week is None:
            return []

        snapshot = self.metrics_df[self.metrics_df["week"] == latest_week].copy()
        findings = []

        for (zone_type, metric), group in snapshot.groupby(["zone_type", "metric"]):
            country_agg = (
                group.groupby("country")["value"]
                .mean()
                .dropna()
                .reset_index()
                .rename(columns={"value": "value"})
            )
            if len(country_agg) < 2:
                continue

            country_agg = country_agg.sort_values("value", ascending=False)
            top = country_agg.iloc[0]
            bottom = country_agg.iloc[-1]
            top_value = self._safe_float(top["value"])
            bottom_value = self._safe_float(bottom["value"])
            if top_value is None or bottom_value in [None, 0]:
                continue

            metric_display = self._metric_display(metric)
            top_val_str = self._fmt(top_value, metric)
            bot_val_str = self._fmt(bottom_value, metric)
            top_country = COUNTRY_DISPLAY_MAP.get(top["country"], top["country"])
            bot_country = COUNTRY_DISPLAY_MAP.get(bottom["country"], bottom["country"])

            gap_verb = "brecha"
            if self._is_percentage_metric(metric):
                top_pct = top_value * 100 if abs(top_value) <= 1 else top_value
                bot_pct = bottom_value * 100 if abs(bottom_value) <= 1 else bottom_value
                abs_gap_pp = top_pct - bot_pct
                if abs_gap_pp < BENCHMARK_MIN_PP_GAP:
                    continue
                gap_label = f"{abs_gap_pp:,.1f} pp"
                severity = "high" if abs_gap_pp >= BENCHMARK_HIGH_SEVERITY_PP else "medium"
            elif bottom_value > 0:
                rel_gap_pct = ((top_value - bottom_value) / abs(bottom_value)) * 100
                if rel_gap_pct < BENCHMARK_MIN_REL_GAP_PCT:
                    continue
                gap_label = f"{rel_gap_pct:,.1f}%"
                severity = "high" if rel_gap_pct >= BENCHMARK_HIGH_SEVERITY_REL else "medium"
            else:
                abs_diff = top_value - bottom_value
                if abs_diff < BENCHMARK_MIN_ABS_GAP:
                    continue
                gap_label = f"{abs_diff:,.2f}"
                gap_verb = "diferencia"
                severity = "high" if abs_diff >= 5 else "medium"

            findings.append(
                self._make_insight(
                    f"{metric_display}: {gap_verb} de {gap_label} entre pa\u00edses ({zone_type})",
                    (
                        f"{top_country} ({top_val_str}) supera a {bot_country} ({bot_val_str}) "
                        f"en {metric_display} para zonas {zone_type} ({self._week_display(latest_week)}) "
                        f"- {gap_verb} de {gap_label}."
                    ),
                    category="cross_country_benchmarking",
                    severity=severity,
                    recommendation=(
                        f"Investigá qu\u00e9 pr\u00e1cticas de {top_country} en zonas {zone_type} "
                        f"podr\u00edan replicarse en {bot_country} para mejorar {metric_display}."
                    ),
                )
            )

        severity_rank = {"high": 0, "medium": 1, "low": 2}
        findings.sort(key=lambda x: severity_rank.get(x.get("severity", "medium"), 1))
        return findings[:8]

    def generate_executive_report(self) -> dict:
        sections = {
            "anomalies": self._generate_anomaly_findings(),
            "trend_deterioration": self._generate_trend_findings(),
            "benchmarking": self._generate_benchmark_findings(),
            "cross_country_benchmarking": self._generate_cross_country_benchmark_findings(),
            "correlations": self._generate_correlation_findings(),
            "opportunities": self._generate_opportunity_findings(),
        }

        all_findings = [item for items in sections.values() for item in items]
        summary = self._build_summary(all_findings, limit=5)

        metadata: dict = {}
        if self.metrics_df is not None and not self.metrics_df.empty:
            metadata["countries"] = int(self.metrics_df["country"].nunique())
            metadata["zones"] = int(self.metrics_df["zone"].nunique())
            metadata["metrics"] = int(self.metrics_df["metric"].nunique())
            metadata["weeks"] = int(self.metrics_df["week"].nunique())

        return {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "summary": summary,
            "sections": sections,
            "counts": {section: len(items) for section, items in sections.items()},
            "metadata": metadata,
        }

    def generate(self, analytical_result: dict) -> list[dict]:
        status = analytical_result.get("status")
        analysis_type = analytical_result.get("analysis_type")

        if status != "success":
            message = analytical_result.get("message", "No hay insight analítico disponible.")
            return [
                self._make_insight(
                    "Sin datos",
                    message,
                    category="operational_readout",
                    severity="medium",
                )
            ]

        if analysis_type == "trend":
            return self._generate_trend_insights(analytical_result)

        if analysis_type == "comparison":
            return self._generate_comparison_insights(analytical_result)

        if analysis_type == "ranking":
            return self._generate_ranking_insights(analytical_result)

        if analysis_type == "distribution":
            return self._generate_distribution_insights(analytical_result)

        if analysis_type == "value_lookup":
            return self._generate_lookup_insights(analytical_result)

        if analysis_type == "anomaly":
            return self._generate_anomaly_insights(analytical_result)

        return [
            self._make_insight(
                "Sin insights",
                "Todavía no se generaron insights automáticos para este tipo de análisis.",
                category="operational_readout",
                severity="low",
            )
        ]
