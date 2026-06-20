from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Node(Base):
    __tablename__ = "nodes"
    id = Column(String(50), primary_key=True, index=True)
    type = Column(String(50), default="default", nullable=False)
    label = Column(String(100), nullable=False)
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=func.now())

class Edge(Base):
    __tablename__ = "edges"
    id = Column(String(50), primary_key=True, index=True)
    
    source_id = Column(String(50), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String(50), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    
    load = Column(Float, default=0.0)
    bandwidth = Column(Integer, default=1000)
    latency = Column(Integer, default=10)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=func.now())