"""modules/activity.py — Cognitive Activity Tests"""
import streamlit as st
import random
import time
from datetime import datetime
from database import save_activity_result, get_activity_results


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY 1 — Memory Sequence Test
# ═══════════════════════════════════════════════════════════════════════════════
def _memory_test(pid: int, session_id: str):
    st.markdown("#### 🧩 Memory Sequence Test")
    st.caption("A sequence of digits will be shown briefly. Memorise it, then type it back.")

    state = st.session_state.setdefault("mem", {
        "phase": "start",
        "sequence": [],
        "show_start": None,
    })

    LEVEL_DIGITS = {1: 4, 2: 5, 3: 6, 4: 7}
    SHOW_SECONDS = 3
    level    = st.slider("Difficulty Level", 1, 4, 2, key="mem_level")
    n_digits = LEVEL_DIGITS[level]

    if state["phase"] == "start":
        if st.button("▶ Start Memory Test", use_container_width=True, key="mem_btn_start"):
            state["sequence"]   = [str(random.randint(0, 9)) for _ in range(n_digits)]
            state["show_start"] = time.time()
            state["phase"]      = "showing"
            st.rerun()

    elif state["phase"] == "showing":
        elapsed   = time.time() - state["show_start"]
        remaining = max(0, SHOW_SECONDS - elapsed)
        seq_str   = "  ".join(state["sequence"])
        st.markdown(f"""
        <div style="background:#1565c0;color:white;border-radius:12px;padding:24px;
                    text-align:center;font-size:2.5rem;font-weight:800;
                    letter-spacing:12px;">{seq_str}</div>
        <div style="text-align:center;margin-top:8px;color:#555;">
            Memorise! Hiding in <b>{remaining:.1f}s</b>…
        </div>
        """, unsafe_allow_html=True)
        if elapsed >= SHOW_SECONDS:
            state["phase"] = "recall"
        time.sleep(0.4)
        st.rerun()

    elif state["phase"] == "recall":
        st.markdown("""<div style="background:#f0f4f8;border-radius:12px;padding:16px;
            text-align:center;"><b>Sequence hidden!</b> Type the digits you saw:</div>""",
            unsafe_allow_html=True)
        answer = st.text_input("Your answer (digits only, no spaces):",
                                key="mem_answer_input", max_chars=n_digits + 2)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Submit Answer", use_container_width=True, key="mem_btn_submit"):
                correct_str  = "".join(state["sequence"])
                user_str     = answer.strip().replace(" ", "")
                matches      = sum(a == b for a, b in zip(user_str.ljust(len(correct_str)), correct_str))
                accuracy     = round(matches / max(len(correct_str), 1) * 100, 1)
                state["phase"]    = "result"
                state["user_ans"] = user_str
                state["accuracy"] = accuracy
                st.rerun()
        with c2:
            if st.button("Give Up", use_container_width=True, key="mem_btn_giveup"):
                state["phase"]    = "result"
                state["user_ans"] = ""
                state["accuracy"] = 0.0
                st.rerun()

    elif state["phase"] == "result":
        correct_str = "".join(state["sequence"])
        user_str    = state.get("user_ans", "")
        accuracy    = state.get("accuracy", 0.0)
        color = "#2e7d32" if accuracy >= 80 else ("#f57f17" if accuracy >= 50 else "#c62828")
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;margin-bottom:12px;">
            <div style="font-size:2rem;font-weight:800;color:{color};">{accuracy}% Accuracy</div>
            <div>Correct: <b>{correct_str}</b> &nbsp;|&nbsp;
                 Your answer: <b>{user_str or "(none)"}</b></div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save & Try Again", use_container_width=True, key="mem_btn_save"):
                save_activity_result(pid, session_id, "Memory Sequence",
                                     accuracy, 0, 100 - accuracy, min(accuracy, 100),
                                     {"correct": correct_str, "given": user_str, "level": level})
                state["phase"] = "start"
                st.rerun()
        with c2:
            if st.button("🔄 Retry", use_container_width=True, key="mem_btn_retry"):
                state["phase"] = "start"
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY 2 — Reaction Time Test
# ═══════════════════════════════════════════════════════════════════════════════
def _reaction_test(pid: int, session_id: str):
    st.markdown("#### ⚡ Reaction Time Test")
    st.caption("Click the green button as fast as you can when it appears. 5 rounds.")

    state = st.session_state.setdefault("rt", {
        "phase": "start",
        "round": 0,
        "times": [],
        "delay": None,
        "start_ts": None,
        "show_ts":  None,
    })
    ROUNDS = 5

    if state["phase"] == "start":
        if st.button("▶ Start Reaction Test", use_container_width=True, key="rt_btn_start"):
            state.update({"round": 0, "times": [], "phase": "wait",
                           "delay": random.uniform(1.5, 4.0),
                           "start_ts": time.time(), "show_ts": None})
            st.rerun()

    elif state["phase"] == "wait":
        elapsed = time.time() - state["start_ts"]
        st.markdown("""<div style="background:#c62828;color:white;border-radius:12px;
                    padding:36px;text-align:center;font-size:1.6rem;font-weight:700;">
                    Wait for green…</div>""", unsafe_allow_html=True)
        if elapsed >= state["delay"]:
            state["phase"]   = "ready"
            state["show_ts"] = time.time()
        time.sleep(0.15)
        st.rerun()

    elif state["phase"] == "ready":
        st.markdown("""<div style="background:#2e7d32;color:white;border-radius:12px;
                    padding:36px;text-align:center;font-size:1.6rem;font-weight:700;">
                    CLICK NOW!</div>""", unsafe_allow_html=True)
        if st.button("⚡ CLICK!", use_container_width=True, key="rt_btn_click"):
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
        times   = state["times"]
        avg_rt  = round(sum(times) / len(times))
        attn    = max(0, min(100, round(100 - (avg_rt - 200) / 8)))
        color   = "#2e7d32" if avg_rt < 350 else ("#f57f17" if avg_rt < 550 else "#c62828")
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">Avg: {avg_rt} ms</div>
            <div>Fastest: {min(times)}ms &nbsp;|&nbsp; Slowest: {max(times)}ms</div>
            <div>Attention Score: <b>{attn}%</b></div>
        </div>
        """, unsafe_allow_html=True)
        import plotly.graph_objects as go
        fig = go.Figure(go.Bar(
            x=[f"R{i+1}" for i in range(len(times))],
            y=times,
            marker_color=["#2e7d32" if t<350 else "#f57f17" if t<550 else "#c62828" for t in times],
            text=[f"{t}ms" for t in times], textposition="outside"
        ))
        fig.update_layout(yaxis_title="ms", paper_bgcolor="white", plot_bgcolor="#f8fafc",
                          height=220, font=dict(family="Inter", size=11),
                          margin=dict(t=10, b=20, l=40, r=10))
        st.plotly_chart(fig, use_container_width=True, key="rt_chart")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save & Retry", use_container_width=True, key="rt_btn_save"):
                save_activity_result(pid, session_id, "Reaction Time",
                                     attn, avg_rt / 1000, 0, attn,
                                     {"times_ms": times, "avg_ms": avg_rt})
                state["phase"] = "start"
                st.rerun()
        with c2:
            if st.button("🔄 Retry", use_container_width=True, key="rt_btn_retry"):
                state["phase"] = "start"
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY 3 — Pattern Recognition
# ═══════════════════════════════════════════════════════════════════════════════
SHAPES = ["⚪", "🔵", "🟡", "🔴", "🟢", "🟣", "🟠", "⭐"]


def _new_pattern_round():
    target  = [random.choice(SHAPES) for _ in range(5)]
    options = [target[:]]
    while len(options) < 4:
        wrong = [random.choice(SHAPES) for _ in range(5)]
        if wrong != target and wrong not in options:
            options.append(wrong)
    random.shuffle(options)
    return target, options


def _pattern_test(pid: int, session_id: str):
    st.markdown("#### 🎨 Pattern Recognition")
    st.caption("Identify which option exactly matches the target pattern. 5 rounds.")

    state = st.session_state.setdefault("pat", {
        "phase":   "start",
        "target":  [], "options": [],
        "round":   0,  "score":   0,
        "correct": None, "start_ts": None,
    })
    ROUNDS = 5

    if state["phase"] == "start":
        if st.button("▶ Start Pattern Test", use_container_width=True, key="pat_btn_start"):
            target, options   = _new_pattern_round()
            state.update({"round": 0, "score": 0, "phase": "question",
                           "target": target, "options": options,
                           "start_ts": time.time()})
            st.rerun()

    elif state["phase"] == "question":
        st.markdown(f"**Round {state['round']+1} of {ROUNDS}**")
        st.markdown("**Target Pattern:**")
        st.markdown(f"""<div style="background:#1565c0;color:white;padding:14px 20px;
                         border-radius:10px;font-size:2rem;letter-spacing:8px;
                         text-align:center;">{"  ".join(state["target"])}</div>""",
                    unsafe_allow_html=True)
        st.markdown("**Which option matches?**")
        cols = st.columns(4)
        for i, opt in enumerate(state["options"]):
            with cols[i]:
                if st.button("  ".join(opt),
                              key=f"pat_opt_{state['round']}_{i}",
                              use_container_width=True):
                    state["correct"]  = (opt == state["target"])
                    state["phase"]    = "feedback"
                    state["rt"]       = round((time.time() - state["start_ts"]) * 1000)
                    if state["correct"]:
                        state["score"] += 1
                    st.rerun()

    elif state["phase"] == "feedback":
        if state["correct"]:
            st.success(f"✅ Correct! ({state['rt']}ms)")
        else:
            st.error(f"❌ Wrong! Correct was: {'  '.join(state['target'])}")
        state["round"] += 1
        if state["round"] >= ROUNDS:
            state["phase"] = "done"
        else:
            target, options   = _new_pattern_round()
            state["target"]   = target
            state["options"]  = options
            state["start_ts"] = time.time()
        if st.button("Next Round →", use_container_width=True,
                      key=f"pat_btn_next_{state['round']}"):
            state["phase"] = "question" if state["round"] < ROUNDS else "done"
            st.rerun()

    elif state["phase"] == "done":
        accuracy = round(state["score"] / ROUNDS * 100)
        color    = "#2e7d32" if accuracy >= 80 else ("#f57f17" if accuracy >= 50 else "#c62828")
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">{accuracy}% Accuracy</div>
            <div>{state['score']}/{ROUNDS} correct</div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save & Retry", use_container_width=True, key="pat_btn_save"):
                save_activity_result(pid, session_id, "Pattern Recognition",
                                     accuracy, 0, 100 - accuracy, accuracy,
                                     {"score": state["score"], "rounds": ROUNDS})
                state["phase"] = "start"
                st.rerun()
        with c2:
            if st.button("🔄 Retry", use_container_width=True, key="pat_btn_retry"):
                state["phase"] = "start"
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY 4 — Continuous Attention Test (CPT)
# ═══════════════════════════════════════════════════════════════════════════════
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWYZ") + ["X"] * 6   # ~20% target


def _attention_test(pid: int, session_id: str):
    st.markdown("#### 🎯 Continuous Attention Test (CPT)")
    st.caption("Press **TARGET** when you see the letter **X**. Ignore all other letters. 20 trials.")

    state = st.session_state.setdefault("att", {
        "phase":     "start",
        "trial":     0,
        "sequence":  [],
        "responses": [],
    })
    TRIALS = 20

    if state["phase"] == "start":
        if st.button("▶ Start Attention Test", use_container_width=True, key="att_btn_start"):
            state.update({"trial": 0,
                           "sequence":  [random.choice(LETTERS) for _ in range(TRIALS)],
                           "responses": [],
                           "phase": "trial"})
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

        st.markdown(f"**Trial {t+1} of {TRIALS}**")
        st.markdown(f"""<div style="background:{bg};color:white;border-radius:16px;
                    padding:40px;text-align:center;font-size:4rem;
                    font-weight:900;margin:12px 0;">{letter}</div>""",
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🎯 TARGET (X)", use_container_width=True, key=f"att_yes_{t}"):
                state["responses"].append((is_target, True))
                state["trial"] += 1
                st.rerun()
        with c2:
            if st.button("⏭ Not Target", use_container_width=True, key=f"att_no_{t}"):
                state["responses"].append((is_target, False))
                state["trial"] += 1
                st.rerun()

    elif state["phase"] == "done":
        responses    = state["responses"]
        hits         = sum(1 for (e, g) in responses if e and g)
        misses       = sum(1 for (e, g) in responses if e and not g)
        fa           = sum(1 for (e, g) in responses if not e and g)
        cr           = sum(1 for (e, g) in responses if not e and not g)
        total_tgts   = hits + misses
        accuracy     = round(hits / max(total_tgts, 1) * 100, 1)
        fa_rate      = round(fa  / max(len(responses) - total_tgts, 1) * 100, 1)

        color = "#2e7d32" if accuracy >= 80 else ("#f57f17" if accuracy >= 50 else "#c62828")
        st.markdown(f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:{color};">{accuracy}% Hit Rate</div>
            <div>Hits: {hits} &nbsp;|&nbsp; Misses: {misses} &nbsp;|&nbsp;
                 False Alarms: {fa} &nbsp;|&nbsp; Correct Rejections: {cr}</div>
            <div>False Alarm Rate: <b>{fa_rate}%</b></div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save & Retry", use_container_width=True, key="att_btn_save"):
                save_activity_result(pid, session_id, "Attention Tracking",
                                     accuracy, 0, fa_rate, accuracy,
                                     {"hits": hits, "misses": misses, "fa": fa, "cr": cr})
                state["phase"] = "start"
                st.rerun()
        with c2:
            if st.button("🔄 Retry", use_container_width=True, key="att_btn_retry"):
                state["phase"] = "start"
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def render_activity():
    st.markdown('<h2 class="page-title">🎮 Cognitive Activity Tests</h2>', unsafe_allow_html=True)

    patient = st.session_state.get("current_patient")
    if not patient:
        st.warning("Please select a patient from the sidebar first.")
        return

    pid        = patient["id"]
    session_id = st.session_state.get("eeg_session_id",
                  datetime.now().strftime("ACT_%Y%m%d_%H%M%S"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧩 Memory", "⚡ Reaction", "🎨 Pattern", "🎯 Attention", "📊 Results"
    ])
    with tab1:
        _memory_test(pid, session_id)
    with tab2:
        _reaction_test(pid, session_id)
    with tab3:
        _pattern_test(pid, session_id)
    with tab4:
        _attention_test(pid, session_id)
    with tab5:
        st.markdown("#### Previous Activity Results")
        results = get_activity_results(pid)
        if not results:
            st.info("No activity results yet.")
            return
        import pandas as pd, plotly.graph_objects as go
        rdf = pd.DataFrame(results)[["activity_name","accuracy","completion_time",
                                      "error_rate","attention_score","completed_at"]]
        rdf.columns = ["Activity","Accuracy %","Time (s)","Error %","Attention %","Completed"]
        st.dataframe(rdf, use_container_width=True, hide_index=True)

        avg = rdf.groupby("Activity")[["Accuracy %","Attention %"]].mean().reset_index()
        if not avg.empty:
            fig = go.Figure()
            for _, row in avg.iterrows():
                fig.add_trace(go.Bar(name=row["Activity"],
                                     x=["Accuracy", "Attention"],
                                     y=[row["Accuracy %"], row["Attention %"]]))
            fig.update_layout(barmode="group", title="Average Performance by Activity",
                               yaxis=dict(range=[0,105], title="%"),
                               paper_bgcolor="white", plot_bgcolor="#f8fafc", height=300,
                               font=dict(family="Inter", size=11),
                               margin=dict(t=40, b=20, l=40, r=20))
            st.plotly_chart(fig, use_container_width=True, key="act_perf_chart")
