import { useEffect, useCallback, useState, useRef } from 'react';
import ReactFlow, { Background, Controls, MiniMap, useNodesState, useEdgesState, ConnectionLineType } from 'reactflow';
import type { Node, Edge, Connection } from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';

interface DbNode { id: string; type: string; label: string; position_x: number; position_y: number; status: string; }
interface DbEdge { id: string; source: string; target: string; load: number; }
interface NetworkStats { total_nodes: number; total_edges: number; active_nodes: number; down_nodes: number; average_load: number; }

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  
  const [sourceNode, setSourceNode] = useState<string>('');
  const [targetNode, setTargetNode] = useState<string>('');
  const [highlightedEdges, setHighlightedEdges] = useState<string[]>([]);
  
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [newNodeLabel, setNewNodeLabel] = useState<string>('');

  const [stats, setStats] = useState<NetworkStats>({
    total_nodes: 0, total_edges: 0, active_nodes: 0, down_nodes: 0, average_load: 0
  });

  const loadTopologyRef = useRef<() => void>(() => {});

  const loadTopology = useCallback(() => {
    axios.get('https://telecom-digital-twin-1.onrender.com')
      .then(response => {
        const formattedNodes = response.data.map((n: DbNode) => ({
          id: n.id, 
          data: { label: n.label }, 
          position: { x: n.position_x, y: n.position_y }, 
          type: 'default',
          style: {
            background: n.status === 'down' ? '#e74c3c' : '#ffffff',
            color: n.status === 'down' ? '#ffffff' : '#333333',
            border: n.status === 'down' ? '2px dashed #c0392b' : '1px solid #777777',
            opacity: n.status === 'down' ? 0.65 : 1,
            fontWeight: n.status === 'down' ? 'bold' : 'normal',
            borderRadius: '6px',
            padding: '10px'
          }
        }));
        setNodes(formattedNodes);
      }).catch(err => console.error("Erreur chargement noeuds:", err));

    axios.get('https://telecom-digital-twin-1.onrender.com')
      .then(response => {
        const formattedEdges = response.data.map((e: DbEdge) => {
          const isHighlighted = highlightedEdges.includes(e.id);
          return {
            id: e.id, source: e.source, target: e.target, animated: true,
            type: 'straight', 
            style: { 
              stroke: isHighlighted ? '#2ecc71' : (e.load > 0.8 ? '#e74c3c' : '#007bff'), 
              strokeWidth: isHighlighted ? 4 : 2 
            },
            data: { load: e.load }
          };
        });
        setEdges(formattedEdges);
      }).catch(err => console.error("Erreur chargement câbles:", err));
  }, [highlightedEdges, setNodes, setEdges]);

  useEffect(() => {
    loadTopologyRef.current = loadTopology;
  }, [loadTopology]);

  useEffect(() => {
    loadTopologyRef.current();

    const ws = new WebSocket('https://telecom-digital-twin-1.onrender.com/ws/network');

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'METRICS_UPDATE' && data.stats) {
          setStats({
            total_nodes: data.stats.total_nodes ?? 0,
            total_edges: data.stats.total_edges ?? 0,
            active_nodes: data.stats.active_nodes ?? 0,
            down_nodes: data.stats.down_nodes ?? 0,
            average_load: data.stats.average_load ?? 0
          });
        } else if (data.type === 'TOPOLOGY_CHANGED') {
          loadTopologyRef.current();
        }
      } catch (err) {
        console.error("Erreur WebSocket :", err);
      }
    };

    return () => { ws.close(); };
  }, []);

  const handleCalculateRoute = () => {
    if (!sourceNode || !targetNode) return;
    axios.get(`https://telecom-digital-twin-1.onrender.com/network/shortest-path?source=${encodeURIComponent(sourceNode)}&target=${encodeURIComponent(targetNode)}`)
      .then(response => {
        setHighlightedEdges(response.data.path_edges);
        setEdges(prevEdges => prevEdges.map(edge => ({
          ...edge,
          style: {
            stroke: response.data.path_edges.includes(edge.id) ? '#2ecc71' : (edge.data?.load > 0.8 ? '#e74c3c' : '#007bff'),
            strokeWidth: response.data.path_edges.includes(edge.id) ? 4 : 2
          }
        })));
      })
      .catch(() => setHighlightedEdges([]));
  };

  const handleClearRoute = () => {
    setHighlightedEdges([]); setSourceNode(''); setTargetNode('');
    loadTopologyRef.current();
  };

  const onConnect = useCallback((params: Edge | Connection) => {
    if (!params.source || !params.target) return;
    if (params.source === params.target) return; 
    
    const newEdgeId = `e-${params.source}-${params.target}`;
    axios.post('https://telecom-digital-twin-1.onrender.com/edges', { id: newEdgeId, source: params.source, target: params.target, load: 0.10 })
      .then(() => loadTopologyRef.current())
      .catch(err => console.error(err));
  }, []);

  const handleCreateNode = () => {
    if (!newNodeLabel.trim()) return;
    const nodeId = newNodeLabel.trim(); 

    axios.post('https://telecom-digital-twin-1.onrender.com/nodes', { id: nodeId, position_x: 300, position_y: 200 })
      .then(() => {
        setNewNodeLabel('');
        loadTopologyRef.current();
      })
      .catch(err => console.error("Erreur création nœud:", err));
  };

  const handleDeleteNode = () => {
    if (!selectedNodeId) return;
    axios.delete(`https://telecom-digital-twin-1.onrender.com/nodes/${encodeURIComponent(selectedNodeId)}`)
      .then(() => {
        setSelectedNodeId(null);
        loadTopologyRef.current();
      })
      .catch(err => {
        console.error("Erreur suppression, purge locale forcée...", err);
        setNodes(prev => prev.filter(n => n.id !== selectedNodeId));
        setSelectedNodeId(null);
      });
  };

  const handlePurgeTout = () => {
    if (window.confirm("Voulez-vous vider tous les équipements récalcitrants de l'écran ?")) {
      nodes.forEach(node => {
        axios.delete(`https://telecom-digital-twin-1.onrender.com/nodes/${encodeURIComponent(node.id)}`).catch(() => {});
      });
      setNodes([]);
      setEdges([]);
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
    }
  };

  const onEdgeDoubleClick = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.stopPropagation();
    const currentLoad = edge.data?.load ?? 0;
    const newLoad = currentLoad < 0.8 ? 0.95 : 0.10;

    axios.put(`https://telecom-digital-twin-1.onrender.com/edges/${edge.id}/load`, {
      id: edge.id, source: edge.source, target: edge.target, load: newLoad
    })
    .then(() => {
      loadTopologyRef.current();
      if (sourceNode && targetNode) handleCalculateRoute();
    })
    .catch(err => console.error(err));
  }, [sourceNode, targetNode]);

  const onEdgeClick = useCallback((event: React.MouseEvent, edge: Edge) => {
    setSelectedEdgeId(edge.id);
    setSelectedNodeId(null);
  }, []);

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
  }, []);

  const onEdgesDelete = useCallback((edgesToDelete: Edge[]) => {
    edgesToDelete.forEach((edge) => {
      axios.delete(`https://telecom-digital-twin-1.onrender.com/edges/${edge.id}`)
        .then(() => {
          setHighlightedEdges(prev => prev.filter(id => id !== edge.id));
          setSelectedEdgeId(null);
          loadTopologyRef.current();
        })
        .catch(err => console.error(err));
    });
  }, []);

  const handleForceDeleteEdge = () => {
    if (!selectedEdgeId) return;
    axios.delete(`https://telecom-digital-twin-1.onrender.com/edges/${selectedEdgeId}`)
      .then(() => {
        setSelectedEdgeId(null);
        loadTopologyRef.current();
      });
  };

  const onNodeDoubleClick = useCallback((event: React.MouseEvent, node: Node) => {
    event.stopPropagation();
    axios.put(`https://telecom-digital-twin-1.onrender.com/nodes/${encodeURIComponent(node.id)}/status`)
      .then(() => {
        loadTopologyRef.current();
        if (sourceNode && targetNode) handleCalculateRoute();
      })
      .catch(err => console.error(err));
  }, [sourceNode, targetNode]);

  const onNodeDragStop = useCallback((event: React.MouseEvent, node: Node) => {
    axios.put(`https://telecom-digital-twin-1.onrender.com/nodes/${encodeURIComponent(node.id)}`, { position_x: node.position.x, position_y: node.position.y })
      .catch(err => console.error(err));
  }, []);

  return (
    <div style={{ width: '100vw', height: '100vh', position: 'relative' }}>
      
      <div style={{ position: 'absolute', top: 20, left: 20, zIndex: 10, display: 'flex', flexDirection: 'column', gap: '15px' }}>
        
        {/* Panneau Routage */}
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)', padding: '15px', borderRadius: '8px', 
          boxShadow: '0 4px 6px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', gap: '10px', width: '220px'
        }}>
          <h4 style={{ margin: 0, color: '#2c3e50', fontFamily: 'sans-serif' }}>Routage OSPF</h4>
          <select 
            value={sourceNode} 
            onChange={(e) => { setSourceNode(e.target.value); setHighlightedEdges([]); }} 
            style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="">Source...</option>
            {nodes.map(n => <option key={n.id} value={n.id}>{n.data?.label || n.id}</option>)}
          </select>
          <select 
            value={targetNode} 
            onChange={(e) => { setTargetNode(e.target.value); setHighlightedEdges([]); }} 
            style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="">Cible...</option>
            {nodes.map(n => <option key={n.id} value={n.id}>{n.data?.label || n.id}</option>)}
          </select>
          <div style={{ display: 'flex', gap: '5px' }}>
            <button onClick={handleCalculateRoute} style={{ background: '#2ecc71', color: 'white', border: 'none', padding: '8px', borderRadius: '4px', cursor: 'pointer', flex: 1, fontWeight: 'bold' }}>Calculer</button>
            <button onClick={handleClearRoute} style={{ background: '#e74c3c', color: 'white', border: 'none', padding: '8px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>X</button>
          </div>

          {selectedEdgeId && (
            <button onClick={handleForceDeleteEdge} style={{ background: '#34495e', color: 'white', border: 'none', padding: '8px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>
              🗑️ Supprimer Câble Sélectionné
            </button>
          )}

          {selectedNodeId && (
            <button onClick={handleDeleteNode} style={{ background: '#c0392b', color: 'white', border: 'none', padding: '8px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>
              🗑️ Supprimer l'Équipement
            </button>
          )}
        </div>

        {/* Panneau d'Ajout */}
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)', padding: '15px', borderRadius: '8px', 
          boxShadow: '0 4px 6px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', gap: '10px', width: '220px'
        }}>
          <h4 style={{ margin: 0, color: '#2c3e50', fontFamily: 'sans-serif' }}>➕ Ajouter un Équipement</h4>
          <input 
            type="text" 
            placeholder="Nom (ex: R1)..." 
            value={newNodeLabel}
            onChange={(e) => setNewNodeLabel(e.target.value)}
            style={{ padding: '6px', borderRadius: '4px', border: '1px solid #ccc', fontFamily: 'sans-serif', fontSize: '13px' }}
          />
          <button onClick={handleCreateNode} style={{ background: '#9b59b6', color: 'white', border: 'none', padding: '8px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px' }}>
            Créer le Nœud
          </button>
          <button onClick={handlePurgeTout} style={{ background: '#d35400', color: 'white', border: 'none', padding: '6px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px', marginTop: '5px' }}>
            💥 Réinitialiser toute la Grille
          </button>
        </div>

      </div>

      {/* Télémesure Live */}
      <div style={{
        position: 'absolute', top: 20, right: 20, zIndex: 10, backgroundColor: '#2c3e50', color: 'white',
        padding: '15px', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)', width: '220px', fontFamily: 'sans-serif'
      }}>
        <h4 style={{ margin: '0 0 15px 0', borderBottom: '1px solid #34495e', paddingBottom: '10px' }}>🌐 Network Status (Live)</h4>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span>Équipements:</span> <strong>{stats.total_nodes}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span>Actifs:</span> <strong style={{ color: '#2ecc71' }}>{stats.active_nodes}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span>En Panne:</span> <strong style={{ color: stats.down_nodes > 0 ? '#e74c3c' : 'white' }}>{stats.down_nodes}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span>Câbles:</span> <strong>{stats.total_edges}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '15px', paddingTop: '10px', borderTop: '1px solid #34495e' }}>
          <span>Charge Moyenne:</span> 
          <strong style={{ color: stats.average_load > 0.8 ? '#e74c3c' : '#f1c40f' }}>
            {(stats.average_load * 100).toFixed(0)}%
          </strong>
        </div>
      </div>

      <ReactFlow 
        nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={onConnect} onNodeDragStop={onNodeDragStop}
        onEdgesDelete={onEdgesDelete}
        onEdgeClick={onEdgeClick}
        onNodeClick={onNodeClick}
        onEdgeDoubleClick={onEdgeDoubleClick}
        onNodeDoubleClick={onNodeDoubleClick}
        connectionLineType={ConnectionLineType.Straight}
        defaultEdgeOptions={{ type: 'straight' }}
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}