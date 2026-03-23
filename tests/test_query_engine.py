import pandas as pd

from query_engine import QueryEngine


def build_mock_metrics_df():
    return pd.DataFrame(
        {
            "country": ["CO"] * 12 + ["PE"] * 12,
            "city": ["Bogota"] * 12 + ["Lima"] * 12,
            "zone": (
                ["Zone A"] * 6
                + ["Zone B"] * 6
                + ["Zone C"] * 6
                + ["Zone D"] * 6
            ),
            "zone_type": (
                ["Dense"] * 12
                + ["Dense"] * 12
            ),
            "zone_prioritization": ["High"] * 24,
            "metric": (
                ["Perfect Orders"] * 3
                + ["Lead Penetration"] * 3
                + ["Perfect Orders"] * 3
                + ["Lead Penetration"] * 3
                + ["Perfect Orders"] * 3
                + ["Lead Penetration"] * 3
                + ["Perfect Orders"] * 3
                + ["Lead Penetration"] * 3
            ),
            "week_raw": (
                ["L2W_ROLL", "L1W_ROLL", "L0W_ROLL"] * 8
            ),
            "value": [
                0.90, 0.95, 1.00,
                0.70, 0.74, 0.78,
                0.82, 0.84, 0.86,
                0.88, 0.90, 0.92,
                0.78, 0.80, 0.82,
                0.72, 0.74, 0.76,
                0.86, 0.88, 0.89,
                0.60, 0.62, 0.64,
            ],
            "week": (["L2W", "L1W", "L0W"] * 8),
            "dataset": ["metrics"] * 24,
        }
    )


def build_mock_orders_df():
    return pd.DataFrame(
        {
            "country": ["CO", "CO", "CO", "CO", "CO", "CO"],
            "city": ["Bogota", "Bogota", "Bogota", "Bogota", "Bogota", "Bogota"],
            "zone": ["Zone A", "Zone A", "Zone A", "Zone B", "Zone B", "Zone B"],
            "metric": ["Orders", "Orders", "Orders", "Orders", "Orders", "Orders"],
            "week_raw": ["L2W", "L1W", "L0W", "L2W", "L1W", "L0W"],
            "value": [1000.0, 1200.0, 1400.0, 900.0, 1100.0, 1300.0],
            "week": ["L2W", "L1W", "L0W", "L2W", "L1W", "L0W"],
            "dataset": ["orders", "orders", "orders", "orders", "orders", "orders"],
        }
    )


def test_trend_analysis_returns_success():
    engine = QueryEngine(
        metrics_df=build_mock_metrics_df(),
        orders_df=build_mock_orders_df(),
    )

    parsed_intent = {
        "intent": "trend_analysis",
        "metric": "Perfect Orders",
        "filters": {
            "country": "CO",
            "city": "Bogota",
            "zone": "Zone A",
            "zone_type": None,
            "zone_prioritization": None,
        },
        "group_by": None,
        "secondary_metric": None,
        "aggregation": None,
        "rank_limit": None,
        "comparison": None,
        "time_scope": ["L2W", "L1W", "L0W"],
        "analysis_type": "trend",
        "chart_requested": False,
    }

    result = engine.run(parsed_intent)

    assert result["status"] == "success"
    assert result["analysis_type"] == "trend"
    assert result["aggregation_method"] == "mean"
    assert result["first_value"] == 0.9
    assert result["last_value"] == 1.0


def test_ranking_analysis_uses_orders_dataset_and_honors_top_n():
    engine = QueryEngine(
        metrics_df=build_mock_metrics_df(),
        orders_df=build_mock_orders_df(),
    )

    parsed_intent = {
        "intent": "ranking",
        "metric": "Orders",
        "filters": {
            "country": "CO",
            "city": "Bogota",
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        },
        "group_by": "zone",
        "secondary_metric": None,
        "aggregation": None,
        "rank_limit": 1,
        "comparison": None,
        "time_scope": ["L2W", "L1W", "L0W"],
        "analysis_type": "ranking",
        "chart_requested": False,
    }

    result = engine.run(parsed_intent)

    assert result["status"] == "success"
    assert result["dataset_used"] == "orders_long"
    assert result["aggregation_method"] == "sum"
    assert result["rank_limit"] == 1
    assert len(result["top_n"]) == 1
    assert result["top_n"][0]["zone"] == "Zone A"
    assert result["top_n"][0]["value"] == 3600.0


def test_comparison_with_mean_aggregation_by_country():
    engine = QueryEngine(
        metrics_df=build_mock_metrics_df(),
        orders_df=build_mock_orders_df(),
    )

    parsed_intent = {
        "intent": "comparison",
        "metric": "Lead Penetration",
        "filters": {
            "country": None,
            "city": None,
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        },
        "group_by": "country",
        "secondary_metric": None,
        "aggregation": "mean",
        "rank_limit": None,
        "comparison": None,
        "time_scope": ["L2W", "L1W", "L0W"],
        "analysis_type": "comparison",
        "chart_requested": False,
    }

    result = engine.run(parsed_intent)

    assert result["status"] == "success"
    assert result["aggregation_method"] == "mean"
    countries = {row["country"] for row in result["latest_snapshot"]}
    assert countries == {"CO", "PE"}


def test_distribution_analysis_returns_high_low_candidates():
    engine = QueryEngine(
        metrics_df=build_mock_metrics_df(),
        orders_df=build_mock_orders_df(),
    )

    parsed_intent = {
        "intent": "distribution",
        "metric": "Lead Penetration",
        "filters": {
            "country": None,
            "city": None,
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        },
        "group_by": "zone",
        "secondary_metric": "Perfect Orders",
        "aggregation": "mean",
        "rank_limit": None,
        "comparison": None,
        "time_scope": ["L2W", "L1W", "L0W"],
        "analysis_type": "distribution",
        "chart_requested": False,
    }

    result = engine.run(parsed_intent)

    assert result["status"] == "success"
    assert result["analysis_type"] == "distribution"
    assert result["latest_week"] == "L0W"
    assert result["primary_threshold"] is not None
    assert result["secondary_threshold"] is not None
    assert len(result["result_table"]) >= 1


def test_no_data_response_is_clear():
    engine = QueryEngine(
        metrics_df=build_mock_metrics_df(),
        orders_df=build_mock_orders_df(),
    )

    parsed_intent = {
        "intent": "metric_lookup",
        "metric": "Perfect Orders",
        "filters": {
            "country": "AR",
            "city": "Buenos Aires",
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        },
        "group_by": None,
        "secondary_metric": None,
        "aggregation": None,
        "rank_limit": None,
        "comparison": None,
        "time_scope": ["L2W", "L1W", "L0W"],
        "analysis_type": "value_lookup",
        "chart_requested": False,
    }

    result = engine.run(parsed_intent)

    assert result["status"] == "no_data"
    assert result["analysis_type"] == "value_lookup"
    assert result["result_table"] == []


def test_anomaly_analysis_ranks_biggest_growth():
    engine = QueryEngine(
        metrics_df=build_mock_metrics_df(),
        orders_df=build_mock_orders_df(),
    )

    parsed_intent = {
        "intent": "anomaly_check",
        "metric": "Orders",
        "filters": {
            "country": "CO",
            "city": "Bogota",
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        },
        "group_by": "zone",
        "secondary_metric": None,
        "aggregation": None,
        "rank_limit": 2,
        "comparison": None,
        "time_scope": ["L2W", "L1W", "L0W"],
        "analysis_type": "anomaly",
        "chart_requested": False,
    }

    result = engine.run(parsed_intent)

    assert result["status"] == "success"
    assert result["analysis_type"] == "anomaly"
    assert len(result["top_n"]) == 2
    assert result["top_n"][0]["zone"] == "Zone B"
    assert result["top_n"][0]["business_direction"] == "favorable"
    assert result["peer_context"]["second_entity"] == "Zone A"
    assert len(result["explanatory_hints"]) >= 1
    assert result["explanatory_hints"][0]["metric"] in {"Lead Penetration", "Perfect Orders"}
