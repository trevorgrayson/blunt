import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Path, Body
from fastapi import FastAPI, HTTPException, Path, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
from pydantic import BaseModel

app = FastAPI(title="Meet API with Subjects & Notes")

DB_PATH = "meet.db"
STATIC_DIR='meet/static'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS agenda_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        );
        """)
init_db()


# ---------- Models ----------

class SubjectCreate(BaseModel):
    subject: str
    description: str | None = None

class SubjectUpdate(BaseModel):
    description: str

class AgendaItemCreate(BaseModel):
    body: str

class AgendaNotesUpdate(BaseModel):
    notes: str


# ---------- Endpoints ----------

@app.post("/subjects")
def create_subject(subject: SubjectCreate):
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute(
                "INSERT INTO subjects (subject, description) VALUES (?, ?)",
                (subject.subject, subject.description)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Subject already exists")
    return {"message": "Subject created", "subject": subject.subject}


@app.patch("/subjects/{subject}")
def update_subject_description(subject: str, body: SubjectUpdate):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE subjects SET description = ? WHERE subject = ?", (body.description, subject))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Subject not found")
        conn.commit()
    return {"message": "Subject updated", "subject": subject, "description": body.description}


@app.get("/subjects")
def list_subjects():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM subjects ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


@app.post("/meet/{subject}")
def add_agenda_item(subject: str, item: AgendaItemCreate = Body(...)):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Ensure subject exists — create automatically if not
        cur.execute("SELECT id FROM subjects WHERE subject = ?", (subject,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO subjects (subject) VALUES (?)", (subject,))
            conn.commit()
            subject_id = cur.lastrowid
        else:
            subject_id = row[0]
        # Insert agenda item
        cur.execute(
            "INSERT INTO agenda_items (subject_id, body) VALUES (?, ?)",
            (subject_id, item.body)
        )
        conn.commit()
    return {"message": "Agenda item added", "subject": subject, "body": item.body}


@app.get("/meet/{subject}")
def get_agenda_items(subject: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM subjects WHERE subject = ?", (subject,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Subject not found")
        subject_id = row[0]
        cur.execute("""
            SELECT * FROM agenda_items
            WHERE subject_id = ?
            ORDER BY created_at DESC
        """, (subject_id,))
        items = [dict(r) for r in cur.fetchall()]
    return {"subject": subject, "items": items}


@app.post("/meet/{subject}/{id}/resolve")
def resolve_item(subject: str, id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE agenda_items
            SET resolved = 1, updated_at = ?
            WHERE id = (SELECT a.id FROM agenda_items a
                        JOIN subjects s ON a.subject_id = s.id
                        WHERE s.subject = ? AND a.id = ?)
        """, (datetime.utcnow(), subject, id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Agenda item not found")
        conn.commit()
    return {"message": "Item resolved", "subject": subject, "id": id}


@app.patch("/meet/{subject}/{id}/notes")
def update_notes(subject: str, id: int, update: AgendaNotesUpdate):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE agenda_items
            SET notes = ?, updated_at = ?
            WHERE id = (SELECT a.id FROM agenda_items a
                        JOIN subjects s ON a.subject_id = s.id
                        WHERE s.subject = ? AND a.id = ?)
        """, (update.notes, datetime.utcnow(), subject, id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Agenda item not found")
        conn.commit()
    return {"message": "Notes updated", "subject": subject, "id": id, "notes": update.notes}

# ---------- Static SPA ----------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

