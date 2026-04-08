"""
api/main_api.py — ADHD Platform FastAPI backend
Complete REST API with auth, patient management, appointments & reviews.
Run: uvicorn api.main_api:app --host 0.0.0.0 --port 8000
"""
import os, sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
import bcrypt
import jwt  # PyJWT

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ADHD Platform API",
    version="2.0.0",
    description="Patient management, appointments, and reviews for the ADHD Assessment Platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET    = os.environ.get("JWT_SECRET", "adhd-platform-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 24
security      = HTTPBearer()


# ── JWT helpers ────────────────────────────────────────────────────────────────
def _create_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return _decode_token(creds.credentials)


def require_role(*roles):
    def _check(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check


# ── Pydantic Models ────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username:  str        = Field(..., min_length=3, max_length=50)
    email:     str        = Field(..., min_length=5)
    password:  str        = Field(..., min_length=6)
    role:      str        = Field("patient", pattern="^(patient|clinician|admin)$")
    full_name: str        = ""
    age:       int        = Field(0, ge=0, le=120)
    gender:    str        = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class AppointmentRequest(BaseModel):
    appt_date: str = Field(..., description="YYYY-MM-DD")
    appt_time: str = Field(..., description="e.g. 10:00 AM")
    reason:    str = ""


class ReviewRequest(BaseModel):
    rating:  int = Field(..., ge=1, le=5)
    comment: str = ""


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(booked|completed|cancelled)$")


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "ADHD Platform API", "version": "2.0.0"}


@app.get("/health", tags=["Health"])
def health():
    db.init_db()
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/register", tags=["Auth"], status_code=201)
def register(req: RegisterRequest):
    """
    Register a new user.

    Sample response (patient):
    ```json
    {
        "message": "Account created successfully",
        "user_id": 5,
        "patient_uid": "PAT-2026-0001",
        "role": "patient"
    }
    ```
    """
    result = db.register_user(
        username=req.username,
        email=req.email,
        password=req.password,
        role=req.role,
        full_name=req.full_name,
        age=req.age,
        gender=req.gender,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "message":     "Account created successfully",
        "user_id":     result["user_id"],
        "patient_uid": result.get("patient_uid") or None,
        "role":        req.role,
    }


@app.post("/login", tags=["Auth"])
def login(req: LoginRequest):
    """
    Authenticate and receive a JWT bearer token.

    Sample response:
    ```json
    {
        "access_token": "eyJ...",
        "token_type": "bearer",
        "user": {"id": 1, "username": "john", "role": "patient"},
        "patient_uid": "PAT-2026-0001"
    }
    ```
    """
    user = db.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    patient_uid = None
    if user["role"] == "patient":
        patient = db.get_user_patient(user["id"])
        patient_uid = patient.get("patient_uid") if patient else None

    token = _create_token({
        "sub":  str(user["id"]),
        "role": user["role"],
        "username": user["username"],
    })
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":       user["id"],
            "username": user["username"],
            "email":    user.get("email", ""),
            "role":     user["role"],
        },
        "patient_uid": patient_uid,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PATIENT
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/patient/dashboard", tags=["Patient"])
def patient_dashboard(current_user: dict = Depends(get_current_user)):
    """
    Return the authenticated patient's dashboard data.

    Sample response:
    ```json
    {
        "patient": {"id": 1, "patient_uid": "PAT-2026-0001", "name": "Jane Doe", ...},
        "stats": {"assessments": 3, "appointments": 2, "upcoming": 1},
        "latest_assessment": {"total_score": 36, "risk_level": "Moderate Risk"},
        "upcoming_appointments": [...]
    }
    ```
    """
    if current_user.get("role") != "patient":
        raise HTTPException(status_code=403, detail="Patient role required")

    user_id = int(current_user["sub"])
    patient = db.get_user_patient(user_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    pid         = patient["id"]
    assessments = db.get_questionnaires(pid)
    appts       = db.get_appointments(pid)
    upcoming    = [a for a in appts if a["status"] == "booked"]

    return {
        "patient": patient,
        "stats": {
            "assessments":  len(assessments),
            "appointments": len(appts),
            "upcoming":     len(upcoming),
        },
        "latest_assessment": assessments[0] if assessments else None,
        "upcoming_appointments": upcoming[:3],
    }


@app.get("/patients", tags=["Patient"])
def list_patients(current_user: dict = Depends(require_role("clinician", "admin"))):
    """List all patients (clinician/admin only)."""
    patients = db.get_patients()
    return {"count": len(patients), "data": patients}


@app.get("/patients/{patient_id}", tags=["Patient"])
def get_patient(patient_id: int,
                current_user: dict = Depends(get_current_user)):
    patient = db.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


# ══════════════════════════════════════════════════════════════════════════════
# APPOINTMENTS
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/appointments/book", tags=["Appointments"], status_code=201)
def book_appointment(req: AppointmentRequest,
                     current_user: dict = Depends(get_current_user)):
    """
    Book an appointment for the authenticated patient.

    Sample response:
    ```json
    {
        "message": "Appointment booked",
        "appointment_id": 3,
        "token": "TOK-20260410-0001",
        "appt_date": "2026-04-10",
        "appt_time": "10:00 AM"
    }
    ```
    """
    user_id = int(current_user["sub"])
    role    = current_user.get("role")

    if role == "patient":
        patient = db.get_user_patient(user_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        pid = patient["id"]
    else:
        raise HTTPException(status_code=403, detail="Only patients can book appointments via this endpoint")

    result = db.book_appointment(
        patient_id=pid,
        user_id=user_id,
        appt_date=req.appt_date,
        appt_time=req.appt_time,
        reason=req.reason,
    )
    return {
        "message":        "Appointment booked",
        "appointment_id": result["id"],
        "token":          result["token"],
        "appt_date":      req.appt_date,
        "appt_time":      req.appt_time,
    }


@app.get("/appointments/list", tags=["Appointments"])
def list_appointments(current_user: dict = Depends(get_current_user)):
    """
    List appointments.
    - Patient sees only their own appointments.
    - Clinician/Admin sees all appointments.

    Sample response:
    ```json
    {
        "count": 2,
        "data": [
            {
                "id": 1, "token": "TOK-20260410-0001",
                "appt_date": "2026-04-10", "appt_time": "10:00 AM",
                "status": "booked", "patient_name": "Jane Doe",
                "patient_uid": "PAT-2026-0001"
            }
        ]
    }
    ```
    """
    user_id = int(current_user["sub"])
    role    = current_user.get("role")

    if role == "patient":
        patient = db.get_user_patient(user_id)
        pid     = patient["id"] if patient else None
        appts   = db.get_appointments(pid) if pid else []
    else:
        appts = db.get_appointments()

    return {"count": len(appts), "data": appts}


@app.patch("/appointments/{appt_id}/status", tags=["Appointments"])
def update_appointment(appt_id: int, req: StatusUpdateRequest,
                       current_user: dict = Depends(get_current_user)):
    """Update appointment status (completed / cancelled)."""
    db.update_appointment_status(appt_id, req.status)
    return {"message": f"Appointment {appt_id} updated to '{req.status}'"}


# ══════════════════════════════════════════════════════════════════════════════
# REVIEWS
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/reviews/add", tags=["Reviews"], status_code=201)
def add_review(req: ReviewRequest,
               current_user: dict = Depends(get_current_user)):
    """
    Submit a review (patients only).

    Sample response:
    ```json
    {"message": "Review submitted", "review_id": 4}
    ```
    """
    if current_user.get("role") != "patient":
        raise HTTPException(status_code=403, detail="Only patients can submit reviews")

    user_id = int(current_user["sub"])
    patient = db.get_user_patient(user_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    review_id = db.add_review(
        patient_id=patient["id"],
        user_id=user_id,
        rating=req.rating,
        comment=req.comment,
    )
    return {"message": "Review submitted", "review_id": review_id}


@app.get("/reviews/list", tags=["Reviews"])
def list_reviews(patient_id: Optional[int] = None):
    """
    List public reviews with average rating.

    Sample response:
    ```json
    {
        "stats": {"total": 12, "avg_rating": 4.3},
        "count": 12,
        "data": [{"patient_name": "Jane D.", "rating": 5, "comment": "...", ...}]
    }
    ```
    """
    reviews = db.get_reviews(patient_id)
    stats   = db.get_review_stats()

    # Anonymise names
    for r in reviews:
        name   = r.get("patient_name", "")
        parts  = name.split()
        r["patient_name"] = (
            f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]
        ) if parts else "Anonymous"

    return {"stats": stats, "count": len(reviews), "data": reviews}


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY EEG + STATS (unchanged)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/eeg", tags=["EEG"])
def get_latest_eeg():
    """Return the most recent EEG sample across all patients."""
    with db.get_conn() as conn:
        row = db._exec(conn,
            "SELECT * FROM eeg_signals ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()

    if not row:
        return {
            "status": "no_data",
            "attention": 0, "meditation": 0, "quality": 0,
            "delta": 0, "theta": 0, "lowAlpha": 0, "highAlpha": 0,
            "lowBeta": 0, "highBeta": 0, "lowGamma": 0, "midGamma": 0,
            "theta_beta_ratio": 0.0,
        }
    r = dict(row)
    return {
        "status":           "live",
        "recorded_at":      r["recorded_at"],
        "patient_id":       r["patient_id"],
        "session_id":       r["session_id"],
        "quality":          r["quality"],
        "attention":        r["attention"],
        "meditation":       r["meditation"],
        "delta":            r["delta"],
        "theta":            r["theta"],
        "lowAlpha":         r["low_alpha"],
        "highAlpha":        r["high_alpha"],
        "lowBeta":          r["low_beta"],
        "highBeta":         r["high_beta"],
        "lowGamma":         r["low_gamma"],
        "midGamma":         r["mid_gamma"],
        "theta_beta_ratio": r["theta_beta_ratio"],
    }


@app.get("/eeg/patient/{patient_id}", tags=["EEG"])
def get_patient_eeg(patient_id: int, limit: int = 100):
    with db.get_conn() as conn:
        rows = db._exec(conn,
            "SELECT * FROM eeg_signals WHERE patient_id=%s ORDER BY recorded_at DESC LIMIT %s",
            (patient_id, limit),
        ).fetchall()
    return {"patient_id": patient_id, "count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/eeg/session/{session_id}", tags=["EEG"])
def get_session_eeg(session_id: str):
    with db.get_conn() as conn:
        rows = db._exec(conn,
            "SELECT * FROM eeg_signals WHERE session_id=%s ORDER BY recorded_at ASC",
            (session_id,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/stats", tags=["Stats"])
def get_stats():
    """Return dashboard statistics."""
    stats = db.get_dashboard_stats()
    return {
        "total_patients":     stats["total_patients"],
        "total_assessments":  stats["total_assessments"],
        "total_eeg_sessions": stats["total_eeg"],
        "total_appointments": stats["total_appointments"],
    }
