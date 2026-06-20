from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json

# Importe tes modules locaux (assure-toi que les noms concordent)
from database import get_db, engine, Base
import models, schemas  # ou adapter selon ta structure de dossiers

# Crée les tables dans SQLite au démarrage
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Telecom Digital Twin API")

# 🌟 CORRECTION CORS : Autorise explicitement Vercel et le local à communiquer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permet la communication globale en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gestionnaire de WebSockets pour les mises à jour Live
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- FONCTION DE CALCUL DES MÉTRIQUES ---
def get_network_stats(db: Session):
    total_nodes = db.query(models.Node).count()
    total_edges = db.query(models.Edge).count()
    active_nodes = db.query(models.Node).filter(models.Node.status == "active").count()
    down_nodes = db.query(models.Node).filter(models.Node.status == "down").count()
    
    edges = db.query(models.Edge).all()
    avg_load = sum([e.load for e in edges]) / total_edges if total_edges > 0 else 0.0
    
    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "active_nodes": active_nodes,
        "down_nodes": down_nodes,
        "average_load": avg_load
    }

async def notify_topology_change(db: Session):
    # Envoie un signal aux clients pour recharger la topologie et les métriques
    stats = get_network_stats(db)
    await manager.broadcast(json.dumps({"type": "TOPOLOGY_CHANGED"}))
    await manager.broadcast(json.dumps({"type": "METRICS_UPDATE", "stats": stats}))

# --- ROUTE WEBSOCKET ---
@app.websocket("/ws/network")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    # Envoi des métriques initiales dès la connexion
    try:
        stats = get_network_stats(db)
        await websocket.send_text(json.dumps({"type": "METRICS_UPDATE", "stats": stats}))
        while True:
            await websocket.receive_text()  # Maintient la connexion ouverte
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- ROUTES API POUR LES NOEUDS ---
@app.get("/nodes")
def read_nodes(db: Session = Depends(get_db)):
    return db.query(models.Node).all()

@app.post("/nodes")
async def create_node(node: schemas.NodeCreate, db: Session = Depends(get_db)):
    db_node = models.Node(id=node.id, label=node.id, position_x=node.position_x, position_y=node.position_y, status="active")
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    await notify_topology_change(db)
    return db_node

@app.put("/nodes/{node_id}")
async def update_node_position(node_id: str, pos: schemas.NodePositionUpdate, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    db_node.position_x = pos.position_x
    db_node.position_y = pos.position_y
    db.commit()
    return db_node

@app.put("/nodes/{node_id}/status")
async def toggle_node_status(node_id: str, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    db_node.status = "down" if db_node.status == "active" else "active"
    db.commit()
    await notify_topology_change(db)
    return db_node

@app.delete("/nodes/{node_id}")
async def delete_node(node_id: str, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    # Supprime aussi les liens rattachés pour éviter les bugs de clés étrangères
    db.query(models.Edge).filter((models.Edge.source == node_id) | (models.Edge.target == node_id)).delete()
    db.delete(db_node)
    db.commit()
    await notify_topology_change(db)
    return {"detail": "Node and related edges deleted"}

# --- ROUTES API POUR LES LIENS (EDGES) ---
@app.get("/edges")
def read_edges(db: Session = Depends(get_db)):
    return db.query(models.Edge).all()

@app.post("/edges")
async def create_edge(edge: schemas.EdgeCreate, db: Session = Depends(get_db)):
    db_edge = models.Edge(id=edge.id, source=edge.source, target=edge.target, load=edge.load)
    db.add(db_edge)
    db.commit()
    db.refresh(db_edge)
    await notify_topology_change(db)
    return db_edge

@app.put("/edges/{edge_id}/load")
async def update_edge_load(edge_id: str, edge_data: schemas.EdgeLoadUpdate, db: Session = Depends(get_db)):
    db_edge = db.query(models.Edge).filter(models.Edge.id == edge_id).first()
    if not db_edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db_edge.load = edge_data.load
    db.commit()
    await notify_topology_change(db)
    return db_edge

@app.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str, db: Session = Depends(get_db)):
    db_edge = db.query(models.Edge).filter(models.Edge.id == edge_id).first()
    if not db_edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(db_edge)
    db.commit()
    await notify_topology_change(db)
    return {"detail": "Edge deleted"}

# --- ROUTE ALGORITHME ROUTAGE (OSPF / SHORTEST PATH) ---
@app.get("/network/shortest-path")
def get_shortest_path(source: str, target: str, db: Session = Depends(get_db)):
    # Implémentation basique de BFS/Dijkstra pour trouver le chemin le court
    nodes = [n.id for n in db.query(models.Node).filter(models.Node.status == "active").all()]
    edges = db.query(models.Edge).all()
    
    if source not in nodes or target not in nodes:
        return {"path_edges": []}
        
    adj = {n: [] for n in nodes}
    edge_map = {}
    for e in edges:
        if e.source in adj and e.target in adj:
            adj[e.source].append(e.target)
            adj[e.target].append(e.source)  # Bidirectionnel
            edge_map[(e.source, e.target)] = e.id
            edge_map[(e.target, e.source)] = e.id

    # Algorithme BFS
    queue = [[source]]
    visited = set([source])
    
    while queue:
        path = queue.pop(0)
        node = path[-1]
        if node == target:
            # Convertit la suite de nœuds en liste d'IDs de liens (edges)
            path_edges = []
            for i in range(len(path) - 1):
                edge_id = edge_map.get((path[i], path[i+1]))
                if edge_id:
                    path_edges.append(edge_id)
            return {"path_edges": path_edges}
            
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                new_path = list(path)
                new_path.append(neighbor)
                queue.append(new_path)
                
    return {"path_edges": []}