FROM python:3.11-slim
WORKDIR /app

# Instala dependências do SO necessárias para compilar drivers
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Roda com -u para log aparecer instantaneamente
CMD ["python", "-u", "main.py"]