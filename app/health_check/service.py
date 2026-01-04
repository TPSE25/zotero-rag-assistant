import json
from datetime import datetime
from .model import HealthCheckModel


class HealthCheckFactory:
    def __init__(self):
        self._entityStartTime: datetime = None
        self._entityStopTime: datetime = None
        self._totalStartTime: datetime = None
        self._totalStopTime: datetime = None

    def __startTimer__(self, entityTimer: bool) -> None:
        if entityTimer:
            self._entityStartTime = datetime.now()
        else:
            self._totalStartTime = datetime.now()

    def __stopTimer__(self, entityTimer: bool) -> None:
        if entityTimer:
            self._entityStopTime = datetime.now()
        else:
            self._totalStopTime = datetime.now()

    def __getTimeTaken__(self, entityTimer: bool) -> datetime:
        if entityTimer:
            return self._entityStopTime - self._entityStartTime
        return self._totalStopTime - self._totalStartTime

    def __dumpModel__(self, model: HealthCheckModel) -> str:
        """Convert Python objects to JSON-friendly dicts."""
        entities_list = []
        for entity in model.entities:
            entity.status = entity.status.value
            entities_list.append(entity.dict())
        return json.dumps(entities_list)
