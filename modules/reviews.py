"""modules/reviews.py — Patient reviews & star ratings"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import (
    get_user_patient, add_review, get_reviews, get_review_stats
)


def _star_html(rating: int, size: str = "1.2rem") -> str:
    full  = "★" * rating
    empty = "☆" * (5 - rating)
    return (f'<span style="color:#f59e0b;font-size:{size};">{full}</span>'
            f'<span style="color:#d1d5db;font-size:{size};">{empty}</span>')


def _time_ago(ts: str) -> str:
    """Simple relative time for display."""
    from datetime import datetime
    try:
        dt   = datetime.strptime(ts[:16], "%Y-%m-%d %H:%M")
        diff = datetime.now() - dt
        days = diff.days
        if days == 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        if days < 30:
            return f"{days} days ago"
        if days < 365:
            return f"{days // 30} months ago"
        return f"{days // 365} years ago"
    except Exception:
        return ts[:10] if ts else "—"


def render_reviews():
    st.markdown('<h2 class="page-title">⭐ Reviews & Feedback</h2>', unsafe_allow_html=True)

    user   = st.session_state.user
    role   = user.get("role")
    is_pat = role == "patient"

    # ── Review Stats Banner ────────────────────────────────────────────────────
    stats = get_review_stats()
    avg   = stats["avg_rating"]
    total = stats["total"]

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e3a5f,#1565c0);
                border-radius:12px;padding:20px 28px;margin-bottom:20px;
                display:flex;align-items:center;gap:28px;">
        <div style="text-align:center;">
            <div style="font-size:2.8rem;font-weight:800;color:white;">{avg:.1f}</div>
            <div style="font-size:1.4rem;color:#f59e0b;">{"★" * round(avg)}{"☆" * (5 - round(avg))}</div>
            <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">{total} review{"s" if total != 1 else ""}</div>
        </div>
        <div style="flex:1;">
            <h3 style="color:white;margin:0 0 4px;">Platform Ratings</h3>
            <p style="color:rgba(255,255,255,0.7);margin:0;font-size:0.87rem;">
                Based on patient feedback for the ADHD Assessment Platform
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_form, col_wall = st.columns([1, 1.5])

    # ── Submit Review (patients only) ──────────────────────────────────────────
    with col_form:
        if is_pat:
            patient = get_user_patient(user["id"])
            if not patient:
                st.error("No patient profile found.")
                return

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Share Your Feedback")

            with st.form("review_form"):
                rating = st.select_slider(
                    "Rating",
                    options=[1, 2, 3, 4, 5],
                    value=5,
                    format_func=lambda x: f"{'★' * x}{'☆' * (5-x)}  ({x}/5)"
                )
                comment = st.text_area(
                    "Your Review",
                    placeholder="Tell others about your experience with the platform...",
                    height=120
                )
                submitted = st.form_submit_button("Submit Review", use_container_width=True)

            if submitted:
                if not comment.strip():
                    st.warning("Please write a comment before submitting.")
                else:
                    add_review(
                        patient_id=patient["id"],
                        user_id=user["id"],
                        rating=rating,
                        comment=comment.strip()
                    )
                    st.success("Thank you for your feedback!")
                    st.balloons()
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        else:
            # Clinician / admin: show rating distribution chart
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Rating Distribution")
            dist = stats["distribution"]
            if dist:
                labels = [f"{'★' * d['rating']} ({d['rating']})" for d in dist]
                values = [d["cnt"] for d in dist]
                fig = go.Figure(go.Bar(
                    x=values, y=labels,
                    orientation="h",
                    marker_color=["#15803d","#22c55e","#84cc16","#f59e0b","#ef4444"][:len(dist)],
                    text=values, textposition="outside",
                ))
                fig.update_layout(
                    paper_bgcolor="white", plot_bgcolor="#f8fafc",
                    height=220, margin=dict(t=10, b=10, l=10, r=30),
                    font=dict(family="Inter", size=12),
                    xaxis=dict(showgrid=False, showticklabels=False),
                )
                st.plotly_chart(fig, use_container_width=True, key="rev_dist")
            else:
                st.info("No reviews yet.")
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Public Review Wall ─────────────────────────────────────────────────────
    with col_wall:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Patient Reviews")

        all_reviews = get_reviews()
        if not all_reviews:
            st.markdown("""
            <div style="text-align:center;padding:40px;color:#94a3b8;">
                <div style="font-size:3rem;">💬</div>
                <p>No reviews yet. Be the first to share!</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Filter by star
            filter_star = st.selectbox(
                "Filter by rating",
                ["All", "5 ★", "4 ★", "3 ★", "2 ★", "1 ★"],
                label_visibility="collapsed"
            )
            filtered = all_reviews
            if filter_star != "All":
                star_num = int(filter_star[0])
                filtered = [r for r in all_reviews if r["rating"] == star_num]

            for rev in filtered[:20]:
                name  = rev.get("patient_name", "Anonymous")
                # Anonymise: show first name + last initial only
                parts = name.split()
                display_name = (f"{parts[0]} {parts[-1][0]}."
                                if len(parts) > 1 else parts[0]) if parts else "Anonymous"
                st.markdown(f"""
                <div style="border:1px solid #e2e8f0;border-radius:10px;
                            padding:14px 16px;margin-bottom:10px;background:#fafafa;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <strong style="color:#0f172a;">{display_name}</strong>
                            <span style="color:#94a3b8;font-size:0.75rem;margin-left:8px;">
                                {_time_ago(rev.get('created_at',''))}
                            </span>
                        </div>
                        <div>{_star_html(rev['rating'])}</div>
                    </div>
                    <p style="margin:8px 0 0;color:#374151;font-size:0.88rem;line-height:1.5;">
                        {rev.get('comment') or ''}
                    </p>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Admin: full table ──────────────────────────────────────────────────────
    if not is_pat:
        st.markdown("---")
        st.markdown("#### All Reviews (Admin View)")
        all_reviews = get_reviews()
        if all_reviews:
            df = pd.DataFrame(all_reviews)[[
                "patient_name","patient_uid","rating","comment","created_at"
            ]]
            df.columns = ["Patient","UID","Rating","Comment","Submitted"]
            st.dataframe(df, use_container_width=True, hide_index=True)
