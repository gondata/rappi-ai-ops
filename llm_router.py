import json
import re
import unicodedata
from typing import Any, Dict

from openai import OpenAI

from config import (
    DEFAULT_MODEL_NAME,
    OPENAI_API_KEY,
    METRIC_ALIASES,
    SUPPORTED_AGGREGATIONS,
    SUPPORTED_INTENTS,
    SUPPORTED_ANALYSIS_TYPES,
    SUPPORTED_GROUP_BY,
    SUPPORTED_TIME_SCOPE,
)
from prompts import ROUTER_SYSTEM_PROMPT


class LLMRouter:
    """
    Router LLM para convertir preguntas en intents estructurados.
    Usa Structured Outputs si hay API key.
    Si no hay API key o falla el LLM, cae a un fallback seguro.
    """

    FOLLOW_UP_MARKERS = [
        "what about",
        "and now",
        "and for",
        "how about",
        "same for",
        "same but",
        "now show",
        "show me now",
        "compare that",
        "that across",
        "those",
        "that one",
        "y ahora",
        "y para",
        "que pasa con",
        "que tal",
        "mostra ahora",
        "mostrame ahora",
        "comparalo",
        "eso entre",
        "esas",
        "esa",
    ]

    CITY_CANONICAL_MAP = {
        "bogota": "Bogota",
        "lima": "Lima",
        "mexico city": "Mexico City",
        "santiago": "Santiago",
        "buenos aires": "Buenos Aires",
    }

    COUNTRY_CANONICAL_MAP = {
        "colombia": "CO",
        "peru": "PE",
        "mexico": "MX",
        "chile": "CL",
        "argentina": "AR",
        "costa rica": "CR",
        "ecuador": "EC",
        "uruguay": "UY",
        "brazil": "BR",
        "brasil": "BR",
        "co": "CO",
        "pe": "PE",
        "mx": "MX",
        "cl": "CL",
        "ar": "AR",
        "cr": "CR",
        "ec": "EC",
        "uy": "UY",
        "br": "BR",
    }

    ZONE_TYPE_MAP = {
        "dense": "Dense",
        "sparse": "Sparse",
        "wealthy": "Wealthy",
        "non wealthy": "Non Wealthy",
        "non-wealthy": "Non Wealthy",
    }

    PRIORITY_MAP = {
        "high priority": "High Priority",
        "prioritized": "Prioritized",
        "not prioritized": "Not Prioritized",
    }

    BUSINESS_INTENT_DEFAULTS = {
        "problematic": {
            "intent": "anomaly_check",
            "analysis_type": "anomaly",
            "metric": "Perfect Orders",
            "group_by": "zone",
        },
        "low_margin": {
            "intent": "anomaly_check",
            "analysis_type": "anomaly",
            "metric": "Gross Profit UE",
            "group_by": "zone",
        },
        "low_conversion": {
            "intent": "anomaly_check",
            "analysis_type": "anomaly",
            "metric": "Non-Pro PTC > OP",
            "group_by": "zone",
        },
        "low_lead_penetration": {
            "intent": "anomaly_check",
            "analysis_type": "anomaly",
            "metric": "Lead Penetration",
            "group_by": "zone",
        },
        "low_pro_adoption": {
            "intent": "anomaly_check",
            "analysis_type": "anomaly",
            "metric": "Pro Adoption",
            "group_by": "zone",
        },
        "growth": {
            "intent": "anomaly_check",
            "analysis_type": "anomaly",
            "metric": "Orders",
            "group_by": "zone",
        },
    }

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key: str = OPENAI_API_KEY):
        self.model_name = model_name
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None

    def _build_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": SUPPORTED_INTENTS,
                },
                "metric": {
                    "type": ["string", "null"],
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "country": {"type": ["string", "null"]},
                        "city": {"type": ["string", "null"]},
                        "zone": {"type": ["string", "null"]},
                        "zone_type": {"type": ["string", "null"]},
                        "zone_prioritization": {"type": ["string", "null"]},
                    },
                    "required": ["country", "city", "zone", "zone_type", "zone_prioritization"],
                    "additionalProperties": False,
                },
                "group_by": {
                    "type": ["string", "null"],
                },
                "secondary_metric": {
                    "type": ["string", "null"],
                },
                "aggregation": {
                    "type": ["string", "null"],
                    "enum": SUPPORTED_AGGREGATIONS + [None],
                },
                "rank_limit": {
                    "type": ["integer", "null"],
                },
                "comparison": {
                    "type": ["string", "null"],
                },
                "time_scope": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "analysis_type": {
                    "type": "string",
                    "enum": SUPPORTED_ANALYSIS_TYPES,
                },
                "chart_requested": {
                    "type": "boolean",
                },
            },
            "required": [
                "intent",
                "metric",
                "filters",
                "group_by",
                "secondary_metric",
                "aggregation",
                "rank_limit",
                "comparison",
                "time_scope",
                "analysis_type",
                "chart_requested",
            ],
            "additionalProperties": False,
        }

    def _build_user_prompt(self, user_query: str, memory_context: dict | None = None) -> str:
        return f"""
User query:
{user_query}

Conversation memory:
{json.dumps(memory_context or {}, ensure_ascii=False, indent=2)}

Return a structured JSON object following the schema.
""".strip()

    def _normalize_text(self, value) -> str:
        if value is None:
            return ""
        value = str(value).strip().lower()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return value

    def _empty_filters(self) -> dict:
        return {
            "country": None,
            "city": None,
            "zone": None,
            "zone_type": None,
            "zone_prioritization": None,
        }

    def _extract_metric(self, lowered: str) -> str | None:
        normalized_query = self._normalize_text(lowered)

        alias_candidates = sorted(METRIC_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
        for alias, canonical in alias_candidates:
            if self._normalize_text(alias) in normalized_query:
                return canonical

        return None

    def _canonicalize_metric(self, metric: str | None) -> str | None:
        if not metric:
            return metric

        normalized_metric = self._normalize_text(metric)
        for alias, canonical in sorted(METRIC_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if self._normalize_text(alias) == normalized_metric:
                return canonical

        return metric

    def _canonicalize_filter_value(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = self._normalize_text(value)

        if key == "country":
            return self.COUNTRY_CANONICAL_MAP.get(normalized_value, value)

        if key == "city":
            return self.CITY_CANONICAL_MAP.get(normalized_value, value)

        if key == "zone_type":
            return self.ZONE_TYPE_MAP.get(normalized_value, value)

        if key == "zone_prioritization":
            return self.PRIORITY_MAP.get(normalized_value, value)

        return value

    def _extract_secondary_metric(self, lowered: str, primary_metric: str | None) -> str | None:
        normalized_query = self._normalize_text(lowered)

        if not any(connector in normalized_query for connector in [" but ", " while ", " pero ", " y ", " con "]):
            return None

        alias_candidates = sorted(METRIC_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
        matched_metrics = []
        for alias, canonical in alias_candidates:
            if self._normalize_text(alias) in normalized_query and canonical not in matched_metrics:
                matched_metrics.append(canonical)

        for metric in matched_metrics:
            if metric != primary_metric:
                return metric

        return None

    def _extract_time_scope(self, lowered: str) -> list[str]:
        lowered = self._normalize_text(lowered)

        if any(token in lowered for token in ["esta semana", "this week", "ultima semana", "last week", "semana actual", "current week"]):
            return ["L0W"]

        if any(token in lowered for token in ["last 3 weeks", "last three weeks", "ultimas 3 semanas", "ultimas tres semanas"]):
            return ["L2W", "L1W", "L0W"]

        if any(token in lowered for token in ["last 5 weeks", "last five weeks", "ultimas 5 semanas", "ultimas cinco semanas"]):
            return ["L4W", "L3W", "L2W", "L1W", "L0W"]

        if any(token in lowered for token in ["last 8 weeks", "last eight weeks", "ultimas 8 semanas", "ultimas ocho semanas"]):
            return ["L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]

        if any(token in lowered for token in ["trend", "over time", "evolution", "last weeks", "tendencia", "evolucion", "en el tiempo", "ultimas semanas"]):
            return ["L4W", "L3W", "L2W", "L1W", "L0W"]

        return ["L4W", "L3W", "L2W", "L1W", "L0W"]

    def _extract_group_by(self, lowered: str, intent: str) -> str | None:
        lowered = self._normalize_text(lowered)

        if any(
            token in lowered
            for token in [
                "across cities",
                "by city",
                "cities",
                "city level",
                "entre ciudades",
                "por ciudad",
                "ciudades",
                "ciudad",
            ]
        ):
            return "city"

        if any(
            token in lowered
            for token in [
                "across zones",
                "by zone",
                "zones",
                "zone level",
                "entre zonas",
                "por zona",
                "zonas",
                "zona",
            ]
        ):
            return "zone"

        if any(
            token in lowered
            for token in [
                "across countries",
                "by country",
                "countries",
                "country level",
                "entre paises",
                "por pais",
                "paises",
                "pais",
            ]
        ):
            return "country"

        if "zone type" in lowered or "tipo de zona" in lowered:
            return "zone_type"

        if "wealthy" in lowered or "non wealthy" in lowered or "non-wealthy" in lowered:
            return "zone_type"

        if "priority zones" in lowered or "prioritization" in lowered or "priorizacion" in lowered or "zonas priorizadas" in lowered:
            return "zone_prioritization"

        if intent == "ranking":
            return "zone"

        if intent == "comparison":
            return "city"

        return None

    def _extract_aggregation(self, lowered: str, metric: str | None = None) -> str | None:
        normalized = self._normalize_text(lowered)

        if any(token in normalized for token in ["average", "avg", "mean", "promedio"]):
            return "mean"

        if any(token in normalized for token in ["total", "sum", "suma"]):
            return "sum"

        if metric and self._normalize_text(metric) == "orders":
            return "sum"

        return None

    def _extract_rank_limit(self, user_query: str, intent: str) -> int | None:
        if intent not in {"ranking", "anomaly_check"}:
            return None

        match = re.search(r"\btop\s+(\d+)\b", user_query, flags=re.IGNORECASE)
        if not match:
            match = re.search(r"\b(\d+)\s+(?:zones|cities|countries|zonas|ciudades|paises)\b", user_query, flags=re.IGNORECASE)

        if not match:
            return None

        try:
            return max(1, int(match.group(1)))
        except ValueError:
            return None

    def _extract_comparison_text(self, user_query: str) -> str | None:
        match = re.search(
            r"([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+?)\s+vs\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)",
            user_query,
            flags=re.IGNORECASE,
        )
        if match:
            left = match.group(1).strip()
            right = match.group(2).strip()

            left = re.sub(r"^(compare|show|what about|and now|compara|comparar|mostra|mostrame|mostrar|y ahora)\s+", "", left, flags=re.IGNORECASE).strip()
            left = re.sub(r"\b(for|para)\b$", "", left, flags=re.IGNORECASE).strip()

            if left and right:
                return f"{left} vs {right.strip()}"

        return None

    def _extract_business_mode(self, lowered: str) -> str | None:
        normalized = self._normalize_text(lowered)

        if any(
            token in normalized
            for token in [
                "bajo margen",
                "baja ganancia",
                "margen bajo",
                "problemas de margen",
                "zonas con bajo gross profit",
                "zonas con margen bajo",
                "baja rentabilidad",
            ]
        ):
            return "low_margin"

        if any(
            token in normalized
            for token in [
                "baja conversion",
                "bajo conversion",
                "problemas de conversion",
                "zonas con baja conversion",
                "zonas con bajo checkout",
                "bajo checkout",
            ]
        ):
            return "low_conversion"

        if any(
            token in normalized
            for token in [
                "baja penetracion",
                "bajo lead penetration",
                "problemas de penetracion",
                "zonas con baja penetracion",
                "zonas con pocas tiendas habilitadas",
            ]
        ):
            return "low_lead_penetration"

        if any(
            token in normalized
            for token in [
                "baja adopcion pro",
                "bajo pro adoption",
                "problemas de adopcion",
                "zonas con baja adopcion",
                "zonas con pocos usuarios pro",
            ]
        ):
            return "low_pro_adoption"

        if any(token in normalized for token in ["problematic zones", "problem zones", "zonas problematicas", "underperforming zones", "zonas con problemas", "zonas criticas", "bajo rendimiento", "mal rendimiento", "peor performance", "zonas debiles"]):
            return "problematic"

        if any(
            token in normalized
            for token in [
                "growth opportunities",
                "growth zones",
                "zonas de crecimiento",
                "fastest growing zones",
                "oportunidades de crecimiento",
                "mas crecen en ordenes",
            ]
        ):
            return "growth"

        return None

    def _extract_filters(self, lowered: str, intent: str, user_query: str) -> dict:
        normalized = self._normalize_text(lowered)
        filters = self._empty_filters()

        comparison_text = self._extract_comparison_text(user_query)
        normalized_comparison = self._normalize_text(comparison_text) if comparison_text else ""

        for city_key, city_value in self.CITY_CANONICAL_MAP.items():
            if city_key in normalized:
                if comparison_text and city_key in normalized_comparison:
                    continue
                if "across cities" in normalized or "entre ciudades" in normalized:
                    continue
                filters["city"] = city_value
                break

        for country_key, country_value in self.COUNTRY_CANONICAL_MAP.items():
            if re.search(rf"\b{re.escape(country_key)}\b", normalized):
                filters["country"] = country_value
                break

        for zone_type_key, zone_type_value in self.ZONE_TYPE_MAP.items():
            if zone_type_key in normalized:
                filters["zone_type"] = zone_type_value
                break

        for priority_key, priority_value in self.PRIORITY_MAP.items():
            if priority_key in normalized:
                filters["zone_prioritization"] = priority_value
                break

        zone_match = re.search(r"zone\s+([a-z0-9]+)", user_query, flags=re.IGNORECASE)
        if zone_match and "across zones" not in normalized:
            zone_suffix = zone_match.group(1).upper()
            filters["zone"] = f"Zone {zone_suffix}"

        if not filters["city"] and not filters["country"] and not filters["zone"]:
            named_location_match = re.search(
                r"\b(?:en|in)\s+([A-Za-zÀ-ÿ0-9 _-]+?)(?:\s+(?:ultimas?|last|over|entre|across|por|this week|esta semana)\b|$)",
                user_query,
                flags=re.IGNORECASE,
            )
            if named_location_match:
                candidate = named_location_match.group(1).strip(" ?!.")
                normalized_candidate = self._normalize_text(candidate)
                candidate_words = [word for word in normalized_candidate.split() if word]
                blocked_words = {
                    "ordenes",
                    "orders",
                    "perfect",
                    "lead",
                    "gross",
                    "profit",
                    "ultimas",
                    "semanas",
                    "las",
                    "los",
                    "this",
                    "week",
                    "semana",
                }
                if candidate and len(candidate_words) <= 3 and not any(word in blocked_words for word in candidate_words):
                    filters["zone"] = candidate

        if intent == "comparison" and ("vs" in normalized or "across cities" in normalized or "entre ciudades" in normalized):
            filters["city"] = None

        if intent == "comparison" and ("across countries" in normalized or "entre paises" in normalized):
            filters["country"] = None

        if intent == "comparison" and ("across zones" in normalized or "entre zonas" in normalized):
            filters["zone"] = None

        return filters

    def _is_follow_up(self, lowered: str, memory_context: dict | None) -> bool:
        normalized = self._normalize_text(lowered)

        if any(marker in normalized for marker in self.FOLLOW_UP_MARKERS):
            return True

        if memory_context and normalized in self.CITY_CANONICAL_MAP:
            return True

        if memory_context and normalized in self.COUNTRY_CANONICAL_MAP:
            return True

        if memory_context and any(
            phrase in normalized
            for phrase in ["last 3 weeks", "last 5 weeks", "last 8 weeks", "ultimas 3 semanas", "ultimas 5 semanas", "ultimas 8 semanas"]
        ):
            return True

        return False

    def _inherit_from_memory(self, parsed: Dict[str, Any], memory_context: dict | None) -> Dict[str, Any]:
        if not memory_context:
            return parsed

        parsed.setdefault("filters", self._empty_filters())

        last_metric = memory_context.get("last_metric")
        last_filters = memory_context.get("last_filters") or {}
        last_dimension = memory_context.get("last_dimension")
        last_intent = memory_context.get("last_intent") or {}
        last_time_scope = last_intent.get("time_scope") or memory_context.get("last_time_scope")

        if not parsed.get("metric") and last_metric:
            parsed["metric"] = last_metric

        if not parsed.get("group_by") and last_dimension:
            parsed["group_by"] = last_dimension

        if not parsed.get("time_scope") and last_time_scope:
            parsed["time_scope"] = last_time_scope

        for key in ["country", "city", "zone", "zone_type", "zone_prioritization"]:
            if parsed["filters"].get(key) is None and key in last_filters:
                parsed["filters"][key] = last_filters.get(key)

        return parsed

    def _sanitize_parsed_output(
        self,
        parsed: Dict[str, Any],
        user_query: str,
        memory_context: dict | None = None,
    ) -> Dict[str, Any]:
        lowered = self._normalize_text(user_query)

        parsed.setdefault("filters", {})
        for key in ["country", "city", "zone", "zone_type", "zone_prioritization"]:
            parsed["filters"].setdefault(key, None)

        parsed["metric"] = self._canonicalize_metric(parsed.get("metric"))
        parsed["secondary_metric"] = self._canonicalize_metric(parsed.get("secondary_metric"))
        for key in ["country", "city", "zone", "zone_type", "zone_prioritization"]:
            parsed["filters"][key] = self._canonicalize_filter_value(key, parsed["filters"].get(key))

        extracted_filters = self._extract_filters(lowered, parsed.get("intent", "unknown"), user_query)
        for key in ["country", "city", "zone", "zone_type", "zone_prioritization"]:
            if parsed["filters"].get(key) is None and extracted_filters.get(key) is not None:
                parsed["filters"][key] = extracted_filters.get(key)

        known_cities = set(self.CITY_CANONICAL_MAP.values())
        parsed_city = parsed["filters"].get("city")
        extracted_zone = extracted_filters.get("zone")
        if parsed_city and parsed_city not in known_cities and extracted_zone and parsed["filters"].get("zone") is None:
            if self._normalize_text(parsed_city) == self._normalize_text(extracted_zone):
                parsed["filters"]["zone"] = extracted_zone
                parsed["filters"]["city"] = None

        if parsed_city and parsed_city not in known_cities and parsed["filters"].get("zone") is None:
            normalized_city = self._normalize_text(parsed_city)
            if re.search(rf"\b(?:en|in)\s+{re.escape(normalized_city)}\b", lowered):
                parsed["filters"]["zone"] = parsed_city
                parsed["filters"]["city"] = None

        if not parsed.get("metric"):
            parsed["metric"] = self._extract_metric(lowered)

        # For anomaly_check: only keep a metric if it was explicitly mentioned in the query.
        # Prevents the LLM from inferring "Perfect Orders" from vague words like "problemáticas".
        if parsed.get("intent") == "anomaly_check" and parsed.get("metric"):
            metric_words = [
                w for w in self._normalize_text(parsed["metric"]).split() if len(w) > 3
            ]
            if metric_words and not any(w in lowered for w in metric_words):
                parsed["metric"] = None

        if not parsed.get("time_scope"):
            parsed["time_scope"] = self._extract_time_scope(lowered)

        if not parsed.get("group_by"):
            parsed["group_by"] = self._extract_group_by(lowered, parsed.get("intent", "unknown"))

        if not parsed.get("aggregation"):
            parsed["aggregation"] = self._extract_aggregation(lowered, parsed.get("metric"))

        if parsed.get("rank_limit") is None:
            parsed["rank_limit"] = self._extract_rank_limit(user_query, parsed.get("intent", "unknown"))

        if not parsed.get("secondary_metric"):
            parsed["secondary_metric"] = self._extract_secondary_metric(lowered, parsed.get("metric"))

        business_mode = self._extract_business_mode(lowered)
        if business_mode:
            defaults = self.BUSINESS_INTENT_DEFAULTS[business_mode]
            parsed["intent"] = defaults["intent"]
            parsed["analysis_type"] = defaults["analysis_type"]
            if not parsed.get("metric"):
                parsed["metric"] = defaults["metric"]
            if not parsed.get("group_by"):
                parsed["group_by"] = defaults["group_by"]
            if parsed.get("rank_limit") is None:
                parsed["rank_limit"] = 5

        if self._is_follow_up(lowered, memory_context):
            parsed = self._inherit_from_memory(parsed, memory_context)

            # Si no vino métrica explícita en el follow-up, heredarla sí o sí
            if not parsed.get("metric") and memory_context:
                parsed["metric"] = memory_context.get("last_metric")

            # Si no vino group_by explícito, heredar dimensión previa
            if not parsed.get("group_by") and memory_context:
                parsed["group_by"] = memory_context.get("last_dimension")

            # Si no vino time_scope explícito, heredar el anterior
            if not parsed.get("time_scope") and memory_context:
                last_intent = memory_context.get("last_intent") or {}
                parsed["time_scope"] = (
                    last_intent.get("time_scope")
                    or memory_context.get("last_time_scope")
                    or parsed.get("time_scope")
                )

            # sobrescribir city si el follow-up trae una nueva explícita
            for city_key, city_value in self.CITY_CANONICAL_MAP.items():
                if city_key in lowered:
                    parsed["filters"]["city"] = city_value
                    break

            for country_key, country_value in self.COUNTRY_CANONICAL_MAP.items():
                if re.search(rf"\b{re.escape(country_key)}\b", lowered):
                    parsed["filters"]["country"] = country_value
                    break

        if "across cities" in lowered or "entre ciudades" in lowered:
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"
            parsed["group_by"] = "city"
            parsed["filters"]["city"] = None

        if "across zones" in lowered or "entre zonas" in lowered:
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"
            parsed["group_by"] = "zone"
            parsed["filters"]["zone"] = None

        if "across countries" in lowered or "entre paises" in lowered:
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"
            parsed["group_by"] = "country"
            parsed["filters"]["country"] = None

        if "top zones by" in lowered or "top zonas por" in lowered:
            parsed["intent"] = "ranking"
            parsed["analysis_type"] = "ranking"
            parsed["group_by"] = "zone"
            parsed["filters"]["zone"] = None

        if "top cities by" in lowered or "top ciudades por" in lowered:
            parsed["intent"] = "ranking"
            parsed["analysis_type"] = "ranking"
            parsed["group_by"] = "city"
            parsed["filters"]["city"] = None

        if parsed.get("rank_limit") is not None and any(
            token in lowered for token in ["mayor", "mejor", "highest", "top"]
        ):
            parsed["intent"] = "ranking"
            parsed["analysis_type"] = "ranking"
            parsed["group_by"] = parsed.get("group_by") or "zone"

        if all(token in lowered for token in ["wealthy", "non wealthy"]) or all(
            token in lowered for token in ["wealthy", "non-wealthy"]
        ):
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"
            parsed["group_by"] = "zone_type"
            parsed["filters"]["zone_type"] = None

        if parsed.get("aggregation") == "mean" and parsed.get("group_by"):
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"

        if any(token in lowered for token in ["average by", "avg by", "mean by", "promedio por"]):
            if parsed.get("group_by"):
                parsed["intent"] = "comparison"
                parsed["analysis_type"] = "comparison"

        if parsed.get("secondary_metric") and any(token in lowered for token in ["high", "low", "but", "while", "alto", "alta", "bajo", "baja", "pero"]):
            parsed["intent"] = "distribution"
            parsed["analysis_type"] = "distribution"
            parsed["group_by"] = parsed.get("group_by") or "zone"

        if parsed.get("group_by") == "zone_type" and any(
            token in lowered for token in ["compare", "comparison", "vs", "wealthy", "non wealthy", "non-wealthy", "compar", "rico", "no rico"]
        ):
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"
            parsed["filters"]["zone_type"] = None

        if any(token in lowered for token in ["esta semana", "this week", "ultima semana", "last week", "semana actual", "current week"]):
            parsed["time_scope"] = ["L0W"]

        if any(token in lowered for token in ["last 5 weeks", "last five weeks", "ultimas 5 semanas", "ultimas cinco semanas"]):
            parsed["time_scope"] = ["L4W", "L3W", "L2W", "L1W", "L0W"]

        if any(token in lowered for token in ["last 3 weeks", "last three weeks", "ultimas 3 semanas", "ultimas tres semanas"]):
            parsed["time_scope"] = ["L2W", "L1W", "L0W"]

        if any(token in lowered for token in ["last 8 weeks", "last eight weeks", "ultimas 8 semanas", "ultimas ocho semanas"]):
            parsed["time_scope"] = ["L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]

        comparison_text = self._extract_comparison_text(user_query)
        if comparison_text:
            parsed["intent"] = "comparison"
            parsed["analysis_type"] = "comparison"
            parsed["comparison"] = comparison_text

            if parsed.get("group_by") is None:
                parsed["group_by"] = "city"

            if parsed["group_by"] == "city":
                parsed["filters"]["city"] = None

        if parsed.get("intent") == "follow_up":
            if "across cities" in lowered or "entre ciudades" in lowered:
                parsed["intent"] = "comparison"
                parsed["analysis_type"] = "comparison"
                parsed["group_by"] = "city"
                parsed["filters"]["city"] = None
            elif "across zones" in lowered or "entre zonas" in lowered:
                parsed["intent"] = "comparison"
                parsed["analysis_type"] = "comparison"
                parsed["group_by"] = "zone"
                parsed["filters"]["zone"] = None
            elif any(token in lowered for token in ["trend", "last 3 weeks", "last 5 weeks", "last 8 weeks", "tendencia", "ultimas 3 semanas", "ultimas 5 semanas", "ultimas 8 semanas"]):
                parsed["intent"] = "trend_analysis"
                parsed["analysis_type"] = "trend"
            elif parsed.get("group_by"):
                parsed["intent"] = "comparison"
                parsed["analysis_type"] = "comparison"
            else:
                parsed["intent"] = "metric_lookup"
                parsed["analysis_type"] = "value_lookup"

        parsed["chart_requested"] = bool(parsed.get("chart_requested", False))
        parsed["comparison"] = parsed.get("comparison")
        parsed["aggregation"] = parsed.get("aggregation")
        parsed["secondary_metric"] = parsed.get("secondary_metric")

        if parsed.get("intent") not in SUPPORTED_INTENTS:
            parsed["intent"] = "unknown"

        if parsed.get("analysis_type") not in SUPPORTED_ANALYSIS_TYPES:
            parsed["analysis_type"] = "unknown"

        if parsed.get("group_by") not in SUPPORTED_GROUP_BY:
            parsed["group_by"] = None

        if parsed.get("aggregation") not in SUPPORTED_AGGREGATIONS:
            parsed["aggregation"] = None

        if parsed.get("rank_limit") is not None:
            try:
                parsed["rank_limit"] = max(1, int(parsed["rank_limit"]))
            except Exception:
                parsed["rank_limit"] = None

        if not parsed.get("time_scope"):
            parsed["time_scope"] = ["L4W", "L3W", "L2W", "L1W", "L0W"]

        parsed["time_scope"] = [w for w in parsed["time_scope"] if w in SUPPORTED_TIME_SCOPE]

        if not parsed["time_scope"]:
            parsed["time_scope"] = ["L4W", "L3W", "L2W", "L1W", "L0W"]

        final_city = parsed["filters"].get("city")
        final_zone = parsed["filters"].get("zone")
        if final_city and final_zone and final_city not in known_cities:
            if self._normalize_text(final_city) == self._normalize_text(final_zone):
                parsed["filters"]["city"] = None

        return parsed

    def _fallback_parse(self, user_query: str, memory_context: dict | None = None) -> Dict[str, Any]:
        lowered = self._normalize_text(user_query)

        intent = "unknown"
        analysis_type = "unknown"

        if self._is_follow_up(lowered, memory_context):
            intent = "follow_up"
            analysis_type = "follow_up"
        elif any(token in lowered for token in ["high", "low", "alto", "alta", "bajo", "baja"]) and any(
            connector in lowered for connector in [" but ", " while ", " pero "]
        ):
            intent = "distribution"
            analysis_type = "distribution"
        elif self._extract_business_mode(lowered) == "problematic":
            intent = "anomaly_check"
            analysis_type = "anomaly"
        elif self._extract_business_mode(lowered) == "growth":
            intent = "anomaly_check"
            analysis_type = "anomaly"
        elif "top " in lowered or "rank" in lowered or re.search(
            r"\b\d+\s+(zones|cities|countries|zonas|ciudades|paises)\b", lowered
        ):
            intent = "ranking"
            analysis_type = "ranking"
        elif any(token in lowered for token in ["mayor", "highest"]) and re.search(
            r"\b\d+\s+(zones|cities|countries|zonas|ciudades|paises)\b", lowered
        ):
            intent = "ranking"
            analysis_type = "ranking"
        elif any(token in lowered for token in ["compare", "compar", " vs ", "across", "entre"]):
            intent = "comparison"
            analysis_type = "comparison"
        elif any(
            token in lowered
            for token in ["trend", "evolution", "over time", "last 5 weeks", "last 3 weeks", "last 8 weeks", "tendencia", "evolucion", "en el tiempo", "ultimas 5 semanas", "ultimas 3 semanas", "ultimas 8 semanas"]
        ):
            intent = "trend_analysis"
            analysis_type = "trend"
        elif any(token in lowered for token in ["show", "what is", "how many", "current", "latest", "mostra", "mostrar", "mostrame", "cual es", "cuanto", "actual", "ultimo"]):
            intent = "metric_lookup"
            analysis_type = "value_lookup"

        metric = self._extract_metric(lowered)
        secondary_metric = self._extract_secondary_metric(lowered, metric)
        time_scope = self._extract_time_scope(lowered)
        group_by = self._extract_group_by(lowered, intent)
        aggregation = self._extract_aggregation(lowered, metric)
        rank_limit = self._extract_rank_limit(user_query, intent)
        comparison = self._extract_comparison_text(user_query)
        filters = self._extract_filters(lowered, intent, user_query)
        chart_requested = any(word in lowered for word in ["chart", "plot", "graph", "grafico", "gráfico"])

        parsed = {
            "intent": intent,
            "metric": metric,
            "filters": filters,
            "group_by": group_by,
            "secondary_metric": secondary_metric,
            "aggregation": aggregation,
            "rank_limit": rank_limit,
            "comparison": comparison,
            "time_scope": time_scope,
            "analysis_type": analysis_type,
            "chart_requested": chart_requested,
        }

        return self._sanitize_parsed_output(parsed, user_query, memory_context)

    def parse(self, user_query: str, memory_context: dict | None = None) -> Dict[str, Any]:
        if not self.client:
            fallback = self._fallback_parse(user_query, memory_context)
            fallback["router_mode"] = "fallback_no_api_key"
            return fallback

        try:
            response = self.client.responses.create(
                model=self.model_name,
                instructions=ROUTER_SYSTEM_PROMPT,
                input=self._build_user_prompt(user_query, memory_context),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "router_output",
                        "schema": self._build_schema(),
                        "strict": True,
                    }
                },
            )

            parsed = json.loads(response.output_text)
            parsed = self._sanitize_parsed_output(parsed, user_query, memory_context)
            parsed["router_mode"] = "llm_structured_output"
            return parsed

        except Exception as e:
            fallback = self._fallback_parse(user_query, memory_context)
            fallback["router_mode"] = f"fallback_error: {str(e)}"
            return fallback
