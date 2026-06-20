-- Création de l'extension pour générer des UUID si besoin
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table des équipements réseau (Nœuds)
CREATE TABLE IF NOT EXISTS nodes (
    id VARCHAR(50) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,          -- ex: 'router', '5g_antenna', 'client'
    label VARCHAR(100) NOT NULL,        -- Nom de l'équipement
    position_x FLOAT NOT NULL,          -- Coordonnée X pour React Flow
    position_y FLOAT NOT NULL,          -- Coordonnée Y pour React Flow
    status VARCHAR(20) DEFAULT 'active',-- 'active', 'offline', 'error'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des liaisons réseau (Arêtes/Câbles)
CREATE TABLE IF NOT EXISTS edges (
    id VARCHAR(50) PRIMARY KEY,
    source_id VARCHAR(50) NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id VARCHAR(50) NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    load FLOAT DEFAULT 0.0,             -- La colonne manquante qui causait l'erreur !
    bandwidth INT DEFAULT 1000,         -- Bande passante en Mbps
    latency INT DEFAULT 10,             -- Latence de base en ms
    status VARCHAR(20) DEFAULT 'active',-- 'active', 'cut' (coupé)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertion de données de test (optionnel mais pratique pour vérifier)
INSERT INTO nodes (id, type, label, position_x, position_y) VALUES
('node-1', 'router', 'Routeur Core de Test', 250, 5),
('node-2', '5g_antenna', 'Antenne 5G de Test', 100, 100)
ON CONFLICT (id) DO NOTHING;

INSERT INTO edges (id, source_id, target_id, bandwidth, load) VALUES
('edge-1-2', 'node-1', 'node-2', 10000, 0.0)
ON CONFLICT (id) DO NOTHING;