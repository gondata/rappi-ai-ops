from insight_engine import InsightEngine
import pandas as pd


def build_report_metrics_df():
    return pd.DataFrame(
        {
            "country": ["CO"] * 12,
            "city": ["Bogota"] * 6 + ["Bogota"] * 6,
            "zone": ["Zone A"] * 6 + ["Zone B"] * 6,
            "zone_type": ["Dense"] * 6 + ["Dense"] * 6,
            "zone_prioritization": ["High"] * 12,
            "metric": (
                ["Perfect Orders"] * 3
                + ["Lead Penetration"] * 3
                + ["Perfect Orders"] * 3
                + ["Lead Penetration"] * 3
            ),
            "week_raw": ["L2W_ROLL", "L1W_ROLL", "L0W_ROLL"] * 4,
            "value": [
                0.92, 0.86, 0.72,
                0.74, 0.81, 0.93,
                0.88, 0.90, 0.91,
                0.60, 0.62, 0.63,
            ],
            "week": ["L2W", "L1W", "L0W"] * 4,
            "dataset": ["metrics"] * 12,
        }
    )


def test_generate_trend_insights():
    engine = InsightEngine()

    analytical_result = {
        "status": "success",
        "analysis_type": "trend",
        "metric": "Late Orders",
        "first_week": "L4W",
        "last_week": "L0W",
        "first_value": 0.10,
        "last_value": 0.15,
        "delta_abs": 0.05,
        "delta_pct": 50.0,
    }

    insights = engine.generate(analytical_result)

    assert len(insights) >= 3
    assert insights[0]["title"] == "Dirección de la tendencia"
    assert "Late Orders aumentó" in insights[0]["message"]
    assert "10.00%" in insights[0]["message"]
    assert "15.00%" in insights[0]["message"]


def test_generate_comparison_insights():
    engine = InsightEngine()

    analytical_result = {
        "status": "success",
        "analysis_type": "comparison",
        "metric": "Perfect Orders",
        "group_by": "city",
        "latest_week": "L0W",
        "latest_snapshot": [
            {"city": "Bogota", "week": "L0W", "value": 0.95},
            {"city": "Lima", "week": "L0W", "value": 0.88},
            {"city": "Mexico City", "week": "L0W", "value": 0.90},
        ],
    }

    insights = engine.generate(analytical_result)

    joined = " ".join(i["message"] for i in insights)
    assert len(insights) >= 3
    assert "Bogota lideró Perfect Orders" in joined
    assert "95.00%" in joined


def test_generate_ranking_insights():
    engine = InsightEngine()

    analytical_result = {
        "status": "success",
        "analysis_type": "ranking",
        "metric": "Orders",
        "group_by": "zone",
        "top_10": [
            {"zone": "Zone A", "value": 1200.0, "rank": 1},
            {"zone": "Zone B", "value": 1000.0, "rank": 2},
            {"zone": "Zone C", "value": 800.0, "rank": 3},
            {"zone": "Zone D", "value": 500.0, "rank": 4},
        ],
    }

    insights = engine.generate(analytical_result)

    joined = " ".join(i["message"] for i in insights)
    assert len(insights) >= 4
    assert "Zone A ocupa el primer lugar" in joined
    assert "top 3 explica" in joined.lower()


def test_generate_lookup_insight_formats_percentage():
    engine = InsightEngine()

    analytical_result = {
        "status": "success",
        "analysis_type": "value_lookup",
        "metric": "Perfect Orders",
        "latest_week": "L0W",
        "latest_value": 0.8611,
        "aggregation_method": "mean",
    }

    insights = engine.generate(analytical_result)

    assert len(insights) == 1
    assert insights[0]["title"] == "Último valor"
    assert "86.11%" in insights[0]["message"]
    assert "agregado usando mean" in insights[0]["message"]


def test_non_success_result_returns_message():
    engine = InsightEngine()

    analytical_result = {
        "status": "no_data",
        "analysis_type": "comparison",
        "message": "No data found for the requested metric, filters, and time scope.",
    }

    insights = engine.generate(analytical_result)

    assert len(insights) == 1
    assert insights[0]["title"] == "Sin datos"
    assert insights[0]["message"] == "No data found for the requested metric, filters, and time scope."


def test_generate_distribution_insights():
    engine = InsightEngine()

    analytical_result = {
        "status": "success",
        "analysis_type": "distribution",
        "metric": "Lead Penetration",
        "secondary_metric": "Perfect Orders",
        "group_by": "zone",
        "matched_count": 1,
        "matched_entities": [
            {"zone": "Zone B", "primary_value": 0.92, "secondary_value": 0.86},
        ],
    }

    insights = engine.generate(analytical_result)

    joined = " ".join(i["message"] for i in insights)
    assert len(insights) == 2
    assert "Zone B" in joined
    assert "Lead Penetration" in joined


def test_generate_executive_report_has_expected_sections():
    engine = InsightEngine(metrics_df=build_report_metrics_df(), orders_df=pd.DataFrame())

    report = engine.generate_executive_report()

    assert "summary" in report
    assert "sections" in report
    assert "anomalies" in report["sections"]
    assert "trend_deterioration" in report["sections"]
    assert "benchmarking" in report["sections"]
    assert "opportunities" in report["sections"]
    assert len(report["summary"]) >= 1


def test_generate_anomaly_insight():
    engine = InsightEngine()

    analytical_result = {
        "status": "success",
        "analysis_type": "anomaly",
        "metric": "Perfect Orders",
        "group_by": "zone",
        "top_n": [
            {"zone": "Zone A", "delta_pct": -20.0},
        ],
    }

    insights = engine.generate(analytical_result)

    assert len(insights) == 1
    assert insights[0]["category"] == "anomalies"
    assert "Zone A" in insights[0]["message"]
