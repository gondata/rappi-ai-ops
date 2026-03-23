"""
Test integral del pipeline end-to-end.
Corre las preguntas del test manual a través de router → query_engine → narrator.
Evalúa que cada pregunta devuelva status=success y una respuesta no vacía.

Nota sobre métricas ausentes en el dummy data:
  Late Orders, Defects, Cancellations no existen en el Excel de prueba.
  Las preguntas que las usan se marcan con xfail(reason="metric absent from dummy data").
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from data_prep import build_data_model
from llm_router import LLMRouter
from query_engine import QueryEngine
from llm_narrator import LLMNarrator
from memory import ConversationMemory
from config import DEFAULT_MODEL_NAME, OPENAI_API_KEY


@pytest.fixture(scope="module")
def shared_pipeline():
    """Pipeline compartido (sin memoria acumulada entre tests)."""
    data_model = build_data_model()
    router = LLMRouter(model_name=DEFAULT_MODEL_NAME, api_key=OPENAI_API_KEY)
    engine = QueryEngine(
        metrics_df=data_model["metrics_long"],
        orders_df=data_model["orders_long"],
    )
    narrator = LLMNarrator(model_name=DEFAULT_MODEL_NAME, api_key=OPENAI_API_KEY)
    return router, engine, narrator


def ask(shared_pipeline, question: str) -> dict:
    """Corre una pregunta con memoria limpia (sin contexto previo)."""
    router, engine, narrator = shared_pipeline
    parsed = router.parse(question, None)
    result = engine.run(parsed)
    text = narrator.narrate(question, parsed, result)
    return {
        "question": question,
        "intent": parsed.get("intent"),
        "metric": parsed.get("metric"),
        "status": result.get("status"),
        "analysis_type": result.get("analysis_type"),
        "answer": text,
    }


# ---------------------------------------------------------------------------
# Metric lookup
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "What are the Perfect Orders in Bogota?",
    "Cuál es el Gross Profit UE en Chapinero?",
    "Dame las órdenes perfectas en México",
    "Show Lead Penetration in Lima",
    "Cuál es la adopción PRO en Argentina?",
    "Turbo Adoption en Colombia",
])
def test_metric_lookup(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Muestra la evolución de Perfect Orders en Bogota las últimas 8 semanas",
    "Show the trend of Gross Profit UE in Chapinero last 5 weeks",
    "Tendencia de Lead Penetration en Argentina últimas 4 semanas",
    "Mostra la evolución de usuarios con órdenes en diferentes verticales en las últimas 5 semanas",
])
def test_trend(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


@pytest.mark.xfail(reason="Late Orders absent from dummy data")
def test_trend_late_orders(shared_pipeline):
    r = ask(shared_pipeline, "Cómo evolucionaron las órdenes tardías en Lima?")
    assert r["status"] == "success"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Compara Perfect Orders entre zonas Wealthy y Non Wealthy en México",
    "Compare Gross Profit UE between Bogota and Lima",
    "Cómo se compara la adopción PRO entre países?",
    "Diferencia entre Wealthy y Non Wealthy en Lead Penetration en Colombia",
])
def test_comparison(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


@pytest.mark.xfail(reason="Late Orders absent from dummy data")
def test_comparison_late_orders(shared_pipeline):
    r = ask(shared_pipeline, "Compara Late Orders entre ciudades de Argentina")
    assert r["status"] == "success"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Cuáles son las top 10 zonas por órdenes en Colombia?",
    "Top zonas por Perfect Orders en México",
    "Cuáles son las peores zonas en Gross Profit UE en Argentina?",
    "Ranking de ciudades por Turbo Adoption",
    "Qué ciudades tienen baja cobertura de tiendas?",
])
def test_ranking(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


@pytest.mark.xfail(reason="Cancellations absent from dummy data")
def test_ranking_cancellations(shared_pipeline):
    r = ask(shared_pipeline, "Qué zonas tienen más cancellations?")
    assert r["status"] == "success"


# ---------------------------------------------------------------------------
# Distribution / screening multivariable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Qué zonas tienen alto Lead Penetration pero bajo Perfect Orders?",
    "Zonas con alta adopción PRO pero bajos órdenes perfectas",
    "Show zones with high Turbo Adoption but low Perfect Orders",
])
def test_distribution(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


@pytest.mark.xfail(reason="Defects absent from dummy data")
def test_distribution_defects(shared_pipeline):
    r = ask(shared_pipeline, "Qué zonas tienen alta penetración de leads pero muchos defectos?")
    assert r["status"] == "success"


# ---------------------------------------------------------------------------
# Anomaly check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Mostrá las zonas problemáticas en México",
    "Qué zonas cayeron más en Perfect Orders?",
    "Detectá anomalías en Gross Profit UE",
    "Cuáles son las zonas que más crecen en órdenes en las últimas 5 semanas y qué podría explicar el crecimiento?",
    "Zonas con caídas fuertes en Colombia",
])
def test_anomaly(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


# ---------------------------------------------------------------------------
# Español libre / aliases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Cuál es el nivel de Perfect Orders en este momento?",
    "Cuáles son las zonas con peor surtido óptimo?",
    "Dónde está cayendo la rentabilidad por orden?",
    "Cuáles son las zonas con menor breakeven de usuarios PRO?",
])
def test_spanish_aliases(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["status"] == "success", (
        f"FAIL [{question}]\n  intent={r['intent']} metric={r['metric']} status={r['status']}"
    )
    assert r["answer"]


@pytest.mark.xfail(reason="Open-ended intent not routed — LLM returns unknown for 'qué tan bien estamos'")
def test_alias_open_ended_quality(shared_pipeline):
    r = ask(shared_pipeline, "Qué tan bien estamos en calidad de pedidos?")
    assert r["status"] == "success"


@pytest.mark.xfail(reason="Negation 'no hacen X' routed as distribution without secondary metric")
def test_alias_negation_breakeven(shared_pipeline):
    # 'no hacen breakeven' → router assigns distribution intent without secondary — NLU limitation
    # Equivalent positive form ('zonas con menor breakeven') passes correctly
    r = ask(shared_pipeline, "Dónde los usuarios pro no hacen breakeven?")
    assert r["status"] == "success"


@pytest.mark.xfail(reason="Cancellations absent from dummy data")
def test_alias_cancelaciones(shared_pipeline):
    r = ask(shared_pipeline, "Qué zonas tienen muchas cancelaciones?")
    assert r["status"] == "success"


# ---------------------------------------------------------------------------
# Follow-ups encadenados (memoria propia, aislada)
# ---------------------------------------------------------------------------

def test_followup_chain(shared_pipeline):
    router, engine, narrator = shared_pipeline
    memory = ConversationMemory()
    turns = [
        "Qué zonas cayeron más en Perfect Orders en Argentina?",
        "Y en Colombia?",
        "Muestra la tendencia de Perfect Orders en Bogota las últimas 5 semanas",
    ]
    for q in turns:
        memory_context = memory.get_context()
        parsed = router.parse(q, memory_context)
        result = engine.run(parsed)
        text = narrator.narrate(q, parsed, result)
        memory.add_turn(q, text)
        assert result.get("status") == "success", (
            f"FAIL follow-up [{q}]\n  status={result.get('status')} intent={parsed.get('intent')}"
        )
        assert text


# ---------------------------------------------------------------------------
# Edge cases (no se exige success, solo que no crashee)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "Qué está pasando en Bahia Blanca?",
    "Resumen general de operaciones",
    "Cuál es la mejor zona de toda la región?",
    "Hay algo preocupante esta semana?",
])
def test_edge_cases(shared_pipeline, question):
    r = ask(shared_pipeline, question)
    assert r["answer"], f"FAIL edge case [{question}] → empty answer"
