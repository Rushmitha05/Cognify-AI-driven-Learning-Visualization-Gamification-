import warnings
import streamlit as st
import os
import json
import urllib.parse
import requests
import re
import time
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image, ImageDraw
from io import BytesIO
from google import genai
from google.genai import types
import graphviz
from dotenv import load_dotenv

try:
    from streamlit_oauth import OAuth2Component
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False

try:
    from streamlit_mic_recorder import speech_to_text
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
load_dotenv()

# ══════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════
CLIENT_ID     = "223087762298-058puus8e3bffg6886tdso2o03lf3nej.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI  = os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8501").strip()
GOOGLE_SCOPES = ["openid","https://www.googleapis.com/auth/userinfo.email","https://www.googleapis.com/auth/userinfo.profile"]
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL     = "https://oauth2.googleapis.com/token"
ADMIN_EMAIL   = "rushmithaarelli05@gmail.com"
ADMIN_PASS    = "Cognify@Admin2025"
GEMINI_API_KEY = os.environ.get("API_KEY", "AIzaSyC9p3CiMBOT5uNnvt8pBJZmLmFHspZlCaI")

# ══════════════════════════════════════════
# USER STORE
# ══════════════════════════════════════════
USERS_FILE = "cognify_users.json"

def load_users():
    if not os.path.exists(USERS_FILE): return {}
    try:
        with open(USERS_FILE) as f: return json.load(f)
    except: return {}

def save_users(u):
    with open(USERS_FILE, "w") as f: json.dump(u, f, indent=2)

def get_user(email): return load_users().get(email)

def upsert_user(email, name, picture):
    users = load_users()
    if email not in users:
        users[email] = {"name":name,"email":email,"picture":picture,
                        "xp":0,"quiz_attempts":0,"total_score":0,
                        "topics_studied":[],"quiz_history":[]}
    else:
        users[email]["name"]    = name
        users[email]["picture"] = picture
    save_users(users)
    return users[email]

def update_user_stats(email, xp_gain=0, quiz_score=None, topic=None):
    users = load_users()
    if email not in users: return
    users[email]["xp"] = users[email].get("xp",0) + xp_gain
    if quiz_score is not None:
        users[email]["quiz_attempts"] = users[email].get("quiz_attempts",0) + 1
        users[email]["total_score"]   = users[email].get("total_score",0) + quiz_score
        if topic:
            h = users[email].get("quiz_history",[])
            h.append({"topic":topic,"score":quiz_score,"time":time.strftime("%Y-%m-%d %H:%M")})
            users[email]["quiz_history"] = h[-20:]
    if topic and topic not in users[email].get("topics_studied",[]):
        users[email].setdefault("topics_studied",[]).append(topic)
    save_users(users)

# ══════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════
st.set_page_config(page_title="COGNIFY — AI Learning", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

# ══════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Poppins:wght@400;500;600;700&family=Fredoka+One&display=swap');

:root {
  --bg:#f0f4ff;--white:#ffffff;--surface:#ffffff;--surface2:#f7f9ff;
  --border:#e0e7ff;--primary:#4f46e5;--primary2:#818cf8;--accent:#f59e0b;
  --accent2:#10b981;--pink:#ec4899;--sky:#0ea5e9;--text:#1e1b4b;
  --muted:#6b7280;--danger:#ef4444;--radius:16px;--radius-lg:28px;
  --shadow:0 4px 24px rgba(79,70,229,.12);--shadow-lg:0 8px 40px rgba(79,70,229,.18);
}
html,body,[data-testid="stApp"]{background:var(--bg)!important;font-family:'Nunito',sans-serif!important;color:var(--text)!important;}
[data-testid="stApp"]{background-image:radial-gradient(circle,#c7d2fe 1px,transparent 1px)!important;background-size:28px 28px!important;background-color:#f0f4ff!important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#4f46e5 0%,#6366f1 60%,#818cf8 100%)!important;border-right:none!important;}
[data-testid="stSidebar"] *{color:#fff!important;}
[data-testid="stSidebar"] .stMetric{background:rgba(255,255,255,.15)!important;border:1px solid rgba(255,255,255,.2)!important;border-radius:12px!important;}
[data-testid="stMetricValue"]{color:#fff!important;font-family:'Fredoka One'!important;font-size:1.6rem!important;}
[data-testid="stMetricLabel"]{color:rgba(255,255,255,.75)!important;font-size:.7rem!important;text-transform:uppercase;letter-spacing:.08em;}
h1,h2,h3,h4,h5,h6{font-family:'Fredoka One',sans-serif!important;color:var(--text)!important;letter-spacing:.01em;}
.stButton>button{background:linear-gradient(135deg,var(--primary),#6366f1)!important;color:#fff!important;border:none!important;border-radius:50px!important;font-family:'Nunito',sans-serif!important;font-weight:800!important;font-size:.88rem!important;letter-spacing:.04em!important;padding:.6rem 1.6rem!important;transition:all .25s ease!important;box-shadow:0 4px 16px rgba(79,70,229,.35)!important;text-transform:uppercase!important;}
.stButton>button:hover{transform:translateY(-3px) scale(1.02)!important;box-shadow:0 8px 28px rgba(79,70,229,.5)!important;}
.stButton>button:active{transform:translateY(0)!important;}
.stButton>button *{color:#fff!important;}
.stTextInput input,.stTextArea textarea{background:var(--white)!important;border:2px solid var(--border)!important;border-radius:var(--radius)!important;color:var(--text)!important;font-family:'Nunito',sans-serif!important;font-size:.95rem!important;}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--primary)!important;box-shadow:0 0 0 4px rgba(79,70,229,.12)!important;}
.stTextInput label,.stTextArea label{color:var(--muted)!important;font-weight:700!important;font-size:.82rem!important;}
div[data-baseweb="tab-list"]{background:var(--white)!important;border-radius:50px!important;padding:5px!important;gap:4px!important;border:2px solid var(--border)!important;box-shadow:var(--shadow)!important;}
div[data-baseweb="tab"]{background:transparent!important;border-radius:50px!important;border:none!important;font-family:'Nunito',sans-serif!important;font-weight:800!important;font-size:.78rem!important;letter-spacing:.05em!important;transition:all .2s!important;color:#000000!important;padding:.35rem 1rem!important;}
div[data-baseweb="tab"] *{color:#000000!important;}
div[aria-selected="true"]{background:linear-gradient(135deg,var(--primary),#6366f1)!important;}
div[aria-selected="true"] *{color:#000000!important;}
button[data-baseweb="tab"]{color:#000000!important;}
button[data-baseweb="tab"] *{color:#000000!important;}
button[data-baseweb="tab"][aria-selected="true"]{color:#000000!important;}
button[data-baseweb="tab"][aria-selected="true"] *{color:#000000!important;}
.stProgress>div>div>div{background:linear-gradient(90deg,var(--primary),var(--pink))!important;border-radius:100px!important;}
.stRadio [role="radiogroup"]>label{background:var(--white)!important;border:2px solid var(--border)!important;border-radius:var(--radius)!important;padding:.6rem 1rem!important;margin:.25rem 0!important;transition:all .2s!important;cursor:pointer;color:var(--text)!important;}
.stRadio [role="radiogroup"] label span{color:#1e1b4b!important;}
.stRadio [role="radiogroup"] label *{color:#1e1b4b!important;}
.stRadio [role="radiogroup"]>label:hover{border-color:var(--primary)!important;background:#f0f4ff!important;transform:translateX(4px);}
.stRadio label{color:var(--text)!important;font-weight:600!important;}
details{background:var(--white)!important;border:2px solid var(--border)!important;border-radius:var(--radius)!important;}
details>summary{color:var(--text)!important;font-family:'Nunito'!important;font-weight:800!important;padding:.8rem 1rem!important;}
hr{border-color:var(--border)!important;}
::-webkit-scrollbar{width:6px;height:6px;}::-webkit-scrollbar-track{background:var(--bg);}::-webkit-scrollbar-thumb{background:var(--primary2);border-radius:100px;}
.card{background:var(--white);border:2px solid var(--border);border-radius:var(--radius-lg);padding:1.5rem;box-shadow:var(--shadow);transition:box-shadow .25s,transform .25s;}
.card:hover{box-shadow:var(--shadow-lg);transform:translateY(-2px);}
.pill{display:inline-flex;align-items:center;gap:.3rem;padding:.28rem .85rem;border-radius:100px;font-family:'Nunito',sans-serif;font-size:.72rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;}
.pill-indigo{background:#eef2ff;color:#4f46e5;border:1.5px solid #c7d2fe;}
.pill-amber{background:#fffbeb;color:#b45309;border:1.5px solid #fde68a;}
.pill-green{background:#ecfdf5;color:#065f46;border:1.5px solid #a7f3d0;}
.pill-pink{background:#fdf2f8;color:#9d174d;border:1.5px solid #fbcfe8;}
.pill-sky{background:#f0f9ff;color:#0c4a6e;border:1.5px solid #bae6fd;}
.pill-red{background:#fef2f2;color:#991b1b;border:1.5px solid #fecaca;}
.hero-title{font-family:'Fredoka One',sans-serif;font-size:clamp(2.8rem,6vw,5rem);background:linear-gradient(135deg,#4f46e5 0%,#ec4899 50%,#f59e0b 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.1;letter-spacing:.01em;}
.role-card{background:var(--white);border:3px solid var(--border);border-radius:var(--radius-lg);padding:2.2rem 1.5rem;text-align:center;cursor:pointer;transition:all .3s ease;position:relative;overflow:hidden;}
.role-card-student{border-top:5px solid var(--primary);}
.role-card-admin{border-top:5px solid var(--accent);}
.role-card:hover{transform:translateY(-6px);box-shadow:var(--shadow-lg);}
.role-card-student:hover{border-color:var(--primary);}
.role-card-admin:hover{border-color:var(--accent);}
.stat-chip{display:inline-flex;align-items:center;gap:.4rem;background:var(--white);border:2px solid var(--border);border-radius:50px;padding:.3rem .9rem;font-size:.8rem;font-weight:800;color:var(--text);box-shadow:0 2px 8px rgba(79,70,229,.1);}
.quiz-card{background:var(--white);border:2px solid var(--border);border-left:6px solid var(--primary);border-radius:var(--radius-lg);padding:1.75rem 2rem;margin:.75rem 0;box-shadow:var(--shadow);}
.topic-tag{display:inline-block;background:#eef2ff;color:#4f46e5;border:1.5px solid #c7d2fe;border-radius:50px;padding:.2rem .7rem;font-size:.72rem;font-weight:800;margin:.15rem;}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
.float{animation:float 3s ease-in-out infinite;display:inline-block;}
.float2{animation:float 3.5s ease-in-out infinite .5s;display:inline-block;}
.float3{animation:float 4s ease-in-out infinite 1s;display:inline-block;}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.fade-up{animation:fadeUp .5s ease forwards;}
.fade-up-2{animation:fadeUp .5s ease .15s forwards;opacity:0;}
.fade-up-3{animation:fadeUp .5s ease .3s forwards;opacity:0;}
</style>
"""

# ══════════════════════════════════════════
# SESSION INIT
# ══════════════════════════════════════════
if "auth"                 not in st.session_state: st.session_state.auth = {"logged_in":False,"user":None,"role":None}
if "login_step"           not in st.session_state: st.session_state.login_step = "role"
if "oauth_token_consumed" not in st.session_state: st.session_state.oauth_token_consumed = False

# ══════════════════════════════════════════
# LOGIN FLOW
# ══════════════════════════════════════════
if not st.session_state.auth["logged_in"]:
    st.markdown(CSS, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;padding:2.5rem 1rem 2rem;">
      <div style="font-size:2rem;margin-bottom:.3rem;">
        <span class="float">🧠</span>&nbsp;<span class="float2">⭐</span>&nbsp;<span class="float3">📚</span>
      </div>
      <div class="hero-title fade-up">COGNIFY</div>
      <p class="fade-up-2" style="color:#6b7280;font-size:1rem;margin-top:.5rem;font-family:'Poppins';font-weight:500;letter-spacing:.06em;">
        AI-DRIVEN LEARNING · VISUALIZATION · GAMIFICATION
      </p>
      <div class="fade-up-3" style="display:flex;justify-content:center;gap:.5rem;margin-top:.9rem;flex-wrap:wrap;">
        <span class="pill pill-indigo">✨ Gemini Powered</span>
        <span class="pill pill-sky">⚡ Real-time Analysis</span>
        <span class="pill pill-pink">🎯 Adaptive Quizzes</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Role selector ──────────────────────────────────────────────
    if st.session_state.login_step == "role":
        st.markdown("<h2 style='text-align:center;font-family:Fredoka One;color:#1e1b4b;margin-bottom:1.5rem;'>Who are you? 👇</h2>", unsafe_allow_html=True)
        _, mid, _ = st.columns([1, 2.5, 1])
        with mid:
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("""
                <div class="role-card role-card-student">
                  <div style="font-size:3.5rem;margin-bottom:.6rem;">🎓</div>
                  <div style="font-family:'Fredoka One';font-size:1.4rem;color:#4f46e5;">Student</div>
                  <div style="color:#6b7280;font-size:.85rem;margin-top:.4rem;line-height:1.6;">Sign in with Google &amp; start your learning journey</div>
                  <div style="margin-top:1rem;"><span class="pill pill-sky">Google Login</span></div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("I'm a Student 🎓", key="btn_student", use_container_width=True):
                    st.session_state.oauth_token_consumed = False
                    st.session_state.login_step = "student"
                    st.rerun()
            with c2:
                st.markdown("""
                <div class="role-card role-card-admin">
                  <div style="font-size:3.5rem;margin-bottom:.6rem;">🔐</div>
                  <div style="font-family:'Fredoka One';font-size:1.4rem;color:#b45309;">Admin</div>
                  <div style="color:#6b7280;font-size:.85rem;margin-top:.4rem;line-height:1.6;">Restricted access — view student data &amp; analytics</div>
                  <div style="margin-top:1rem;"><span class="pill pill-amber">Password Only</span></div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("I'm an Admin 🔐", key="btn_admin", use_container_width=True):
                    st.session_state.login_step = "admin"
                    st.rerun()

    # ── Student Google Login ───────────────────────────────────────
    elif st.session_state.login_step == "student":
        _, mid, _ = st.columns([1, 1.4, 1])
        with mid:
            st.markdown("""
            <div class="card" style="text-align:center;padding:2rem;">
              <div style="font-size:3rem;margin-bottom:.5rem;">🎓</div>
              <div style="font-family:'Fredoka One';font-size:1.5rem;color:#4f46e5;">Student Login</div>
              <div style="color:#6b7280;font-size:.88rem;margin-top:.35rem;">Click the button below to sign in with your Google account</div>
              <div style="margin-top:.75rem;padding:.75rem;background:#eef2ff;border-radius:12px;">
                <div style="font-size:.78rem;color:#4f46e5;font-weight:700;">🔒 Safe &amp; secure · We only read your name &amp; email</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            if not OAUTH_AVAILABLE:
                st.error("streamlit-oauth not installed. Run: pip install streamlit-oauth")
            else:
                oauth2 = OAuth2Component(
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                    authorize_endpoint=AUTHORIZE_URL,
                    token_endpoint=TOKEN_URL,
                )
                if not st.session_state.oauth_token_consumed:
                    result = oauth2.authorize_button(
                        name="🚀 Sign in with Google",
                        redirect_uri=REDIRECT_URI,
                        scope=" ".join(GOOGLE_SCOPES),
                        key="google_oauth_widget",
                        use_container_width=True,
                        extras_params={"prompt": "select_account"},
                    )
                    if result and result.get("token"):
                        access_token = result["token"].get("access_token", "")
                        if access_token:
                            st.session_state.oauth_token_consumed = True
                            try:
                                ui = requests.get(
                                    "https://www.googleapis.com/oauth2/v3/userinfo",
                                    headers={"Authorization": f"Bearer {access_token}"},
                                    timeout=10,
                                ).json()
                                email   = ui.get("email", "")
                                name    = ui.get("name", email)
                                picture = ui.get("picture", "")
                                if not email:
                                    st.error("Could not retrieve email. Please try again.")
                                    st.session_state.oauth_token_consumed = False
                                else:
                                    upsert_user(email, name, picture)
                                    st.session_state.auth = {"logged_in": True, "user": email, "role": "user"}
                                    st.session_state.login_step = "role"
                                    st.session_state.oauth_token_consumed = False
                                    st.rerun()
                            except Exception as e:
                                st.session_state.oauth_token_consumed = False
                                st.error(f"Login failed: {e}. Please try again.")
                else:
                    st.info("✅ Signing you in… please wait.")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("← Back to role selection", key="back_student"):
                st.session_state.login_step = "role"
                st.session_state.oauth_token_consumed = False
                st.rerun()

    # ── Admin Password Login ───────────────────────────────────────
    elif st.session_state.login_step == "admin":
        _, mid, _ = st.columns([1, 1.4, 1])
        with mid:
            st.markdown("""
            <div class="card" style="text-align:center;padding:2rem;">
              <div style="font-size:3rem;margin-bottom:.5rem;">🔐</div>
              <div style="font-family:'Fredoka One';font-size:1.5rem;color:#b45309;">Admin Console</div>
              <div style="color:#6b7280;font-size:.88rem;margin-top:.35rem;">Restricted access — authorised personnel only</div>
              <div style="margin-top:.75rem;padding:.75rem;background:#fffbeb;border-radius:12px;">
                <div style="font-size:.78rem;color:#92400e;font-weight:700;">⚠️ This area is for administrators only</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            admin_pwd = st.text_input("Admin Password", type="password", placeholder="Enter your secret password…")
            ca, cb = st.columns(2, gap="small")
            with ca:
                if st.button("🔓 Login as Admin", key="do_admin_login", use_container_width=True):
                    if admin_pwd == ADMIN_PASS:
                        upsert_user(ADMIN_EMAIL, "Admin", "")
                        st.session_state.auth = {"logged_in": True, "user": ADMIN_EMAIL, "role": "admin"}
                        st.session_state.login_step = "role"
                        st.rerun()
                    else:
                        st.error("❌ Wrong password. Try again.")
            with cb:
                if st.button("← Back", key="back_admin", use_container_width=True):
                    st.session_state.login_step = "role"
                    st.rerun()

    st.stop()

# ══════════════════════════════════════════
# AUTHENTICATED — Common setup
# ══════════════════════════════════════════
st.markdown(CSS, unsafe_allow_html=True)

cur_email = st.session_state.auth["user"]
cur_role  = st.session_state.auth["role"]
cur_user  = get_user(cur_email) or {}

# ══════════════════════════════════════════
# PERFORMANCE PREDICTION HELPERS
# ══════════════════════════════════════════
def compute_prediction(user: dict) -> dict:
    history  = user.get("quiz_history", [])
    xp       = user.get("xp", 0)
    attempts = user.get("quiz_attempts", 0)
    scores   = [h["score"] for h in history if isinstance(h.get("score"), (int, float))]
    topics   = [h.get("topic", "?") for h in history]

    result = {
        "predicted_score": None,
        "trend": "insufficient_data",
        "trend_delta": 0.0,
        "risk_flag": "insufficient_data",
        "consistency": "insufficient_data",
        "std_dev": 0.0,
        "scores": scores,
        "topics": topics,
        "xp": xp,
        "attempts": attempts,
    }

    if len(scores) < 2:
        return result

    # Weighted predicted next score (exponential — recent scores count more)
    n       = len(scores)
    weights = [math.exp(0.3 * i) for i in range(n)]
    total_w = sum(weights)
    predicted = sum(s * w for s, w in zip(scores, weights)) / total_w
    result["predicted_score"] = round(predicted, 1)

    # Trend — linear regression slope on last 5 quizzes
    window  = scores[-5:]
    x       = list(range(len(window)))
    x_mean  = sum(x) / len(x)
    y_mean  = sum(window) / len(window)
    num     = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, window))
    den     = sum((xi - x_mean) ** 2 for xi in x) or 1
    slope   = num / den
    result["trend_delta"] = round(slope, 2)

    if slope > 0.3:
        result["trend"] = "improving"
    elif slope < -0.3:
        result["trend"] = "declining"
    else:
        result["trend"] = "stable"

    # Consistency — std deviation
    mean_s = sum(scores) / len(scores)
    std    = math.sqrt(sum((s - mean_s) ** 2 for s in scores) / len(scores))
    result["std_dev"] = round(std, 2)

    if std <= 1.2:
        result["consistency"] = "consistent"
    elif std <= 2.5:
        result["consistency"] = "variable"
    else:
        result["consistency"] = "erratic"

    # Risk flag
    avg = mean_s
    if avg >= 8 and result["trend"] != "declining":
        result["risk_flag"] = "excelling"
    elif avg >= 6:
        result["risk_flag"] = "on_track"
    elif avg >= 4:
        result["risk_flag"] = "at_risk"
    else:
        result["risk_flag"] = "struggling"

    return result


def _sparkline_chart(scores: list, predicted: float) -> BytesIO:
    fig, ax = plt.subplots(figsize=(5.5, 2.2))
    fig.patch.set_facecolor("#f7f9ff")
    ax.set_facecolor("#f7f9ff")

    x = list(range(1, len(scores) + 1))
    ax.plot(x, scores, color="#4f46e5", linewidth=2.5, marker="o",
            markersize=5, markerfacecolor="#818cf8", zorder=3)
    ax.fill_between(x, scores, alpha=0.12, color="#4f46e5")

    if predicted is not None:
        ax.plot([len(scores), len(scores) + 1], [scores[-1], predicted],
                color="#ec4899", linewidth=2, linestyle="--", marker="o",
                markersize=6, markerfacecolor="#ec4899", zorder=4)
        ax.annotate(f"Pred: {predicted}",
                    xy=(len(scores) + 1, predicted),
                    xytext=(5, -12), textcoords="offset points",
                    fontsize=8, color="#ec4899", fontweight="bold")

    ax.set_ylim(-0.5, 11)
    ax.set_yticks([0, 5, 10])
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{i}" for i in x], fontsize=7, color="#6b7280")
    ax.yaxis.set_tick_params(labelsize=7, labelcolor="#6b7280")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color("#e0e7ff")
    ax.spines["bottom"].set_color("#e0e7ff")
    ax.axhline(y=7, color="#10b981", linewidth=1, linestyle=":", alpha=0.6)
    ax.text(0.98, 7.15, "pass line", transform=ax.get_yaxis_transform(),
            fontsize=7, color="#10b981", ha="right")

    pink_patch   = mpatches.Patch(color="#ec4899", label="Predicted")
    indigo_patch = mpatches.Patch(color="#4f46e5", label="Actual")
    ax.legend(handles=[indigo_patch, pink_patch], fontsize=7, loc="upper left", framealpha=0.4)

    plt.tight_layout(pad=0.5)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _get_ai_advice(gemini_client, user_name: str, pred: dict) -> str:
    scores = pred["scores"]
    topics = pred["topics"]
    history_lines = "\n".join(
        f"  Q{i+1}: {s}/10 on '{t}'"
        for i, (s, t) in enumerate(zip(scores, topics))
    ) or "  No quiz history yet."

    prompt = f"""You are an academic performance advisor. Analyze this student's quiz data and give short, specific, encouraging advice.

Student: {user_name}
Quiz history (chronological):
{history_lines}

Predicted next score: {pred['predicted_score']}/10
Trend: {pred['trend']} (slope: {pred['trend_delta']} per quiz)
Risk flag: {pred['risk_flag']}
Consistency: {pred['consistency']} (std dev: {pred['std_dev']})
Total XP: {pred['xp']}

Write exactly 3 bullet points (use • symbol):
1. One observation about their performance pattern
2. One specific weakness or risk to address
3. One concrete action they should take next

Keep each bullet under 20 words. Be direct, warm, and constructive. No preamble."""

    try:
        resp = gemini_client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=200),
        )
        return resp.text.strip()
    except:
        return "• Keep practising consistently to build a strong score pattern.\n• Focus on topics where you scored below 6.\n• Review mistakes after each quiz to reinforce learning."


def render_performance_prediction(gemini_client, email: str, user: dict):
    pred   = compute_prediction(user)
    name   = user.get("name", "Student")
    scores = pred["scores"]

    st.markdown("---")
    st.markdown(
        '<div style="font-family:\'Fredoka One\';font-size:1rem;color:#4f46e5;margin-bottom:.75rem;">'
        '🔮 Performance Prediction</div>',
        unsafe_allow_html=True,
    )

    if len(scores) < 2:
        st.markdown(
            '<div style="background:#f7f9ff;border:2px dashed #e0e7ff;border-radius:12px;'
            'padding:1rem;text-align:center;color:#9ca3af;font-size:.85rem;">'
            '📊 Not enough quiz data yet — needs at least 2 quizzes for prediction.</div>',
            unsafe_allow_html=True,
        )
        return

    RISK_META = {
        "excelling":         {"icon": "🏆", "label": "EXCELLING"},
        "on_track":          {"icon": "✅", "label": "ON TRACK"},
        "at_risk":           {"icon": "⚠️", "label": "AT RISK"},
        "struggling":        {"icon": "🚨", "label": "STRUGGLING"},
        "insufficient_data": {"icon": "❓", "label": "UNKNOWN"},
    }
    TREND_META = {
        "improving":         {"icon": "📈", "color": "#10b981"},
        "declining":         {"icon": "📉", "color": "#ef4444"},
        "stable":            {"icon": "➡️",  "color": "#f59e0b"},
        "insufficient_data": {"icon": "❓", "color": "#9ca3af"},
    }
    CONS_META = {
        "consistent":        {"icon": "🎯", "color": "#10b981"},
        "variable":          {"icon": "〰️", "color": "#f59e0b"},
        "erratic":           {"icon": "⚡", "color": "#ef4444"},
        "insufficient_data": {"icon": "❓", "color": "#9ca3af"},
    }

    risk_m  = RISK_META[pred["risk_flag"]]
    trend_m = TREND_META[pred["trend"]]
    cons_m  = CONS_META[pred["consistency"]]

    # ── KPI row ───────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔮 Predicted Score",  f"{pred['predicted_score']}/10")
    k2.metric("📈 Score Trend",      pred["trend"].replace("_"," ").title(),
              delta=f"{pred['trend_delta']:+.2f}/quiz")
    k3.metric("🎯 Consistency",      pred["consistency"].title(),
              help=f"Std dev: {pred['std_dev']} — lower = more consistent")
    k4.metric("⚡ XP Momentum",      f"{pred['xp']:,} XP")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Risk badge + sparkline ─────────────────────────────────────
    badge_col, chart_col = st.columns([1, 2])

    with badge_col:
        risk_bg = {"excelling":"#ecfdf5","on_track":"#f0f9ff","at_risk":"#fffbeb","struggling":"#fef2f2"}.get(pred["risk_flag"],"#f7f9ff")
        risk_bd = {"excelling":"#a7f3d0","on_track":"#bae6fd","at_risk":"#fde68a","struggling":"#fecaca"}.get(pred["risk_flag"],"#e0e7ff")
        risk_tc = {"excelling":"#065f46","on_track":"#0c4a6e","at_risk":"#92400e","struggling":"#991b1b"}.get(pred["risk_flag"],"#1e1b4b")

        st.markdown(f"""
        <div style="background:{risk_bg};border:2px solid {risk_bd};border-radius:16px;
                    padding:1.2rem;text-align:center;">
          <div style="font-size:2.8rem;margin-bottom:.3rem;">{risk_m['icon']}</div>
          <div style="font-family:'Fredoka One';font-size:1rem;color:{risk_tc};">{risk_m['label']}</div>
          <div style="color:{risk_tc};font-size:.72rem;font-weight:700;margin-top:.3rem;opacity:.8;">Risk Assessment</div>
          <div style="margin-top:.75rem;display:flex;flex-direction:column;gap:.3rem;">
            <div style="background:rgba(255,255,255,.6);border-radius:8px;padding:.35rem .6rem;
                        font-size:.75rem;color:{risk_tc};font-weight:700;">
              {trend_m['icon']} Trend: {pred['trend'].replace('_',' ').title()}
            </div>
            <div style="background:rgba(255,255,255,.6);border-radius:8px;padding:.35rem .6rem;
                        font-size:.75rem;color:{cons_m['color']};font-weight:700;">
              {cons_m['icon']} {pred['consistency'].title()} performer
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with chart_col:
        st.markdown(
            '<div style="font-size:.75rem;font-weight:800;color:#6b7280;'
            'text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem;">'
            '📊 Score History + Prediction</div>',
            unsafe_allow_html=True,
        )
        chart_buf = _sparkline_chart(scores, pred["predicted_score"])
        st.image(chart_buf, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── AI Advice ─────────────────────────────────────────────────
    ai_key = f"ai_advice_{email}"
    st.markdown(
        '<div style="font-size:.75rem;font-weight:800;color:#6b7280;'
        'text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem;">'
        '🤖 AI-Generated Advice</div>',
        unsafe_allow_html=True,
    )

    if ai_key not in st.session_state:
        if st.button(f"✨ Generate AI Advice for {name.split()[0]}", key=f"btn_ai_{email}"):
            with st.spinner("Analysing with Gemini…"):
                advice = _get_ai_advice(gemini_client, name, pred)
                st.session_state[ai_key] = advice
            st.rerun()
    else:
        advice = st.session_state[ai_key]
        lines  = [l.strip() for l in advice.split("\n") if l.strip()]
        colors = ["#4f46e5","#ec4899","#10b981"]
        icons  = ["🔍","⚠️","🚀"]
        bullet_html = ""
        bi = 0
        for line in lines:
            clean = line.lstrip("•·-–1234567890. ").strip()
            if not clean: continue
            c  = colors[bi % len(colors)]
            ic = icons[bi % len(icons)]
            bullet_html += f"""
            <div style="display:flex;align-items:flex-start;gap:.7rem;
                        background:#f7f9ff;border:2px solid #e0e7ff;
                        border-left:4px solid {c};border-radius:12px;
                        padding:.65rem .9rem;margin-bottom:.4rem;">
              <span style="font-size:1rem;flex-shrink:0;">{ic}</span>
              <span style="color:#374151;font-size:.88rem;line-height:1.6;">{clean}</span>
            </div>"""
            bi += 1
        st.markdown(bullet_html, unsafe_allow_html=True)

        if st.button("🔄 Regenerate Advice", key=f"regen_{email}"):
            del st.session_state[ai_key]
            st.rerun()


# ══════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════
if cur_role == "admin":
    # Gemini client for AI advice
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    all_users = load_users()
    students  = [(e, u) for e, u in all_users.items() if e != ADMIN_EMAIL]

    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:1.5rem 0 1rem;">
          <div style="font-size:2.5rem;">🔐</div>
          <div style="font-family:'Fredoka One';font-size:1.2rem;">Admin Console</div>
          <div style="opacity:.7;font-size:.75rem;margin-top:.2rem;">Cognify Control Panel</div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
        st.metric("👥 Students", len(students))
        total_q  = sum(u.get("quiz_attempts",0) for _,u in students)
        total_xp = sum(u.get("xp",0) for _,u in students)
        st.metric("📝 Quizzes Done", total_q)
        st.metric("⚡ Total XP", f"{total_xp:,}")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {"logged_in":False,"user":None,"role":None}
            st.session_state.login_step = "role"
            st.session_state.oauth_token_consumed = False
            st.rerun()

    st.markdown("""
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap;">
      <div class="hero-title" style="font-size:2.5rem;">Admin Dashboard</div>
      <span class="pill pill-amber">🔐 ADMIN</span>
    </div>
    """, unsafe_allow_html=True)

    if not students:
        st.markdown("""
        <div class="card" style="text-align:center;padding:3rem;">
          <div style="font-size:3rem;margin-bottom:.5rem;">📭</div>
          <div style="font-family:'Fredoka One';font-size:1.3rem;color:#6b7280;">No students yet!</div>
          <div style="color:#9ca3af;font-size:.9rem;margin-top:.3rem;">Students will appear here once they sign up.</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Registered", len(students))
    active = sum(1 for _,u in students if u.get("quiz_attempts",0) > 0)
    c2.metric("Active Learners", active)
    avgs = [int(u["total_score"]/u["quiz_attempts"]) for _,u in students if u.get("quiz_attempts",0)>0]
    c3.metric("Avg Score", f"{int(sum(avgs)/len(avgs)) if avgs else 0}/10")
    c4.metric("Max XP", f"{max((u.get('xp',0) for _,u in students),default=0):,}")

    st.divider()

    search = st.text_input("🔍 Search students…", placeholder="Name or email…", label_visibility="collapsed")
    st.markdown('<div style="color:#9ca3af;font-size:.8rem;margin-bottom:.75rem;">Filter students by name or email</div>', unsafe_allow_html=True)

    filtered = [(e,u) for e,u in students if not search
                or search.lower() in u.get("name","").lower()
                or search.lower() in e.lower()]

    st.markdown(f'<div style="color:#6b7280;font-size:.8rem;margin-bottom:1rem;font-weight:700;">Showing {len(filtered)} of {len(students)} students</div>', unsafe_allow_html=True)

    for email_s, user_s in filtered:
        name_s   = user_s.get("name","Unknown")
        pic_s    = user_s.get("picture","")
        xp_s     = user_s.get("xp",0)
        att_s    = user_s.get("quiz_attempts",0)
        sc_s     = user_s.get("total_score",0)
        avg_s    = int(sc_s/att_s) if att_s else 0
        topics_s = user_s.get("topics_studied",[])
        hist_s   = user_s.get("quiz_history",[])
        lvl      = "🏆 MASTER" if avg_s>=9 else "⭐ EXPERT" if avg_s>=7 else "📈 PROFICIENT" if avg_s>=5 else "🌱 BEGINNER"
        lvl_pill = "pill-green" if avg_s>=7 else "pill-sky" if avg_s>=5 else "pill-pink"
        avatar   = f'<img src="{pic_s}" style="width:42px;height:42px;border-radius:50%;border:2px solid #c7d2fe;object-fit:cover;"/>' if pic_s else '<div style="width:42px;height:42px;border-radius:50%;background:#eef2ff;display:flex;align-items:center;justify-content:center;font-size:1.3rem;">🎓</div>'

        with st.expander(f"  {name_s}   ·   {email_s}   ·   {lvl}", expanded=False):
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;padding:.75rem;background:#f7f9ff;border-radius:12px;">
              {avatar}
              <div>
                <div style="font-family:'Fredoka One';font-size:1.1rem;color:#1e1b4b;">{name_s}</div>
                <div style="color:#6b7280;font-size:.8rem;">{email_s}</div>
              </div>
              <div style="margin-left:auto;"><span class="pill {lvl_pill}">{lvl}</span></div>
            </div>
            """, unsafe_allow_html=True)

            m1,m2,m3,m4 = st.columns(4)
            m1.metric("⚡ XP", xp_s)
            m2.metric("📝 Quizzes", att_s)
            m3.metric("🎯 Total Score", sc_s)
            m4.metric("📊 Avg Score", f"{avg_s}/10")

            if topics_s:
                st.markdown("**📚 Topics Studied:**")
                tags = "".join([f'<span class="topic-tag">{t[:24]}</span>' for t in topics_s[-12:]])
                st.markdown(f"<div style='margin:.5rem 0 1rem;'>{tags}</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#9ca3af;font-size:.85rem;font-style:italic;margin-bottom:.5rem;">No topics studied yet</div>', unsafe_allow_html=True)

            if hist_s:
                st.markdown("**🗂️ Recent Quiz History:**")
                for h in reversed(hist_s[-6:]):
                    sc_h  = h.get("score",0)
                    col_h = "#065f46" if sc_h>=7 else "#92400e" if sc_h>=5 else "#991b1b"
                    bg_h  = "#ecfdf5" if sc_h>=7 else "#fffbeb" if sc_h>=5 else "#fef2f2"
                    bd_h  = "#a7f3d0" if sc_h>=7 else "#fde68a" if sc_h>=5 else "#fecaca"
                    st.markdown(f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;
                                background:{bg_h};border:1.5px solid {bd_h};border-radius:12px;
                                padding:.55rem 1rem;margin:.25rem 0;">
                      <div>
                        <div style="font-weight:700;font-size:.88rem;color:#1e1b4b;">{h.get('topic','?')[:40]}</div>
                        <div style="color:#9ca3af;font-size:.72rem;">{h.get('time','')}</div>
                      </div>
                      <div style="font-family:'Fredoka One';font-size:1.1rem;color:{col_h};">{sc_h}/10</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#9ca3af;font-size:.85rem;font-style:italic;">No quiz history yet</div>', unsafe_allow_html=True)

            # ── 🔮 PERFORMANCE PREDICTION ──────────────────────────
            render_performance_prediction(gemini_client, email_s, user_s)

    st.stop()

# ══════════════════════════════════════════
# STUDENT APP — AI Helpers
# ══════════════════════════════════════════
def get_client():
    return genai.Client(api_key=GEMINI_API_KEY)

client = get_client()
WIKI_H = {"User-Agent":"Mozilla/5.0"}
GFG_H  = {"User-Agent":"Mozilla/5.0"}
W3_H   = {"User-Agent":"Mozilla/5.0"}

def _trunc(text, limit=800):
    if not text: return ""
    s=" ".join(str(text).split())
    if len(s)<=limit: return s
    cut=s[:limit]
    for sep in[".",  "!", "?"]:
        i=cut.rfind(sep)
        if i!=-1 and i>=int(limit*.6): return cut[:i+1]
    si=cut.rfind(" ")
    return (cut[:si]+"...") if si!=-1 else cut+"..."

def _gfg_urls(q, n=3):
    if not DDGS_AVAILABLE: return []
    urls=[]
    try:
        with DDGS() as d:
            for r in d.text(f"site:geeksforgeeks.org {q}", max_results=8):
                link=r.get("href") or r.get("link") or r.get("url")
                if link and "geeksforgeeks.org" in str(link) and link not in urls:
                    urls.append(link)
                    if len(urls)>=n: break
    except: pass
    return urls

def _w3_urls(q, n=3):
    if not DDGS_AVAILABLE: return []
    urls=[]
    try:
        with DDGS() as d:
            for r in d.text(f"site:w3schools.com {q}", max_results=8):
                link=r.get("href") or r.get("link") or r.get("url")
                if link and "w3schools.com" in str(link) and link not in urls:
                    urls.append(link)
                    if len(urls)>=n: break
    except: pass
    return urls

def wiki_summary(topic):
    for v in [topic.strip(), topic.strip().replace(" ","_"), topic.strip().title()]:
        try:
            r=requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(v)}", timeout=10, headers=WIKI_H)
            if r.status_code==200:
                ex=r.json().get("extract","")
                if ex and len(ex)>40: return ex.strip()
        except: pass
    return None

def get_summary(topic):
    s=wiki_summary(topic)
    if s and len(s)>30: return _trunc(s,1200)
    if DDGS_AVAILABLE:
        try:
            with DDGS() as d:
                for r in d.answers(topic):
                    t=r.get("text") or r.get("abstract") if isinstance(r,dict) else None
                    if t and len(t)>30: return _trunc(t,1200)
        except: pass
    return None

def _pil(img):
    if img is None: return None
    return img.convert("RGB") if img.mode in("RGBA","P") else img

def _hash(img):
    try: return hash(img.resize((64,64),Image.Resampling.LANCZOS).convert("L").tobytes())
    except: return hash(img.tobytes())

def _bad_url(url):
    if not url: return True
    return any(s in url.lower() for s in("almanac","manuscript","archive.org","antique","newspaper"))

def _dedup(imgs):
    seen,out=set(),[]
    for img in imgs:
        if img is None: continue
        h=_hash(img)
        if h not in seen: seen.add(h); out.append(img)
    return out

def _placeholder(topic):
    w,h=400,260
    img=Image.new("RGB",(w,h),color=(238,242,255))
    draw=ImageDraw.Draw(img)
    draw.rectangle([(3,3),(w-4,h-4)],outline="#4f46e5",width=3)
    title=(str(topic)[:28]+"…") if len(str(topic))>28 else str(topic)
    draw.text((w//2-55,h//2-15),title,fill="#1e1b4b")
    draw.text((w//2-38,h//2+12),"Visualization",fill="#6b7280")
    return img

def _extract_urls(html):
    urls=set()
    urls.update(re.findall(r'src=["\'](https?://[^"\']+)["\']',html,re.I))
    urls.update(re.findall(r'data-src=["\'](https?://[^"\']+)["\']',html,re.I))
    for s in re.findall(r'srcset=["\']([^"\']+)["\']',html,re.I):
        for p in s.split(","):
            u=p.strip().split(" ")[0]
            if u.startswith("http"): urls.add(u)
    return list(urls)

def _dl(urls,headers,n=5):
    out,seen=[],set()
    for url in urls:
        low=url.lower()
        if any(x in low for x in["logo","icon","avatar","favicon","pixel","banner","ads","spacer"]): continue
        try:
            r=requests.get(url,headers=headers,timeout=10)
            if r.status_code!=200 or len(r.content)<800: continue
            img=_pil(Image.open(BytesIO(r.content)))
            if not img or img.size[0]<220 or img.size[1]<180: continue
            h=_hash(img)
            if h in seen: continue
            seen.add(h); out.append(img)
            if len(out)>=n: break
        except: continue
    return out

CSE_KEY="AIzaSyBHY0WmJs8VcjmsGRdoxWP5yQuxEcsArc8"
CSE_CX ="865d79e8bd12c4859"

def _cse_urls(q,n=5):
    try:
        r=requests.get("https://www.googleapis.com/customsearch/v1",
            params={"key":CSE_KEY,"cx":CSE_CX,"q":q,"searchType":"image","num":n,"safe":"active"},timeout=10)
        if r.status_code!=200: return []
        return [i["link"] for i in r.json().get("items",[]) if i.get("link","").startswith("http")][:n]
    except: return []

def get_cse_images(topic,n=5):
    if not(topic or"").strip(): return []
    imgs=[]
    for q in[f"{topic} diagram",f"{topic} architecture",f"{topic} workflow"]:
        if len(imgs)>=n: break
        imgs.extend(_dl(_cse_urls(q,n-len(imgs)),WIKI_H,n-len(imgs)))
    return _dedup(imgs)[:n]

def get_wiki_images(topic,n=5):
    seen_p,seen_i,out=set(),set(),[]
    for v in[topic.strip(),topic.strip().replace(" ","_"),topic.strip().title()]:
        if not v or v in seen_p or len(out)>=n: continue
        seen_p.add(v)
        try:
            data=requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(v)}",timeout=10,headers=WIKI_H).json()
            img_url=(data.get("originalimage") or data.get("thumbnail") or{}).get("source")
            if not img_url or img_url in seen_i or _bad_url(img_url): continue
            seen_i.add(img_url)
            r=requests.get(img_url,timeout=10,headers=WIKI_H)
            if r.status_code!=200 or len(r.content)<500: continue
            img=_pil(Image.open(BytesIO(r.content)))
            if img and img.size[0]>=200 and img.size[1]>=200: out.append(img)
        except: continue
    return out

def get_gfg_images(topic,n=5):
    imgs=[]
    for q in[f"what is {topic}",f"{topic} diagram geeksforgeeks"]:
        for u in _gfg_urls(q,4):
            try:
                r=requests.get(u,headers=GFG_H,timeout=12)
                if r.status_code!=200: continue
                imgs.extend(_dl(_extract_urls(r.text),GFG_H,n-len(imgs)))
                if len(imgs)>=n: return imgs[:n]
            except: continue
    return imgs[:n]

def get_w3_images(topic,n=5):
    imgs=[]
    for q in[f"{topic} tutorial w3schools",f"{topic} example w3schools"]:
        for u in _w3_urls(q,4):
            try:
                r=requests.get(u,headers=W3_H,timeout=12)
                if r.status_code!=200: continue
                imgs.extend(_dl(_extract_urls(r.text),W3_H,n-len(imgs)))
                if len(imgs)>=n: return imgs[:n]
            except: continue
    return imgs[:n]

def fetch_images(topic):
    topic=(topic or"").strip()
    imgs=[]
    imgs.extend(get_cse_images(topic,5))
    if len(imgs)<5: imgs.extend(get_wiki_images(topic,5-len(imgs)))
    if len(imgs)<5: imgs.extend(get_gfg_images(topic,5-len(imgs)))
    if len(imgs)<5: imgs.extend(get_w3_images(topic,5-len(imgs)))
    imgs=_dedup(imgs)
    while len(imgs)<5: imgs.append(_placeholder(topic))
    return imgs[:5]

def gen_img(prompt):
    t=prompt.split("-")[0].strip()
    imgs=fetch_images(t)
    return imgs[0] if imgs else _placeholder(t)

def fallback(topic):
    return {
        "summary": f"{topic} is a fascinating subject that shapes how we understand the world around us. It helps us solve real problems and powers many technologies we use every day. Learning it gives you a superpower to understand and create amazing things!",
        "keywords": [{"word":w,"description":f"Key idea in {topic}"} for w in["Core Concept","Main Process","Key System","Important Function","Real-World Use"]],
        "flowchart": [
            {"title":"What is it?",   "description":f"Understand the basic idea and purpose of {topic}."},
            {"title":"How it works",  "description":f"Break down the steps and processes inside {topic}."},
            {"title":"Real examples", "description":f"See {topic} in action in real life."},
            {"title":"Why it matters","description":f"Discover the impact and uses of {topic} in the world."}
        ],
        "concepts": [
            {"id":"c1","label":f"Basics of {topic}","description":f"The foundational definitions and core properties that make up {topic}."},
            {"id":"c2","label":"How It Works",       "description":f"The step-by-step mechanism behind {topic} — from input to output."},
            {"id":"c3","label":"Real Examples",      "description":f"Concrete, everyday examples that show {topic} in action."},
            {"id":"c4","label":"Why It Matters",     "description":f"The real-world significance and impact of understanding {topic}."}
        ],
        "quiz":[
            {"id":i+1,"type":"mcq","question":f"Question {i+1} about {topic}?",
             "options":["Option A","Option B","Option C","Option D"],"correctAnswer":0,"analyticalAnswer":""}
            for i in range(7)
        ]+[
            {"id":8, "type":"analytical","question":f"Explain how {topic} affects our daily lives.",   "options":[],"correctAnswer":0,"analyticalAnswer":f"{topic} affects daily life by enabling better understanding."},
            {"id":9, "type":"analytical","question":f"Describe the main process in {topic}.",          "options":[],"correctAnswer":0,"analyticalAnswer":"Sequential interdependent steps."},
            {"id":10,"type":"analytical","question":f"Give a practical example of {topic}.",           "options":[],"correctAnswer":0,"analyticalAnswer":"Direct real-world application."},
        ]
    }

def process_topic(topic):
    prompt = f"""ACT AS AN AI TUTOR for school students.
Topic: "{topic}".
Generate 10 questions (7 MCQs + 3 Analytical). Difficulty: Medium-Hard.
Return ONLY VALID JSON with these keys:
- summary: 3-5 sentences in simple, friendly English a school student can easily understand
- keywords: 5 objects with "word" and "description"
- flowchart: 4 sequential objects with "title" and "description"
- concepts: 4 objects with "id", "label", "description"
- quiz: 10 objects with "id", "type"("mcq"/"analytical"), "question",
  "options"(4 items for mcq / empty for analytical), "correctAnswer"(index 0-3), "analyticalAnswer"
"""
    fb = fallback(topic)
    ov = get_summary(topic)
    if ov and len(ov)>30: fb["summary"]=_trunc(ov,800)
    if os.environ.get("USE_FALLBACK_ONLY","").lower() in("1","true","yes"): return fb
    try:
        resp = client.models.generate_content(
            model="gemini-flash-latest", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        result = json.loads(resp.text)
        result["summary"] = _trunc(ov,800) if(ov and len(ov)>30) else _trunc(result.get("summary",""),800)
        return result
    except Exception as e:
        err=str(e)
        if "429" in err or "quota" in err.lower(): st.warning("⚠️ Gemini quota reached — using fallback analysis.")
        elif "403" not in err: st.warning("⚠️ API error — using fallback analysis.")
        return fb

# ══════════════════════════════════════════
# STUDENT SESSION STATE
# ══════════════════════════════════════════
if "vault"      not in st.session_state: st.session_state.vault=[]
if "active_idx" not in st.session_state: st.session_state.active_idx=0

xp_v  = cur_user.get("xp",0)
att_v = cur_user.get("quiz_attempts",0)
sc_v  = cur_user.get("total_score",0)
avg_v = int(sc_v/att_v) if att_v else 0
level = "🏆 MASTER" if avg_v>=9 else "⭐ EXPERT" if avg_v>=7 else "📈 PROFICIENT" if avg_v>=5 else "🌱 BEGINNER"
lp    = "pill-green" if avg_v>=7 else "pill-sky" if avg_v>=5 else "pill-pink"

# ══════════════════════════════════════════
# SIDEBAR — Student
# ══════════════════════════════════════════
with st.sidebar:
    pic = cur_user.get("picture","")
    if pic:
        st.markdown(f'<div style="text-align:center;padding:1.2rem 0 .6rem;"><img src="{pic}" style="width:72px;height:72px;border-radius:50%;border:3px solid rgba(255,255,255,.5);object-fit:cover;box-shadow:0 4px 16px rgba(0,0,0,.2);"/></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align:center;font-size:3rem;padding:1rem 0 .5rem;">🎓</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center;margin-bottom:.75rem;">
      <div style="font-family:'Fredoka One';font-size:1.05rem;">{cur_user.get('name','Student')}</div>
      <div style="opacity:.7;font-size:.72rem;margin-top:.1rem;">{cur_email}</div>
      <div style="margin-top:.5rem;"><span style="background:rgba(255,255,255,.2);color:#fff;padding:.2rem .75rem;border-radius:50px;font-size:.7rem;font-weight:800;letter-spacing:.08em;">{level}</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.metric("⚡ XP Earned", f"{xp_v:,}")
    st.metric("📝 Quizzes Taken", att_v)
    st.metric("🎯 Avg Score", f"{avg_v}/10")

    topics_s = cur_user.get("topics_studied",[])
    if topics_s:
        st.divider()
        st.markdown('<div style="font-size:.72rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;opacity:.7;margin-bottom:.4rem;">Recent Topics</div>', unsafe_allow_html=True)
        for t in topics_s[-5:][::-1]:
            st.markdown(f'<div style="font-size:.78rem;padding:.25rem 0;opacity:.85;">› {t[:28]}</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth={"logged_in":False,"user":None,"role":None}
        st.session_state.login_step = "role"
        st.session_state.oauth_token_consumed = False
        st.rerun()

# ══════════════════════════════════════════
# MAIN STUDENT AREA
# ══════════════════════════════════════════
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;flex-wrap:wrap;gap:.75rem;">
  <div>
    <div class="hero-title" style="font-size:2.2rem;">🧠 COGNIFY</div>
    <div style="color:#6b7280;font-size:.82rem;letter-spacing:.08em;font-weight:700;">YOUR AI LEARNING COMPANION</div>
  </div>
  <div style="display:flex;gap:.4rem;align-items:center;flex-wrap:wrap;">
    <span class="stat-chip">⚡ {xp_v:,} XP</span>
    <span class="pill {lp}">{level}</span>
    <span class="pill pill-sky">📦 {len(st.session_state.vault)} topics</span>
  </div>
</div>
""", unsafe_allow_html=True)

left_space, col_in, col_viz, right_space = st.columns([0.6, 1.2, 2.3, 0.6], gap="large")

# ── Input Panel ────────────────────────────────────────────
with col_in:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:\'Fredoka One\';font-size:1.2rem;color:#4f46e5;margin-bottom:.9rem;">🔍 What do you want to learn?</div>', unsafe_allow_html=True)

    if MIC_AVAILABLE:
        tc,mc = st.columns([3,1])
        with mc:
            st.markdown('<div style="font-size:.7rem;color:#9ca3af;margin-top:1.5rem;text-align:center;">🎙️ Speak</div>', unsafe_allow_html=True)
            vt = speech_to_text(language="en", use_container_width=True, just_once=True, key="voice_m")
        if vt: st.session_state["ti_m"]=vt
        with tc:
            input_text = st.text_area("Topic", placeholder="e.g. Photosynthesis, Arrays, Climate Change…", height=115, key="ti_m", label_visibility="collapsed")
    else:
        input_text = st.text_area("Topic", placeholder="e.g. Photosynthesis, Arrays, Climate Change…", height=115, label_visibility="collapsed")

    st.markdown('<div style="color:#9ca3af;font-size:.75rem;margin-top:-.5rem;margin-bottom:.6rem;">💡 Try: Photosynthesis, Machine Learning, World War 2…</div>', unsafe_allow_html=True)

    if st.button("✨ Explore This Topic!", use_container_width=True):
        if input_text and input_text.strip():
            prog = st.progress(0, text="🚀 Starting…")
            try:
                prog.progress(20, "🖼️ Fetching images…")
                images = fetch_images(input_text.strip())
                prog.progress(60, "🧠 Building your cognitive map…")
                analysis = process_topic(input_text.strip())
                prog.progress(90, "💾 Saving to vault…")
                st.session_state.vault.insert(0,{"topic":input_text.strip(),"analysis":analysis,"images":images})
                st.session_state.active_idx=0
                update_user_stats(cur_email, xp_gain=100, topic=input_text.strip())
                prog.progress(100,"✅ Done!")
                time.sleep(.3); prog.empty()
                st.success("🎉 Added to your learning vault!")
            except Exception as e:
                prog.empty(); st.error(f"Something went wrong: {e}")
        else:
            st.warning("👆 Please type a topic first!")

    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.vault:
        st.markdown('<div style="margin-top:1.25rem;">', unsafe_allow_html=True)
        st.markdown('<div style="font-family:\'Fredoka One\';font-size:1rem;color:#4f46e5;margin-bottom:.65rem;">📦 My Learning Vault</div>', unsafe_allow_html=True)
        for idx,entry in enumerate(st.session_state.vault):
            is_a = (idx==st.session_state.active_idx)
            bg   = "linear-gradient(135deg,#eef2ff,#e0e7ff)" if is_a else "#ffffff"
            bd   = "#4f46e5" if is_a else "#e0e7ff"
            fw   = "800" if is_a else "600"
            st.markdown(f"""
            <div style="background:{bg};border:2px solid {bd};border-radius:12px;padding:.55rem .9rem;margin-bottom:.35rem;">
              <div style="font-size:.82rem;font-weight:{fw};color:#1e1b4b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {'📖' if is_a else '📄'} {entry['topic'][:30]}
              </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open →", key=f"v_{idx}", use_container_width=True):
                st.session_state.active_idx=idx; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ── Visualization Panel ─────────────────────────────────────
with col_viz:
    if st.session_state.vault:
        aidx     = st.session_state.active_idx
        data     = st.session_state.vault[aidx]
        analysis = data["analysis"]

        tab1,tab2,tab3,tab4 = st.tabs(["🖼️ Gallery","🗺️ Mind Map","📈 Flow","📝 Quiz"])

        # ─ Gallery ──────────────────────────────────────────
        with tab1:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#eef2ff 0%,#fdf2f8 100%);border-radius:var(--radius-lg);padding:1.2rem 1.5rem;margin-bottom:1.2rem;border:2px solid #e0e7ff;">
              <div style="font-family:'Fredoka One';font-size:1.7rem;color:#4f46e5;margin-bottom:.3rem;">{data['topic']}</div>
              <div style="display:flex;gap:.4rem;flex-wrap:wrap;"><span class="pill pill-indigo">✨ AI Summary</span><span class="pill pill-pink">📚 Topic Overview</span></div>
            </div>
            """, unsafe_allow_html=True)

            summ = (analysis.get("summary") or "No summary available.").strip()
            st.markdown(f"""
            <div style="background:#fff;border:2px solid #c7d2fe;border-left:5px solid #4f46e5;border-radius:var(--radius);padding:1.1rem 1.3rem;margin-bottom:1.1rem;font-size:.93rem;line-height:1.75;color:#1e1b4b;">
              <span style="color:#4f46e5;font-weight:800;font-size:.72rem;letter-spacing:.1em;display:block;margin-bottom:.4rem;text-transform:uppercase;">📝 Summary</span>
              {summ}
            </div>
            """, unsafe_allow_html=True)

            if data.get("images"):
                imgs = data["images"][:5]
                ic   = st.columns(len(imgs))
                for i,img in enumerate(imgs):
                    with ic[i]: st.image(img, use_container_width=True)

            st.markdown('<div style="margin-top:1rem;">', unsafe_allow_html=True)
            st.markdown('<div style="font-family:Fredoka One;color:#6b7280;font-size:.85rem;margin-bottom:.5rem;">🎨 Generate More Visuals:</div>', unsafe_allow_html=True)
            kc = st.columns(3)
            for i,kw in enumerate(analysis["keywords"][1:4]):
                if kc[i].button(f"+ {kw['word'][:14]}", key=f"gen_{kw['word']}_{aidx}"):
                    with st.spinner(f"Generating visual for {kw['word']}…"):
                        ni = gen_img(f"{data['topic']} - {kw['word']}")
                        if ni:
                            ex=data.get("images",[]); cm=_dedup(ex+[ni])
                            if len(cm)>len(ex): data["images"]=cm
                            st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div style="margin-top:1.1rem;">', unsafe_allow_html=True)
            st.markdown('<div style="font-family:Fredoka One;color:#4f46e5;font-size:1rem;margin-bottom:.6rem;">🔑 Key Terms</div>', unsafe_allow_html=True)
            for kw in analysis.get("keywords",[]):
                st.markdown(f"""
                <div style="display:flex;align-items:flex-start;gap:.7rem;background:#f7f9ff;border:2px solid #e0e7ff;border-radius:12px;padding:.65rem .9rem;margin-bottom:.35rem;transition:all .2s;">
                  <span class="pill pill-indigo" style="flex-shrink:0;">{kw['word']}</span>
                  <span style="color:#6b7280;font-size:.83rem;line-height:1.55;">{kw['description']}</span>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # ─ Mind Map ─────────────────────────────────────────
        with tab2:
            st.markdown('<div style="font-family:Fredoka One;font-size:1.15rem;color:#4f46e5;margin-bottom:1rem;">🗺️ Concept Mind Map</div>', unsafe_allow_html=True)
            dot = graphviz.Digraph()
            dot.attr(rankdir="LR", size="9,5", bgcolor="white")
            dot.attr("node",fontname="Helvetica"); dot.attr("edge",fontname="Helvetica")
            cl = (analysis.get("keywords") or [{}])[0].get("word","").strip() or data["topic"]
            if cl.lower() in("concept","topic","main concept"): cl=data["topic"]
            dot.node("C",cl.upper(),shape="doublecircle",color="#4f46e5",style="filled",fillcolor="#4f46e5",fontcolor="white",penwidth="2")
            nc=["#ec4899","#0ea5e9","#10b981","#f59e0b"]
            for i,c in enumerate(analysis.get("concepts",[])):
                cid=c.get("id",f"c{i}"); lbl=c.get("label") or c.get("word") or f"Concept {i+1}"; col=nc[i%len(nc)]
                dot.node(cid,lbl,shape="box",style="rounded,filled",fillcolor="#fafafa",fontcolor=col,color=col,penwidth="2")
                dot.edge("C",cid,color="#c7d2fe",penwidth="2",arrowsize=".7")
            st.graphviz_chart(dot)
            for i,c in enumerate(analysis.get("concepts",[])):
                lbl=c.get("label") or c.get("word") or f"Concept {i+1}"; desc=c.get("description","No description."); col=nc[i%len(nc)]
                with st.expander(f"  {lbl}"):
                    st.markdown(f'<div style="color:#374151;font-size:.9rem;line-height:1.75;">{desc}</div>', unsafe_allow_html=True)

        # ─ Flow ─────────────────────────────────────────────
        with tab3:
            st.markdown('<div style="font-family:Fredoka One;font-size:1.15rem;color:#4f46e5;margin-bottom:1rem;">📈 Learning Flow</div>', unsafe_allow_html=True)
            fd = graphviz.Digraph()
            fd.attr(rankdir="TB", size="7,6", bgcolor="white")
            fd.attr("node",fontname="Helvetica")
            sc=["#4f46e5","#ec4899","#0ea5e9","#10b981"]
            for i,step in enumerate(analysis["flowchart"]):
                c=sc[i%len(sc)]
                fd.node(f"s{i}",f"{i+1}. {step['title']}",shape="box",style="rounded,filled",fillcolor=c,fontcolor="white",color=c,penwidth="0")
                if i>0: fd.edge(f"s{i-1}",f"s{i}",color="#c7d2fe",penwidth="2")
            st.graphviz_chart(fd)
            st.divider()

            sel=st.select_slider("👆 Tap a stage to explore:",options=range(len(analysis["flowchart"])),
                                 format_func=lambda x:f"Stage {x+1}: {analysis['flowchart'][x]['title']}")
            cs=analysis["flowchart"][sel]; cc=sc[sel%len(sc)]
            st.markdown(f"""
            <div style="background:#fff;border:2px solid #e0e7ff;border-left:6px solid {cc};border-radius:var(--radius-lg);padding:1.5rem 1.8rem;margin:1rem 0;box-shadow:var(--shadow);">
              <div style="font-size:.7rem;color:{cc};font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">🚦 STAGE {sel+1} OF {len(analysis['flowchart'])}</div>
              <div style="font-family:'Fredoka One';font-size:1.4rem;margin-bottom:.6rem;color:#1e1b4b;">{cs['title']}</div>
              <div style="color:#4b5563;font-size:.93rem;line-height:1.75;">{cs['description']}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"🖼️ Generate Visual for Stage {sel+1}", key=f"fb_{sel}_{aidx}"):
                with st.spinner("Creating visual…"):
                    ni=gen_img(f"{data['topic']} - {cs['title']}")
                    if ni:
                        ex=data.get("images",[]); cm=_dedup(ex+[ni])
                        if len(cm)>len(ex): data["images"]=cm; st.success("✅ Added to Gallery!")
                        st.rerun()

        # ─ Quiz ─────────────────────────────────────────────
        with tab4:
            st.markdown('<div style="font-family:Fredoka One;font-size:1.15rem;color:#4f46e5;margin-bottom:.75rem;">📝 Knowledge Quiz</div>', unsafe_allow_html=True)
            qsk=f"qs_{aidx}"
            if qsk not in st.session_state:
                st.session_state[qsk]={"started":False,"current_idx":0,"responses":[],"terminated":False,"start_time":None,"completed":False}
            qs=st.session_state[qsk]

            if qs["started"] and not qs["completed"]:
                elapsed=time.time()-qs["start_time"]; rem=max(0,900-int(elapsed))
                mins=rem//60; secs=rem%60
                timer_col=("#10b981" if rem>300 else "#f59e0b" if rem>120 else "#ef4444")
                st.components.v1.html(f"""
                <div style="background:#f7f9ff;border:2px solid #e0e7ff;border-radius:50px;padding:8px 20px;display:flex;justify-content:space-between;align-items:center;font-family:'Nunito',sans-serif;margin-bottom:8px;">
                  <div style="font-size:1rem;font-weight:900;color:{timer_col};">⏱️ <span id="tmr">{mins:02d}:{secs:02d}</span></div>
                  <div style="font-size:.72rem;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">Question {qs['current_idx']+1} of 10</div>
                  <div style="font-size:.72rem;color:#10b981;font-weight:800;">● LIVE</div>
                </div>
                <script>
                let t={rem};const d=document.getElementById('tmr');
                function tick(){{if(t<=0)return;d.innerText=String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');if(t<=120)d.style.color='#ef4444';else if(t<=300)d.style.color='#f59e0b';t--;}}
                setInterval(tick,1000);
                document.addEventListener('visibilitychange',function(){{if(document.hidden)alert('⚠️ Tab switch detected! Please stay on this page during your quiz.');}});
                </script>
                """, height=52)

            if not qs["started"] and not qs["completed"] and not qs["terminated"]:
                st.markdown(f"""
                <div class="card" style="padding:1.75rem;">
                  <div style="text-align:center;margin-bottom:1.25rem;">
                    <div style="font-size:3rem;margin-bottom:.4rem;">🎯</div>
                    <div style="font-family:'Fredoka One';font-size:1.3rem;color:#4f46e5;">Ready to test your knowledge?</div>
                    <div style="color:#6b7280;font-size:.88rem;margin-top:.3rem;">Topic: <b style="color:#1e1b4b;">{data['topic']}</b></div>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;margin-bottom:1.25rem;">
                    <div style="background:#eef2ff;border-radius:12px;padding:.75rem;text-align:center;"><div style="font-size:1.4rem;">📋</div><div style="font-family:'Fredoka One';font-size:.9rem;color:#4f46e5;">10 Questions</div><div style="color:#9ca3af;font-size:.72rem;">7 MCQ + 3 Written</div></div>
                    <div style="background:#fdf2f8;border-radius:12px;padding:.75rem;text-align:center;"><div style="font-size:1.4rem;">⏰</div><div style="font-family:'Fredoka One';font-size:.9rem;color:#ec4899;">15 Minutes</div><div style="color:#9ca3af;font-size:.72rem;">Countdown timer</div></div>
                    <div style="background:#ecfdf5;border-radius:12px;padding:.75rem;text-align:center;"><div style="font-size:1.4rem;">⚡</div><div style="font-family:'Fredoka One';font-size:.9rem;color:#10b981;">+XP Reward</div><div style="color:#9ca3af;font-size:.72rem;">Up to +500 XP</div></div>
                  </div>
                  <div style="background:#fffbeb;border:1.5px solid #fde68a;border-radius:12px;padding:.75rem 1rem;">
                    <div style="font-size:.8rem;color:#92400e;font-weight:700;">⚠️ Rules: Stay on this tab · No external help · Answers are final</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🚀 Start the Quiz!", use_container_width=True):
                    qs["started"]=True; qs["start_time"]=time.time(); st.rerun()

            elif qs["terminated"]:
                st.error("🚨 Quiz ended — integrity violation detected.")
                if st.button("↩️ Try Again (−150 XP)"):
                    del st.session_state[qsk]; st.rerun()

            elif qs["completed"]:
                score=0
                for i,resp in enumerate(qs["responses"]):
                    q=analysis["quiz"][i]
                    if q.get("type")=="mcq" or(q.get("options") and len(q.get("options",[]))>0):
                        if resp in q["options"] and q["options"].index(resp)==q["correctAnswer"]: score+=1
                    else:
                        gold=q.get("analyticalAnswer","").lower()
                        if gold and gold[:30] in resp.lower(): score+=1
                pct=int(score/len(analysis["quiz"])*100)
                lvl_r="🏆 MASTER" if pct>=90 else "⭐ EXPERT" if pct>=70 else "📈 PROFICIENT" if pct>=50 else "🌱 KEEP GOING"
                bar_c="#10b981" if pct>=70 else "#f59e0b" if pct>=50 else "#ef4444"
                bg_c ="#ecfdf5" if pct>=70 else "#fffbeb" if pct>=50 else "#fef2f2"
                bd_c ="#a7f3d0" if pct>=70 else "#fde68a" if pct>=50 else "#fecaca"
                emoji="🎉" if pct>=70 else "💪" if pct>=50 else "📖"

                st.markdown(f"""
                <div style="background:{bg_c};border:2px solid {bd_c};border-radius:var(--radius-lg);padding:2.5rem 2rem;text-align:center;box-shadow:var(--shadow);">
                  <div style="font-size:3.5rem;margin-bottom:.5rem;">{emoji}</div>
                  <div style="font-family:'Fredoka One';font-size:.9rem;color:#6b7280;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.5rem;">Quiz Complete!</div>
                  <div style="font-family:'Fredoka One';font-size:4.5rem;color:{bar_c};line-height:1;">{score}<span style="font-size:2rem;color:#9ca3af;">/10</span></div>
                  <div style="margin:.75rem 0;"><span class="pill" style="background:{bg_c};color:{bar_c};border:2px solid {bd_c};font-size:.85rem;padding:.35rem 1.1rem;">{lvl_r}</span></div>
                  <div style="background:rgba(255,255,255,.6);border-radius:100px;height:10px;overflow:hidden;margin:.75rem 0;">
                    <div style="width:{pct}%;height:100%;background:{bar_c};border-radius:100px;transition:width 1s;"></div>
                  </div>
                  <div style="color:#6b7280;font-size:.82rem;font-weight:700;">{pct}% accuracy · +{score*50} XP earned!</div>
                </div>
                """, unsafe_allow_html=True)
                update_user_stats(cur_email,xp_gain=score*50,quiz_score=score,topic=data["topic"])
                if st.button("💾 Save Results & Continue", use_container_width=True):
                    del st.session_state[qsk]; st.rerun()

            elif qs["started"]:
                if time.time()-qs["start_time"]>=900: qs["completed"]=True; st.rerun()
                qi=qs["current_idx"]
                q=analysis["quiz"][qi]
                mcq=q.get("type")=="mcq" or(q.get("options") and len(q.get("options",[]))>0)
                pct_d=int(qi/10*100)

                st.markdown(f"""
                <div style="margin-bottom:.85rem;">
                  <div style="display:flex;justify-content:space-between;margin-bottom:.35rem;">
                    <span style="font-size:.75rem;font-weight:800;color:#4f46e5;">Progress</span>
                    <span style="font-size:.75rem;font-weight:800;color:#6b7280;">{qi} of 10 done</span>
                  </div>
                  <div style="background:#e0e7ff;border-radius:100px;height:8px;overflow:hidden;">
                    <div style="width:{pct_d}%;height:100%;background:linear-gradient(90deg,#4f46e5,#ec4899);border-radius:100px;transition:width .5s;"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                badge=f'<span class="pill pill-indigo">MCQ</span>' if mcq else f'<span class="pill pill-pink">Written ✍️</span>'
                st.markdown(f"""
                <div class="quiz-card">
                  <div style="display:flex;align-items:center;gap:.7rem;margin-bottom:.9rem;">
                    <span style="background:#4f46e5;color:#fff;border-radius:50%;width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;font-family:'Fredoka One';font-size:.85rem;flex-shrink:0;">{qi+1}</span>
                    {badge}
                  </div>
                  <div style="font-family:'Poppins';font-weight:600;font-size:1.05rem;line-height:1.55;color:#1e1b4b;">{q['question']}</div>
                </div>
                """, unsafe_allow_html=True)

                if mcq:
                    response=st.radio("",q["options"],key=f"a_{qi}_{aidx}",label_visibility="collapsed")
                else:
                    st.markdown('<div style="color:#6b7280;font-size:.8rem;font-weight:700;margin-bottom:.4rem;">✍️ Write your answer:</div>', unsafe_allow_html=True)
                    response=st.text_area("",placeholder="Type your detailed answer here…",key=f"a_{qi}_{aidx}",height=110,label_visibility="collapsed")

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✅ Submit Answer & Next", use_container_width=True):
                    qs["responses"].append(response or "")
                    if qs["current_idx"]<9: qs["current_idx"]+=1; st.rerun()
                    else: qs["completed"]=True; st.rerun()
                st.markdown('<div style="text-align:center;margin-top:.6rem;color:#9ca3af;font-size:.7rem;font-weight:700;">🔒 Monitored session · Stay on this tab · Answers are final</div>', unsafe_allow_html=True)

    else:
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:420px;text-align:center;">
          <div style="font-size:5rem;margin-bottom:1rem;"><span class="float">🧠</span></div>
          <div style="font-family:'Fredoka One';font-size:1.6rem;color:#4f46e5;margin-bottom:.5rem;">Your vault is empty!</div>
          <div style="color:#6b7280;font-size:.92rem;max-width:300px;line-height:1.7;">
            Type any topic on the left and tap<br>
            <b style="color:#4f46e5;">✨ Explore This Topic!</b><br>
            to create your first cognitive map 🚀
          </div>
        </div>
        """, unsafe_allow_html=True)