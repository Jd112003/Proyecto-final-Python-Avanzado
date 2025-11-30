from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import database
from database import Score, SessionLocal
import os

app = FastAPI()

# Inicializar DB
database.init_db()

# Dependencia para obtener sesión de DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos Pydantic
class ScoreCreate(BaseModel):
    username: str
    score: int

class ScoreResponse(BaseModel):
    username: str
    score: int
    
    class Config:
        from_attributes = True

# --- API Endpoints ---

@app.get("/api/scores", response_model=list[ScoreResponse])
def get_top_scores(db: Session = Depends(get_db)):
    # Retorna los top 10 puntajes
    return db.query(Score).order_by(Score.score.desc()).limit(10).all()

@app.post("/api/scores")
def create_score(score: ScoreCreate, db: Session = Depends(get_db)):
    db_score = Score(username=score.username, score=score.score)
    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    return db_score

# --- Servir Frontend y Juego ---
# (ELIMINADO: El frontend ahora lo sirve Nginx en otro contenedor)

# @app.get("/") ... (ELIMINADO)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
