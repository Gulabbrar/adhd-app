"""modules/patient_activities.py — Cognitive activity games for patients"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import random, time
from datetime import datetime
from database import get_user_patient, save_activity_result, get_activity_results

# ── Shared scale labels ────────────────────────────────────────────────────────
ACTIVITY_INFO = {
    "Memory Sequence":    ("🧩", "Trains working memory and digit recall."),
    "Reaction Time":      ("⚡", "Measures processing speed and sustained attention."),
    "Pattern Recognition":("🎨", "Tests visual discrimination and focused attention."),
    "Attention Tracking": ("🎯", "Continuous performance test for impulse control."),
}


def _perf_color(score: float) -> str:
    if score >= 80: return "#2e7d32"
    if score >= 55: return "#f57f17"
    return "#c62828"


def _perf_label(score: float) -> str:
    if score >= 80: return "Great"
    if score >= 55: return "Average"
    return "Needs Practice"


# ══════════════════════════════════════════════════════════════════════════════
# GAME 1 — Memory Sequence
# ══════════════════════════════════════════════════════════════════════════════
def _memory_game(pid: int, session_id: str):
    st.markdown("#### 🧩 Memory Sequence")
    st.caption("A sequence of digits will appear briefly. Memorise it, then type it back.")

    state = st.session_state.setdefault("pat_mem", {
        "phase": "start", "sequence": [], "show_start": None,
    })
    LEVEL_DIGITS = {1: 4, 2: 5, 3: 6, 4: 7}
    SHOW_SECS    = 3
    level   = st.select_slider("Difficulty", [1, 2, 3, 4],
                                format_func=lambda x: ["Easy","Medium","Hard","Expert"][x-1],
                                key="pat_mem_level")
    n = LEVEL_DIGITS[level]

    if state["phase"] == "start":
        if st.button("▶ Start", use_container_width=True, key="pm_start"):
            state.update({"sequence": [str(random.randint(0,9)) for _ in range(n)],
                          "show_start": time.time(), "phase": "showing"})
            st.rerun()

    elif state["phase"] == "showing":
        elapsed   = time.time() - state["show_start"]
        remaining = max(0, SHOW_SECS - elapsed)
        st.markdown(f"""
        <div style="background:#1565c0;color:white;border-radius:12px;padding:28px;
                    text-align:center;font-size:2.8rem;font-weight:900;letter-spacing:14px;">
            {"  ".join(state["sequence"])}
        </div>
        <div style="text-align:center;margin-top:8px;color:#555;">
            Memorise! Hiding in <b>{remaining:.1f}s</b>…
        </div>
        """, unsafe_allow_html=True)
        if elapsed >= SHOW_SECS:
            state["phase"] = "recall"
        time.sleep(0.35)
        st.rerun()

    elif state["phase"] == "recall":
        st.markdown("""<div style="background:#f0f4f8;border-radius:10px;padding:14px;
            text-align:center;"><b>Sequence hidden — type what you saw:</b></div>""",
            unsafe_allow_html=True)
        answer = st.text_input("Your answer:", key="pm_ans_input",
                                max_chars=n + 2, placeholder="Digits only, no spaces")
        c1, c2 = st.columns(2)
        if c1.button("Submit", use_container_width=True, key="pm_submit"):
            correct  = "".join(state["sequence"])
            given    = answer.strip().replace(" ","")
            matches  = sum(a == b for a, b in zip(given.ljust(len(correct)), correct))
            accuracy = round(matches / max(len(correct), 1) * 100, 1)
            state.update({"phase": "result", "user_ans": given, "accuracy": accuracy})
            st.rerun()
        if c2.button("Give Up", use_container_width=True, key="pm_giveup"):
            state.update({"phase": "result", "user_ans": "", "accuracy": 0.0})
            st.rerun()

    elif state["phase"] == "result":
        correct  = "".join(state["sequence"])
        given    = state.get("user_ans","")
        accuracy = state.get("accuracy", 0.0)
        color    = _perf_color(accuracy)
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">
                {accuracy:.0f}% — {_perf_label(accuracy)}
            </div>
            <div style="margin-top:6px;">
                Correct: <b>{correct}</b> &nbsp;|&nbsp; Your answer: <b>{given or "(none)"}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("💾 Save & Play Again", use_container_width=True, key="pm_save"):
            save_activity_result(pid, session_id, "Memory Sequence",
                                 accuracy, 0, 100 - accuracy, min(accuracy,100),
                                 {"correct": correct, "given": given, "level": level})
            state["phase"] = "start"
            st.rerun()
        if c2.button("🔄 Retry", use_container_width=True, key="pm_retry"):
            state["phase"] = "start"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# GAME 2 — Reaction Time
# ══════════════════════════════════════════════════════════════════════════════
def _reaction_game(pid: int, session_id: str):
    st.markdown("#### ⚡ Reaction Time")
    st.caption("Click the green button as fast as you can when it appears. 5 rounds.")

    state = st.session_state.setdefault("pat_rt", {
        "phase": "start", "round": 0, "times": [],
        "delay": None, "start_ts": None, "show_ts": None,
    })
    ROUNDS = 5

    if state["phase"] == "start":
        if st.button("▶ Start", use_container_width=True, key="prt_start"):
            state.update({"round": 0, "times": [], "phase": "wait",
                          "delay": random.uniform(1.5, 4.0),
                          "start_ts": time.time(), "show_ts": None})
            st.rerun()

    elif state["phase"] == "wait":
        elapsed = time.time() - state["start_ts"]
        st.markdown("""<div style="background:#c62828;color:white;border-radius:12px;
                    padding:40px;text-align:center;font-size:1.5rem;font-weight:700;">
                    Wait for green…</div>""", unsafe_allow_html=True)
        if elapsed >= state["delay"]:
            state.update({"phase": "ready", "show_ts": time.time()})
        time.sleep(0.15)
        st.rerun()

    elif state["phase"] == "ready":
        st.markdown("""<div style="background:#2e7d32;color:white;border-radius:12px;
                    padding:40px;text-align:center;font-size:1.5rem;font-weight:700;">
                    CLICK NOW! ⚡</div>""", unsafe_allow_html=True)
        if st.button("⚡ CLICK!", use_container_width=True, key="prt_click"):
            rt_ms = round((time.time() - state["show_ts"]) * 1000)
            state["times"].append(rt_ms)
            state["round"] += 1
            if state["round"] >= ROUNDS:
                state["phase"] = "done"
            else:
                state.update({"phase": "wait",
                               "delay": random.uniform(1.5, 4.0),
                               "start_ts": time.time()})
            st.rerun()

    elif state["phase"] == "done":
        times  = state["times"]
        avg_rt = round(sum(times) / len(times))
        attn   = max(0, min(100, round(100 - (avg_rt - 200) / 8)))
        color  = _perf_color(attn)
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">
                {avg_rt} ms avg — {_perf_label(attn)}
            </div>
            <div>Fastest: {min(times)}ms &nbsp;|&nbsp; Slowest: {max(times)}ms
                 &nbsp;|&nbsp; Attention: <b>{attn}%</b></div>
        </div>
        """, unsafe_allow_html=True)
        fig = go.Figure(go.Bar(
            x=[f"R{i+1}" for i in range(len(times))], y=times,
            marker_color=[_perf_color(max(0,min(100,100-(t-200)//8))) for t in times],
            text=[f"{t}ms" for t in times], textposition="outside",
        ))
        fig.update_layout(yaxis_title="ms", paper_bgcolor="white", plot_bgcolor="#f8fafc",
                          height=200, font=dict(family="Inter",size=11),
                          margin=dict(t=10,b=20,l=40,r=10))
        st.plotly_chart(fig, use_container_width=True, key="prt_chart")
        c1, c2 = st.columns(2)
        if c1.button("💾 Save & Play Again", use_container_width=True, key="prt_save"):
            save_activity_result(pid, session_id, "Reaction Time",
                                 attn, avg_rt/1000, 0, attn,
                                 {"times_ms": times, "avg_ms": avg_rt})
            state["phase"] = "start"
            st.rerun()
        if c2.button("🔄 Retry", use_container_width=True, key="prt_retry"):
            state["phase"] = "start"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# GAME 3 — Pattern Recognition
# ══════════════════════════════════════════════════════════════════════════════
SHAPES = ["⚪","🔵","🟡","🔴","🟢","🟣","🟠","⭐"]


def _new_round():
    target  = [random.choice(SHAPES) for _ in range(5)]
    options = [target[:]]
    while len(options) < 4:
        wrong = [random.choice(SHAPES) for _ in range(5)]
        if wrong != target and wrong not in options:
            options.append(wrong)
    random.shuffle(options)
    return target, options


def _pattern_game(pid: int, session_id: str):
    st.markdown("#### 🎨 Pattern Recognition")
    st.caption("Find which option exactly matches the target pattern. 5 rounds.")

    state = st.session_state.setdefault("pat_pat", {
        "phase": "start", "target": [], "options": [],
        "round": 0, "score": 0, "correct": None, "start_ts": None,
    })
    ROUNDS = 5

    if state["phase"] == "start":
        if st.button("▶ Start", use_container_width=True, key="ppa_start"):
            t, o = _new_round()
            state.update({"round": 0, "score": 0, "phase": "question",
                          "target": t, "options": o, "start_ts": time.time()})
            st.rerun()

    elif state["phase"] == "question":
        st.markdown(f"**Round {state['round']+1} / {ROUNDS}** &nbsp; Score so far: **{state['score']}**")
        st.markdown(f"""<div style="background:#1565c0;color:white;padding:14px 20px;
                         border-radius:10px;font-size:2rem;letter-spacing:8px;
                         text-align:center;">{"  ".join(state["target"])}</div>""",
                    unsafe_allow_html=True)
        st.markdown("**Choose the matching option:**")
        cols = st.columns(4)
        for i, opt in enumerate(state["options"]):
            if cols[i].button("  ".join(opt), key=f"ppa_opt_{state['round']}_{i}",
                               use_container_width=True):
                correct = (opt == state["target"])
                state.update({"correct": correct,
                               "phase": "feedback",
                               "rt": round((time.time()-state["start_ts"])*1000)})
                if correct:
                    state["score"] += 1
                st.rerun()

    elif state["phase"] == "feedback":
        if state["correct"]:
            st.success(f"✅ Correct! ({state['rt']}ms)")
        else:
            st.error(f"❌ Incorrect. Target was: {'  '.join(state['target'])}")
        # NOTE: do NOT mutate state here — this block re-runs on every Streamlit
        # refresh (hover, scroll, etc.). All mutations go inside the button handler.
        if st.button("Next →", use_container_width=True,
                      key=f"ppa_next_{state['round']}"):
            state["round"] += 1
            if state["round"] < ROUNDS:
                t, o = _new_round()
                state.update({"target": t, "options": o,
                               "start_ts": time.time(), "phase": "question"})
            else:
                state["phase"] = "done"
            st.rerun()

    elif state["phase"] == "done":
        accuracy = round(state["score"] / ROUNDS * 100)
        color    = _perf_color(accuracy)
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">
                {accuracy}% — {state['score']}/{ROUNDS} correct
            </div>
            <div>{_perf_label(accuracy)}</div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("💾 Save & Play Again", use_container_width=True, key="ppa_save"):
            save_activity_result(pid, session_id, "Pattern Recognition",
                                 float(accuracy), 0, float(100-accuracy), float(accuracy),
                                 {"score": state["score"], "rounds": ROUNDS})
            state["phase"] = "start"
            st.rerun()
        if c2.button("🔄 Retry", use_container_width=True, key="ppa_retry"):
            state["phase"] = "start"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# GAME 4 — Attention Tracking (CPT)
# ══════════════════════════════════════════════════════════════════════════════
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWYZ") + ["X"] * 6


def _attention_game(pid: int, session_id: str):
    st.markdown("#### 🎯 Attention Tracking")
    st.caption("Press **TARGET (X)** only when you see the letter X. Ignore everything else. 20 trials.")

    state = st.session_state.setdefault("pat_att", {
        "phase": "start", "trial": 0, "sequence": [], "responses": [],
    })
    TRIALS = 20

    if state["phase"] == "start":
        if st.button("▶ Start", use_container_width=True, key="patt_start"):
            state.update({"trial": 0,
                          "sequence": [random.choice(LETTERS) for _ in range(TRIALS)],
                          "responses": [], "phase": "trial"})
            st.rerun()

    elif state["phase"] == "trial":
        t = state["trial"]
        if t >= TRIALS:
            state["phase"] = "done"
            st.rerun()
            return
        letter    = state["sequence"][t]
        is_target = (letter == "X")
        bg        = "#c62828" if not is_target else "#2e7d32"
        st.markdown(f"**Trial {t+1} of {TRIALS}** &nbsp; — &nbsp; Press TARGET only for X")
        st.markdown(f"""<div style="background:{bg};color:white;border-radius:16px;
                    padding:44px;text-align:center;font-size:4.5rem;font-weight:900;">
                    {letter}</div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("🎯 TARGET (X)", use_container_width=True, key=f"patt_yes_{t}"):
            state["responses"].append((is_target, True))
            state["trial"] += 1
            st.rerun()
        if c2.button("⏭ Not X", use_container_width=True, key=f"patt_no_{t}"):
            state["responses"].append((is_target, False))
            state["trial"] += 1
            st.rerun()

    elif state["phase"] == "done":
        resp       = state["responses"]
        hits       = sum(1 for (e,g) in resp if e and g)
        misses     = sum(1 for (e,g) in resp if e and not g)
        fa         = sum(1 for (e,g) in resp if not e and g)
        cr         = sum(1 for (e,g) in resp if not e and not g)
        total_tgt  = hits + misses
        accuracy   = round(hits / max(total_tgt, 1) * 100, 1)
        fa_rate    = round(fa / max(len(resp)-total_tgt, 1) * 100, 1)
        color      = _perf_color(accuracy)
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">
                {accuracy:.0f}% Hit Rate — {_perf_label(accuracy)}
            </div>
            <div>Hits: {hits} &nbsp;|&nbsp; Misses: {misses} &nbsp;|&nbsp;
                 False Alarms: {fa} &nbsp;|&nbsp; False Alarm Rate: {fa_rate}%</div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("💾 Save & Play Again", use_container_width=True, key="patt_save"):
            save_activity_result(pid, session_id, "Attention Tracking",
                                 accuracy, 0, fa_rate, accuracy,
                                 {"hits": hits, "misses": misses, "fa": fa, "cr": cr})
            state["phase"] = "start"
            st.rerun()
        if c2.button("🔄 Retry", use_container_width=True, key="patt_retry"):
            state["phase"] = "start"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS PANEL
# ══════════════════════════════════════════════════════════════════════════════
def _results_panel(pid: int):
    results = get_activity_results(pid)
    if not results:
        st.info("No results yet. Complete an activity and save it to see your stats here.")
        return

    df = pd.DataFrame(results)

    # Personal bests
    st.markdown("#### Personal Bests")
    pb_cols = st.columns(len(ACTIVITY_INFO))
    for i, (act, (emoji, _)) in enumerate(ACTIVITY_INFO.items()):
        subset = df[df["activity_name"] == act]
        if not subset.empty:
            best = subset["accuracy"].max()
            pb_cols[i].metric(f"{emoji} {act}", f"{best:.0f}%")
        else:
            pb_cols[i].metric(f"{emoji} {act}", "—")

    # Trend per activity
    st.markdown("#### Accuracy Over Time")
    fig = go.Figure()
    colors = ["#1565c0","#c62828","#2e7d32","#f57f17"]
    for idx, act in enumerate(ACTIVITY_INFO):
        subset = df[df["activity_name"] == act].sort_values("completed_at")
        if not subset.empty:
            fig.add_trace(go.Scatter(
                x=subset["completed_at"],
                y=subset["accuracy"],
                name=act, mode="lines+markers",
                line=dict(color=colors[idx % 4], width=2),
                marker=dict(size=7),
            ))
    fig.update_layout(
        yaxis=dict(range=[0, 105], title="Accuracy %"),
        paper_bgcolor="white", plot_bgcolor="#f8fafc",
        height=300, font=dict(family="Inter", size=11),
        legend=dict(bgcolor="white", bordercolor="#e2e8f0", borderwidth=1),
        margin=dict(t=20, b=20, l=40, r=20),
    )
    st.plotly_chart(fig, use_container_width=True, key="pat_act_trend")

    # Average performance radar
    st.markdown("#### Average Performance by Activity")
    avg = df.groupby("activity_name")["accuracy"].mean()
    if not avg.empty:
        fig2 = go.Figure(go.Bar(
            x=avg.index.tolist(),
            y=avg.values.tolist(),
            marker_color=[_perf_color(v) for v in avg.values],
            text=[f"{v:.0f}%" for v in avg.values],
            textposition="outside",
        ))
        fig2.update_layout(
            yaxis=dict(range=[0, 110], title="Avg Accuracy %"),
            paper_bgcolor="white", plot_bgcolor="#f8fafc",
            height=260, font=dict(family="Inter", size=11),
            margin=dict(t=20, b=20, l=40, r=20),
        )
        st.plotly_chart(fig2, use_container_width=True, key="pat_act_avg")

    # Session history table
    st.markdown("#### Activity Log")
    show = df[["activity_name","accuracy","attention_score","completed_at"]].copy()
    show.columns = ["Activity","Accuracy %","Attention %","Completed"]
    show["Completed"] = show["Completed"].str[:16]
    st.dataframe(show.iloc[::-1].reset_index(drop=True),
                 use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════════════
def render_patient_activities():
    st.markdown('<h2 class="page-title">🎮 Cognitive Activities</h2>',
                unsafe_allow_html=True)

    user    = st.session_state.user
    patient = get_user_patient(user["id"])
    if not patient:
        st.error("Patient profile not found.")
        return

    pid        = patient["id"]
    session_id = datetime.now().strftime("PAT_%Y%m%d")

    # Intro card
    results = get_activity_results(pid)
    total   = len(results)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e3a5f,#1565c0);border-radius:12px;
                padding:18px 24px;margin-bottom:18px;display:flex;
                align-items:center;gap:20px;">
        <div style="font-size:2.5rem;">🎮</div>
        <div>
            <h3 style="color:white;margin:0;">Cognitive Training Games</h3>
            <p style="color:rgba(255,255,255,0.75);margin:4px 0 0;font-size:0.87rem;">
                {total} session{"s" if total!=1 else ""} completed &nbsp;|&nbsp;
                Train memory, reaction speed, pattern recognition & attention
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧩 Memory", "⚡ Reaction", "🎨 Pattern", "🎯 Attention", "📊 My Stats"
    ])

    with tab1:
        _memory_game(pid, session_id)
    with tab2:
        _reaction_game(pid, session_id)
    with tab3:
        _pattern_game(pid, session_id)
    with tab4:
        _attention_game(pid, session_id)
    with tab5:
        _results_panel(pid)
