import pandas as pd
import unicodedata


class QueryEngine:
    """
    Motor analitico deterministico.
    Recibe un intent estructurado y ejecuta consultas sobre dataframes preparados.
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

    def __init__(self, metrics_df: pd.DataFrame, orders_df: pd.DataFrame):
        self.metrics_df = metrics_df.copy()
        self.orders_df = orders_df.copy()

    def _normalize_text(self, value) -> str:
        if value is None:
            return ""

        value = str(value).strip().lower()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(char for char in value if not unicodedata.combining(char))
        return value

    def _sort_weeks(self, df: pd.DataFrame) -> pd.DataFrame:
        if "week" not in df.columns or df.empty:
            return df

        ordered = df.copy()
        ordered["week_order"] = ordered["week"].map(self.WEEK_ORDER)
        ordered = ordered.sort_values("week_order").drop(columns=["week_order"])
        return ordered

    def _select_dataset(self, metric_name: str | None) -> tuple[pd.DataFrame, str]:
        if self._normalize_text(metric_name) == "orders":
            return self.orders_df.copy(), "orders_long"
        return self.metrics_df.copy(), "metrics_long"

    def _get_aggregation_method(
        self,
        metric_name: str | None,
        dataset_used: str,
        parsed_intent: dict | None = None,
    ) -> str:
        if parsed_intent and parsed_intent.get("aggregation") in {"mean", "sum"}:
            return parsed_intent["aggregation"]

        normalized_metric = self._normalize_text(metric_name)
        if normalized_metric == "orders" or dataset_used == "orders_long":
            return "sum"

        return "mean"

    def _aggregate(
        self,
        df: pd.DataFrame,
        group_cols: list[str],
        metric_name: str | None,
        dataset_used: str,
        parsed_intent: dict | None = None,
    ) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        agg_method = self._get_aggregation_method(metric_name, dataset_used, parsed_intent)
        if agg_method == "sum":
            return df.groupby(group_cols, as_index=False)["value"].sum()

        return df.groupby(group_cols, as_index=False)["value"].mean()

    def _apply_filters(self, df: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
        if not filters:
            return df

        filtered = df.copy()
        for key, value in filters.items():
            if value is None:
                continue
            if key in filtered.columns:
                normalized_value = self._normalize_text(value)
                filtered = filtered[filtered[key].apply(self._normalize_text) == normalized_value]

        return filtered

    def _apply_metric_filter(self, df: pd.DataFrame, metric: str | None) -> pd.DataFrame:
        if metric is None or "metric" not in df.columns:
            return df

        normalized_metric = self._normalize_text(metric)
        return df[df["metric"].apply(self._normalize_text) == normalized_metric]

    def _apply_time_scope(self, df: pd.DataFrame, time_scope: list[str] | None) -> pd.DataFrame:
        if not time_scope or "week" not in df.columns:
            return df

        return df[df["week"].isin(time_scope)]

    def _apply_common_filters(
        self,
        df: pd.DataFrame,
        parsed_intent: dict,
        metric_name: str | None = None,
    ) -> pd.DataFrame:
        filtered = df.copy()
        if metric_name is not None:
            filtered = self._apply_metric_filter(filtered, metric_name)
        filtered = self._apply_filters(filtered, parsed_intent.get("filters", {}))
        filtered = self._apply_time_scope(filtered, parsed_intent.get("time_scope", []))
        return filtered

    def _safe_round(self, value):
        if pd.isna(value):
            return None
        return round(float(value), 4)

    def _resolve_rank_limit(self, parsed_intent: dict, default: int = 10) -> int:
        try:
            return max(1, int(parsed_intent.get("rank_limit") or default))
        except Exception:
            return default

    def _is_lower_better(self, metric_name: str | None) -> bool:
        return metric_name in self.LOWER_IS_BETTER

    def _metric_business_direction(self, metric_name: str | None, delta_pct: float | None) -> str:
        if delta_pct is None or delta_pct == 0:
            return "stable"
        if self._is_lower_better(metric_name):
            return "favorable" if delta_pct < 0 else "unfavorable"
        return "favorable" if delta_pct > 0 else "unfavorable"

    def _build_explanatory_hints(
        self,
        group_by: str,
        entity: str,
        parsed_intent: dict,
        first_week: str,
        last_week: str,
        limit: int = 3,
    ) -> list[dict]:
        if group_by not in self.metrics_df.columns:
            return []

        filters = (parsed_intent.get("filters") or {}).copy()
        filters[group_by] = entity

        scoped_df = self._apply_filters(self.metrics_df, filters)
        scoped_df = scoped_df[scoped_df["week"].isin([first_week, last_week])]
        if scoped_df.empty:
            return []

        hints = []
        for metric_name, metric_df in scoped_df.groupby("metric"):
            ordered = self._sort_weeks(metric_df)
            if ordered["week"].nunique() < 2:
                continue

            first_row = ordered[ordered["week"] == first_week]
            last_row = ordered[ordered["week"] == last_week]
            if first_row.empty or last_row.empty:
                continue

            first_value = self._safe_round(first_row.iloc[0]["value"])
            last_value = self._safe_round(last_row.iloc[0]["value"])
            if first_value is None or last_value is None or first_value == 0:
                continue

            delta_abs = last_value - first_value
            delta_pct = (delta_abs / abs(first_value)) * 100
            business_direction = self._metric_business_direction(metric_name, delta_pct)

            if business_direction != "favorable" or abs(delta_pct) < 3:
                continue

            hints.append(
                {
                    "metric": metric_name,
                    "first_week": first_week,
                    "last_week": last_week,
                    "first_value": first_value,
                    "last_value": last_value,
                    "delta_pct": self._safe_round(delta_pct),
                    "delta_abs": self._safe_round(delta_abs),
                    "business_direction": business_direction,
                }
            )

        hints = sorted(hints, key=lambda item: abs(item.get("delta_pct") or 0), reverse=True)
        current_metric = self._normalize_text(parsed_intent.get("metric"))
        filtered_hints = [item for item in hints if self._normalize_text(item["metric"]) != current_metric]
        return filtered_hints[:limit]

    def _no_data_response(self, analysis_type: str, dataset_used: str, parsed_intent: dict) -> dict:
        return {
            "status": "no_data",
            "dataset_used": dataset_used,
            "analysis_type": analysis_type,
            "metric": parsed_intent.get("metric"),
            "secondary_metric": parsed_intent.get("secondary_metric"),
            "filters": parsed_intent.get("filters"),
            "group_by": parsed_intent.get("group_by"),
            "comparison": parsed_intent.get("comparison"),
            "time_scope": parsed_intent.get("time_scope", []),
            "aggregation_method": self._get_aggregation_method(
                parsed_intent.get("metric"),
                dataset_used,
                parsed_intent,
            ),
            "result_table": [],
            "message": "No data found for the requested metric, filters, and time scope.",
        }

    def _extract_comparison_entities(self, comparison_text: str | None) -> list[str]:
        if not comparison_text:
            return []

        lowered = comparison_text.lower()
        if " vs " not in lowered:
            return []

        parts = [part.strip() for part in re_split_vs(comparison_text) if part.strip()]
        if len(parts) != 2:
            return []

        return parts

    def _metric_lookup(self, df: pd.DataFrame, parsed_intent: dict, dataset_used: str) -> dict:
        if df.empty:
            return self._no_data_response("value_lookup", dataset_used, parsed_intent)

        summary = self._aggregate(
            df=df,
            group_cols=["week"],
            metric_name=parsed_intent.get("metric"),
            dataset_used=dataset_used,
            parsed_intent=parsed_intent,
        )
        summary = self._sort_weeks(summary)

        latest_row = summary.iloc[-1]
        aggregation_method = self._get_aggregation_method(
            parsed_intent.get("metric"),
            dataset_used,
            parsed_intent,
        )

        return {
            "status": "success",
            "dataset_used": dataset_used,
            "analysis_type": "value_lookup",
            "metric": parsed_intent.get("metric"),
            "filters": parsed_intent.get("filters"),
            "weeks_considered": summary["week"].tolist(),
            "aggregation_method": aggregation_method,
            "latest_week": latest_row["week"],
            "latest_value": self._safe_round(latest_row["value"]),
            "result_table": summary.to_dict(orient="records"),
        }

    def _trend_analysis(self, df: pd.DataFrame, parsed_intent: dict, dataset_used: str) -> dict:
        if df.empty:
            return self._no_data_response("trend", dataset_used, parsed_intent)

        trend_df = self._aggregate(
            df=df,
            group_cols=["week"],
            metric_name=parsed_intent.get("metric"),
            dataset_used=dataset_used,
            parsed_intent=parsed_intent,
        )
        trend_df = self._sort_weeks(trend_df)

        first_value = trend_df.iloc[0]["value"]
        last_value = trend_df.iloc[-1]["value"]
        delta_abs = last_value - first_value
        delta_pct = None if first_value == 0 else (delta_abs / first_value) * 100

        return {
            "status": "success",
            "dataset_used": dataset_used,
            "analysis_type": "trend",
            "metric": parsed_intent.get("metric"),
            "filters": parsed_intent.get("filters"),
            "weeks_considered": trend_df["week"].tolist(),
            "aggregation_method": self._get_aggregation_method(
                parsed_intent.get("metric"),
                dataset_used,
                parsed_intent,
            ),
            "first_week": trend_df.iloc[0]["week"],
            "last_week": trend_df.iloc[-1]["week"],
            "first_value": self._safe_round(first_value),
            "last_value": self._safe_round(last_value),
            "delta_abs": self._safe_round(delta_abs),
            "delta_pct": self._safe_round(delta_pct),
            "result_table": trend_df.to_dict(orient="records"),
        }

    def _comparison_analysis(self, df: pd.DataFrame, parsed_intent: dict, dataset_used: str) -> dict:
        if df.empty:
            return self._no_data_response("comparison", dataset_used, parsed_intent)

        group_by = parsed_intent.get("group_by") or "city"
        if group_by not in df.columns:
            return {
                "status": "error",
                "dataset_used": dataset_used,
                "analysis_type": "comparison",
                "metric": parsed_intent.get("metric"),
                "filters": parsed_intent.get("filters"),
                "group_by": group_by,
                "comparison": parsed_intent.get("comparison"),
                "result_table": [],
                "message": f"Invalid group_by: {group_by}",
            }

        result_df = df.copy()
        comparison_entities = self._extract_comparison_entities(parsed_intent.get("comparison"))
        if comparison_entities:
            normalized_entities = {self._normalize_text(x) for x in comparison_entities}
            result_df = result_df[result_df[group_by].apply(self._normalize_text).isin(normalized_entities)]

        if result_df.empty:
            return self._no_data_response("comparison", dataset_used, parsed_intent)

        comparison_df = self._aggregate(
            df=result_df,
            group_cols=[group_by, "week"],
            metric_name=parsed_intent.get("metric"),
            dataset_used=dataset_used,
            parsed_intent=parsed_intent,
        )
        comparison_df["week_order"] = comparison_df["week"].map(self.WEEK_ORDER)
        comparison_df = comparison_df.sort_values([group_by, "week_order"]).drop(columns=["week_order"])

        latest_week = max(comparison_df["week"].unique(), key=lambda w: self.WEEK_ORDER.get(w, -1))
        latest_snapshot = comparison_df[comparison_df["week"] == latest_week].sort_values("value", ascending=False)

        return {
            "status": "success",
            "dataset_used": dataset_used,
            "analysis_type": "comparison",
            "metric": parsed_intent.get("metric"),
            "filters": parsed_intent.get("filters"),
            "group_by": group_by,
            "comparison": parsed_intent.get("comparison"),
            "aggregation_method": self._get_aggregation_method(
                parsed_intent.get("metric"),
                dataset_used,
                parsed_intent,
            ),
            "latest_week": latest_week,
            "latest_snapshot": latest_snapshot.to_dict(orient="records"),
            "result_table": comparison_df.to_dict(orient="records"),
        }

    def _ranking_analysis(self, df: pd.DataFrame, parsed_intent: dict, dataset_used: str) -> dict:
        if df.empty:
            return self._no_data_response("ranking", dataset_used, parsed_intent)

        group_by = parsed_intent.get("group_by") or "zone"
        if group_by not in df.columns:
            return {
                "status": "error",
                "dataset_used": dataset_used,
                "analysis_type": "ranking",
                "metric": parsed_intent.get("metric"),
                "filters": parsed_intent.get("filters"),
                "group_by": group_by,
                "result_table": [],
                "message": f"Invalid group_by: {group_by}",
            }

        ranking_df = self._aggregate(
            df=df,
            group_cols=[group_by],
            metric_name=parsed_intent.get("metric"),
            dataset_used=dataset_used,
            parsed_intent=parsed_intent,
        ).sort_values("value", ascending=False)
        ranking_df["rank"] = range(1, len(ranking_df) + 1)

        rank_limit = self._resolve_rank_limit(parsed_intent)
        return {
            "status": "success",
            "dataset_used": dataset_used,
            "analysis_type": "ranking",
            "metric": parsed_intent.get("metric"),
            "filters": parsed_intent.get("filters"),
            "group_by": group_by,
            "aggregation_method": self._get_aggregation_method(
                parsed_intent.get("metric"),
                dataset_used,
                parsed_intent,
            ),
            "rank_limit": rank_limit,
            "top_n": ranking_df.head(rank_limit).to_dict(orient="records"),
            "top_10": ranking_df.head(10).to_dict(orient="records"),
            "result_table": ranking_df.to_dict(orient="records"),
        }

    def _distribution_analysis(self, parsed_intent: dict) -> dict:
        group_by = parsed_intent.get("group_by") or "zone"
        primary_metric = parsed_intent.get("metric")
        secondary_metric = parsed_intent.get("secondary_metric")

        if not primary_metric or not secondary_metric:
            return {
                "status": "error",
                "dataset_used": "metrics_long",
                "analysis_type": "distribution",
                "metric": primary_metric,
                "secondary_metric": secondary_metric,
                "filters": parsed_intent.get("filters"),
                "group_by": group_by,
                "result_table": [],
                "message": "Distribution analysis requires both a primary and a secondary metric.",
            }

        primary_source, _ = self._select_dataset(primary_metric)
        if group_by not in primary_source.columns:
            return {
                "status": "error",
                "dataset_used": "metrics_long",
                "analysis_type": "distribution",
                "metric": primary_metric,
                "secondary_metric": secondary_metric,
                "filters": parsed_intent.get("filters"),
                "group_by": group_by,
                "result_table": [],
                "message": f"Invalid group_by: {group_by}",
            }
        secondary_source, _ = self._select_dataset(secondary_metric)
        primary_df = self._apply_common_filters(primary_source, parsed_intent, primary_metric)
        secondary_df = self._apply_common_filters(secondary_source, parsed_intent, secondary_metric)
        if primary_df.empty or secondary_df.empty:
            return self._no_data_response("distribution", "metrics_long", parsed_intent)

        # For cross-sectional screening, use the latest available week in scope rather than
        # averaging across multiple weeks. This makes "high vs low" answers easier to defend.
        primary_latest_week = max(primary_df["week"].unique(), key=lambda w: self.WEEK_ORDER.get(w, -1))
        secondary_latest_week = max(secondary_df["week"].unique(), key=lambda w: self.WEEK_ORDER.get(w, -1))
        primary_df = primary_df[primary_df["week"] == primary_latest_week].copy()
        secondary_df = secondary_df[secondary_df["week"] == secondary_latest_week].copy()

        primary_agg = self._aggregate(
            df=primary_df,
            group_cols=[group_by],
            metric_name=primary_metric,
            dataset_used="metrics_long",
            parsed_intent=parsed_intent,
        ).rename(columns={"value": "primary_value"})
        secondary_agg = self._aggregate(
            df=secondary_df,
            group_cols=[group_by],
            metric_name=secondary_metric,
            dataset_used="metrics_long",
            parsed_intent=parsed_intent,
        ).rename(columns={"value": "secondary_value"})

        merged = primary_agg.merge(secondary_agg, on=group_by, how="inner")
        if merged.empty:
            return self._no_data_response("distribution", "metrics_long", parsed_intent)

        primary_threshold = float(merged["primary_value"].quantile(0.75))
        secondary_threshold = float(merged["secondary_value"].quantile(0.25))

        matched_df = merged[
            (merged["primary_value"] >= primary_threshold)
            & (merged["secondary_value"] <= secondary_threshold)
        ].copy()
        matched_df = matched_df.sort_values(["primary_value", "secondary_value"], ascending=[False, True])

        return {
            "status": "success",
            "dataset_used": "metrics_long",
            "analysis_type": "distribution",
            "metric": primary_metric,
            "secondary_metric": secondary_metric,
            "filters": parsed_intent.get("filters"),
            "group_by": group_by,
            "aggregation_method": self._get_aggregation_method(
                primary_metric,
                "metrics_long",
                parsed_intent,
            ),
            "latest_week": primary_latest_week,
            "primary_threshold": self._safe_round(primary_threshold),
            "secondary_threshold": self._safe_round(secondary_threshold),
            "matched_entities": matched_df.to_dict(orient="records"),
            "matched_count": int(len(matched_df)),
            "result_table": merged.sort_values("primary_value", ascending=False).to_dict(orient="records"),
        }

    def _anomaly_analysis(self, df: pd.DataFrame, parsed_intent: dict, dataset_used: str) -> dict:
        if df.empty:
            return self._no_data_response("anomaly", dataset_used, parsed_intent)

        group_by = parsed_intent.get("group_by") or "zone"
        if group_by not in df.columns:
            return {
                "status": "error",
                "dataset_used": dataset_used,
                "analysis_type": "anomaly",
                "metric": parsed_intent.get("metric"),
                "filters": parsed_intent.get("filters"),
                "group_by": group_by,
                "result_table": [],
                "message": f"Invalid group_by: {group_by}",
            }

        normalized_metric = self._normalize_text(parsed_intent.get("metric"))
        if normalized_metric == "orders":
            preferred_direction = "increase"
        elif self._is_lower_better(parsed_intent.get("metric")):
            preferred_direction = "decrease"
        else:
            preferred_direction = "decrease"

        rows = []
        for entity, entity_df in df.groupby(group_by):
            ordered = self._sort_weeks(
                self._aggregate(
                    df=entity_df,
                    group_cols=[group_by, "week"],
                    metric_name=parsed_intent.get("metric"),
                    dataset_used=dataset_used,
                    parsed_intent=parsed_intent,
                )
            )
            if len(ordered) < 2:
                continue

            first_row = ordered.iloc[0]
            last_row = ordered.iloc[-1]
            first_value = self._safe_round(first_row["value"])
            last_value = self._safe_round(last_row["value"])
            if first_value is None or last_value is None or first_value == 0:
                continue

            delta_abs = last_value - first_value
            delta_pct = (delta_abs / abs(first_value)) * 100

            if normalized_metric == "orders":
                anomaly_score = delta_pct
            elif self._is_lower_better(parsed_intent.get("metric")):
                anomaly_score = delta_pct
            else:
                anomaly_score = -delta_pct

            if delta_pct > 0:
                raw_direction = "increase"
            elif delta_pct < 0:
                raw_direction = "decrease"
            else:
                raw_direction = "flat"

            if raw_direction == "flat":
                business_direction = "stable"
            elif self._is_lower_better(parsed_intent.get("metric")):
                business_direction = "unfavorable" if raw_direction == "increase" else "favorable"
            else:
                business_direction = "favorable" if raw_direction == "increase" else "unfavorable"

            abs_delta_pct = abs(delta_pct)
            if abs_delta_pct >= 20:
                severity = "high"
            elif abs_delta_pct >= 10:
                severity = "medium"
            else:
                severity = "low"

            rows.append(
                {
                    group_by: entity,
                    "first_week": first_row["week"],
                    "last_week": last_row["week"],
                    "first_value": first_value,
                    "last_value": last_value,
                    "delta_abs": self._safe_round(delta_abs),
                    "delta_pct": self._safe_round(delta_pct),
                    "anomaly_score": self._safe_round(anomaly_score),
                    "raw_direction": raw_direction,
                    "business_direction": business_direction,
                    "severity": severity,
                }
            )

        if not rows:
            return self._no_data_response("anomaly", dataset_used, parsed_intent)

        anomaly_df = pd.DataFrame(rows).sort_values("anomaly_score", ascending=False)
        rank_limit = self._resolve_rank_limit(parsed_intent, default=5)
        top_n = anomaly_df.head(rank_limit)
        peer_context = None
        if len(top_n) >= 2:
            peer_context = {
                "second_entity": top_n.iloc[1][group_by],
                "second_delta_pct": self._safe_round(top_n.iloc[1]["delta_pct"]),
            }

        explanatory_hints = []
        if not top_n.empty:
            leader = top_n.iloc[0]
            explanatory_hints = self._build_explanatory_hints(
                group_by=group_by,
                entity=leader[group_by],
                parsed_intent=parsed_intent,
                first_week=leader["first_week"],
                last_week=leader["last_week"],
            )

        return {
            "status": "success",
            "dataset_used": dataset_used,
            "analysis_type": "anomaly",
            "metric": parsed_intent.get("metric"),
            "filters": parsed_intent.get("filters"),
            "group_by": group_by,
            "aggregation_method": self._get_aggregation_method(
                parsed_intent.get("metric"),
                dataset_used,
                parsed_intent,
            ),
            "preferred_direction": preferred_direction,
            "rank_limit": rank_limit,
            "top_n": top_n.to_dict(orient="records"),
            "peer_context": peer_context,
            "explanatory_hints": explanatory_hints,
            "result_table": anomaly_df.to_dict(orient="records"),
        }

    def _anomaly_analysis_best_metric(self, parsed_intent: dict) -> dict:
        """Escanea todas las métricas y devuelve la anomalía más preocupante."""
        filters = parsed_intent.get("filters", {})
        filtered_df = self._apply_filters(self.metrics_df, filters)
        available_metrics = filtered_df["metric"].dropna().unique().tolist()

        best_result = None
        best_score = -1.0

        for metric_name in available_metrics:
            synthetic_intent = {**parsed_intent, "metric": metric_name}
            metric_df = self._apply_metric_filter(filtered_df, metric_name)
            result = self._anomaly_analysis(metric_df, synthetic_intent, "metrics_long")
            if result.get("status") != "success":
                continue
            top_n = result.get("top_n", [])
            if not top_n:
                continue
            top = top_n[0]
            if top.get("business_direction") != "unfavorable":
                continue
            score = abs(top.get("delta_pct") or 0)
            if score > best_score:
                best_score = score
                best_result = result

        if best_result:
            return best_result
        return self._no_data_response("anomaly", "metrics_long", parsed_intent)

    def run(self, parsed_intent: dict) -> dict:
        metric = parsed_intent.get("metric")
        intent = parsed_intent.get("intent")

        if intent == "distribution":
            return self._distribution_analysis(parsed_intent)

        base_df, dataset_used = self._select_dataset(metric)
        base_df = self._apply_metric_filter(base_df, metric)
        base_df = self._apply_filters(base_df, parsed_intent.get("filters", {}))
        base_df = self._apply_time_scope(base_df, parsed_intent.get("time_scope", []))

        if intent == "metric_lookup":
            return self._metric_lookup(base_df, parsed_intent, dataset_used)

        if intent == "trend_analysis":
            return self._trend_analysis(base_df, parsed_intent, dataset_used)

        if intent == "comparison":
            return self._comparison_analysis(base_df, parsed_intent, dataset_used)

        if intent == "ranking":
            return self._ranking_analysis(base_df, parsed_intent, dataset_used)

        if intent == "anomaly_check":
            # Anomaly needs ≥2 weeks to compute a delta. If time_scope collapsed
            # to a single week (e.g. user said "esta semana"), rebuild with a
            # wider window so the comparison is still meaningful.
            if base_df["week"].nunique() < 2 if "week" in base_df.columns and not base_df.empty else False:
                wider_df, _ = self._select_dataset(metric)
                wider_df = self._apply_metric_filter(wider_df, metric)
                wider_df = self._apply_filters(wider_df, parsed_intent.get("filters", {}))
                base_df = wider_df
            if not metric:
                return self._anomaly_analysis_best_metric(parsed_intent)
            return self._anomaly_analysis(base_df, parsed_intent, dataset_used)

        if intent == "follow_up":
            if parsed_intent.get("group_by"):
                return self._comparison_analysis(base_df, parsed_intent, dataset_used)
            return self._metric_lookup(base_df, parsed_intent, dataset_used)

        return {
            "status": "not_implemented",
            "dataset_used": dataset_used,
            "analysis_type": parsed_intent.get("analysis_type", "unknown"),
            "metric": parsed_intent.get("metric"),
            "secondary_metric": parsed_intent.get("secondary_metric"),
            "filters": parsed_intent.get("filters"),
            "group_by": parsed_intent.get("group_by"),
            "comparison": parsed_intent.get("comparison"),
            "time_scope": parsed_intent.get("time_scope", []),
            "result_table": [],
            "message": f"Intent '{intent}' is not implemented yet.",
        }


def re_split_vs(text: str) -> list[str]:
    lowered = text.lower()
    idx = lowered.find(" vs ")
    if idx == -1:
        return [text]
    left = text[:idx]
    right = text[idx + 4 :]
    return [left, right]
