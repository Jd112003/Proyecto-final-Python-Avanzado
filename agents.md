# Guía rápida para agentes y colaboradores

Contexto: juego Breakout escrito en Python/Pygame, compilado a WebAssembly con Pygbag y servido por Nginx. Un backend FastAPI guarda puntajes en SQLite y expone `/api/scores`.

## Backend (API y persistencia)
- Ruta: `backend/`. Entrypoint: `server.py`; modelo `Score` y sesión en `database.py`.
- Dependencias clave: FastAPI, SQLAlchemy, Uvicorn (ver `backend/requirements.txt` y `backend/Dockerfile`).
- Endpoints: `GET /api/scores` (Top 5 descendente) y `POST /api/scores` con `{username, score}`; `ScoreResponse` usa `from_attributes=True` para mapear a ORM.
- La base `data/scores.db` se crea automáticamente; en Docker se monta `./data:/app/data` para persistirla. Si cambias el esquema, actualiza modelo SQLAlchemy y modelos Pydantic.
- Comando local: `uvicorn server:app --reload --host 0.0.0.0 --port 8000` dentro de un virtualenv con las dependencias instaladas.

## Frontend web (juego + UI)
- Ruta: `frontend/`. El juego web está en `frontend/breakout.py`; el Dockerfile multi-stage lo compila con `pygbag --build` y renombra `build/web/index.html` a `game.html`.
- `frontend/index.html` actúa como landing: incrusta `game.html` en un iframe y consulta la API para mostrar el Top 5 (polling cada 5s). No modificar el fetch base (`/api`) a menos que cambie el proxy.
- `frontend/nginx.conf` enruta `/` a los artefactos compilados y proxy-pasa `/api` a `backend:8000`.
- Para iterar sin Docker: `pip install pygbag pygame-ce`, luego `pygbag --build breakout.py` y renombra el `index.html` generado a `game.html`.

## Juego de escritorio (debug y balance)
- Ruta: `breakout.py` en la raíz. Ejecuta con `pip install pygame` y `python breakout.py`. Útil para probar mecánicas sin compilar a WebAssembly. No envía puntajes; solo juego local.

## Infra y operaciones
- `docker-compose.yml` levanta `frontend` (puerto 80) y `backend` (puerto 8000 interno). Usa la red por defecto; el nombre de host `backend` es crítico para el proxy de Nginx.
- Cambios en dependencias backend o juego web requieren `docker compose build` y luego `docker compose up`. El volumen `./data` conserva la base entre reinicios.
- Archivos ignorados por Docker están en `.dockerignore`; no almacenes archivos grandes en `frontend/build/` en el repo, se generan en el build stage.

## Checklist de smoke test
- `docker compose up --build` → entrar a `http://localhost/` y verificar que el juego carga y que la lista de puntajes aparece.
- Completar un juego en el navegador, enviar puntaje, y confirmar que `GET /api/scores` refleja el registro.
- Reiniciar contenedores y comprobar que los puntajes persisten gracias al volumen `./data`.
