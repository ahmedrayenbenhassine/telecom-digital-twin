from pydantic import BaseModel, Field, ConfigDict
from typing import List

class NodeUpdate(BaseModel):
    position_x: float
    position_y: float

    model_config = ConfigDict(from_attributes=True)

class EdgeCreate(BaseModel):
    id: str
    source: str
    target: str
    load: float = Field(default=0.0, ge=0.0, le=1.5)

    model_config = ConfigDict(from_attributes=True)

class ShortestPathResponse(BaseModel):
    path_nodes: List[str]
    path_edges: List[str]
    total_cost: float

    model_config = ConfigDict(from_attributes=True)

class NetworkStats(BaseModel):
    total_nodes: int = Field(..., ge=0)
    total_edges: int = Field(..., ge=0)
    active_nodes: int = Field(..., ge=0)
    down_nodes: int = Field(..., ge=0)
    average_load: float

    model_config = ConfigDict(from_attributes=True)