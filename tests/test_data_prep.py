import pandas as pd

from data_prep import clean_long_format, standardize_text_columns, melt_metrics_data


def test_standardize_text_columns_trims_strings_without_stringifying_nulls():
    df = pd.DataFrame(
        {
            "COUNTRY": ["  CO  ", None, ""],
            "CITY": ["  Bogota ", float("nan"), "   "],
        }
    )

    result = standardize_text_columns(df)

    assert result.loc[0, "COUNTRY"] == "CO"
    assert result.loc[0, "CITY"] == "Bogota"
    assert pd.isna(result.loc[1, "COUNTRY"])
    assert pd.isna(result.loc[1, "CITY"])
    assert pd.isna(result.loc[2, "COUNTRY"])
    assert pd.isna(result.loc[2, "CITY"])


def test_clean_long_format_coerces_numeric_and_drops_invalid_rows():
    df = pd.DataFrame(
        {
            "country": ["CO", "CO", "CO", "CO"],
            "city": ["Bogota", "Bogota", "Bogota", "Bogota"],
            "zone": ["Zone A", "Zone A", "Zone A", "Zone A"],
            "metric": ["Perfect Orders"] * 4,
            "week_raw": ["L1W_ROLL", "L0W_ROLL", "L0W_ROLL", "BAD_WEEK"],
            "value": ["0.91", "not_a_number", "0.95", "0.96"],
            "week": ["L1W", "L0W", "L0W", None],
            "dataset": ["metrics"] * 4,
        }
    )

    result = clean_long_format(df)

    assert len(result) == 2
    assert result.loc[0, "value"] == 0.91
    assert result.loc[0, "week"] == "L1W"
    assert result.loc[1, "value"] == 0.95
    assert result.loc[1, "week"] == "L0W"


def test_clean_long_format_deduplicates_exact_rows():
    df = pd.DataFrame(
        {
            "country": ["CO", "CO"],
            "city": ["Bogota", "Bogota"],
            "zone": ["Zone A", "Zone A"],
            "metric": ["Perfect Orders", "Perfect Orders"],
            "week_raw": ["L0W_ROLL", "L0W_ROLL"],
            "value": [0.95, 0.95],
            "week": ["L0W", "L0W"],
            "dataset": ["metrics", "metrics"],
        }
    )

    result = clean_long_format(df)

    assert len(result) == 1


def test_melt_metrics_data_returns_long_format():
    df = pd.DataFrame(
        {
            "COUNTRY": ["CO"],
            "CITY": ["Bogota"],
            "ZONE": ["Zone A"],
            "ZONE_TYPE": ["Dense"],
            "ZONE_PRIORITIZATION": ["High"],
            "METRIC": ["Perfect Orders"],
            "L8W_ROLL": [90],
            "L7W_ROLL": [91],
            "L6W_ROLL": [92],
            "L5W_ROLL": [93],
            "L4W_ROLL": [94],
            "L3W_ROLL": [95],
            "L2W_ROLL": [96],
            "L1W_ROLL": [97],
            "L0W_ROLL": [98],
        }
    )

    result = melt_metrics_data(df)

    assert len(result) == 9
    assert "week" in result.columns
    assert "value" in result.columns
    assert result["dataset"].iloc[0] == "metrics"
