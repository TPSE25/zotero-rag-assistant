# route.py
from typing import Callable
from starlette.responses import JSONResponse
from .service import HealthCheckFactory
from .enum import HealthCheckStatusEnum


def healthCheckRoute(factory: HealthCheckFactory) -> Callable[[], JSONResponse]:
    """
    Returns a FastAPI-compatible endpoint function that runs the health check factory
    and returns JSONResponse with status 200 if healthy, 500 if unhealthy.
    """
    _factory = factory

    def endpoint() -> JSONResponse:
        res: dict[str, str] = _factory.check()  # assume check() returns dict[str, str]
        if res['status'] == HealthCheckStatusEnum.UNHEALTHY.value:
            return JSONResponse(content=res, status_code=500)
        return JSONResponse(content=res, status_code=200)

    return endpoint

