from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
import smtplib
import textwrap

COUNTRY_DISPLAY_MAP = {
    "AR": "Argentina",
    "BR": "Brasil",
    "CL": "Chile",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "EC": "Ecuador",
    "MX": "M\u00e9xico",
    "PE": "Per\u00fa",
    "UY": "Uruguay",
}

METRIC_DISPLAY_MAP = {
    "Orders": "\u00d3rdenes",
    "Perfect Orders": "\u00d3rdenes Perfectas",
    "Lead Penetration": "Penetraci\u00f3n de Leads",
    "Gross Profit UE": "Gross Profit UE",
    "% PRO Users Who Breakeven": "% Usuarios PRO que hacen breakeven",
    "% Restaurants Sessions With Optimal Assortment": "% Sesiones con surtido \u00f3ptimo",
    "MLTV Top Verticals Adoption": "Adopci\u00f3n de verticales top en MLTV",
    "Non-Pro PTC > OP": "Conversi\u00f3n No Pro PTC > OP",
    "Pro Adoption": "Adopci\u00f3n PRO",
    "Pro Adoption (Last Week Status)": "Adopci\u00f3n PRO (estado \u00faltima semana)",
    "Restaurants Markdowns / GMV": "Markdowns de restaurantes / GMV",
    "Restaurants SS > ATC CVR": "Conversi\u00f3n restaurantes SS > ATC",
    "Restaurants SST > SS CVR": "Conversi\u00f3n restaurantes SST > SS",
    "Retail SST > SS CVR": "Conversi\u00f3n retail SST > SS",
    "Turbo Adoption": "Adopci\u00f3n Turbo",
    "Late Orders": "\u00d3rdenes Tard\u00edas",
    "Defects": "Defectos",
    "Cancellations": "Cancelaciones",
}

WEEK_DISPLAY_MAP = {
    "L0W": "Semana actual (L0W)",
    "L1W": "Hace 1 semana (L1W)",
    "L2W": "Hace 2 semanas (L2W)",
    "L3W": "Hace 3 semanas (L3W)",
    "L4W": "Hace 4 semanas (L4W)",
    "L5W": "Hace 5 semanas (L5W)",
    "L6W": "Hace 6 semanas (L6W)",
    "L7W": "Hace 7 semanas (L7W)",
    "L8W": "Hace 8 semanas (L8W)",
}

SECTION_LABELS = {
    "anomalies": "Anomal\u00edas",
    "trend_deterioration": "Deterioro de tendencia",
    "benchmarking": "Benchmarking",
    "cross_country_benchmarking": "Benchmarking internacional",
    "correlations": "Correlaciones",
    "opportunities": "Oportunidades",
}

SEVERITY_DISPLAY_MAP = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}

CATEGORY_DISPLAY_MAP = {
    "anomalies": "Anomal\u00edas",
    "anomaly": "Anomal\u00eda",
    "trend_deterioration": "Deterioro de tendencia",
    "trend_watch": "An\u00e1lisis de tendencia",
    "benchmarking": "Benchmarking",
    "cross_country_benchmarking": "Benchmarking internacional",
    "correlations": "Correlaciones",
    "correlation": "Correlaci\u00f3n",
    "opportunities": "Oportunidades",
    "opportunity": "Oportunidad",
    "operational_readout": "Lectura operativa",
}

PDF_COLORS = {
    "ink": (0.10, 0.16, 0.24),
    "muted": (0.41, 0.46, 0.55),
    "accent": (1.00, 0.33, 0.20),
    "accent_soft": (1.00, 0.93, 0.90),
    "panel": (0.98, 0.98, 0.99),
    "border": (0.93, 0.86, 0.82),
    "white": (1.00, 1.00, 1.00),
    "chip": (1.00, 0.95, 0.92),
}

SEVERITY_BAR_COLORS = {
    "high": (0.78, 0.10, 0.10),
    "medium": (1.00, 0.55, 0.00),
    "low": (0.15, 0.68, 0.38),
}

SEVERITY_BG_COLORS = {
    "high": (0.99, 0.96, 0.96),
    "medium": (1.00, 0.98, 0.94),
    "low": (0.96, 0.99, 0.97),
}


def ensure_directories(paths: list[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def display_value(value):
    if value is None or value == "":
        return value

    text = str(value)
    if text in METRIC_DISPLAY_MAP:
        return METRIC_DISPLAY_MAP[text]
    if text in WEEK_DISPLAY_MAP:
        return WEEK_DISPLAY_MAP[text]
    if text.lower() in SEVERITY_DISPLAY_MAP:
        return SEVERITY_DISPLAY_MAP[text.lower()]
    if text.lower() in CATEGORY_DISPLAY_MAP:
        return CATEGORY_DISPLAY_MAP[text.lower()]
    return COUNTRY_DISPLAY_MAP.get(text, text)


def display_filter_value(key: str, value):
    if value is None or value == "":
        return value

    if key == "country":
        return display_value(value)

    return str(display_value(value))


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_safe_text(text: str) -> str:
    return _pdf_escape(str(text)).encode("latin-1", errors="replace").decode("latin-1")


def _wrap_pdf_text(text: str, width: int = 92) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(str(text), width=width, break_long_words=False, break_on_hyphens=False) or [""]


def _wrap_card_lines(text: str, width: int = 74) -> list[str]:
    if not text:
        return []
    return textwrap.wrap(str(text), width=width, break_long_words=False, break_on_hyphens=False)


def _draw_rect(commands: list[str], x: float, y: float, width: float, height: float, fill=None, stroke=None) -> None:
    if fill:
        commands.append(f"q {fill[0]:.2f} {fill[1]:.2f} {fill[2]:.2f} rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f Q")
    if stroke:
        commands.append(
            f"q {stroke[0]:.2f} {stroke[1]:.2f} {stroke[2]:.2f} RG 0.8 w {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S Q"
        )


def _draw_text(commands: list[str], x: float, y: float, text: str, font: str, size: int, color) -> None:
    commands.append(
        f"BT /{font} {size} Tf {color[0]:.2f} {color[1]:.2f} {color[2]:.2f} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ({_pdf_safe_text(text)}) Tj ET"
    )


def _draw_wrapped_text(
    commands: list[str],
    x: float,
    y: float,
    text: str,
    font: str,
    size: int,
    color,
    width: int,
    line_gap: int,
) -> float:
    lines = _wrap_card_lines(text, width=width)
    for index, line in enumerate(lines):
        _draw_text(commands, x, y - (index * line_gap), line, font, size, color)
    if not lines:
        return y
    return y - (len(lines) * line_gap)


def _build_stat_cards(counts: dict, sections: dict, metadata: dict | None = None) -> list[dict]:
    active_categories = sum(1 for items in sections.values() if items)
    top_section = max(SECTION_LABELS, key=lambda key: len(sections.get(key, []))) if sections else "benchmarking"
    cards = [
        {"label": "Hallazgos", "value": str(sum(counts.values()))},
        {"label": "Categor\u00edas activas", "value": str(active_categories)},
        {"label": "Foco principal", "value": SECTION_LABELS.get(top_section, "Benchmarking")},
    ]
    if metadata:
        if "zones" in metadata:
            cards.append({"label": "Zonas analizadas", "value": str(metadata["zones"])})
        elif "countries" in metadata:
            cards.append({"label": "Pa\u00edses", "value": str(metadata["countries"])})
    return cards


def _build_report_cards(report: dict) -> list[dict]:
    cards = []
    summary = report.get("summary", [])
    sections = report.get("sections", {})

    metadata = report.get("metadata", {})
    scope_parts = []
    if metadata.get("weeks"):
        scope_parts.append(f"{metadata['weeks']} semanas")
    if metadata.get("countries"):
        n_c = metadata["countries"]
        country_label = "pa\u00eds" if n_c == 1 else "pa\u00edses"
        scope_parts.append(f"{n_c} {country_label}")
    if metadata.get("zones"):
        scope_parts.append(f"{metadata['zones']} zonas")
    if metadata.get("metrics"):
        scope_parts.append(f"{metadata['metrics']} m\u00e9tricas")
    scope_prefix = ("Alcance: " + " \u00b7 ".join(scope_parts) + ". ") if scope_parts else ""
    cards.append(
        {
            "kind": "section",
            "title": "Resumen ejecutivo",
            "subtitle": scope_prefix + "Top hallazgos seleccionados autom\u00e1ticamente.",
        }
    )

    if summary:
        for item in summary:
            cards.append({"kind": "insight", "item": item})
    else:
        cards.append(
            {
                "kind": "note",
                "title": "Sin hallazgos prioritarios",
                "message": "No se detectaron hallazgos relevantes para el resumen ejecutivo.",
            }
        )

    for section_key, section_label in SECTION_LABELS.items():
        section_items = sections.get(section_key, [])
        cards.append(
            {
                "kind": "section",
                "title": section_label,
                "subtitle": f"{len(section_items)} hallazgo{'s' if len(section_items) != 1 else ''} en esta categor\u00eda.",
            }
        )
        if section_items:
            for item in section_items:
                cards.append({"kind": "insight", "item": item})
        else:
            cards.append(
                {
                    "kind": "note",
                    "title": f"Sin hallazgos en {section_label.lower()}",
                    "message": "Con la data actual y las reglas configuradas no aparecieron alertas en esta categor\u00eda.",
                }
            )

    return cards


def _estimate_card_height(card: dict) -> float:
    if card["kind"] == "section":
        return 44

    if card["kind"] == "note":
        title_lines = _wrap_card_lines(card["title"], width=72)
        message_lines = _wrap_card_lines(card["message"], width=88)
        return 26 + (len(title_lines) * 14) + (len(message_lines) * 13) + 24

    item = card["item"]
    meta = []
    if item.get("category"):
        cat_display = str(display_value(item["category"]))
        meta.append(cat_display[:1].upper() + cat_display[1:] if cat_display else "")
    if item.get("severity"):
        meta.append(f"Severidad: {display_value(item['severity'])}")
    title_lines = _wrap_card_lines(str(display_value(item.get("title", "Hallazgo"))), width=72)
    meta_lines = _wrap_card_lines(" · ".join(meta), width=88) if meta else []
    message_lines = _wrap_card_lines(str(display_value(item.get("message", ""))), width=88)
    recommendation_lines = _wrap_card_lines(
        f"Acci\u00f3n recomendada: {display_value(item.get('recommendation', ''))}",
        width=88,
    ) if item.get("recommendation") else []
    return 26 + (len(title_lines) * 14) + (len(meta_lines) * 13) + (len(message_lines) * 13) + (len(recommendation_lines) * 13) + 24


def _draw_section_card(commands: list[str], y: float, title: str, subtitle: str) -> float:
    _draw_text(commands, 54, y, title, "F1", 15, PDF_COLORS["ink"])
    _draw_text(commands, 54, y - 16, subtitle, "F2", 10, PDF_COLORS["muted"])
    commands.append(
        f"q {PDF_COLORS['accent'][0]:.2f} {PDF_COLORS['accent'][1]:.2f} {PDF_COLORS['accent'][2]:.2f} rg 54.00 {y - 28:.2f} 64.00 2.40 re f Q"
    )
    return y - 40


def _draw_note_card(commands: list[str], y: float, title: str, message: str) -> float:
    height = _estimate_card_height({"kind": "note", "title": title, "message": message})
    bottom = y - height
    _draw_rect(commands, 48, bottom, 516, height, fill=PDF_COLORS["panel"], stroke=PDF_COLORS["border"])
    cursor_y = y - 24
    cursor_y = _draw_wrapped_text(commands, 66, cursor_y, title, "F1", 12, PDF_COLORS["ink"], width=72, line_gap=14)
    _draw_wrapped_text(commands, 66, cursor_y - 4, message, "F2", 10, PDF_COLORS["muted"], width=88, line_gap=13)
    return bottom - 12


def _draw_insight_card(commands: list[str], y: float, item: dict) -> float:
    height = _estimate_card_height({"kind": "insight", "item": item})
    bottom = y - height
    severity = item.get("severity", "medium")
    bar_color = SEVERITY_BAR_COLORS.get(severity, PDF_COLORS["accent"])
    bg_color = SEVERITY_BG_COLORS.get(severity, PDF_COLORS["white"])
    _draw_rect(commands, 48, bottom, 516, height, fill=bg_color, stroke=PDF_COLORS["border"])
    _draw_rect(commands, 48, bottom, 5, height, fill=bar_color)

    title = str(display_value(item.get("title", "Hallazgo")))
    message = str(display_value(item.get("message", "")))
    recommendation = item.get("recommendation")
    category = item.get("category")

    meta = []
    if category:
        cat_display = str(display_value(category))
        meta.append(cat_display[:1].upper() + cat_display[1:] if cat_display else "")
    if severity:
        sev_display = display_value(severity)
        meta.append(f"Severidad: {sev_display}")
    meta_text = " · ".join(meta)

    cursor_y = y - 24
    cursor_y = _draw_wrapped_text(commands, 66, cursor_y, title, "F1", 12, bar_color, width=72, line_gap=14)

    if meta_text:
        cursor_y = _draw_wrapped_text(commands, 66, cursor_y - 2, meta_text, "F2", 10, PDF_COLORS["muted"], width=88, line_gap=13)

    cursor_y = _draw_wrapped_text(commands, 66, cursor_y - 4, message, "F2", 10, PDF_COLORS["ink"], width=88, line_gap=13)

    if recommendation:
        _draw_wrapped_text(
            commands,
            66,
            cursor_y - 6,
            f"Acci\u00f3n recomendada: {display_value(recommendation)}",
            "F1",
            10,
            PDF_COLORS["ink"],
            width=88,
            line_gap=13,
        )

    return bottom - 12


def _format_generated_at(iso_str: str) -> str:
    _MONTHS_ES = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return f"{dt.day} de {_MONTHS_ES[dt.month - 1]} de {dt.year}"
    except Exception:
        return iso_str


def build_executive_report_pdf(report: dict) -> bytes:
    counts = report.get("counts", {})
    sections = report.get("sections", {})
    generated_at = _format_generated_at(report.get("generated_at", ""))
    metadata = report.get("metadata", {})

    page_width = 612
    page_height = 792
    top_margin = 54
    bottom_margin = 48
    pages: list[list[str]] = []
    page_counter = [0]

    def start_page() -> tuple[list[str], float]:
        page_counter[0] += 1
        is_first = page_counter[0] == 1
        commands: list[str] = []
        _draw_rect(commands, 0, 0, page_width, page_height, fill=PDF_COLORS["white"])

        if is_first:
            _draw_rect(commands, 42, 654, 528, 96, fill=PDF_COLORS["accent"])
            _draw_text(commands, 58, 716, "Rappi AI Operations Assistant", "F1", 24, PDF_COLORS["white"])
            _draw_text(commands, 58, 694, "Reporte Ejecutivo", "F2", 12, PDF_COLORS["white"])
            _draw_text(commands, 58, 680, "Resumen de operaciones listo para compartir", "F2", 10, PDF_COLORS["white"])
            _draw_text(commands, 58, 666, f"Generado: {generated_at}", "F2", 10, PDF_COLORS["white"])

            stat_cards = _build_stat_cards(counts, sections, metadata)
            n = len(stat_cards)
            stat_w = (514 - 8 * (n - 1)) // n
            stat_gap = stat_w + 8
            stat_x = 58
            for stat in stat_cards:
                _draw_rect(commands, stat_x, 616, stat_w, 38, fill=PDF_COLORS["chip"])
                _draw_text(commands, stat_x + 10, 638, stat["label"], "F2", 8, PDF_COLORS["muted"])
                _draw_text(commands, stat_x + 10, 623, stat["value"], "F1", 11, PDF_COLORS["ink"])
                stat_x += stat_gap

            return commands, 594
        else:
            # Minimal continuation header — compact stripe so content fills the page
            _draw_rect(commands, 42, 762, 528, 22, fill=PDF_COLORS["accent"])
            _draw_text(
                commands, 58, 769,
                f"Rappi AI Operations Assistant  |  Reporte Ejecutivo  |  {generated_at}",
                "F2", 9, PDF_COLORS["white"],
            )
            return commands, 748

    current_commands, current_y = start_page()

    def ensure_space(required_height: float) -> None:
        nonlocal current_commands, current_y
        if current_y - required_height >= bottom_margin:
            return
        pages.append(current_commands)
        current_commands, current_y = start_page()

    for card in _build_report_cards(report):
        card_height = _estimate_card_height(card)
        ensure_space(card_height + 8)
        if card["kind"] == "section":
            current_y = _draw_section_card(current_commands, current_y, card["title"], card["subtitle"])
        elif card["kind"] == "note":
            current_y = _draw_note_card(current_commands, current_y, card["title"], card["message"])
        else:
            current_y = _draw_insight_card(current_commands, current_y, card["item"])

    for page_number, commands in enumerate([*pages, current_commands], start=1):
        _draw_text(commands, 496, 24, f"P\u00e1gina {page_number}", "F2", 9, PDF_COLORS["muted"])

    all_pages = [*pages, current_commands]
    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    bold_font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    body_font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    page_ids: list[int] = []
    pages_id = add_object(b"<< /Type /Pages /Kids [ ] /Count 0 >>")

    for commands in all_pages:
        stream_data = "\n".join(commands).encode("latin-1", errors="replace")
        content_id = add_object(
            b"<< /Length " + str(len(stream_data)).encode("ascii") + b" >>\nstream\n" + stream_data + b"\nendstream"
        )
        page_id = add_object(
            (
                b"<< /Type /Page /Parent "
                + str(pages_id).encode("ascii")
                + b" 0 R /MediaBox [0 0 612 792] /Contents "
                + str(content_id).encode("ascii")
                + b" 0 R /Resources << /Font << /F1 "
                + str(bold_font_id).encode("ascii")
                + b" 0 R /F2 "
                + str(body_font_id).encode("ascii")
                + b" 0 R >> >> >>"
            )
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids).encode("ascii")
    objects[pages_id - 1] = (
        b"<< /Type /Pages /Kids [ " + kids + b" ] /Count " + str(len(page_ids)).encode("ascii") + b" >>"
    )

    catalog_id = add_object(b"<< /Type /Catalog /Pages " + str(pages_id).encode("ascii") + b" 0 R >>")

    pdf_parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    current_offset = len(pdf_parts[0])

    for index, payload in enumerate(objects, start=1):
        offsets.append(current_offset)
        obj_bytes = f"{index} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"
        pdf_parts.append(obj_bytes)
        current_offset += len(obj_bytes)

    xref_offset = current_offset
    xref_lines = [f"xref\n0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf_parts.extend(xref_lines)
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode(
            "ascii"
        )
    )
    pdf_parts.append(trailer)
    return b"".join(pdf_parts)


def report_pdf_filename(prefix: str = "rappi_executive_report") -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.pdf"


def smtp_configured(smtp_settings: dict) -> bool:
    required_keys = ["host", "port", "username", "password", "from_email"]
    return all(bool(smtp_settings.get(key)) for key in required_keys)


def send_report_email(
    smtp_settings: dict,
    to_email: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
    filename: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_settings["from_email"]
    message["To"] = to_email
    message.set_content(body)
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    with smtplib.SMTP(smtp_settings["host"], int(smtp_settings["port"])) as server:
        if smtp_settings.get("use_tls", True):
            server.starttls()
        server.login(smtp_settings["username"], smtp_settings["password"])
        server.send_message(message)
