from utils import build_executive_report_pdf, report_pdf_filename, smtp_configured, send_report_email


def test_build_executive_report_pdf_returns_pdf_bytes():
    report = {
        "generated_at": "2026-03-22T12:00:00Z",
        "summary": [
            {
                "title": "Divergencia de benchmark",
                "message": "Zona A supera a Zona B en Perfect Orders.",
                "recommendation": "Comparar prácticas operativas.",
                "category": "benchmarking",
                "severity": "high",
            }
        ],
        "sections": {
            "anomalies": [],
            "trend_deterioration": [],
            "benchmarking": [
                {
                    "title": "Divergencia de benchmark",
                    "message": "Zona A supera a Zona B en Perfect Orders.",
                    "recommendation": "Comparar prácticas operativas.",
                    "category": "benchmarking",
                    "severity": "high",
                }
            ],
            "correlations": [],
            "opportunities": [],
        },
        "counts": {
            "anomalies": 0,
            "trend_deterioration": 0,
            "benchmarking": 1,
            "correlations": 0,
            "opportunities": 0,
        },
    }

    pdf_bytes = build_executive_report_pdf(report)

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"Reporte Ejecutivo" in pdf_bytes


def test_report_pdf_filename_uses_pdf_extension():
    filename = report_pdf_filename()

    assert filename.endswith(".pdf")
    assert filename.startswith("rappi_executive_report_")


def test_smtp_configured_requires_all_main_fields():
    assert not smtp_configured({"host": "", "port": 587, "username": "a", "password": "b", "from_email": "x@y.com"})
    assert smtp_configured(
        {"host": "smtp.test.com", "port": 587, "username": "a", "password": "b", "from_email": "x@y.com"}
    )


def test_send_report_email_builds_message_and_uses_smtp(monkeypatch):
    captured = {}

    class DummySMTP:
        def __init__(self, host, port):
            captured["host"] = host
            captured["port"] = port
            captured["started_tls"] = False
            captured["logged_in"] = None
            captured["message"] = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            captured["started_tls"] = True

        def login(self, username, password):
            captured["logged_in"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("utils.smtplib.SMTP", DummySMTP)

    send_report_email(
        smtp_settings={
            "host": "smtp.test.com",
            "port": 587,
            "username": "user",
            "password": "secret",
            "from_email": "ops@test.com",
            "use_tls": True,
        },
        to_email="dest@test.com",
        subject="Reporte",
        body="Adjunto reporte",
        pdf_bytes=b"%PDF-1.4 fake",
        filename="reporte.pdf",
    )

    assert captured["host"] == "smtp.test.com"
    assert captured["port"] == 587
    assert captured["started_tls"] is True
    assert captured["logged_in"] == ("user", "secret")
    assert captured["message"]["To"] == "dest@test.com"
    assert captured["message"]["Subject"] == "Reporte"
