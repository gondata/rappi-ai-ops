from utils import display_filter_value, display_value


def pretty_group(group_by: str | None, singular: bool = False) -> str:
    labels = {
        "city": ("ciudades", "ciudad"),
        "zone": ("zonas", "zona"),
        "country": ("países", "país"),
        "zone_type": ("tipos de zona", "tipo de zona"),
        "zone_prioritization": ("niveles de priorización", "nivel de priorización"),
    }
    plural, single = labels.get(group_by, (str(group_by or "dimensiones"), str(group_by or "dimensión")))
    return single if singular else plural


class LLMNarrator:
    """
    Redacta una respuesta ejecutiva a partir del resultado analítico.
    En esta versión, la narración es determinística para garantizar:
    - consistencia visual
    - no alucinación
    - formateo correcto de porcentajes
    """

    def __init__(self, model_name=None, api_key=None):
        self.model_name = model_name
        self.api_key = api_key
        self.client = None

    def _is_percentage_metric(self, metric_name: str | None) -> bool:
        if not metric_name:
            return False

        percentage_metrics = {
            "Perfect Orders",
            "Late Orders",
            "Defects",
            "Cancellations",
            "Lead Penetration",
            "Pro Adoption",
            "Turbo Adoption",
            "Non-Pro PTC > OP",
            "Restaurants SS > ATC CVR",
            "Restaurants SST > SS CVR",
            "Retail SST > SS CVR",
            "% PRO Users Who Breakeven",
            "% Restaurants Sessions With Optimal Assortment",
            "MLTV Top Verticals Adoption",
        }
        return metric_name in percentage_metrics

    def _fmt(self, value, metric_name: str | None = None) -> str:
        if value is None:
            return "N/D"

        try:
            numeric_value = float(value)

            if self._is_percentage_metric(metric_name):
                return f"{numeric_value * 100:,.2f}%"

            return f"{numeric_value:,.2f}"
        except Exception:
            return str(value)

    def _build_scope_text(self, filters: dict | None) -> str:
        if not filters:
            return ""

        ordered_keys = ["country", "city", "zone", "zone_type", "zone_prioritization"]
        parts = []

        for key in ordered_keys:
            value = filters.get(key)
            if value not in [None, ""]:
                parts.append(str(display_filter_value(key, value)))

        if not parts:
            return ""

        return f" para {' / '.join(parts)}"

    def _narrate_lookup(self, analytical_result: dict) -> str:
        raw_metric = analytical_result.get("metric", "the requested metric")
        metric = display_value(raw_metric)
        latest_week = display_value(analytical_result.get("latest_week"))
        latest_value = analytical_result.get("latest_value")
        filters = analytical_result.get("filters") or {}

        return (
            f"El último valor disponible de {metric}{self._build_scope_text(filters)} "
            f"es {self._fmt(latest_value, raw_metric)} en {latest_week}."
        )

    def _narrate_trend(self, analytical_result: dict) -> str:
        raw_metric = analytical_result.get("metric", "the requested metric")
        metric = display_value(raw_metric)
        first_week = display_value(analytical_result.get("first_week"))
        last_week = display_value(analytical_result.get("last_week"))
        first_value = analytical_result.get("first_value")
        last_value = analytical_result.get("last_value")
        delta_pct = analytical_result.get("delta_pct")
        filters = analytical_result.get("filters") or {}

        if first_value is None or last_value is None:
            return f"Encontré una consulta de tendencia para {metric}, pero la serie temporal está incompleta."

        first_value_f = float(first_value)
        last_value_f = float(last_value)

        if last_value_f > first_value_f:
            direction = "aumentó"
        elif last_value_f < first_value_f:
            direction = "disminuyó"
        else:
            direction = "se mantuvo estable"

        if direction == "se mantuvo estable":
            return (
                f"{metric}{self._build_scope_text(filters)} se mantuvo bastante estable entre "
                f"{first_week} y {last_week}, alrededor de {self._fmt(last_value, raw_metric)}."
            )

        delta_pct_text = ""
        if delta_pct is not None:
            delta_pct_text = f" ({float(delta_pct):,.2f}%)"

        return (
            f"{metric}{self._build_scope_text(filters)} {direction} desde "
            f"{self._fmt(first_value, raw_metric)} en {first_week} hasta "
            f"{self._fmt(last_value, raw_metric)} en {last_week}{delta_pct_text}."
        )

    def _narrate_comparison(self, analytical_result: dict) -> str:
        raw_metric = analytical_result.get("metric", "the requested metric")
        metric = display_value(raw_metric)
        latest_week = display_value(analytical_result.get("latest_week"))
        latest_snapshot = analytical_result.get("latest_snapshot", [])
        group_by = analytical_result.get("group_by", "dimension")

        if not latest_snapshot:
            return f"Encontré una consulta de comparación para {metric}, pero no hay snapshot reciente disponible."

        ordered = sorted(
            latest_snapshot,
            key=lambda x: float(x.get("value", 0)),
            reverse=True,
        )

        top = ordered[0]
        bottom = ordered[-1]

        top_name = top.get(group_by, "Top entity")
        bottom_name = bottom.get(group_by, "Bottom entity")
        top_value = top.get("value")
        bottom_value = bottom.get("value")
        count = len(ordered)

        gap_text = ""
        if top_value is not None and bottom_value is not None:
            try:
                tv, bv = float(top_value), float(bottom_value)
                if self._is_percentage_metric(raw_metric):
                    gap_pp = abs(tv - bv) * 100
                    gap_text = f" La brecha entre ambos extremos es de {gap_pp:,.1f} pp."
                elif bv != 0:
                    gap_rel = abs((tv - bv) / abs(bv)) * 100
                    gap_text = f" La brecha relativa entre extremos es de {gap_rel:,.1f}%."
            except Exception:
                pass

        count_text = f" Se compararon {count} {pretty_group(group_by)}." if count > 2 else ""

        return (
            f"En {latest_week}, {top_name} lideró {metric} con "
            f"{self._fmt(top_value, raw_metric)}, mientras que {bottom_name} quedó último con "
            f"{self._fmt(bottom_value, raw_metric)}.{gap_text}{count_text}"
        )

    def _narrate_ranking(self, analytical_result: dict) -> str:
        raw_metric = analytical_result.get("metric", "the requested metric")
        metric = display_value(raw_metric)
        top_results = analytical_result.get("top_n") or analytical_result.get("top_10", [])
        group_by = analytical_result.get("group_by", "dimension")
        filters = analytical_result.get("filters") or {}
        rank_limit = analytical_result.get("rank_limit")

        if not top_results:
            return f"Encontré una consulta de ranking para {metric}, pero el resultado del ranking está vacío."

        leader = top_results[0]
        leader_name = leader.get(group_by, "Top entity")
        leader_value = leader.get("value")
        limit_text = f"top {rank_limit} " if rank_limit else "top "

        return (
            f"Dentro del ranking {limit_text}de {pretty_group(group_by)} para {metric}{self._build_scope_text(filters)}, "
            f"el {pretty_group(group_by, singular=True)} líder es {display_value(leader_name)}, "
            f"con un valor de {self._fmt(leader_value, raw_metric)}."
        )

    def _narrate_distribution(self, analytical_result: dict) -> str:
        raw_metric = analytical_result.get("metric", "the primary metric")
        raw_secondary_metric = analytical_result.get("secondary_metric", "the secondary metric")
        metric = display_value(raw_metric)
        secondary_metric = display_value(raw_secondary_metric)
        group_by = analytical_result.get("group_by", "dimension")
        matched_entities = analytical_result.get("matched_entities", [])
        latest_week = analytical_result.get("latest_week")

        if not matched_entities:
            return (
                f"Evalué {pretty_group(group_by)} con {metric} alto y {secondary_metric} bajo"
                f"{f' en {display_value(latest_week)}' if latest_week else ''}, "
                "pero ninguna entidad cumplió ambas condiciones en el scope seleccionado."
            )

        top_match = matched_entities[0]
        entity_name = top_match.get(group_by, "Top opportunity")
        primary_value = top_match.get("primary_value")
        secondary_value = top_match.get("secondary_value")
        matched_count = analytical_result.get("matched_count", len(matched_entities))

        return (
            f"Encontré {matched_count} {pretty_group(group_by)} con {metric} alto pero {secondary_metric} bajo"
            f"{f' en {display_value(latest_week)}' if latest_week else ''}. "
            f"El mejor candidato es {display_value(entity_name)}, con {metric} en {self._fmt(primary_value, raw_metric)} "
            f"y {secondary_metric} en {self._fmt(secondary_value, raw_secondary_metric)}."
        )

    def _narrate_anomaly(self, analytical_result: dict) -> str:
        raw_metric = analytical_result.get("metric", "the requested metric")
        metric = display_value(raw_metric)
        group_by = analytical_result.get("group_by", "dimension")
        top_results = analytical_result.get("top_n", [])
        filters = analytical_result.get("filters") or {}

        if not top_results:
            return f"Busqué movimientos inusuales en {metric}, pero no encontré un resultado rankeado suficientemente claro."

        leader = top_results[0]
        entity_name = display_value(leader.get(group_by, "Top entity"))
        delta_pct = leader.get("delta_pct")
        first_week = display_value(leader.get("first_week"))
        last_week = display_value(leader.get("last_week"))
        first_value = leader.get("first_value")
        last_value = leader.get("last_value")
        business_direction = leader.get("business_direction")
        severity = leader.get("severity", "medium")
        peer_context = analytical_result.get("peer_context") or {}
        explanatory_hints = analytical_result.get("explanatory_hints") or []

        if business_direction == "unfavorable":
            framing = "La más preocupante"
            direction_text = "se deterioró"
        elif business_direction == "favorable":
            framing = "La más destacada"
            direction_text = "mejoró"
        else:
            framing = "La más relevante"
            direction_text = "se movió"

        severity_text = ""
        if severity == "high":
            severity_text = " Es un movimiento de alta severidad."
        elif severity == "medium":
            severity_text = " Tiene suficiente magnitud como para revisarlo."

        peer_text = ""
        if peer_context.get("second_entity") and peer_context.get("second_delta_pct") is not None:
            peer_text = (
                f" La siguiente {pretty_group(group_by, singular=True)} más relevante es {display_value(peer_context['second_entity'])} "
                f"con {float(peer_context['second_delta_pct']):,.2f}%."
            )

        recommendation_text = ""
        if business_direction == "unfavorable":
            recommendation_text = " La usaría como primer candidato para una revisión de causa raíz."
        elif business_direction == "favorable" and self._fmt(last_value, raw_metric) != "N/D":
            recommendation_text = " La usaría como benchmark para entender qué está funcionando operativamente."

        explanatory_text = ""
        if business_direction == "favorable" and explanatory_hints:
            top_hints = []
            for hint in explanatory_hints[:2]:
                top_hints.append(
                    f"{display_value(hint['metric'])} pasó de {self._fmt(hint.get('first_value'), hint['metric'])} a {self._fmt(hint.get('last_value'), hint['metric'])}"
                )
            if top_hints:
                joined_hints = "; ".join(top_hints)
                explanatory_text = (
                    f" Posibles factores asociados a este crecimiento: {joined_hints}. "
                    "Lo tomaría como una señal para investigar, no como causalidad probada."
                )

        return (
            f"{framing} {pretty_group(group_by, singular=True)} para {metric}{self._build_scope_text(filters)} es {entity_name}, "
            f"que {direction_text} desde {self._fmt(first_value, raw_metric)} en {first_week} "
            f"hasta {self._fmt(last_value, raw_metric)} en {last_week} ({float(delta_pct):,.2f}%)."
            f"{severity_text}{peer_text}{recommendation_text}{explanatory_text}"
        )

    _SCOPE_SUGGESTIONS = (
        "Podés preguntarme cosas como:\n"
        "- \"Cuál es el Gross Profit UE en Bogota?\"\n"
        "- \"Mostrá las zonas problemáticas en México\"\n"
        "- \"Compara Perfect Orders entre Wealthy y Non Wealthy en Argentina\"\n"
        "- \"Qué zonas tienen alto Lead Penetration pero bajo Perfect Orders?\"\n"
        "- \"Tendencia de Turbo Adoption en Colombia últimas 5 semanas\""
    )

    def _narrate_non_success(
        self,
        status: str,
        analytical_result: dict,
        parsed_intent: dict,
        user_query: str,
    ) -> str:
        metric = analytical_result.get("metric") or parsed_intent.get("metric")
        filters = analytical_result.get("filters") or parsed_intent.get("filters") or {}
        city = filters.get("city")
        country = filters.get("country")
        location = city or country

        if status == "not_implemented":
            return (
                "No pude interpretar esa pregunta como una consulta analítica sobre los datos disponibles.\n\n"
                + self._SCOPE_SUGGESTIONS
            )

        if status == "no_data":
            parts = []
            if metric:
                parts.append(f"No encontré datos de **{metric}**")
            else:
                parts.append("No encontré datos")
            if location:
                parts.append(f"para **{location}**")
            parts.append("en el scope seleccionado.")
            base = " ".join(parts)
            return (
                f"{base}\n\n"
                "Verificá que la métrica y el filtro geográfico estén disponibles en el dataset. "
                "Podés cambiar el filtro de país, ciudad o zona para ampliar el scope."
            )

        if status == "error":
            raw_msg = analytical_result.get("message", "")
            if "requires both" in raw_msg or "primary" in raw_msg:
                return (
                    "Para este tipo de análisis necesito dos métricas: una primaria y una secundaria. "
                    "Por ejemplo: \"Qué zonas tienen alto Lead Penetration pero bajo Perfect Orders?\""
                )
            return (
                "Ocurrió un error al procesar la consulta. "
                "Intentá reformularla con una métrica y un filtro geográfico más específico."
            )

        # Fallback genérico para cualquier otro status no-success
        return (
            analytical_result.get("message")
            or "No encontré datos suficientes para responder esa pregunta."
        )

    def narrate(
        self,
        user_query: str,
        parsed_intent: dict,
        analytical_result: dict,
    ) -> str:
        status = analytical_result.get("status")
        analysis_type = analytical_result.get("analysis_type")

        if status != "success":
            return self._narrate_non_success(status, analytical_result, parsed_intent, user_query)

        if analysis_type == "value_lookup":
            return self._narrate_lookup(analytical_result)

        if analysis_type == "trend":
            return self._narrate_trend(analytical_result)

        if analysis_type == "comparison":
            return self._narrate_comparison(analytical_result)

        if analysis_type == "ranking":
            return self._narrate_ranking(analytical_result)

        if analysis_type == "distribution":
            return self._narrate_distribution(analytical_result)

        if analysis_type == "anomaly":
            return self._narrate_anomaly(analytical_result)

        return "El análisis se completó, pero aún no tengo una plantilla de narración para este tipo de resultado."
