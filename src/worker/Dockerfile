FROM python:3.11-slim

# 1. CRÍTICO: Garante que os logs apareçam imediatamente no painel (Resolve o "Sem Log")
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema para o Postgres
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Instala as bibliotecas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do robô
COPY . .

# 2. CRÍTICO: Comando explícito para iniciar o robô
CMD ["python", "main.py"]