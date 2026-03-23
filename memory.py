import json
from datetime import datetime
from pathlib import Path


class ConversationMemory:
    """
    Memoria conversacional con persistencia opcional en disco.

    Si se pasa persist_path, el historial de las últimas MEMORY_MAX_TURNS
    conversaciones se guarda en un JSON local y se recupera al iniciar la app.
    Esto permite follow-ups entre sesiones distintas.

    Si persist_path es None, funciona igual que antes (solo en memoria).
    last_result nunca se persiste porque puede contener DataFrames.
    """

    def __init__(self, persist_path=None, max_turns: int = 10):
        self.persist_path = Path(persist_path) if persist_path else None
        self.max_turns = max_turns

        self.history = []
        self.last_user_query = None
        self.last_assistant_response = None
        self.last_filters = {}
        self.last_entities = {}
        self.last_metric = None
        self.last_dimension = None
        self.last_result = None   # nunca persiste — puede contener DataFrames
        self.last_intent = None

        if self.persist_path:
            self._load()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            with open(self.persist_path, encoding="utf-8") as f:
                data = json.load(f)
            self.history = data.get("history", [])
            self.last_user_query = data.get("last_user_query")
            self.last_assistant_response = data.get("last_assistant_response")
            self.last_filters = data.get("last_filters") or {}
            self.last_entities = data.get("last_entities") or {}
            self.last_metric = data.get("last_metric")
            self.last_dimension = data.get("last_dimension")
            self.last_intent = data.get("last_intent")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass  # primera vez o archivo corrupto — empezamos de cero

    def save(self) -> None:
        """Persiste el estado actual en disco. Llamar al final de cada turno."""
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "history": self.history[-self.max_turns:],
                "last_user_query": self.last_user_query,
                "last_assistant_response": self.last_assistant_response,
                "last_filters": self.last_filters,
                "last_entities": self.last_entities,
                "last_metric": self.last_metric,
                "last_dimension": self.last_dimension,
                "last_intent": self.last_intent,
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # fallo silencioso — la persistencia es best-effort

    def clear(self) -> None:
        """Resetea la memoria en RAM y borra el archivo de disco."""
        self.history = []
        self.last_user_query = None
        self.last_assistant_response = None
        self.last_filters = {}
        self.last_entities = {}
        self.last_metric = None
        self.last_dimension = None
        self.last_result = None
        self.last_intent = None
        if self.persist_path and self.persist_path.exists():
            try:
                self.persist_path.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # API pública (igual que antes, más save())
    # ------------------------------------------------------------------

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        self.history.append({"user": user_message, "assistant": assistant_message})
        self.last_user_query = user_message
        self.last_assistant_response = assistant_message

    def set_last_filters(self, filters: dict) -> None:
        self.last_filters = filters

    def set_last_entities(self, entities: dict) -> None:
        self.last_entities = entities

    def set_last_metric(self, metric: str) -> None:
        self.last_metric = metric

    def set_last_dimension(self, dimension: str) -> None:
        self.last_dimension = dimension

    def set_last_result(self, result) -> None:
        self.last_result = result  # solo en RAM, nunca a disco

    def set_last_intent(self, intent: dict) -> None:
        self.last_intent = intent

    def get_context(self) -> dict:
        return {
            "history": self.history,
            "last_user_query": self.last_user_query,
            "last_assistant_response": self.last_assistant_response,
            "last_filters": self.last_filters,
            "last_entities": self.last_entities,
            "last_metric": self.last_metric,
            "last_dimension": self.last_dimension,
            "last_result": self.last_result,
            "last_intent": self.last_intent,
        }
