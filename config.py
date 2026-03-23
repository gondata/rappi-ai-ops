from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Lee una variable de entorno local (.env) o st.secrets (Streamlit Cloud)."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return str(st.secrets.get(key, default))
    except Exception:
        return default

# =========================
# Paths base
# =========================
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

OUTPUTS_DIR = BASE_DIR / "outputs"
CHARTS_DIR = OUTPUTS_DIR / "charts"
REPORTS_DIR = OUTPUTS_DIR / "reports"
EXPORTS_DIR = OUTPUTS_DIR / "exports"

# =========================
# Archivo fuente principal
# =========================
RAW_EXCEL_FILE = RAW_DATA_DIR / "Sistema de Análisis Inteligente para Operaciones Rappi - Dummy Data.xlsx"

# =========================
# Hojas del Excel
# =========================
SHEET_METRICS = "RAW_INPUT_METRICS"
SHEET_ORDERS = "RAW_ORDERS"
SHEET_SUMMARY = "RAW_SUMMARY"

# =========================
# App / modelo
# =========================
APP_TITLE = "Rappi AI Operations Assistant"
APP_SUBTITLE = "Technical Challenge Demo"

DEFAULT_MODEL_NAME = _get_secret("MODEL_NAME", "gpt-4.1")
OPENAI_API_KEY = _get_secret("OPENAI_API_KEY", "")

SMTP_HOST = _get_secret("SMTP_HOST", "")
SMTP_PORT = int(_get_secret("SMTP_PORT", "587"))
SMTP_USERNAME = _get_secret("SMTP_USERNAME", "")
SMTP_PASSWORD = _get_secret("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = _get_secret("SMTP_FROM_EMAIL", "")
SMTP_USE_TLS = _get_secret("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

# =========================
# Columnas esperadas
# =========================
DIMENSION_COLS_METRICS = [
    "COUNTRY",
    "CITY",
    "ZONE",
    "ZONE_TYPE",
    "ZONE_PRIORITIZATION",
    "METRIC",
]

DIMENSION_COLS_ORDERS = [
    "COUNTRY",
    "CITY",
    "ZONE",
    "METRIC",
]

WEEK_COLS_METRICS = [
    "L8W_ROLL",
    "L7W_ROLL",
    "L6W_ROLL",
    "L5W_ROLL",
    "L4W_ROLL",
    "L3W_ROLL",
    "L2W_ROLL",
    "L1W_ROLL",
    "L0W_ROLL",
]

WEEK_COLS_ORDERS = [
    "L8W",
    "L7W",
    "L6W",
    "L5W",
    "L4W",
    "L3W",
    "L2W",
    "L1W",
    "L0W",
]

# =========================
# Mapeo de semanas
# =========================
WEEK_LABEL_MAP = {
    "L8W_ROLL": "L8W",
    "L7W_ROLL": "L7W",
    "L6W_ROLL": "L6W",
    "L5W_ROLL": "L5W",
    "L4W_ROLL": "L4W",
    "L3W_ROLL": "L3W",
    "L2W_ROLL": "L2W",
    "L1W_ROLL": "L1W",
    "L0W_ROLL": "L0W",
    "L8W": "L8W",
    "L7W": "L7W",
    "L6W": "L6W",
    "L5W": "L5W",
    "L4W": "L4W",
    "L3W": "L3W",
    "L2W": "L2W",
    "L1W": "L1W",
    "L0W": "L0W",
}

# =========================
# Aliases de métricas
# =========================
METRIC_ALIASES = {
    "perfect orders": "Perfect Orders",
    "perfect order": "Perfect Orders",
    "orders": "Orders",
    "ordenes": "Orders",
    "órdenes": "Orders",
    "pedidos": "Orders",
    "late orders": "Late Orders",
    "defects": "Defects",
    "cancellations": "Cancellations",
    "cancelations": "Cancellations",
    "gross profit ue": "Gross Profit UE",
    "gross profit": "Gross Profit UE",
    "lead penetration": "Lead Penetration",
    "pro adoption": "Pro Adoption (Last Week Status)",
    "pro adoption (last week status)": "Pro Adoption (Last Week Status)",
    "turbo adoption": "Turbo Adoption",
    "restaurants markdowns / gmv": "Restaurants Markdowns / GMV",
    "restaurants ss > atc cvr": "Restaurants SS > ATC CVR",
    "restaurants sst > ss cvr": "Restaurants SST > SS CVR",
    "retail sst > ss cvr": "Retail SST > SS CVR",
    "non-pro ptc > op": "Non-Pro PTC > OP",
    "% pro users who breakeven": "% PRO Users Who Breakeven",
    "pro users who breakeven": "% PRO Users Who Breakeven",
    "% restaurants sessions with optimal assortment": "% Restaurants Sessions With Optimal Assortment",
    "restaurants sessions with optimal assortment": "% Restaurants Sessions With Optimal Assortment",
    "mltv top verticals adoption": "MLTV Top Verticals Adoption",
    "usuarios con ordenes en diferentes verticales": "MLTV Top Verticals Adoption",
    "usuarios con ordenes en diferentes verticales sobre total usuarios": "MLTV Top Verticals Adoption",
    "usuarios con pedidos en diferentes verticales": "MLTV Top Verticals Adoption",
    "usuarios con pedidos en restaurantes super pharmacy liquors": "MLTV Top Verticals Adoption",
    "usuarios con ordenes en restaurantes super pharmacy liquors": "MLTV Top Verticals Adoption",
    "adopcion de multiples verticales": "MLTV Top Verticals Adoption",
    "usuarios pro que hacen breakeven": "% PRO Users Who Breakeven",
    "porcentaje de usuarios pro que hacen breakeven": "% PRO Users Who Breakeven",
    "sesiones de restaurantes con surtido optimo": "% Restaurants Sessions With Optimal Assortment",
    "porcentaje de sesiones de restaurantes con surtido optimo": "% Restaurants Sessions With Optimal Assortment",
    "conversion de retail de sst a ss": "Retail SST > SS CVR",
    "conversion retail sst a ss": "Retail SST > SS CVR",
    "conversion de restaurantes de sst a ss": "Restaurants SST > SS CVR",
    "conversion de restaurantes de ss a atc": "Restaurants SS > ATC CVR",
    # Spanish libre - métricas de calidad
    "ordenes perfectas": "Perfect Orders",
    "ordenes sin defectos": "Perfect Orders",
    "calidad de ordenes": "Perfect Orders",
    "calidad de pedidos": "Perfect Orders",
    "ordenes tardias": "Late Orders",
    "pedidos tardios": "Late Orders",
    "defectos en ordenes": "Defects",
    "cancelaciones": "Cancellations",
    # Spanish libre - métricas de margen
    "margen bruto": "Gross Profit UE",
    "ganancia bruta": "Gross Profit UE",
    "margen por orden": "Gross Profit UE",
    "rentabilidad por orden": "Gross Profit UE",
    # Spanish libre - Lead Penetration
    "penetracion de leads": "Lead Penetration",
    "penetracion de tiendas": "Lead Penetration",
    "tiendas habilitadas": "Lead Penetration",
    "cobertura de tiendas": "Lead Penetration",
    # Spanish libre - adopciones
    "adopcion pro": "Pro Adoption (Last Week Status)",
    "usuarios pro": "Pro Adoption (Last Week Status)",
    "suscriptores pro": "Pro Adoption (Last Week Status)",
    "adopcion turbo": "Turbo Adoption",
    "usuarios turbo": "Turbo Adoption",
    "adopcion de multiples verticales": "MLTV Top Verticals Adoption",
    "adopcion multi vertical": "MLTV Top Verticals Adoption",
    # Spanish libre - conversiones
    "conversion no pro": "Non-Pro PTC > OP",
    "conversion de usuarios no pro": "Non-Pro PTC > OP",
    "checkout a orden": "Non-Pro PTC > OP",
    "conversion de checkout": "Non-Pro PTC > OP",
    "conversion de tienda a carrito": "Restaurants SS > ATC CVR",
    "agregar al carrito": "Restaurants SS > ATC CVR",
    "seleccion de tienda": "Restaurants SST > SS CVR",
    "conversion de seleccion de tienda retail": "Retail SST > SS CVR",
    # Spanish libre - descuentos
    "descuentos restaurantes": "Restaurants Markdowns / GMV",
    "markdowns de restaurantes": "Restaurants Markdowns / GMV",
    "descuentos sobre gmv": "Restaurants Markdowns / GMV",
    # Spanish libre - surtido
    "surtido optimo": "% Restaurants Sessions With Optimal Assortment",
    "sesiones con buen surtido": "% Restaurants Sessions With Optimal Assortment",
    # Spanish libre - pro breakeven
    "usuarios pro que se pagan solos": "% PRO Users Who Breakeven",
    "pro que hacen breakeven": "% PRO Users Who Breakeven",
    "breakeven": "% PRO Users Who Breakeven",
    "pro breakeven": "% PRO Users Who Breakeven",
    "no hacen breakeven": "% PRO Users Who Breakeven",
    # English LLM normalizations
    "profit per order": "Gross Profit UE",
    "gross profit per order": "Gross Profit UE",
    "unit economics": "Gross Profit UE",
    "store coverage": "Lead Penetration",
    "store penetration": "Lead Penetration",
    "lead coverage": "Lead Penetration",
    "breakeven de usuarios pro": "% PRO Users Who Breakeven",
    "menor breakeven": "% PRO Users Who Breakeven",
    # MLTV short forms
    "usuarios con ordenes": "MLTV Top Verticals Adoption",
    "usuarios con pedidos": "MLTV Top Verticals Adoption",
    "multiples verticales": "MLTV Top Verticals Adoption",
    "multi vertical": "MLTV Top Verticals Adoption",
}

# =========================
# Memoria conversacional
# =========================
MEMORY_PERSIST_PATH = PROCESSED_DATA_DIR / "conversation_memory.json"
MEMORY_MAX_TURNS = 10          # turnos máximos a guardar en disco

# =========================
# Thresholds de detección de insights
# =========================

# Anomalías semana-a-semana
ANOMALY_MIN_PCT_CHANGE = 10        # variación mínima (%) para registrar una anomalía
ANOMALY_EXTREME_THRESHOLD = 100    # variación (%) a partir de la cual se considera extrema y se muestra cambio absoluto
ANOMALY_HIGH_SEVERITY_PCT = 15     # variación mínima (%) para severidad alta en deterioros
ANOMALY_BRUSCA_THRESHOLD = 20      # variación mínima (%) para calificar como "brusca" (vs "moderada")

# Deterioro de tendencia (3 semanas consecutivas)
TREND_MIN_TOTAL_DELTA_PCT = 2      # cambio total mínimo (%) para registrar un deterioro de tendencia

# Benchmarking (brecha entre mejor y peor zona)
BENCHMARK_MIN_PP_GAP = 2           # brecha mínima en pp para métricas porcentuales
BENCHMARK_MIN_REL_GAP_PCT = 8      # brecha mínima en % relativo para métricas no porcentuales
BENCHMARK_MIN_ABS_GAP = 1          # brecha mínima absoluta para métricas con base negativa
BENCHMARK_HIGH_SEVERITY_PP = 10    # pp gap mínimo para severidad alta (métricas %)
BENCHMARK_HIGH_SEVERITY_REL = 20   # % relativo mínimo para severidad alta (métricas no %)

SUPPORTED_AGGREGATIONS = [
    "mean",
    "sum",
]

SUPPORTED_INTENTS = [
    "metric_lookup",
    "trend_analysis",
    "comparison",
    "ranking",
    "distribution",
    "anomaly_check",
    "follow_up",
    "unknown",
]

SUPPORTED_ANALYSIS_TYPES = [
    "value_lookup",
    "trend",
    "comparison",
    "ranking",
    "distribution",
    "anomaly",
    "follow_up",
    "unknown",
]

SUPPORTED_GROUP_BY = [
    "country",
    "city",
    "zone",
    "zone_type",
    "zone_prioritization",
    "metric",
]

SUPPORTED_TIME_SCOPE = ["L8W", "L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]
