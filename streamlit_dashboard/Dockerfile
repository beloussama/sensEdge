# Utilise une image Python légère
FROM python:3.10-slim

# Répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances
COPY requirements.txt .

# Installation des dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copie du reste de l'application
COPY . .

# Port exposé par Streamlit
EXPOSE 8501

# Lancement de l'app Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
