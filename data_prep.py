import pandas as pd

from config import (
    RAW_EXCEL_FILE,
    SHEET_METRICS,
    SHEET_ORDERS,
    SHEET_SUMMARY,
    DIMENSION_COLS_METRICS,
    DIMENSION_COLS_ORDERS,
    WEEK_COLS_METRICS,
    WEEK_COLS_ORDERS,
    WEEK_LABEL_MAP,
)


def load_raw_data() -> dict:
    """
    Carga las hojas principales del Excel y las devuelve en un diccionario.
    """
    metrics_df = pd.read_excel(RAW_EXCEL_FILE, sheet_name=SHEET_METRICS)
    orders_df = pd.read_excel(RAW_EXCEL_FILE, sheet_name=SHEET_ORDERS)
    summary_df = pd.read_excel(RAW_EXCEL_FILE, sheet_name=SHEET_SUMMARY)

    return {
        "metrics_raw": metrics_df,
        "orders_raw": orders_df,
        "summary_raw": summary_df,
    }


def standardize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia columnas de texto sin convertir nulos en el string "nan".
    """
    result = df.copy()

    for col in result.columns:
        if result[col].dtype == "object":
            result[col] = result[col].apply(
                lambda value: value.strip() if isinstance(value, str) else value
            )
            result[col] = result[col].replace({"": None, "nan": None, "NaN": None, "None": None})

    return result


def clean_long_format(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica higiene mínima al formato long:
    - normaliza texto
    - fuerza value a numérico
    - elimina filas sin semana o valor
    - deduplica filas exactas
    """
    result = standardize_text_columns(df)
    result = result.copy()
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result.dropna(subset=["week", "value"]).drop_duplicates().reset_index(drop=True)
    return result


def melt_metrics_data(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte RAW_INPUT_METRICS desde wide a long.
    """
    df = standardize_text_columns(metrics_df.copy())

    metrics_long = df.melt(
        id_vars=DIMENSION_COLS_METRICS,
        value_vars=WEEK_COLS_METRICS,
        var_name="week_raw",
        value_name="value",
    )

    metrics_long["week"] = metrics_long["week_raw"].map(WEEK_LABEL_MAP)
    metrics_long["dataset"] = "metrics"
    metrics_long.columns = [col.lower() for col in metrics_long.columns]

    return clean_long_format(metrics_long)


def melt_orders_data(orders_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte RAW_ORDERS desde wide a long.
    """
    df = standardize_text_columns(orders_df.copy())

    orders_long = df.melt(
        id_vars=DIMENSION_COLS_ORDERS,
        value_vars=WEEK_COLS_ORDERS,
        var_name="week_raw",
        value_name="value",
    )

    orders_long["week"] = orders_long["week_raw"].map(WEEK_LABEL_MAP)
    orders_long["dataset"] = "orders"
    orders_long.columns = [col.lower() for col in orders_long.columns]

    return clean_long_format(orders_long)


def build_data_model() -> dict:
    """
    Carga el Excel y devuelve un modelo de datos listo para análisis.
    """
    raw_data = load_raw_data()

    metrics_raw = raw_data["metrics_raw"]
    orders_raw = raw_data["orders_raw"]
    summary_raw = raw_data["summary_raw"]

    metrics_long = melt_metrics_data(metrics_raw)
    orders_long = melt_orders_data(orders_raw)

    return {
        "metrics_raw": metrics_raw,
        "orders_raw": orders_raw,
        "summary_raw": summary_raw,
        "metrics_long": metrics_long,
        "orders_long": orders_long,
    }


def get_data_overview(data_model: dict) -> dict:
    """
    Genera un resumen simple del modelo de datos.
    """
    metrics_raw = data_model["metrics_raw"]
    orders_raw = data_model["orders_raw"]
    summary_raw = data_model["summary_raw"]
    metrics_long = data_model["metrics_long"]
    orders_long = data_model["orders_long"]

    overview = {
        "metrics_raw_shape": metrics_raw.shape,
        "orders_raw_shape": orders_raw.shape,
        "summary_raw_shape": summary_raw.shape,
        "metrics_long_shape": metrics_long.shape,
        "orders_long_shape": orders_long.shape,
        "metrics_unique_countries": metrics_long["country"].nunique(),
        "metrics_unique_cities": metrics_long["city"].nunique(),
        "metrics_unique_zones": metrics_long["zone"].nunique(),
        "metrics_unique_metrics": metrics_long["metric"].nunique(),
        "orders_unique_countries": orders_long["country"].nunique(),
        "orders_unique_cities": orders_long["city"].nunique(),
        "orders_unique_zones": orders_long["zone"].nunique(),
        "orders_unique_metrics": orders_long["metric"].nunique(),
    }

    return overview
