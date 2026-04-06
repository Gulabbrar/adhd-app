"""
database.py — Centralized SQLite data layer
ADHD Assessment Platform
"""
import sqlite3, os, json, bcrypt
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "adhd_platform.db")
)


@contextmanager
def get_conn():
    """Thread-safe SQLite connection with WAL mode."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn):
    """Add new columns to existing tables without breaking existing data."""
    migrations = [
        ("users",    "email",       "TEXT DEFAULT ''"),
        ("patients", "user_id",     "INTEGER DEFAULT NULL"),
        ("patients", "patient_uid", "TEXT DEFAULT ''"),
    ]
    for table, col, typedef in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass  # column already exists


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            email      TEXT DEFAULT '',
            password   TEXT NOT NULL,
            role       TEXT DEFAULT 'clinician',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS patients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER DEFAULT NULL REFERENCES users(id),
            patient_uid TEXT DEFAULT '',
            name        TEXT NOT NULL,
            age         INTEGER DEFAULT 0,
            gender      TEXT DEFAULT '',
            email       TEXT DEFAULT '',
            phone       TEXT DEFAULT '',
            notes       TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS eeg_signals (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id       INTEGER REFERENCES patients(id),
            session_id       TEXT NOT NULL,
            recorded_at      TEXT DEFAULT (datetime('now','localtime')),
            quality          INTEGER DEFAULT 0,
            attention        INTEGER DEFAULT 0,
            meditation       INTEGER DEFAULT 0,
            delta            INTEGER DEFAULT 0,
            theta            INTEGER DEFAULT 0,
            low_alpha        INTEGER DEFAULT 0,
            high_alpha       INTEGER DEFAULT 0,
            low_beta         INTEGER DEFAULT 0,
            high_beta        INTEGER DEFAULT 0,
            low_gamma        INTEGER DEFAULT 0,
            mid_gamma        INTEGER DEFAULT 0,
            theta_beta_ratio REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS questionnaire_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER REFERENCES patients(id),
            session_id   TEXT NOT NULL,
            responses    TEXT NOT NULL DEFAULT '{}',
            total_score  INTEGER DEFAULT 0,
            inatt_score  INTEGER DEFAULT 0,
            hyper_score  INTEGER DEFAULT 0,
            risk_level   TEXT DEFAULT '',
            assessed_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS emotion_logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id       INTEGER REFERENCES patients(id),
            session_id       TEXT NOT NULL,
            logged_at        TEXT DEFAULT (datetime('now','localtime')),
            dominant_emotion TEXT DEFAULT '',
            happy            REAL DEFAULT 0,
            neutral          REAL DEFAULT 0,
            sad              REAL DEFAULT 0,
            angry            REAL DEFAULT 0,
            fear             REAL DEFAULT 0,
            surprise         REAL DEFAULT 0,
            disgust          REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS activity_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER REFERENCES patients(id),
            session_id      TEXT NOT NULL,
            activity_name   TEXT NOT NULL,
            accuracy        REAL DEFAULT 0,
            completion_time REAL DEFAULT 0,
            error_rate      REAL DEFAULT 0,
            attention_score REAL DEFAULT 0,
            details         TEXT DEFAULT '{}',
            completed_at    TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS assessment_reports (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id            INTEGER REFERENCES patients(id),
            session_id            TEXT NOT NULL,
            eeg_interpretation    TEXT DEFAULT '',
            questionnaire_summary TEXT DEFAULT '',
            emotion_summary       TEXT DEFAULT '',
            activity_summary      TEXT DEFAULT '',
            final_classification  TEXT DEFAULT '',
            risk_score            REAL DEFAULT 0,
            eeg_score             REAL DEFAULT 0,
            questionnaire_score   REAL DEFAULT 0,
            emotion_score         REAL DEFAULT 0,
            activity_score        REAL DEFAULT 0,
            generated_at          TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  INTEGER REFERENCES patients(id),
            user_id     INTEGER REFERENCES users(id),
            appt_date   TEXT NOT NULL,
            appt_time   TEXT NOT NULL,
            token       TEXT NOT NULL,
            reason      TEXT DEFAULT '',
            status      TEXT DEFAULT 'booked',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  INTEGER REFERENCES patients(id),
            user_id     INTEGER REFERENCES users(id),
            rating      INTEGER NOT NULL,
            comment     TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS mood_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER REFERENCES patients(id),
            user_id      INTEGER REFERENCES users(id),
            logged_at    TEXT DEFAULT (datetime('now','localtime')),
            mood_score   INTEGER DEFAULT 5,
            energy_level INTEGER DEFAULT 5,
            sleep_hours  REAL    DEFAULT 7,
            mood_label   TEXT    DEFAULT '',
            notes        TEXT    DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_eeg_patient    ON eeg_signals(patient_id, session_id);
        CREATE INDEX IF NOT EXISTS idx_q_patient      ON questionnaire_results(patient_id);
        CREATE INDEX IF NOT EXISTS idx_emo_patient    ON emotion_logs(patient_id, session_id);
        CREATE INDEX IF NOT EXISTS idx_act_patient    ON activity_results(patient_id);
        CREATE INDEX IF NOT EXISTS idx_rep_patient    ON assessment_reports(patient_id);
        CREATE INDEX IF NOT EXISTS idx_appt_patient   ON appointments(patient_id);
        CREATE INDEX IF NOT EXISTS idx_review_patient ON reviews(patient_id);
        CREATE INDEX IF NOT EXISTS idx_mood_patient   ON mood_logs(patient_id);
        """)

        # Seed default staff accounts (plain text — legacy, still works via fallback auth)
        conn.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?,?,?,?)",
            ("admin", "admin@adhd.local", "admin123", "admin")
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?,?,?,?)",
            ("clinician", "clinic@adhd.local", "clinic123", "clinician")
        )

        # Run migrations for any pre-existing DB
        _migrate(conn)

        # Ensure mood_logs exists in older databases
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS mood_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER REFERENCES patients(id),
            user_id      INTEGER REFERENCES users(id),
            logged_at    TEXT DEFAULT (datetime('now','localtime')),
            mood_score   INTEGER DEFAULT 5,
            energy_level INTEGER DEFAULT 5,
            sleep_hours  REAL    DEFAULT 7,
            mood_label   TEXT    DEFAULT '',
            notes        TEXT    DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_mood_patient ON mood_logs(patient_id);
        """)


# ── Password helpers ──────────────────────────────────────────────────────────
def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, stored: str) -> bool:
    """Support both bcrypt hashes and legacy plain-text passwords."""
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        try:
            return bcrypt.checkpw(plain.encode(), stored.encode())
        except Exception:
            return False
    # Legacy plain-text fallback (for seeded admin/clinician accounts)
    return plain == stored


# ── Patient UID generation ────────────────────────────────────────────────────
def _generate_patient_uid(conn) -> str:
    year = datetime.now().year
    row = conn.execute(
        "SELECT COUNT(*) FROM patients WHERE patient_uid LIKE ?",
        (f"PAT-{year}-%",)
    ).fetchone()
    seq = (row[0] if row else 0) + 1
    return f"PAT-{year}-{seq:04d}"


# ── Auth ──────────────────────────────────────────────────────────────────────
def authenticate(username: str, password: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, role, password FROM users WHERE username=?",
            (username,)
        ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password"]):
        return None
    return {"id": row["id"], "username": row["username"],
            "email": row["email"], "role": row["role"]}


def register_user(username: str, email: str, password: str, role: str,
                  full_name: str = "", age: int = 0, gender: str = "") -> dict:
    """
    Register a new user. If role == 'patient', also creates a patients record
    and generates a PAT-YYYY-XXXX patient UID.
    Returns: {"ok": True, "user_id": ..., "patient_uid": ...} or {"ok": False, "error": ...}
    """
    hashed = _hash_password(password)
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password, role) VALUES (?,?,?,?)",
                (username, email, hashed, role)
            )
            user_id = cur.lastrowid
            patient_uid = ""
            patient_id  = None

            if role == "patient":
                patient_uid = _generate_patient_uid(conn)
                name = full_name.strip() if full_name.strip() else username
                pc = conn.execute(
                    "INSERT INTO patients (user_id, patient_uid, name, age, gender, email) "
                    "VALUES (?,?,?,?,?,?)",
                    (user_id, patient_uid, name, age, gender, email)
                )
                patient_id = pc.lastrowid

        return {"ok": True, "user_id": user_id,
                "patient_uid": patient_uid, "patient_id": patient_id}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "Username already exists."}


def get_user_patient(user_id: int) -> dict:
    """Return the patients record linked to a user account."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else {}


# ── Patients ──────────────────────────────────────────────────────────────────
def add_patient(name, age, gender, email="", phone="", notes="") -> int:
    with get_conn() as conn:
        # Auto-assign a patient_uid even for clinician-added patients
        uid = _generate_patient_uid(conn)
        cur = conn.execute(
            "INSERT INTO patients (patient_uid, name, age, gender, email, phone, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, name, age, gender, email, phone, notes)
        )
        return cur.lastrowid


def get_patients() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_patient(patient_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE id=?", (patient_id,)
        ).fetchone()
    return dict(row) if row else {}


def update_patient(patient_id, name, age, gender, email, phone, notes):
    with get_conn() as conn:
        conn.execute(
            "UPDATE patients SET name=?,age=?,gender=?,email=?,phone=?,notes=? WHERE id=?",
            (name, age, gender, email, phone, notes, patient_id)
        )


def delete_patient(patient_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM patients WHERE id=?", (patient_id,))


# ── Appointments ──────────────────────────────────────────────────────────────
def _generate_token(conn, appt_date: str) -> str:
    date_str = appt_date.replace("-", "")
    row = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE appt_date=?", (appt_date,)
    ).fetchone()
    seq = (row[0] if row else 0) + 1
    return f"TOK-{date_str}-{seq:04d}"


def book_appointment(patient_id: int, user_id: int,
                     appt_date: str, appt_time: str, reason: str = "") -> dict:
    with get_conn() as conn:
        token = _generate_token(conn, appt_date)
        cur = conn.execute(
            "INSERT INTO appointments (patient_id, user_id, appt_date, appt_time, token, reason) "
            "VALUES (?,?,?,?,?,?)",
            (patient_id, user_id, appt_date, appt_time, token, reason)
        )
        return {"id": cur.lastrowid, "token": token}


def get_appointments(patient_id: int = None) -> list:
    with get_conn() as conn:
        if patient_id:
            rows = conn.execute("""
                SELECT a.*, p.name as patient_name, p.patient_uid
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                WHERE a.patient_id=?
                ORDER BY a.appt_date DESC, a.appt_time DESC
            """, (patient_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT a.*, p.name as patient_name, p.patient_uid
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                ORDER BY a.appt_date DESC, a.appt_time DESC
            """).fetchall()
    return [dict(r) for r in rows]


def update_appointment_status(appt_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE appointments SET status=? WHERE id=?", (status, appt_id)
        )


# ── Mood Logs ─────────────────────────────────────────────────────────────────
def add_mood_log(patient_id: int, user_id: int, mood_score: int,
                 energy_level: int, sleep_hours: float,
                 mood_label: str = "", notes: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO mood_logs "
            "(patient_id, user_id, mood_score, energy_level, sleep_hours, mood_label, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (patient_id, user_id, mood_score, energy_level, sleep_hours, mood_label, notes)
        )
        return cur.lastrowid


def get_mood_logs(patient_id: int, limit: int = 90) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mood_logs WHERE patient_id=? "
            "ORDER BY logged_at DESC LIMIT ?",
            (patient_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def get_mood_streak(patient_id: int) -> int:
    """Count consecutive days the patient logged their mood (ending today)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DATE(logged_at) as day FROM mood_logs "
            "WHERE patient_id=? GROUP BY day ORDER BY day DESC",
            (patient_id,)
        ).fetchall()
    if not rows:
        return 0
    from datetime import date, timedelta
    today  = date.today()
    streak = 0
    for row in rows:
        expected = today - timedelta(days=streak)
        if str(row["day"]) == str(expected):
            streak += 1
        else:
            break
    return streak


# ── Reviews ───────────────────────────────────────────────────────────────────
def add_review(patient_id: int, user_id: int, rating: int, comment: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reviews (patient_id, user_id, rating, comment) VALUES (?,?,?,?)",
            (patient_id, user_id, rating, comment)
        )
        return cur.lastrowid


def get_reviews(patient_id: int = None) -> list:
    with get_conn() as conn:
        if patient_id:
            rows = conn.execute("""
                SELECT r.*, p.name as patient_name, p.patient_uid
                FROM reviews r
                JOIN patients p ON r.patient_id = p.id
                WHERE r.patient_id=?
                ORDER BY r.created_at DESC
            """, (patient_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.*, p.name as patient_name, p.patient_uid
                FROM reviews r
                JOIN patients p ON r.patient_id = p.id
                ORDER BY r.created_at DESC
            """).fetchall()
    return [dict(r) for r in rows]


def get_review_stats() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as total, AVG(rating) as avg_rating FROM reviews"
        ).fetchone()
        dist = conn.execute(
            "SELECT rating, COUNT(*) as cnt FROM reviews GROUP BY rating ORDER BY rating DESC"
        ).fetchall()
    return {
        "total":      row["total"] if row else 0,
        "avg_rating": round(row["avg_rating"] or 0, 1),
        "distribution": [dict(r) for r in dist],
    }


# ── EEG ───────────────────────────────────────────────────────────────────────
def save_eeg_signal(patient_id, session_id, data: dict):
    beta = max(data.get("lowBeta", 0) + data.get("highBeta", 0), 1)
    tbr  = round(data.get("theta", 0) / beta, 4)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO eeg_signals
            (patient_id,session_id,quality,attention,meditation,delta,theta,
             low_alpha,high_alpha,low_beta,high_beta,low_gamma,mid_gamma,theta_beta_ratio)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            patient_id, session_id,
            data.get("quality", 0), data.get("attention", 0), data.get("meditation", 0),
            data.get("delta", 0),   data.get("theta", 0),
            data.get("lowAlpha", 0), data.get("highAlpha", 0),
            data.get("lowBeta", 0),  data.get("highBeta", 0),
            data.get("lowGamma", 0), data.get("midGamma", 0),
            tbr
        ))


def get_eeg_signals(patient_id, session_id=None, limit=300) -> list:
    with get_conn() as conn:
        if session_id:
            rows = conn.execute("""
                SELECT * FROM eeg_signals WHERE patient_id=? AND session_id=?
                ORDER BY recorded_at ASC LIMIT ?
            """, (patient_id, session_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM eeg_signals WHERE patient_id=?
                ORDER BY recorded_at ASC LIMIT ?
            """, (patient_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_eeg_sessions(patient_id) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT session_id, MIN(recorded_at) as started_at,
                   COUNT(*) as samples,
                   AVG(attention) as avg_attention,
                   AVG(theta_beta_ratio) as avg_tbr
            FROM eeg_signals WHERE patient_id=?
            GROUP BY session_id ORDER BY started_at DESC
        """, (patient_id,)).fetchall()
    return [dict(r) for r in rows]


def get_all_eeg_sessions() -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT e.session_id, p.name as patient_name,
                   MIN(e.recorded_at) as started_at,
                   COUNT(*) as samples,
                   AVG(e.attention) as avg_attention
            FROM eeg_signals e JOIN patients p ON e.patient_id=p.id
            GROUP BY e.session_id ORDER BY started_at DESC LIMIT 10
        """).fetchall()
    return [dict(r) for r in rows]


# ── Questionnaire ──────────────────────────────────────────────────────────────
def save_questionnaire(patient_id, session_id, responses: dict,
                        total_score, inatt_score, hyper_score, risk_level):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO questionnaire_results
            (patient_id,session_id,responses,total_score,inatt_score,hyper_score,risk_level)
            VALUES (?,?,?,?,?,?,?)
        """, (patient_id, session_id, json.dumps(responses),
              total_score, inatt_score, hyper_score, risk_level))


def get_questionnaires(patient_id) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM questionnaire_results WHERE patient_id=?
            ORDER BY assessed_at DESC
        """, (patient_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Emotion ────────────────────────────────────────────────────────────────────
def save_emotion_log(patient_id, session_id, dominant, scores: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO emotion_logs
            (patient_id,session_id,dominant_emotion,happy,neutral,sad,angry,fear,surprise,disgust)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            patient_id, session_id, dominant,
            scores.get("happy", 0),   scores.get("neutral", 0),
            scores.get("sad", 0),     scores.get("angry", 0),
            scores.get("fear", 0),    scores.get("surprise", 0),
            scores.get("disgust", 0)
        ))


def get_emotion_logs(patient_id, session_id=None) -> list:
    with get_conn() as conn:
        if session_id:
            rows = conn.execute("""
                SELECT * FROM emotion_logs WHERE patient_id=? AND session_id=?
                ORDER BY logged_at ASC
            """, (patient_id, session_id)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM emotion_logs WHERE patient_id=?
                ORDER BY logged_at DESC
            """, (patient_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Activity ───────────────────────────────────────────────────────────────────
def save_activity_result(patient_id, session_id, activity_name,
                          accuracy, completion_time, error_rate, attention_score, details: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO activity_results
            (patient_id,session_id,activity_name,accuracy,completion_time,error_rate,attention_score,details)
            VALUES (?,?,?,?,?,?,?,?)
        """, (patient_id, session_id, activity_name,
              accuracy, completion_time, error_rate, attention_score,
              json.dumps(details)))


def get_activity_results(patient_id) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM activity_results WHERE patient_id=?
            ORDER BY completed_at DESC
        """, (patient_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Reports ────────────────────────────────────────────────────────────────────
def save_report(patient_id, session_id, eeg_interpretation, questionnaire_summary,
                emotion_summary, activity_summary, final_classification,
                risk_score, eeg_score, questionnaire_score, emotion_score, activity_score):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO assessment_reports
            (patient_id,session_id,eeg_interpretation,questionnaire_summary,
             emotion_summary,activity_summary,final_classification,
             risk_score,eeg_score,questionnaire_score,emotion_score,activity_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (patient_id, session_id, eeg_interpretation, questionnaire_summary,
              emotion_summary, activity_summary, final_classification,
              risk_score, eeg_score, questionnaire_score, emotion_score, activity_score))


def get_reports(patient_id) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM assessment_reports WHERE patient_id=?
            ORDER BY generated_at DESC
        """, (patient_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Dashboard Stats ────────────────────────────────────────────────────────────
def get_dashboard_stats() -> dict:
    with get_conn() as conn:
        total_patients    = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        total_assessments = conn.execute("SELECT COUNT(*) FROM questionnaire_results").fetchone()[0]
        total_eeg         = conn.execute("SELECT COUNT(DISTINCT session_id) FROM eeg_signals").fetchone()[0]
        total_appts       = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        risk_dist = conn.execute("""
            SELECT risk_level, COUNT(*) as count FROM questionnaire_results
            WHERE risk_level != '' GROUP BY risk_level
        """).fetchall()
        recent_sessions = conn.execute("""
            SELECT e.session_id, p.name as patient_name,
                   MIN(e.recorded_at) as started_at, COUNT(*) as samples
            FROM eeg_signals e JOIN patients p ON e.patient_id=p.id
            GROUP BY e.session_id ORDER BY started_at DESC LIMIT 5
        """).fetchall()
        recent_q = conn.execute("""
            SELECT q.*, p.name as patient_name FROM questionnaire_results q
            JOIN patients p ON q.patient_id=p.id
            ORDER BY q.assessed_at DESC LIMIT 5
        """).fetchall()
    return {
        "total_patients":    total_patients,
        "total_assessments": total_assessments,
        "total_eeg":         total_eeg,
        "total_appointments": total_appts,
        "risk_distribution": [dict(r) for r in risk_dist],
        "recent_sessions":   [dict(r) for r in recent_sessions],
        "recent_questionnaires": [dict(r) for r in recent_q],
    }
