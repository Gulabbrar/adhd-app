"""
main.py — ADHD Assessment Platform
Entry point: streamlit run main.py
"""
import streamlit as st
from database import init_db, get_patients, add_patient, authenticate, register_user

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ADHD Assessment Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB Init ────────────────────────────────────────────────────────────────────
init_db()

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}
.main { background-color: #f0f4f8 !important; }
.main .block-container { padding: 1.5rem 2rem 2rem !important; max-width: 1300px !important; }

/* ── Sidebar ─────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1628 0%, #0d47a1 100%) !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] * { color: rgba(255,255,255,0.9) !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: white !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2) !important; }
section[data-testid="stSidebar"] .stSelectbox div { color: #0a1628 !important; }

/* ── Sidebar form inputs ─────────────────────────────────────────────── */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] input[type="text"],
section[data-testid="stSidebar"] input[type="number"],
section[data-testid="stSidebar"] textarea {
    color: #0a1628 !important;
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
}
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder { color: #94a3b8 !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] details summary {
    color: rgba(255,255,255,0.9) !important;
}
section[data-testid="stSidebar"] [data-testid="stForm"] label {
    color: rgba(255,255,255,0.85) !important;
}
section[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
    color: #0a1628 !important;
    background-color: #ffffff !important;
}

/* ── Cards ──────────────────────────────────────────────────────────── */
.card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 10px rgba(15,23,42,0.07);
    margin-bottom: 12px;
}

/* ── Page Title ─────────────────────────────────────────────────────── */
.page-title {
    color: #0d47a1 !important;
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    margin-bottom: 1rem !important;
}

/* ── Metrics ────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: white !important;
    border: 1px solid #e2e8f0 !important;
    border-top: 4px solid #1565c0 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    box-shadow: 0 2px 8px rgba(15,23,42,0.07) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: 0.5px; color: #64748b !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.8rem !important; font-weight: 700 !important; color: #0d47a1 !important;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #1565c0, #0d47a1) !important;
    color: white !important; border: none !important;
    border-radius: 8px !important; font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.18s ease !important;
    box-shadow: 0 2px 8px rgba(13,71,161,0.3) !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; }
.stDownloadButton > button {
    background: linear-gradient(135deg, #2e7d32, #1b5e20) !important;
    color: white !important; border: none !important;
    border-radius: 8px !important; font-weight: 600 !important;
}

/* ── Tabs ───────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #e2e8f0; padding: 4px; border-radius: 10px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px !important; font-weight: 500 !important;
    font-size: 0.82rem !important; padding: 0.4rem 0.9rem !important;
    color: #64748b !important; background: transparent !important; border: none !important;
}
.stTabs [aria-selected="true"] {
    background: white !important; color: #0d47a1 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.1) !important; font-weight: 700 !important;
}

/* ── Question cards ──────────────────────────────────────────────────── */
.q-card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-left: 4px solid #1565c0;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 4px;
    font-size: 0.88rem; font-weight: 500; color: #0f172a;
}
.q-num {
    display: inline-block; background: #1565c0; color: white;
    font-size: 0.68rem; font-weight: 700; padding: 2px 7px;
    border-radius: 50px; margin-right: 6px;
}

/* ── Questionnaire horizontal radio buttons ──────────────────────────── */
[data-testid="stForm"] [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    gap: 0 !important;
    background: #f1f5f9;
    border-radius: 8px;
    padding: 4px;
    margin-bottom: 10px;
}
[data-testid="stForm"] [role="radiogroup"] label {
    flex: 1 !important;
    text-align: center !important;
    cursor: pointer;
    padding: 6px 4px !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    color: #475569 !important;
    transition: background 0.15s, color 0.15s;
    white-space: nowrap;
}
[data-testid="stForm"] [role="radiogroup"] label:has(input:checked) {
    background: white !important;
    color: #0d47a1 !important;
    font-weight: 700 !important;
    box-shadow: 0 1px 4px rgba(13,71,161,0.18) !important;
}
[data-testid="stForm"] [role="radiogroup"] input[type="radio"] {
    display: none !important;
}

/* ── DataFrames ─────────────────────────────────────────────────────── */
.stDataFrame { border-radius: 10px !important; box-shadow: 0 2px 8px rgba(15,23,42,0.07) !important; }

/* ── Auth card ───────────────────────────────────────────────────────── */
.login-wrap { max-width: 480px; margin: 60px auto 0; }
.login-header {
    background: linear-gradient(135deg, #0d47a1, #1565c0);
    padding: 28px 24px; border-radius: 14px 14px 0 0; text-align: center;
}
.login-header h2 { color: white !important; margin: 8px 0 4px !important; font-size: 1.3rem !important; }
.login-header p  { color: rgba(255,255,255,0.75); font-size: 0.82rem; margin: 0; }
.login-body {
    background: white; border: 1px solid #e2e8f0; border-top: none;
    border-radius: 0 0 14px 14px; padding: 24px;
    box-shadow: 0 10px 40px rgba(13,71,161,0.15);
}
.role-badge {
    display:inline-block;padding:3px 12px;border-radius:50px;
    font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
if "user" not in st.session_state:
    st.session_state.user = None
if "current_patient" not in st.session_state:
    st.session_state.current_patient = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "Login"


# ══════════════════════════════════════════════════════════════════════════════
# AUTH PAGE
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.user is None:
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div class="login-wrap">
        <div class="login-header">
            <h2>ADHD Assessment Platform</h2>
            <p>Questionnaire &nbsp;·&nbsp; Emotion &nbsp;·&nbsp; Cognitive Testing &nbsp;·&nbsp; Patient Portal</p>
        </div>
        <div class="login-body">
        """, unsafe_allow_html=True)

        mode = st.selectbox("Mode", ["Login", "Register"],
                            index=0 if st.session_state.auth_mode == "Login" else 1,
                            label_visibility="collapsed",
                            key="auth_mode_sel")

        # ── LOGIN ──────────────────────────────────────────────────────────────
        if mode == "Login":
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                sign_in  = st.form_submit_button("Sign In", use_container_width=True)

            if sign_in:
                if username and password:
                    user = authenticate(username, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.warning("Please enter username and password.")

            st.markdown("""
            <p style="text-align:center;color:#94a3b8;font-size:0.8rem;margin-top:16px;">
                Don't have an account?
                <a href="#" style="color:#1565c0;">Register below</a>
            </p>
            """, unsafe_allow_html=True)

        # ── REGISTER ───────────────────────────────────────────────────────────
        else:
            # Admin role is NOT available for public registration.
            # Admin accounts are created only by an existing admin via the Admin Panel.
            role_info = {
                "patient":   ("Patient",   "", "#dbeafe", "#1d4ed8",
                               "Access your dashboard, book appointments & track progress"),
                "clinician": ("Clinician", "", "#dcfce7", "#15803d",
                               "Run assessments, view EEG data & manage patients"),
            }

            with st.form("register_form"):
                role = st.selectbox(
                    "Register As",
                    ["patient", "clinician"],
                    format_func=lambda r: role_info[r][0]
                )

                # Show role description
                ri = role_info[role]
                st.markdown(f"""
                <div style="background:{ri[2]};color:{ri[3]};border-radius:8px;
                            padding:8px 12px;font-size:0.8rem;margin-bottom:8px;">
                    {ri[4]}
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                username  = c1.text_input("Username *",   placeholder="Choose a username")
                email     = c2.text_input("Email *",      placeholder="your@email.com")
                full_name = st.text_input("Full Name",     placeholder="Optional")

                if role == "patient":
                    c3, c4 = st.columns(2)
                    age    = c3.number_input("Age", min_value=3, max_value=120, value=18)
                    gender = c4.selectbox("Gender", ["", "Male", "Female", "Other"],
                                          format_func=lambda x: "Select gender" if x == "" else x)
                else:
                    age, gender = 0, ""

                c5, c6 = st.columns(2)
                password  = c5.text_input("Password *",         type="password", placeholder="Min 6 chars")
                password2 = c6.text_input("Confirm Password *", type="password", placeholder="Repeat password")

                submitted = st.form_submit_button("Create Account", use_container_width=True)

            if submitted:
                if not username or not email or not password:
                    st.error("Username, email, and password are required.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif password != password2:
                    st.error("Passwords do not match.")
                elif "@" not in email:
                    st.error("Please enter a valid email address.")
                else:
                    result = register_user(
                        username=username.strip(),
                        email=email.strip(),
                        password=password,
                        role=role,
                        full_name=full_name.strip(),
                        age=int(age) if role == "patient" else 0,
                        gender=gender if role == "patient" else "",
                    )
                    if result["ok"]:
                        if role == "patient":
                            st.success(
                                f"Account created! Your Patient ID is "
                                f"**{result['patient_uid']}**. Please log in."
                            )
                            st.markdown(f"""
                            <div style="background:#f0fdf4;border:1px solid #86efac;
                                        border-radius:8px;padding:12px 16px;margin-top:8px;">
                                <p style="margin:0;color:#166534;font-size:0.88rem;">
                                    Save this ID:
                                    <code style="font-size:1rem;background:#dcfce7;
                                    padding:3px 10px;border-radius:6px;">
                                    {result['patient_uid']}</code>
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.success("Account created! Please log in.")
                    else:
                        st.error(result["error"])

        st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PATIENT PORTAL — separate layout for patient role
# ══════════════════════════════════════════════════════════════════════════════
user = st.session_state.user
role = user.get("role")

if role == "patient":
    from database import get_user_patient
    patient = get_user_patient(user["id"])
    pat_uid = patient.get("patient_uid", "") if patient else ""

    # Patient sidebar
    with st.sidebar:
        st.markdown("## ADHD Platform")
        st.markdown(f"**{patient['name'] if patient else user['username']}**")
        if pat_uid:
            st.markdown(f"`{pat_uid}`")
        st.markdown(f"*Patient Portal*")
        st.markdown("---")

        st.markdown("### Navigation")
        pat_pages = [
            "My Dashboard",
            "Self-Assessment",
            "My Report",
            "Mood Tracker",
            "Activities",
            "Book Appointment",
            "Reviews",
        ]
        page = st.radio("Go to", pat_pages, label_visibility="collapsed",
                        key="patient_page")
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    # Patient page routing
    if "Dashboard" in page:
        from modules.patient_dashboard import render_patient_dashboard
        render_patient_dashboard()
    elif "Self-Assessment" in page:
        from modules.patient_assessment import render_patient_assessment
        render_patient_assessment()
    elif "My Report" in page:
        from modules.patient_report import render_patient_report
        render_patient_report()
    elif "Mood" in page:
        from modules.patient_mood import render_patient_mood
        render_patient_mood()
    elif "Activities" in page:
        from modules.patient_activities import render_patient_activities
        render_patient_activities()
    elif "Appointment" in page:
        from modules.appointments import render_appointments
        render_appointments()
    elif "Reviews" in page:
        from modules.reviews import render_reviews
        render_reviews()

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# CLINICIAN / ADMIN SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ADHD Platform")
    role_label = {"admin": "Admin", "clinician": "Clinician"}.get(role, role.title())
    st.markdown(f"*Logged in as:* **{role_label}**")
    st.markdown("---")

    # ── Patient Selector ─────────────────────────────────────────────────────
    patients = get_patients()
    st.markdown("### Active Patient")

    if patients:
        pt_opts  = {"— Select Patient —": None}
        pt_opts.update({f"{p['name']} (#{p['id']})": p for p in patients})
        sel_key  = st.selectbox("Patient", list(pt_opts.keys()),
                                label_visibility="collapsed")
        st.session_state.current_patient = pt_opts[sel_key]
        if st.session_state.current_patient:
            p = st.session_state.current_patient
            uid = p.get("patient_uid") or ""
            st.caption(f"Age: {p['age']} | Gender: {p['gender']}"
                       + (f"\nID: {uid}" if uid else ""))
    else:
        st.caption("No patients yet.")

    # Quick-add patient
    with st.expander("Quick Add Patient"):
        with st.form("quick_add"):
            qname   = st.text_input("Name *")
            qa, qg  = st.columns(2)
            qage    = qa.number_input("Age", 3, 100, 10)
            qgender = qg.selectbox("Gender", ["Male", "Female", "Other"])
            if st.form_submit_button("Add"):
                if qname.strip():
                    new_id = add_patient(qname.strip(), qage, qgender)
                    st.success(f"Added #{new_id}")
                    st.rerun()
                else:
                    st.error("Name required.")

    st.markdown("---")

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown("### Navigation")
    pages = [
        "Home Dashboard",
        "ADHD Questionnaire",
        "Emotion Monitoring",
        "Activity Builder",
        "EEG Assessment",
        "Patient Progress",
        "Historical Data",
        "ADHD Report",
        "Appointments",
        "Reviews",
    ]
    if role == "admin":
        pages.append("Admin Panel")

    page = st.radio("Go to", pages, label_visibility="collapsed")

    st.markdown("---")
    if st.button("Logout", use_container_width=True):
        st.session_state.user            = None
        st.session_state.current_patient = None
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CLINICIAN / ADMIN PAGE ROUTING
# ══════════════════════════════════════════════════════════════════════════════
if   "Home"          in page:
    from modules.home          import render_home;          render_home()
elif "Questionnaire" in page:
    from modules.questionnaire import render_questionnaire; render_questionnaire()
elif "Emotion"       in page:
    from modules.emotion       import render_emotion;       render_emotion()
elif "Activity"      in page:
    from modules.activity      import render_activity;      render_activity()
elif "EEG"           in page:
    from modules.eeg           import render_eeg;           render_eeg()
elif "Progress"      in page:
    from modules.progress      import render_progress;      render_progress()
elif "Historical"    in page:
    from modules.history       import render_history;       render_history()
elif "Report"        in page:
    from modules.report        import render_report;        render_report()
elif "Appointments"  in page:
    from modules.appointments  import render_appointments;  render_appointments()
elif "Reviews"       in page:
    from modules.reviews       import render_reviews;       render_reviews()
elif "Admin"         in page:
    from modules.admin         import render_admin;         render_admin()
