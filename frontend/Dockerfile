# Etapa 1: Compilación del juego (Python -> WebAssembly)
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar pygbag
RUN pip install pygbag pygame-ce

# Copiar el juego y renombrarlo a main.py (estándar de pygbag)
COPY breakout.py main.py

# Compilar el juego (genera carpeta build/web)
RUN pygbag --build main.py

# Renombrar el index.html generado por pygbag a game.html
# para que nuestro index.html personalizado sea el principal
RUN mv build/web/index.html build/web/game.html

# Etapa 2: Servidor Web (Nginx)
FROM nginx:alpine

# Copiar configuración de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar los archivos compilados desde la etapa anterior
COPY --from=builder /app/build/web /usr/share/nginx/html

# Copiar nuestro index.html personalizado (UI con puntajes)
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80
