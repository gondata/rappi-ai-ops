from llm_narrator import LLMNarrator


def test_lookup_narration_formats_percentage():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "metric_lookup",
        "metric": "Perfect Orders",
        "filters": {"country": "CO", "city": "Bogota", "zone": None, "zone_type": None, "zone_prioritization": None},
    }

    analytical_result = {
        "status": "success",
        "analysis_type": "value_lookup",
        "metric": "Perfect Orders",
        "filters": {"country": "CO", "city": "Bogota", "zone": None, "zone_type": None, "zone_prioritization": None},
        "latest_week": "L0W",
        "latest_value": 0.8611,
    }

    text = narrator.narrate("Show Perfect Orders in Bogota", parsed_intent, analytical_result)

    assert "86.11%" in text
    assert "Bogota" in text
    assert "Órdenes Perfectas" in text


def test_trend_narration_formats_percentage():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "trend_analysis",
        "metric": "Perfect Orders",
        "filters": {"country": None, "city": "Bogota", "zone": None, "zone_type": None, "zone_prioritization": None},
    }

    analytical_result = {
        "status": "success",
        "analysis_type": "trend",
        "metric": "Perfect Orders",
        "filters": {"country": None, "city": "Bogota", "zone": None, "zone_type": None, "zone_prioritization": None},
        "first_week": "L4W",
        "last_week": "L0W",
        "first_value": 0.8639,
        "last_value": 0.8611,
        "delta_pct": -0.32,
    }

    text = narrator.narrate(
        "Show the trend of Perfect Orders in Bogota over the last 5 weeks",
        parsed_intent,
        analytical_result,
    )

    assert "86.39%" in text
    assert "86.11%" in text
    assert "Hace 4 semanas" in text


def test_comparison_narration():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "comparison",
        "metric": "Perfect Orders",
    }

    analytical_result = {
        "status": "success",
        "analysis_type": "comparison",
        "metric": "Perfect Orders",
        "group_by": "city",
        "latest_week": "L0W",
        "latest_snapshot": [
            {"city": "Bogota", "value": 0.95},
            {"city": "Lima", "value": 0.88},
        ],
    }

    text = narrator.narrate("Compare Perfect Orders in Lima vs Bogota", parsed_intent, analytical_result)

    assert "Bogota" in text
    assert "95.00%" in text
    assert "88.00%" in text
    assert "Órdenes Perfectas" in text


def test_ranking_narration_orders_keeps_numeric_format():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "ranking",
        "metric": "Orders",
        "filters": {"country": "CO", "city": "Bogota", "zone": None, "zone_type": None, "zone_prioritization": None},
    }

    analytical_result = {
        "status": "success",
        "analysis_type": "ranking",
        "metric": "Orders",
        "filters": {"country": "CO", "city": "Bogota", "zone": None, "zone_type": None, "zone_prioritization": None},
        "group_by": "zone",
        "top_10": [
            {"zone": "Zone A", "value": 3600.0},
            {"zone": "Zone B", "value": 3300.0},
        ],
    }

    text = narrator.narrate("Top zones by Orders", parsed_intent, analytical_result)

    assert "Zone A" in text
    assert "3,600.00" in text


def test_distribution_narration_mentions_candidate_and_metrics():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "distribution",
        "metric": "Lead Penetration",
        "secondary_metric": "Perfect Orders",
    }

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

    text = narrator.narrate(
        "What zones have high Lead Penetration but low Perfect Orders?",
        parsed_intent,
        analytical_result,
    )

    assert "Zone B" in text
    assert "Penetración de Leads" in text
    assert "Órdenes Perfectas" in text


def test_anomaly_narration_mentions_top_entity():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "anomaly_check",
        "metric": "Perfect Orders",
    }

    analytical_result = {
        "status": "success",
        "analysis_type": "anomaly",
        "metric": "Perfect Orders",
        "filters": {"country": "MX", "city": None, "zone": None, "zone_type": None, "zone_prioritization": None},
        "group_by": "zone",
        "top_n": [
            {
                "zone": "Zone A",
                "delta_pct": -20.0,
                "first_week": "L2W",
                "last_week": "L0W",
                "first_value": 0.90,
                "last_value": 0.72,
                "business_direction": "unfavorable",
                "severity": "high",
            },
        ],
        "peer_context": {"second_entity": "Zone B", "second_delta_pct": -12.0},
    }

    text = narrator.narrate("Show problematic zones", parsed_intent, analytical_result)

    assert "Zone A" in text
    assert "20.00%" in text
    assert "alta severidad" in text
    assert "Zone B" in text
    assert "México" in text


def test_growth_anomaly_narration_includes_explanatory_hints():
    narrator = LLMNarrator()

    parsed_intent = {
        "intent": "anomaly_check",
        "metric": "Orders",
    }

    analytical_result = {
        "status": "success",
        "analysis_type": "anomaly",
        "metric": "Orders",
        "filters": {"country": None, "city": None, "zone": None, "zone_type": None, "zone_prioritization": None},
        "group_by": "zone",
        "top_n": [
            {
                "zone": "Zone A",
                "delta_pct": 30.0,
                "first_week": "L4W",
                "last_week": "L0W",
                "first_value": 100.0,
                "last_value": 130.0,
                "business_direction": "favorable",
                "severity": "high",
            },
        ],
        "peer_context": {"second_entity": "Zone B", "second_delta_pct": 18.0},
        "explanatory_hints": [
            {
                "metric": "Lead Penetration",
                "first_value": 0.40,
                "last_value": 0.55,
            },
            {
                "metric": "Perfect Orders",
                "first_value": 0.82,
                "last_value": 0.90,
            },
        ],
    }

    text = narrator.narrate("Que zonas crecen en ordenes", parsed_intent, analytical_result)

    assert "Posibles factores asociados" in text
    assert "Lead Penetration" in text or "Penetración" in text
