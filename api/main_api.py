"""
api/main_api.py — ADHD Platform FastAPI backend
Serves latest EEG data from SQLite database.
Run: uvicorn api.main_api:app --host 0.0.0.0 --port 8000
"""
import os, sys, sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="ADHD Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "adhd_platform.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def root():
    return {"status": "ok", "service": "ADHD Platform API"}


@app.get("/eeg")
def get_latest_eeg():
    """Return the most recent EEG sample across all patients."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM eeg_signals ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {
            "status": "no_data",
            "attention": 0,
            "meditation": 0,
            "quality": 0,
            "delta": 0,
            "theta": 0,
            "lowAlpha": 0,
            "highAlpha": 0,
            "lowBeta": 0,
            "highBeta": 0,
            "lowGamma": 0,
            "midGamma": 0,
            "theta_beta_ratio": 0.0,
        }

    r = dict(row)
    return {
        "status": "live",
        "recorded_at": r["recorded_at"],
        "patient_id": r["patient_id"],
        "session_id": r["session_id"],
        "quality": r["quality"],
        "attention": r["attention"],
        "meditation": r["meditation"],
        "delta": r["delta"],
        "theta": r["theta"],
        "lowAlpha": r["low_alpha"],
        "highAlpha": r["high_alpha"],
        "lowBeta": r["low_beta"],
        "highBeta": r["high_beta"],
        "lowGamma": r["low_gamma"],
        "midGamma": r["mid_gamma"],
        "theta_beta_ratio": r["theta_beta_ratio"],
    }


@app.get("/eeg/patient/{patient_id}")
def get_patient_eeg(patient_id: int, limit: int = 100):
    """Return recent EEG samples for a specific patient."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM eeg_signals WHERE patient_id=? ORDER BY recorded_at DESC LIMIT ?",
            (patient_id, limit),
        ).fetchall()
    finally:
        conn.close()

    return {"patient_id": patient_id, "count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/eeg/session/{session_id}")
def get_session_eeg(session_id: str):
    """Return all EEG samples for a specific session."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM eeg_signals WHERE session_id=? ORDER BY recorded_at ASC",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/patients")
def get_patients():
    """Return all patients."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT id, name, age, gender, created_at FROM patients ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/stats")
def get_stats():
    """Return dashboard statistics."""
    conn = _get_conn()
    try:
        total_patients    = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        total_eeg         = conn.execute("SELECT COUNT(*) FROM eeg_signals").fetchone()[0]
        total_assessments = conn.execute("SELECT COUNT(*) FROM questionnaire_results").fetchone()[0]
        total_emotions    = conn.execute("SELECT COUNT(*) FROM emotion_logs").fetchone()[0]
    finally:
        conn.close()
    return {
        "total_patients": total_patients,
        "total_eeg_samples": total_eeg,
        "total_assessments": total_assessments,
        "total_emotion_logs": total_emotions,
    }
