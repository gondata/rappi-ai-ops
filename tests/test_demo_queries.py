import pytest

from data_prep import build_data_model
from llm_narrator import LLMNarrator
from llm_router import LLMRouter
from query_engine import QueryEngine


@pytest.fixture(scope="module")
def demo_pipeline():
    data_model = build_data_model()
    router = LLMRouter(api_key="")
    engine = QueryEngine(
        metrics_df=data_model["metrics_long"],
        orders_df=data_model["orders_long"],
    )
    narrator = LLMNarrator(api_key="")
    return router, engine, narrator


@pytest.mark.parametrize(
    ("question", "expected_intent", "expected_analysis", "expected_metric"),
    [
        ("Mostra las zonas problematicas en Mexico", "anomaly_check", "anomaly", "Perfect Orders"),
        ("Compara Perfect Orders entre zonas Wealthy y Non Wealthy en Mexico", "comparison", "comparison", "Perfect Orders"),
        ("Cual es el promedio de Lead Penetration por pais?", "comparison", "comparison", "Lead Penetration"),
        ("Que zonas tienen alto Lead Penetration pero bajo Perfect Orders?", "distribution", "distribution", "Lead Penetration"),
        (
            "Cuales son las zonas que mas crecen en ordenes en las ultimas 5 semanas y que podria explicar el crecimiento?",
            "anomaly_check",
            "anomaly",
            "Orders",
        ),
    ],
)
def test_demo_questions_run_successfully(demo_pipeline, question, expected_intent, expected_analysis, expected_metric):
    router, engine, narrator = demo_pipeline

    parsed = router.parse(question)
    result = engine.run(parsed)
    answer = narrator.narrate(question, parsed, result)

    assert parsed["intent"] == expected_intent
    assert parsed["analysis_type"] == expected_analysis
    assert parsed["metric"] == expected_metric
    assert result["status"] == "success"
    assert answer


def test_demo_growth_question_includes_explanatory_hints(demo_pipeline):
    router, engine, narrator = demo_pipeline
    question = "Cuales son las zonas que mas crecen en ordenes en las ultimas 5 semanas y que podria explicar el crecimiento?"

    parsed = router.parse(question)
    result = engine.run(parsed)
    answer = narrator.narrate(question, parsed, result)

    assert result["status"] == "success"
    assert result["analysis_type"] == "anomaly"
    assert result.get("explanatory_hints")
    assert "Posibles factores asociados" in answer


def test_demo_distribution_question_returns_reasonable_candidates(demo_pipeline):
    router, engine, narrator = demo_pipeline
    question = "Que zonas tienen alto Lead Penetration pero bajo Perfect Orders?"

    parsed = router.parse(question)
    result = engine.run(parsed)
    answer = narrator.narrate(question, parsed, result)

    assert result["status"] == "success"
    assert result["analysis_type"] == "distribution"
    assert result["latest_week"] == "L0W"
    assert result["matched_count"] > 0
    assert result["matched_count"] < 100
    assert "Penetración de Leads" in answer
    assert "Órdenes Perfectas" in answer


def test_demo_trend_question_for_named_zone_runs_successfully(demo_pipeline):
    router, engine, narrator = demo_pipeline
    question = "Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas"

    parsed = router.parse(question)
    result = engine.run(parsed)
    answer = narrator.narrate(question, parsed, result)

    assert parsed["intent"] == "trend_analysis"
    assert parsed["filters"]["zone"] == "Chapinero"
    assert result["status"] == "success"
    assert result["analysis_type"] == "trend"
    assert len(result["result_table"]) >= 5
    assert "Gross Profit UE" in answer
