FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del backend
COPY . .

# Crear directorio para la DB
RUN mkdir -p data

# Exponer puerto
EXPOSE 8000

# Ejecutar servidor
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
