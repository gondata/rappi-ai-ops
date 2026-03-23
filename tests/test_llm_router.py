from llm_router import LLMRouter


def build_memory_context():
    return {
        "last_metric": "Perfect Orders",
        "last_filters": {
            "country": "CO",
            "city": "Bogota",
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        },
        "last_dimension": None,
        "last_time_scope": ["L4W", "L3W", "L2W", "L1W", "L0W"],
        "last_intent": {
            "intent": "trend_analysis",
            "metric": "Perfect Orders",
            "filters": {
                "country": "CO",
                "city": "Bogota",
                "zone": None,
                "zone_type": None,
                "zone_prioritization": None,
            },
            "group_by": None,
            "comparison": None,
            "time_scope": ["L4W", "L3W", "L2W", "L1W", "L0W"],
            "analysis_type": "trend",
            "chart_requested": False,
        },
    }


def test_extracts_metric_from_alias():
    router = LLMRouter(api_key="")
    parsed = router.parse("Show perfect order trend in Bogota")

    assert parsed["metric"] == "Perfect Orders"
    assert parsed["intent"] == "trend_analysis"
    assert parsed["analysis_type"] == "trend"
    assert parsed["filters"]["city"] == "Bogota"


def test_detects_explicit_vs_comparison():
    router = LLMRouter(api_key="")
    parsed = router.parse("Compare Perfect Orders in Lima vs Bogota")

    assert parsed["intent"] == "comparison"
    assert parsed["analysis_type"] == "comparison"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["comparison"] is not None
    assert "Lima" in parsed["comparison"]
    assert "Bogota" in parsed["comparison"]
    assert parsed["filters"]["city"] is None


def test_follow_up_inherits_metric_and_country_from_memory():
    router = LLMRouter(api_key="")
    parsed = router.parse("and now Lima", memory_context=build_memory_context())

    assert parsed["metric"] == "Perfect Orders"
    assert parsed["filters"]["country"] == "CO"
    assert parsed["filters"]["city"] == "Lima"


def test_follow_up_across_cities_turns_into_comparison():
    router = LLMRouter(api_key="")
    parsed = router.parse("compare that across cities", memory_context=build_memory_context())

    assert parsed["intent"] == "comparison"
    assert parsed["analysis_type"] == "comparison"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["group_by"] == "city"
    assert parsed["filters"]["city"] is None


def test_follow_up_last_3_weeks_turns_into_trend():
    router = LLMRouter(api_key="")
    parsed = router.parse("show me the last 3 weeks", memory_context=build_memory_context())

    assert parsed["intent"] == "trend_analysis"
    assert parsed["analysis_type"] == "trend"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["time_scope"] == ["L2W", "L1W", "L0W"]


def test_ranking_extracts_top_n_and_group():
    router = LLMRouter(api_key="")
    parsed = router.parse("What are the top 5 zones by Orders in Bogota?")

    assert parsed["intent"] == "ranking"
    assert parsed["analysis_type"] == "ranking"
    assert parsed["metric"] == "Orders"
    assert parsed["group_by"] == "zone"
    assert parsed["rank_limit"] == 5


def test_average_by_country_sets_mean_aggregation():
    router = LLMRouter(api_key="")
    parsed = router.parse("What is the average Lead Penetration by country?")

    assert parsed["intent"] == "comparison"
    assert parsed["analysis_type"] == "comparison"
    assert parsed["metric"] == "Lead Penetration"
    assert parsed["group_by"] == "country"
    assert parsed["aggregation"] == "mean"


def test_multivariable_query_extracts_secondary_metric():
    router = LLMRouter(api_key="")
    parsed = router.parse("What zones have high Lead Penetration but low Perfect Orders?")

    assert parsed["intent"] == "distribution"
    assert parsed["analysis_type"] == "distribution"
    assert parsed["metric"] == "Lead Penetration"
    assert parsed["secondary_metric"] == "Perfect Orders"
    assert parsed["group_by"] == "zone"


def test_problematic_zones_maps_to_anomaly_check():
    router = LLMRouter(api_key="")
    parsed = router.parse("Show problematic zones in Mexico")

    assert parsed["intent"] == "anomaly_check"
    assert parsed["analysis_type"] == "anomaly"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["filters"]["country"] == "MX"
    assert parsed["group_by"] == "zone"
    assert parsed["rank_limit"] == 5


def test_growth_opportunities_maps_to_orders_anomaly():
    router = LLMRouter(api_key="")
    parsed = router.parse("What growth opportunities do you see in Bogota?")

    assert parsed["intent"] == "anomaly_check"
    assert parsed["analysis_type"] == "anomaly"
    assert parsed["metric"] == "Orders"
    assert parsed["filters"]["city"] == "Bogota"


def test_priority_filter_matches_real_dataset_values():
    router = LLMRouter(api_key="")
    parsed = router.parse("Show Perfect Orders in prioritized zones")

    assert parsed["filters"]["zone_prioritization"] == "Prioritized"


def test_sanitize_canonicalizes_llm_style_filter_values():
    router = LLMRouter(api_key="")
    parsed = router._sanitize_parsed_output(
        {
            "intent": "anomaly_check",
            "metric": "Perfect Orders",
            "filters": {
                "country": "Mexico",
                "city": None,
                "zone": None,
                "zone_type": "Wealthy",
                "zone_prioritization": "High Priority",
            },
            "group_by": "zone",
            "secondary_metric": None,
            "aggregation": None,
            "rank_limit": 5,
            "comparison": None,
            "time_scope": ["L4W", "L3W", "L2W", "L1W", "L0W"],
            "analysis_type": "anomaly",
            "chart_requested": False,
        },
        "Show problematic zones in Mexico",
    )

    assert parsed["filters"]["country"] == "MX"
    assert parsed["filters"]["zone_type"] == "Wealthy"
    assert parsed["filters"]["zone_prioritization"] == "High Priority"


def test_spanish_problematic_zones_query_maps_to_anomaly():
    router = LLMRouter(api_key="")
    parsed = router.parse("Mostrá las zonas problemáticas en México")

    assert parsed["intent"] == "anomaly_check"
    assert parsed["analysis_type"] == "anomaly"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["filters"]["country"] == "MX"
    assert parsed["group_by"] == "zone"


def test_spanish_compare_between_cities_maps_to_comparison():
    router = LLMRouter(api_key="")
    parsed = router.parse("Compará Perfect Orders entre ciudades")

    assert parsed["intent"] == "comparison"
    assert parsed["analysis_type"] == "comparison"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["group_by"] == "city"
    assert parsed["filters"]["city"] is None


def test_spanish_trend_and_time_scope_are_detected():
    router = LLMRouter(api_key="")
    parsed = router.parse("Mostrá la tendencia de Perfect Orders en Bogota en las últimas 5 semanas")

    assert parsed["intent"] == "trend_analysis"
    assert parsed["analysis_type"] == "trend"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["filters"]["city"] == "Bogota"
    assert parsed["time_scope"] == ["L4W", "L3W", "L2W", "L1W", "L0W"]


def test_spanish_distribution_query_extracts_secondary_metric():
    router = LLMRouter(api_key="")
    parsed = router.parse("¿Qué zonas tienen Lead Penetration alto pero Perfect Orders bajo?")

    assert parsed["intent"] == "distribution"
    assert parsed["analysis_type"] == "distribution"
    assert parsed["metric"] == "Lead Penetration"
    assert parsed["secondary_metric"] == "Perfect Orders"
    assert parsed["group_by"] == "zone"


def test_spanish_top_5_query_maps_to_ranking():
    router = LLMRouter(api_key="")
    parsed = router.parse("¿Cuáles son las 5 zonas con mayor Lead Penetration esta semana?")

    assert parsed["intent"] == "ranking"
    assert parsed["analysis_type"] == "ranking"
    assert parsed["metric"] == "Lead Penetration"
    assert parsed["group_by"] == "zone"
    assert parsed["rank_limit"] == 5


def test_spanish_wealthy_vs_non_wealthy_maps_to_zone_type_comparison():
    router = LLMRouter(api_key="")
    parsed = router.parse("Compara Perfect Orders entre zonas Wealthy y Non Wealthy en Mexico")

    assert parsed["intent"] == "comparison"
    assert parsed["analysis_type"] == "comparison"
    assert parsed["metric"] == "Perfect Orders"
    assert parsed["group_by"] == "zone_type"
    assert parsed["filters"]["country"] == "MX"
    assert parsed["filters"]["zone_type"] is None


def test_spanish_orders_alias_and_growth_phrase_map_to_orders():
    router = LLMRouter(api_key="")
    parsed = router.parse("Cuales son las zonas que mas crecen en ordenes en las ultimas 5 semanas")

    assert parsed["metric"] == "Orders"
    assert parsed["time_scope"] == ["L4W", "L3W", "L2W", "L1W", "L0W"]


def test_named_zone_after_en_is_captured():
    router = LLMRouter(api_key="")
    parsed = router.parse("Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas")

    assert parsed["metric"] == "Gross Profit UE"
    assert parsed["filters"]["zone"] == "Chapinero"


def test_description_style_query_maps_to_mltv_metric():
    router = LLMRouter(api_key="")
    parsed = router.parse("Mostra la tendencia de usuarios con ordenes en diferentes verticales en las ultimas 5 semanas")

    assert parsed["metric"] == "MLTV Top Verticals Adoption"
    assert parsed["intent"] == "trend_analysis"
    assert parsed["analysis_type"] == "trend"


def test_business_description_query_maps_to_breakeven_metric():
    router = LLMRouter(api_key="")
    parsed = router.parse("Compara el porcentaje de usuarios pro que hacen breakeven entre paises")

    assert parsed["metric"] == "% PRO Users Who Breakeven"
    assert parsed["intent"] == "comparison"
    assert parsed["group_by"] == "country"


def test_sanitize_recovers_named_zone_from_query_when_llm_omits_it():
    router = LLMRouter(api_key="")
    parsed = router._sanitize_parsed_output(
        {
            "intent": "trend_analysis",
            "metric": "Gross Profit UE",
            "filters": {
                "country": None,
                "city": None,
                "zone": None,
                "zone_type": None,
                "zone_prioritization": None,
            },
            "group_by": None,
            "secondary_metric": None,
            "aggregation": None,
            "rank_limit": None,
            "comparison": None,
            "time_scope": ["L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"],
            "analysis_type": "trend",
            "chart_requested": False,
        },
        "Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas",
    )

    assert parsed["filters"]["zone"] == "Chapinero"


def test_sanitize_moves_unknown_city_to_zone_when_query_points_to_named_zone():
    router = LLMRouter(api_key="")
    parsed = router._sanitize_parsed_output(
        {
            "intent": "trend_analysis",
            "metric": "Gross Profit UE",
            "filters": {
                "country": None,
                "city": "Chapinero",
                "zone": None,
                "zone_type": None,
                "zone_prioritization": None,
            },
            "group_by": None,
            "secondary_metric": None,
            "aggregation": None,
            "rank_limit": None,
            "comparison": None,
            "time_scope": ["L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"],
            "analysis_type": "trend",
            "chart_requested": False,
        },
        "Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas",
    )

    assert parsed["filters"]["city"] is None
    assert parsed["filters"]["zone"] == "Chapinero"
