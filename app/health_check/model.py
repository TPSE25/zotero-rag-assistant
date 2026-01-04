from datetime import datetime
from typing import List, Optional, Union
from .enum import HealthCheckStatusEnum
from pydantic import BaseModel


class HealthCheckEntityModel(BaseModel):
    name: str
    status: HealthCheckStatusEnum
    timestamp: Optional[datetime] = None


class HealthCheckModel(BaseModel):
    entities: List[HealthCheckEntityModel]
    totalStartTime: Optional[datetime] = None
    totalStopTime: Optional[datetime] = None
