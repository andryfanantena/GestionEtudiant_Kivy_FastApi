import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Gestion de présence")
DB_FILE = "students.db"


# ---------- Petit utilitaire pour parler à la base SQLite ----------
def run(sql, params=()):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        conn.commit()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Création de la table au démarrage (si elle n'existe pas)
run(
    """CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'none'
    )"""
)


# ---------- Modèles de données (ce que le client envoie) ----------
class StudentIn(BaseModel):
    name: str


class PresenceIn(BaseModel):
    present: bool


class AttendanceStartIn(BaseModel):
    present_student_ids: list[int] = Field(default_factory=list)


# ---------- Étudiants ----------
@app.get("/students")
def list_students():
    return run("SELECT * FROM students ORDER BY name")


@app.post("/students")
def add_student(student: StudentIn):
    name = student.name.strip()
    if not name:
        raise HTTPException(400, "Le nom ne peut pas être vide")
    run("INSERT INTO students (name) VALUES (?)", (name,))
    return {"message": f"{name} ajouté"}


@app.delete("/students/{student_id}")
def delete_student(student_id: int):
    if not run("SELECT id FROM students WHERE id = ?", (student_id,)):
        raise HTTPException(404, "Étudiant introuvable")
    run("DELETE FROM students WHERE id = ?", (student_id,))
    return {"message": "Étudiant supprimé"}


# ---------- Présence ----------
@app.post("/attendance/start")
def start_attendance(body: AttendanceStartIn | None = None):
    """Démarre une présence en conservant les étudiants cochés avant le démarrage."""
    present_ids = set((body or AttendanceStartIn()).present_student_ids)
    if present_ids:
        placeholders = ", ".join("?" for _ in present_ids)
        run(
            f"UPDATE students SET status = CASE WHEN id IN ({placeholders}) "
            "THEN 'present' ELSE 'absent' END",
            tuple(present_ids),
        )
    else:
        run("UPDATE students SET status = 'absent'")
    return {"message": "Présence démarrée"}


@app.put("/students/{student_id}/presence")
def set_presence(student_id: int, body: PresenceIn):
    status = "present" if body.present else "absent"
    run("UPDATE students SET status = ? WHERE id = ?", (status, student_id))
    return {"message": "Présence mise à jour", "status": status}


@app.get("/attendance/present")
def list_present():
    return run("SELECT * FROM students WHERE status = 'present' ORDER BY name")


@app.get("/attendance/absent")
def list_absent():
    return run("SELECT * FROM students WHERE status = 'absent' ORDER BY name")

