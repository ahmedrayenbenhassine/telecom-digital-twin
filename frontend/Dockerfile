# Utilisation d'une image node légère
FROM node:20-slim

# Définition du répertoire de travail
WORKDIR /app

# Copie des fichiers de configuration pour installer les dépendances
COPY package*.json ./
RUN npm install

# Copie du reste du code source
COPY . .

# Exposition du port
EXPOSE 5173

# Commande pour démarrer le serveur de développement sur le port 3000
CMD ["npm", "run", "dev", "--", "--host", "--port", "3000"]