# service.py
import json
from datetime import datetime, timedelta
from typing import Optional
from .model import HealthCheckModel

class HealthCheckFactory:
    def __init__(self) -> None:
        self._entityStartTime: Optional[datetime] = None
        self._entityStopTime: Optional[datetime] = None
        self._totalStartTime: Optional[datetime] = None
        self._totalStopTime: Optional[datetime] = None

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

    def __getTimeTaken__(self, entityTimer: bool) -> Optional[timedelta]:
        """Return elapsed time as timedelta."""
        if entityTimer:
            if self._entityStartTime and self._entityStopTime:
                return self._entityStopTime - self._entityStartTime
            return None
        if self._totalStartTime and self._totalStopTime:
            return self._totalStopTime - self._totalStartTime
        return None

    def __dumpModel__(self, model: HealthCheckModel) -> str:
        """Convert Python objects to JSON-friendly dicts."""
        entities_list = []
        for entity in model.entities:
            # assuming entity.status is an Enum
            entity.status = entity.status.value
            entities_list.append(entity.dict())
        return json.dumps(entities_list)
        ...
async def check(self) -> dict[str, str]:
        """
        Performs a health check by calling Ollama embed API.
        Returns a dict with 'status'.
        """
        client = AsyncClient(base_url=self.base_url)

        try:
            # We just test a small dummy embedding
            response = await client.embed(model=self.model, input="health check")
            if response.embedding:
                return {"status": HealthCheckStatusEnum.HEALTHY.value}
            else:
                return {"status": HealthCheckStatusEnum.UNHEALTHY.value}

        except Exception as e:
            logging.error(f"Ollama health check failed: {e}", exc_info=True)
            return {"status": HealthCheckStatusEnum.UNHEALTHY.value}
