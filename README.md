# Breakout Web (Python, FastAPI, Pygbag)

Proyecto final: versión web del clásico Breakout escrita en Python/Pygame, compilada a WebAssembly con Pygbag y servida con Nginx. Un backend en FastAPI expone una API de puntajes persistida en SQLite y consumida desde el frontend.

## Características del juego
- **5 niveles** con patrones únicos: Estándar, Tablero de ajedrez, Pirámide, Columnas, Aleatorio
- **Sistema de desbloqueo progresivo** de niveles
- **Menú de selección** de niveles interactivo
- **Input de nombre** del jugador al finalizar
- **Contador de FPS en tiempo real** para comparar rendimiento Nativo vs WebAssembly
- **Tabla de puntajes** persistente (Top 5)

## Arquitectura
- `frontend/`: código del juego para web (`breakout.py`), `index.html` con UI y tabla de puntajes, `nginx.conf` y Dockerfile multi-stage que compila con Pygbag y publica los artefactos.
- `backend/`: API FastAPI (`server.py`) con modelo `Score` en SQLite (`data/scores.db`), manejado por SQLAlchemy; Dockerfile slim.
- `breakout.py`: versión de escritorio del juego (mismas funcionalidades que la web, optimizada para ejecución nativa).
- `docker-compose.yml`: orquesta los contenedores `frontend` (puerto 80) y `backend` (expuesto internamente en 8000) y monta `./data` para persistir la base.

## Comparativa de rendimiento: Nativo vs WebAssembly

El juego incluye un contador de FPS en la esquina superior izquierda para comparar el rendimiento entre ejecución nativa y WebAssembly.

### Resultados del benchmark (mediciones reales)

| Métrica | Nativo (Pygame) | WebAssembly (Pygbag) |
|---------|-----------------|----------------------|
| **FPS Promedio** | ~123 FPS | ~73 FPS |
| **FPS Mínimo** | ~120 FPS | ~69 FPS |
| **FPS Máximo** | ~125 FPS | ~102 FPS |
| **Target FPS** | 120 | 120 |

> **Nota**: El rendimiento de WebAssembly mejora a medida que disminuyen los bloques en pantalla (menos objetos que renderizar). También mejora cuando el navegador está en primer plano.

### Factores que afectan el rendimiento
- **Nativo**: Sin límites de sandbox, acceso directo a GPU, menor overhead
- **WebAssembly**: Sandbox del navegador, overhead de emulación, depende del estado del navegador (primer/segundo plano)
- **Carga de renderizado**: Más bloques en pantalla = menor FPS en ambas versiones

## Requisitos
- Docker y Docker Compose.
- Para desarrollo sin contenedores: Python 3.11+ y pip.
- Para recompilar el frontend web localmente: `pygbag` y `pygame-ce` (solo necesarios si modificas `frontend/breakout.py`).

## Puesta en marcha rápida (Docker)
```bash
docker compose up --build
```
- Frontend: http://localhost/ (carga `index.html`, incrusta `game.html` generado por Pygbag y muestra Top 5).
- Backend API: accesible desde el frontend vía `/api`; base persistida en `./data/scores.db` gracias al volumen.

## Controles del juego
| Tecla | Acción |
|-------|--------|
| ← → / A D | Mover paddle |
| Espacio | Lanzar bola |
| P | Pausar/Reanudar |
| M / ESC | Volver al menú |
| F10 | Cheat: dejar 1 ladrillo |

## Uso de la API de puntajes
- `GET /api/scores` → lista de los 5 mejores puntajes ordenados de mayor a menor.
- `POST /api/scores` con cuerpo `{"username": "Alice", "score": 1234}` → crea un registro.

Ejemplo rápido:
```bash
curl -X POST http://localhost/api/scores \
  -H "Content-Type: application/json" \
  -d '{"username":"Player1","score":9000}'

curl http://localhost/api/scores
```

## Desarrollo sin Docker
### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```
- La base se crea en `backend/data/scores.db` automáticamente.

### Juego de escritorio (Pygame)
```bash
pip install pygame
python breakout.py
```
Observa el contador **FPS: XX.X (Nativo)** en la esquina superior izquierda.

### Recompilar el frontend web (opcional)
```bash
cd frontend
pip install pygbag pygame-ce
pygbag --build breakout.py
mv build/web/index.html build/web/game.html  # renombrar para que lo consuma nuestro index.html
```
Luego sirve `build/web/` con un servidor simple o reemplaza el contenido del contenedor Nginx si estás iterando en Docker.

## Notas
- El backend se inicializa al importar `database.init_db()`, por lo que no se necesitan migraciones para el esquema actual.
- El frontend usa `fetch('/api/scores')`, y Nginx enruta `/api` al servicio backend dentro de la red de Docker Compose.
- Ambas versiones del juego (nativa y web) comparten las mismas funcionalidades: 5 niveles, menú, input de nombre, FPS counter.
- El contador de FPS permite comparar el rendimiento entre plataformas en tiempo real.
