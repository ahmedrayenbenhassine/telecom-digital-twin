from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models, schemas
from database import SessionLocal, engine
import heapq
from typing import List
import urllib.parse

models.Base.metadata.create_all(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class NodeCreateRequest(BaseModel):
    id: str
    position_x: float
    position_y: float

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

async def broadcast_network_metrics(db: Session):
    nodes = db.query(models.Node).all()
    edges = db.query(models.Edge).all()
    
    total_nodes = len(nodes)
    total_edges = len(edges)
    active_nodes = sum(1 for n in nodes if n.status == "active")
    avg_load = sum(e.load for e in edges) / total_edges if total_edges > 0 else 0.0

    payload = {
        "type": "METRICS_UPDATE",
        "stats": {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "active_nodes": active_nodes,
            "down_nodes": total_nodes - active_nodes,
            "average_load": round(avg_load, 2)
        }
    }
    await manager.broadcast(payload)

@app.websocket("/ws/network")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        with SessionLocal() as db:
            await broadcast_network_metrics(db)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/nodes")
def get_nodes(db: Session = Depends(get_db)):
    return db.query(models.Node).all()

@app.post("/nodes")
async def create_node(node: NodeCreateRequest, db: Session = Depends(get_db)):
    existing_node = db.query(models.Node).filter(models.Node.id == node.id).first()
    if existing_node:
        raise HTTPException(status_code=400, detail="Ce nœud existe déjà")
        
    db_node = models.Node(
        id=node.id,
        label=node.id,
        position_x=node.position_x,
        position_y=node.position_y,
        status="active"
    )
    db.add(db_node)
    db.commit()
    
    await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
    await broadcast_network_metrics(db)
    return {"status": "success", "node_id": db_node.id}

@app.delete("/nodes/{node_id}")
async def delete_node(node_id: str, db: Session = Depends(get_db)):
    actual_id = urllib.parse.unquote(node_id)
    db_node = db.query(models.Node).filter(models.Node.id == actual_id).first()
    
    if not db_node:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    
    db.query(models.Edge).filter((models.Edge.source_id == actual_id) | (models.Edge.target_id == actual_id)).delete()
    db.delete(db_node)
    db.commit()
    
    await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
    await broadcast_network_metrics(db)
    return {"status": "success"}

@app.put("/nodes/{node_id}")
async def update_node_position(node_id: str, node_data: schemas.NodeUpdate, db: Session = Depends(get_db)):
    actual_id = urllib.parse.unquote(node_id)
    db_node = db.query(models.Node).filter(models.Node.id == actual_id).first()
    if db_node:
        db_node.position_x = node_data.position_x
        db_node.position_y = node_data.position_y
        db.commit()
        await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
        await broadcast_network_metrics(db)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Nœud introuvable")

@app.put("/nodes/{node_id}/status")
async def toggle_node_status(node_id: str, db: Session = Depends(get_db)):
    actual_id = urllib.parse.unquote(node_id)
    db_node = db.query(models.Node).filter(models.Node.id == actual_id).first()
    if not db_node:
        raise HTTPException(status_code=404, detail="Nœud introuvable")
    
    db_node.status = "down" if db_node.status == "active" else "active"
    db.commit()
    
    await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
    await broadcast_network_metrics(db)
    return {"status": "success", "new_status": db_node.status}

@app.get("/edges")
def get_edges(db: Session = Depends(get_db)):
    edges = db.query(models.Edge).all()
    return [{"id": e.id, "source": e.source_id, "target": e.target_id, "load": e.load} for e in edges]

@app.post("/edges")
async def create_edge(edge: schemas.EdgeCreate, db: Session = Depends(get_db)):
    existing_edge = db.query(models.Edge).filter(models.Edge.id == edge.id).first()
    if existing_edge:
        return {"id": existing_edge.id, "source": existing_edge.source_id, "target": existing_edge.target_id, "load": existing_edge.load}
    db_edge = models.Edge(id=edge.id, source_id=edge.source, target_id=edge.target, load=edge.load)
    db.add(db_edge)
    db.commit()
    await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
    await broadcast_network_metrics(db)
    return {"id": db_edge.id, "source": db_edge.source_id, "target": db_edge.target_id, "load": db_edge.load}

@app.put("/edges/{edge_id}/load")
async def update_edge_load(edge_id: str, load_data: schemas.EdgeCreate, db: Session = Depends(get_db)):
    db_edge = db.query(models.Edge).filter(models.Edge.id == edge_id).first()
    if not db_edge:
        raise HTTPException(status_code=404, detail="Câble introuvable")
    db_edge.load = load_data.load
    db.commit()
    await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
    await broadcast_network_metrics(db)
    return {"status": "success"}

@app.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str, db: Session = Depends(get_db)):
    db_edge = db.query(models.Edge).filter(models.Edge.id == edge_id).first()
    if db_edge:
        db.delete(db_edge)
        db.commit()
        await manager.broadcast({"type": "TOPOLOGY_CHANGED"})
        await broadcast_network_metrics(db)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Câble introuvable")

@app.get("/network/shortest-path", response_model=schemas.ShortestPathResponse)
def get_shortest_path(source: str, target: str, db: Session = Depends(get_db)):
    nodes = db.query(models.Node).all()
    edges = db.query(models.Edge).all()
    
    node_status = {n.id: n.status for n in nodes}
    
    if node_status.get(source) == "down" or node_status.get(target) == "down":
        raise HTTPException(status_code=404, detail="Route impossible : Équipement source ou cible en panne")

    graph = {n.id: {} for n in nodes if n.status == "active"}
    for e in edges:
        if node_status.get(e.source_id) == "down" or node_status.get(e.target_id) == "down":
            continue
            
        safe_load = min(e.load, 1.05)
        cost = 10.0 / (1.1 - safe_load)
        if e.source_id in graph and e.target_id in graph:
            graph[e.source_id][e.target_id] = {"cost": cost, "edge_id": e.id}
            graph[e.target_id][e.source_id] = {"cost": cost, "edge_id": e.id}

    if source not in graph or target not in graph:
        raise HTTPException(status_code=404, detail="Route introuvable")

    queue = [(0.0, source, [], [])]
    visited = set()

    while queue:
        total_cost, current, path_nodes, path_edges = heapq.heappop(queue)
        if current in visited:
            continue
        visited.add(current)
        new_path_nodes = path_nodes + [current]

        if current == target:
            return {"path_nodes": new_path_nodes, "path_edges": path_edges, "total_cost": total_cost}

        for neighbor, link_info in graph[current].items():
            if neighbor not in visited:
                heapq.heappush(queue, (total_cost + link_info["cost"], neighbor, new_path_nodes, path_edges + [link_info["edge_id"]]))
                
    raise HTTPException(status_code=404, detail="Aucun chemin alternatif trouvé")