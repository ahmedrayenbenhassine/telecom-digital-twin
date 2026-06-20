# Utilisation d'une image Python légère
FROM python:3.11-slim

# Définition du répertoire de travail dans le conteneur
WORKDIR /app

# Copie des dépendances et installation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du reste du code
COPY . .

# Commande pour démarrer le serveur avec rechargement à chaud
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]