"""
Script 5 — Publisher (Production)
Leader Decision Tracker · Philippines / Marcos Jr.

Generates a full multi-page institutional website from promise data.
Pages: Home, Promises, Meter, Issues, About
Design: ProPublica/Reuters editorial meets Stripe product cleanliness.

Run: python publisher.py
Output: site/index.html
Deploy: git add site/ && git commit -m "publish" && git push
"""

import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

PROMISES_DIR       = Path("data/promises")
REPORT_FILE        = Path("data/verdicts_report.json")
SITE_DIR           = Path("site")
OUTPUT_FILE        = SITE_DIR / "index.html"
AUTO_PUSH          = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

VERDICT_META = {
    "kept":         {"label": "Kept",         "symbol": "✓", "color": "#2d6a4f", "bg": "#d8f3dc", "bar": "#52b788"},
    "broken":       {"label": "Broken",       "symbol": "✗", "color": "#9b2226", "bg": "#fde8e9", "bar": "#e63946"},
    "partial":      {"label": "Partial",      "symbol": "◑", "color": "#7b4f12", "bg": "#fff0d6", "bar": "#f4a261"},
    "too_early":    {"label": "Too early",    "symbol": "◷", "color": "#14375a", "bg": "#dbeafe", "bar": "#3b82f6"},
    "unverifiable": {"label": "Unverifiable", "symbol": "?", "color": "#4a4a4a", "bg": "#f0f0f0", "bar": "#aaa"},
}

CATEGORY_META = {
    "economy":         {"label": "Economy",         "icon": "▲"},
    "infrastructure":  {"label": "Infrastructure",  "icon": "◼"},
    "healthcare":      {"label": "Healthcare",       "icon": "✚"},
    "education":       {"label": "Education",        "icon": "◆"},
    "agriculture":     {"label": "Agriculture",      "icon": "❋"},
    "security":        {"label": "Security",         "icon": "◉"},
    "anti_corruption": {"label": "Anti-corruption",  "icon": "⊘"},
    "social_welfare":  {"label": "Social welfare",   "icon": "♦"},
    "environment":     {"label": "Environment",      "icon": "◎"},
    "foreign_policy":  {"label": "Foreign policy",   "icon": "◈"},
    "other":           {"label": "Other",            "icon": "•"},
}

def esc(t):
    if not t: return ""
    return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def fmt_date(d):
    if not d: return ""
    try: return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except: return d

def load_promises():
    if not PROMISES_DIR.exists(): return []
    out = []
    for p in sorted(PROMISES_DIR.glob("*.json")):
        with open(p) as f:
            d = json.load(f)
        if d.get("verdict"): out.append(d)
    order = {"broken":0,"partial":1,"kept":2,"too_early":3,"unverifiable":4}
    out.sort(key=lambda x: (order.get(x.get("verdict","unverifiable"),5), x.get("speech_date","") or ""))
    return out

def load_report():
    if REPORT_FILE.exists():
        with open(REPORT_FILE) as f: return json.load(f)
    return {}

def compute_stats(promises, report):
    vb = report.get("verdict_breakdown", {})
    if not vb:
        vc = Counter(p.get("verdict") for p in promises)
        vb = {k: vc.get(k,0) for k in VERDICT_META}
    kept = vb.get("kept",0); broken = vb.get("broken",0); partial = vb.get("partial",0)
    scoreable = kept + broken + partial
    rate = round(kept / scoreable * 100) if scoreable else 0
    by_cat = defaultdict(lambda: {"kept":0,"broken":0,"partial":0,"too_early":0,"unverifiable":0,"total":0})
    for p in promises:
        c = p.get("category","other"); v = p.get("verdict","unverifiable")
        by_cat[c][v] = by_cat[c].get(v,0) + 1
        by_cat[c]["total"] += 1
    for c in by_cat:
        s = by_cat[c]["kept"] + by_cat[c]["broken"] + by_cat[c]["partial"]
        by_cat[c]["keep_rate"] = round(by_cat[c]["kept"]/s*100) if s else None
    return {"vb":vb,"rate":rate,"scoreable":scoreable,"total":len(promises),"by_cat":dict(by_cat)}

# ─────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=Lora:ital,wght@0,400;0,600;1,400;1,600&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --ink:#111827;--ink2:#374151;--ink3:#6b7280;--ink4:#9ca3af;
  --paper:#ffffff;--paper2:#f9fafb;--paper3:#f3f4f6;
  --rule:#e5e7eb;--rule2:#d1d5db;
  --accent:#c8001e;--accent2:#9b001a;
  --kept:#2d6a4f;--kept-bg:#d8f3dc;--kept-bar:#52b788;
  --broken:#9b2226;--broken-bg:#fde8e9;--broken-bar:#e63946;
  --partial:#7b4f12;--partial-bg:#fff0d6;--partial-bar:#f4a261;
  --early:#14375a;--early-bg:#dbeafe;--early-bar:#3b82f6;
  --unver:#4a4a4a;--unver-bg:#f0f0f0;--unver-bar:#aaaaaa;
  --ff-sans:'Libre Franklin',system-ui,sans-serif;
  --ff-serif:'Lora',Georgia,serif;
  --ff-mono:'JetBrains Mono',monospace;
  --max:1160px;
  --nav-h:56px;
}
html{font-size:16px;scroll-behavior:smooth;-webkit-font-smoothing:antialiased}
body{background:var(--paper);color:var(--ink);font-family:var(--ff-sans);font-size:15px;line-height:1.6}
a{color:inherit;text-decoration:none}
button{font-family:var(--ff-sans);cursor:pointer}
img{display:block;max-width:100%}

/* ── PAGE SYSTEM ── */
.page{display:none}
.page.active{display:block}

/* ── NAV ── */
.site-nav{
  position:sticky;top:0;z-index:200;
  background:var(--paper);
  border-bottom:1px solid var(--rule);
  height:var(--nav-h);
}
.nav-inner{
  max-width:var(--max);margin:0 auto;
  padding:0 32px;height:100%;
  display:flex;align-items:center;gap:0;
}
.nav-brand{display:flex;align-items:center;gap:9px;margin-right:40px;flex-shrink:0}
.nav-brand-mark{
  width:28px;height:28px;background:var(--accent);border-radius:5px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
}
.nav-brand-mark svg{width:14px;height:14px;fill:white}
.nav-brand-name{font-family:var(--ff-sans);font-size:16px;font-weight:700;letter-spacing:-0.3px;color:var(--ink)}
.nav-links{display:flex;align-items:center;gap:2px;flex:1}
.nav-link{
  font-size:13px;font-weight:500;color:var(--ink3);
  padding:6px 14px;border-radius:6px;border:none;background:none;
  transition:color .15s,background .15s;white-space:nowrap;
}
.nav-link:hover{color:var(--ink);background:var(--paper3)}
.nav-link.active{color:var(--ink);background:var(--paper3)}
.nav-right{display:flex;align-items:center;gap:12px;margin-left:auto}
.nav-tag{
  font-family:var(--ff-mono);font-size:10px;letter-spacing:.06em;
  padding:4px 11px;border-radius:20px;border:1px solid var(--rule2);
  color:var(--ink3);display:flex;align-items:center;gap:6px;
}
.nav-live{width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0}
.nav-updated{font-family:var(--ff-mono);font-size:10px;color:var(--ink4)}

/* ── TOP RULE ── */
.top-rule{height:3px;background:var(--accent);width:100%}

/* ── WRAPPERS ── */
.wrap{max-width:var(--max);margin:0 auto;padding:0 32px}

/* ── HOME HERO ── */
.hero{
  border-bottom:1px solid var(--rule);
  padding:52px 0 44px;
}
.hero-inner{display:grid;grid-template-columns:1fr 420px;gap:60px;align-items:center}
.hero-eyebrow{
  font-family:var(--ff-mono);font-size:10px;letter-spacing:.15em;text-transform:uppercase;
  color:var(--accent);margin-bottom:14px;display:flex;align-items:center;gap:8px;
}
.hero-eyebrow::before{content:'';display:block;width:20px;height:1px;background:var(--accent)}
.hero-h1{
  font-family:var(--ff-serif);font-size:38px;font-weight:600;line-height:1.18;
  letter-spacing:-.5px;color:var(--ink);margin-bottom:16px;
}
.hero-h1 em{font-style:italic;color:var(--accent)}
.hero-lede{font-size:15px;color:var(--ink2);line-height:1.75;max-width:480px;margin-bottom:28px}
.hero-cta{
  display:inline-flex;align-items:center;gap:8px;
  background:var(--accent);color:white;
  font-size:13px;font-weight:600;letter-spacing:.02em;
  padding:10px 22px;border-radius:6px;border:none;
  transition:background .15s;
}
.hero-cta:hover{background:var(--accent2)}
.hero-cta svg{width:14px;height:14px;fill:white}
.hero-scorecard{
  background:var(--paper2);border:1px solid var(--rule);border-radius:12px;
  padding:28px;
}
.sc-label{
  font-family:var(--ff-mono);font-size:9px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink4);margin-bottom:18px;
}
.sc-subject{display:flex;align-items:center;gap:12px;margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--rule)}
.sc-avatar{
  width:44px;height:44px;border-radius:50%;
  background:var(--ink);color:white;
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;flex-shrink:0;
}
.sc-name{font-size:14px;font-weight:600;color:var(--ink);line-height:1.3}
.sc-role{font-size:11px;color:var(--ink3);margin-top:2px}
.sc-rate{
  margin-left:auto;text-align:right;
}
.sc-rate-n{font-family:var(--ff-serif);font-size:32px;font-weight:600;color:var(--ink);line-height:1}
.sc-rate-l{font-family:var(--ff-mono);font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink4);margin-top:3px}
.sc-bar{height:8px;background:var(--rule);border-radius:4px;overflow:hidden;display:flex;gap:2px;margin-bottom:16px}
.sc-seg{height:100%;border-radius:2px;transition:width .4s ease}
.sc-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.sc-stat{text-align:center;padding:10px 8px;background:var(--paper);border:1px solid var(--rule);border-radius:8px}
.sc-stat-n{font-family:var(--ff-serif);font-size:20px;font-weight:600;display:block;line-height:1;margin-bottom:3px}
.sc-stat-l{font-family:var(--ff-mono);font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink4)}

/* ── SECTION STRIPS ── */
.section-strip{padding:44px 0;border-bottom:1px solid var(--rule)}
.section-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:24px}
.section-title{font-family:var(--ff-sans);font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink)}
.section-more{font-size:13px;color:var(--accent);border:none;background:none;font-weight:500}
.section-more:hover{text-decoration:underline}

/* ── PROMISE CARDS ── */
.cards-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.p-card{
  background:var(--paper);border:1px solid var(--rule);
  border-top:3px solid var(--rule2);
  border-radius:10px;padding:20px;
  display:flex;flex-direction:column;gap:11px;
  cursor:pointer;transition:border-color .15s,box-shadow .15s;
}
.p-card:hover{border-color:var(--rule2);box-shadow:0 4px 24px rgba(0,0,0,.07)}
.p-card.broken{border-top-color:var(--broken-bar)}
.p-card.kept{border-top-color:var(--kept-bar)}
.p-card.partial{border-top-color:var(--partial-bar)}
.p-card.too_early{border-top-color:var(--early-bar)}
.p-card.unverifiable{border-top-color:var(--unver-bar)}
.p-card.hidden{display:none}
.card-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.v-badge{
  font-family:var(--ff-mono);font-size:10px;font-weight:500;
  letter-spacing:.05em;text-transform:uppercase;
  padding:3px 10px;border-radius:20px;flex-shrink:0;
}
.vb-kept{background:var(--kept-bg);color:var(--kept)}
.vb-broken{background:var(--broken-bg);color:var(--broken)}
.vb-partial{background:var(--partial-bg);color:var(--partial)}
.vb-too_early{background:var(--early-bg);color:var(--early)}
.vb-unverifiable{background:var(--unver-bg);color:var(--unver)}
.card-cat{font-family:var(--ff-mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink4)}
.card-summary{font-size:14px;font-weight:600;color:var(--ink);line-height:1.4}
.card-quote{
  font-family:var(--ff-serif);font-size:12px;font-style:italic;color:var(--ink3);
  border-left:2px solid var(--rule2);padding-left:11px;line-height:1.6;border-radius:0;
}
.card-verdict-text{font-size:12px;color:var(--ink2);line-height:1.6}
.card-evidence{
  font-size:11px;color:var(--ink3);
  background:var(--paper2);border-left:2px solid var(--rule2);
  padding:7px 10px;border-radius:0 4px 4px 0;line-height:1.5;
}
.card-sources{display:flex;flex-wrap:wrap;gap:6px}
.source-link{
  font-family:var(--ff-mono);font-size:10px;letter-spacing:.03em;
  color:var(--accent);border:1px solid var(--accent);
  padding:2px 9px;border-radius:4px;
  transition:background .15s,color .15s;
}
.source-link:hover{background:var(--accent);color:white}
.card-foot{
  display:flex;justify-content:space-between;align-items:center;
  padding-top:10px;border-top:1px solid var(--rule);margin-top:auto;
}
.card-date{font-family:var(--ff-mono);font-size:10px;color:var(--ink4)}
.card-conf{font-family:var(--ff-mono);font-size:10px;color:var(--ink4)}

/* ── TOOLBAR ── */
.toolbar{
  position:sticky;top:var(--nav-h);z-index:100;
  background:var(--paper);border-bottom:1px solid var(--rule);
  padding:12px 32px;
}
.toolbar-inner{max-width:var(--max);margin:0 auto;display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.tb-group-label{font-family:var(--ff-mono);font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink4);margin-right:2px;flex-shrink:0}
.tb-sep{width:1px;height:18px;background:var(--rule2);margin:0 6px;flex-shrink:0}
.tb-chip{
  font-family:var(--ff-sans);font-size:12px;font-weight:500;
  padding:5px 14px;border-radius:20px;
  border:1px solid var(--rule2);background:transparent;color:var(--ink3);
  transition:all .15s;white-space:nowrap;
}
.tb-chip:hover{border-color:var(--ink3);color:var(--ink);background:var(--paper2)}
.tb-chip.active{background:var(--ink);color:white;border-color:var(--ink)}
.tb-chip.active-broken{background:var(--broken-bg);color:var(--broken);border-color:var(--broken-bar)}
.tb-chip.active-kept{background:var(--kept-bg);color:var(--kept);border-color:var(--kept-bar)}
.tb-chip.active-partial{background:var(--partial-bg);color:var(--partial);border-color:var(--partial-bar)}
.tb-chip.active-too_early{background:var(--early-bg);color:var(--early);border-color:var(--early-bar)}
.tb-count{margin-left:auto;font-family:var(--ff-mono);font-size:11px;color:var(--ink4)}

/* ── PROMISES PAGE ── */
.promises-content{max-width:var(--max);margin:0 auto;padding:28px 32px 60px}

/* ── METER PAGE ── */
.meter-wrap{max-width:860px;margin:0 auto;padding:48px 32px 72px}
.meter-head-row{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:6px}
.meter-page-title{font-family:var(--ff-serif);font-size:28px;font-weight:600;color:var(--ink)}
.meter-updated{font-family:var(--ff-mono);font-size:10px;color:var(--ink4)}
.meter-lede{font-size:14px;color:var(--ink3);line-height:1.75;margin-bottom:36px;max-width:560px}
.meter-subject-card{
  border:1px solid var(--rule);border-radius:12px;padding:24px 28px;
  margin-bottom:36px;display:flex;align-items:center;gap:20px;
}
.ms-avatar{
  width:56px;height:56px;border-radius:50%;background:var(--ink);
  color:white;display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:700;flex-shrink:0;
}
.ms-name{font-size:17px;font-weight:700;color:var(--ink)}
.ms-role{font-size:12px;color:var(--ink3);margin-top:3px}
.ms-meta{margin-left:auto;text-align:right}
.ms-rate-big{font-family:var(--ff-serif);font-size:44px;font-weight:600;line-height:1;color:var(--ink)}
.ms-rate-label{font-family:var(--ff-mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink4);margin-top:4px}
.meter-section-title{
  font-family:var(--ff-mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink4);margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--rule);
}
.meter-breakdown{margin-bottom:36px}
.breakdown-bar{height:10px;background:var(--rule);border-radius:5px;overflow:hidden;display:flex;gap:2px;margin-bottom:20px}
.bb-seg{height:100%;border-radius:3px}
.breakdown-legend{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.bl-item{padding:14px 12px;border:1px solid var(--rule);border-radius:8px;text-align:center}
.bl-swatch{width:10px;height:10px;border-radius:50%;margin:0 auto 8px}
.bl-num{font-family:var(--ff-serif);font-size:22px;font-weight:600;display:block;line-height:1;margin-bottom:4px}
.bl-pct{font-size:11px;color:var(--ink3);margin-bottom:2px}
.bl-label{font-family:var(--ff-mono);font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink4)}
.meter-by-issue{margin-bottom:36px}
.issue-score-row{
  display:flex;align-items:center;gap:16px;
  padding:13px 0;border-bottom:1px solid var(--rule);
}
.issue-score-row:last-child{border-bottom:none}
.is-label{font-size:13px;color:var(--ink2);width:140px;flex-shrink:0}
.is-bar-wrap{flex:1;height:6px;background:var(--paper3);border-radius:3px;overflow:hidden;position:relative}
.is-bar-vol{height:100%;background:var(--rule2);border-radius:3px}
.is-bar-kept{position:absolute;top:0;left:0;height:100%;border-radius:3px;transition:width .6s ease}
.is-count{font-family:var(--ff-mono);font-size:11px;color:var(--ink4);width:70px;text-align:right;flex-shrink:0}
.is-rate{font-family:var(--ff-mono);font-size:11px;font-weight:500;width:36px;text-align:right;flex-shrink:0}
.meter-methodology{background:var(--paper2);border:1px solid var(--rule);border-radius:10px;padding:24px 28px;margin-top:36px}
.method-title{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:14px}
.method-row{display:flex;gap:12px;margin-bottom:10px}
.method-badge{flex-shrink:0;margin-top:1px}
.method-text{font-size:13px;color:var(--ink2);line-height:1.6}

/* ── ISSUES PAGE ── */
.issues-wrap{max-width:var(--max);margin:0 auto;padding:48px 32px 72px}
.issues-intro{font-size:14px;color:var(--ink3);line-height:1.75;max-width:560px;margin-bottom:36px}
.issues-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.issue-card{
  border:1px solid var(--rule);border-radius:10px;padding:22px;
  cursor:pointer;transition:border-color .15s,box-shadow .15s;
}
.issue-card:hover{border-color:var(--rule2);box-shadow:0 4px 20px rgba(0,0,0,.06)}
.issue-card-icon{font-size:20px;margin-bottom:12px;display:block}
.issue-card-name{font-size:15px;font-weight:700;color:var(--ink);margin-bottom:4px}
.issue-card-sub{font-size:12px;color:var(--ink3);margin-bottom:14px}
.issue-vol-bar{height:4px;background:var(--rule);border-radius:2px;overflow:hidden;margin-bottom:6px}
.issue-vol-fill{height:100%;border-radius:2px;background:var(--rule2)}
.issue-kept-bar{height:4px;background:var(--rule);border-radius:2px;overflow:hidden;margin-bottom:10px;position:relative}
.issue-kept-fill{position:absolute;top:0;left:0;height:100%;border-radius:2px;background:var(--kept-bar)}
.issue-card-footer{display:flex;justify-content:space-between;align-items:center}
.issue-rate-label{font-family:var(--ff-mono);font-size:10px;color:var(--ink4)}
.issue-rate-val{font-family:var(--ff-serif);font-size:16px;font-weight:600;color:var(--ink)}

/* ── ABOUT PAGE ── */
.about-wrap{max-width:680px;margin:0 auto;padding:56px 32px 80px}
.about-h1{font-family:var(--ff-serif);font-size:30px;font-weight:600;color:var(--ink);margin-bottom:12px}
.about-lede{font-size:15px;color:var(--ink2);line-height:1.8;margin-bottom:40px;border-bottom:1px solid var(--rule);padding-bottom:32px}
.about-section{margin-bottom:36px}
.about-section-title{font-family:var(--ff-mono);font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink4);margin-bottom:16px}
.about-p{font-size:14px;color:var(--ink2);line-height:1.8;margin-bottom:14px}
.verdict-def-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px}
.vdef{border:1px solid var(--rule);border-radius:8px;padding:14px 16px}
.vdef-head{font-size:12px;font-weight:700;margin-bottom:5px}
.vdef-body{font-size:12px;color:var(--ink3);line-height:1.6}
.pipeline-item{display:flex;gap:14px;margin-bottom:16px;align-items:flex-start}
.pipeline-n{
  width:24px;height:24px;border-radius:50%;
  background:var(--paper3);border:1px solid var(--rule2);
  display:flex;align-items:center;justify-content:center;
  font-family:var(--ff-mono);font-size:11px;font-weight:500;color:var(--ink3);
  flex-shrink:0;margin-top:1px;
}
.pipeline-content{font-size:13px;color:var(--ink2);line-height:1.7}
.pipeline-content strong{color:var(--ink);font-weight:600}
.about-data-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--rule);font-size:13px}
.about-data-row:last-child{border-bottom:none}
.about-data-key{color:var(--ink3)}
.about-data-val{color:var(--ink);font-weight:500;font-family:var(--ff-mono);font-size:12px}

/* ── FOOTER ── */
.site-footer{
  background:var(--ink);color:#9ca3af;
  border-top:1px solid var(--rule);
}
.footer-upper{max-width:var(--max);margin:0 auto;padding:40px 32px 32px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:32px}
.footer-brand-name{font-size:15px;font-weight:700;color:white;margin-bottom:8px}
.footer-brand-desc{font-size:12px;line-height:1.7;color:#6b7280}
.footer-col-title{font-family:var(--ff-mono);font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:#6b7280;margin-bottom:12px}
.footer-link{display:block;font-size:13px;color:#9ca3af;margin-bottom:8px;background:none;border:none;text-align:left;padding:0;transition:color .15s}
.footer-link:hover{color:white}
.footer-lower{border-top:1px solid #1f2937;max-width:var(--max);margin:0 auto;padding:18px 32px;display:flex;justify-content:space-between;align-items:center}
.footer-copy{font-family:var(--ff-mono);font-size:10px;color:#4b5563;letter-spacing:.03em}
.footer-badges{display:flex;gap:10px}
.footer-badge{font-family:var(--ff-mono);font-size:9px;letter-spacing:.08em;padding:3px 9px;border-radius:4px;border:1px solid #374151;color:#6b7280}

/* ── RESPONSIVE ── */
@media(max-width:900px){
  .hero-inner{grid-template-columns:1fr;gap:32px}
  .hero-scorecard{display:none}
  .cards-grid,.issues-grid{grid-template-columns:1fr 1fr}
  .breakdown-legend{grid-template-columns:repeat(3,1fr)}
  .footer-upper{grid-template-columns:1fr 1fr}
  .verdict-def-grid{grid-template-columns:1fr}
}
@media(max-width:600px){
  .wrap,.toolbar-inner,.promises-content,.footer-upper,.footer-lower,.meter-wrap,.issues-wrap,.about-wrap{padding-left:16px;padding-right:16px}
  .cards-grid,.issues-grid{grid-template-columns:1fr}
  .sc-grid{grid-template-columns:1fr 1fr 1fr}
}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.p-card{animation:fadeUp .35s ease both}
.p-card:nth-child(1){animation-delay:.04s}.p-card:nth-child(2){animation-delay:.08s}
.p-card:nth-child(3){animation-delay:.12s}.p-card:nth-child(4){animation-delay:.16s}
.p-card:nth-child(5){animation-delay:.20s}.p-card:nth-child(6){animation-delay:.24s}
.p-card:nth-child(n+7){animation-delay:.28s}
"""

# ─────────────────────────────────────────────────────────────────
# COMPONENT BUILDERS
# ─────────────────────────────────────────────────────────────────

def nav_html(active_page):
    links = [
        ("home","Home"),("promises","Promises"),
        ("meter","Meter"),("issues","Issues"),("about","About"),
    ]
    items = "".join(
        f'<button class="nav-link{" active" if p==active_page else ""}" '
        f'onclick="goPage(\'{p}\')">{label}</button>'
        for p,label in links
    )
    return f"""
<nav class="site-nav">
  <div class="nav-inner">
    <div class="nav-brand" onclick="goPage('home')" style="cursor:pointer">
      <div class="nav-brand-mark">
        <svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="6"/></svg>
      </div>
      <span class="nav-brand-name">PromiseLog</span>
    </div>
    <div class="nav-links">{items}</div>
    <div class="nav-right">
      <div class="nav-tag"><span class="nav-live"></span>Philippines</div>
    </div>
  </div>
</nav>"""

def promise_card_html(p):
    v = p.get("verdict","unverifiable")
    m = VERDICT_META.get(v, VERDICT_META["unverifiable"])
    cat = CATEGORY_META.get(p.get("category","other"), CATEGORY_META["other"])
    urls = (p.get("evidence_urls") or [])[:3]
    src_links = "".join(
        f'<a href="{esc(u)}" target="_blank" rel="noopener" class="source-link">Source {i+1} ↗</a>'
        for i,u in enumerate(urls)
    ) if urls else ""
    src_block = f'<div class="card-sources">{src_links}</div>' if src_links else ""
    evidence_block = ""
    ke = p.get("key_evidence","")
    if ke and ke != "No direct evidence found.":
        evidence_block = f'<div class="card-evidence">{esc(ke[:180])}</div>'
    conf = p.get("confidence","")
    conf_label = {"high":"High confidence","medium":"Medium confidence","low":"Low confidence"}.get(conf,"")
    return f"""
<article class="p-card {v}" data-verdict="{v}" data-cat="{esc(p.get('category','other'))}">
  <div class="card-head">
    <span class="v-badge vb-{v}">{m['symbol']} {m['label']}</span>
    <span class="card-cat">{esc(cat['label'])}</span>
  </div>
  <div class="card-summary">{esc(p.get('summary',''))}</div>
  <blockquote class="card-quote">"{esc((p.get('exact_quote') or '')[:200])}"</blockquote>
  <div class="card-verdict-text">{esc(p.get('verdict_summary',''))}</div>
  {evidence_block}
  {src_block}
  <div class="card-foot">
    <span class="card-date">{fmt_date(p.get('speech_date'))}</span>
    <span class="card-conf">{esc(conf_label)}</span>
  </div>
</article>"""

# ─────────────────────────────────────────────────────────────────
# PAGE BUILDERS
# ─────────────────────────────────────────────────────────────────

def page_home(promises, stats):
    recent = promises[:6]
    cards = "".join(promise_card_html(p) for p in recent)
    vb = stats["vb"]
    rate = stats["rate"]
    total = stats["total"]
    kept=vb.get("kept",0); broken=vb.get("broken",0)
    partial=vb.get("partial",0); early=vb.get("too_early",0); unver=vb.get("unverifiable",0)
    seg_pct = lambda n: round(n/total*100) if total else 0
    by_cat = stats["by_cat"]
    top_cats = sorted(by_cat.items(), key=lambda x: x[1]["total"], reverse=True)[:5]
    cat_pills = "".join(
        f'<button class="tb-chip" style="margin-right:4px" '
        f'onclick="goPageWithCat(\'promises\',\'{c}\')">'
        f'{CATEGORY_META.get(c,{"label":c})["label"]} '
        f'<span style="opacity:.55">({d["total"]})</span></button>'
        for c,d in top_cats
    )
    return f"""
<div class="page active" id="page-home">
  <div class="hero">
    <div class="wrap">
      <div class="hero-inner">
        <div>
          <div class="hero-eyebrow">Political accountability · Philippines</div>
          <h1 class="hero-h1">Every promise made.<br><em>Every verdict sourced.</em></h1>
          <p class="hero-lede">An automated pipeline monitors official speeches by President Marcos Jr., extracts specific commitments, searches for evidence weekly, and publishes source-backed verdicts — with no editorial slant.</p>
          <button class="hero-cta" onclick="goPage('promises')">
            Browse all promises
            <svg viewBox="0 0 14 14"><path d="M2 7h10M8 3l4 4-4 4"/></svg>
          </button>
        </div>
        <div class="hero-scorecard">
          <div class="sc-label">Promise scorecard</div>
          <div class="sc-subject">
            <div class="sc-avatar">BBM</div>
            <div>
              <div class="sc-name">Ferdinand Marcos Jr.</div>
              <div class="sc-role">President · Philippines · Jul 2022–present</div>
            </div>
            <div class="sc-rate">
              <div class="sc-rate-n">{rate}%</div>
              <div class="sc-rate-l">Keep rate</div>
            </div>
          </div>
          <div class="sc-bar">
            <div class="sc-seg" style="width:{seg_pct(kept)}%;background:var(--kept-bar)"></div>
            <div class="sc-seg" style="width:{seg_pct(partial)}%;background:var(--partial-bar)"></div>
            <div class="sc-seg" style="width:{seg_pct(broken)}%;background:var(--broken-bar)"></div>
            <div class="sc-seg" style="width:{seg_pct(early)}%;background:var(--early-bar)"></div>
            <div class="sc-seg" style="width:{seg_pct(unver)}%;background:var(--unver-bar)"></div>
          </div>
          <div class="sc-grid">
            <div class="sc-stat"><span class="sc-stat-n" style="color:var(--kept)">{kept}</span><span class="sc-stat-l">Kept</span></div>
            <div class="sc-stat"><span class="sc-stat-n" style="color:var(--broken)">{broken}</span><span class="sc-stat-l">Broken</span></div>
            <div class="sc-stat"><span class="sc-stat-n" style="color:var(--partial)">{partial}</span><span class="sc-stat-l">Partial</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="section-strip">
    <div class="wrap">
      <div class="section-head">
        <span class="section-title">Latest verdicts</span>
        <button class="section-more" onclick="goPage('promises')">View all {total} promises →</button>
      </div>
      <div class="cards-grid">{cards}</div>
    </div>
  </div>

  <div class="section-strip" style="border-bottom:none">
    <div class="wrap">
      <div class="section-head">
        <span class="section-title">Browse by issue</span>
        <button class="section-more" onclick="goPage('issues')">All issues →</button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px">{cat_pills}</div>
    </div>
  </div>
</div>"""

def page_promises(promises, stats):
    cats = sorted({p.get("category","other") for p in promises})
    cat_chips = "".join(
        f'<button class="tb-chip" id="chip-c-{c}" onclick="filterCat(\'{c}\',this)">'
        f'{CATEGORY_META.get(c,{"label":c})["label"]}</button>'
        for c in cats
    )
    cards = "".join(promise_card_html(p) for p in promises)
    return f"""
<div class="page" id="page-promises">
  <div class="toolbar">
    <div class="toolbar-inner">
      <span class="tb-group-label">Verdict</span>
      <button class="tb-chip active" id="chip-v-all" onclick="filterV('all',this)">All</button>
      <button class="tb-chip" id="chip-v-broken" onclick="filterV('broken',this)">Broken</button>
      <button class="tb-chip" id="chip-v-kept" onclick="filterV('kept',this)">Kept</button>
      <button class="tb-chip" id="chip-v-partial" onclick="filterV('partial',this)">Partial</button>
      <button class="tb-chip" id="chip-v-too_early" onclick="filterV('too_early',this)">Too early</button>
      <button class="tb-chip" id="chip-v-unverifiable" onclick="filterV('unverifiable',this)">Unverifiable</button>
      <div class="tb-sep"></div>
      <span class="tb-group-label">Issue</span>
      {cat_chips}
      <span class="tb-count" id="promise-count">{len(promises)} promises</span>
    </div>
  </div>
  <div class="promises-content">
    <div class="cards-grid" id="promise-grid">{cards}</div>
  </div>
</div>"""

def page_meter(promises, stats):
    vb = stats["vb"]
    rate = stats["rate"]
    total = stats["total"]
    kept=vb.get("kept",0); broken=vb.get("broken",0)
    partial=vb.get("partial",0); early=vb.get("too_early",0); unver=vb.get("unverifiable",0)
    scoreable = stats["scoreable"]
    now = datetime.utcnow().strftime("%b %d, %Y")
    seg_w = lambda n: round(n/total*100) if total else 0

    def bl(n, label, color, bar_color, pct_of=None):
        pct = f"{round(n/pct_of*100)}% of total" if pct_of else ""
        return f"""<div class="bl-item">
          <div class="bl-swatch" style="background:{bar_color}"></div>
          <span class="bl-num" style="color:{color}">{n}</span>
          <div class="bl-pct">{pct}</div>
          <div class="bl-label">{label}</div>
        </div>"""

    legend = (
        bl(kept,"Kept","var(--kept)","var(--kept-bar)",total) +
        bl(broken,"Broken","var(--broken)","var(--broken-bar)",total) +
        bl(partial,"Partial","var(--partial)","var(--partial-bar)",total) +
        bl(early,"Too early","var(--early)","var(--early-bar)",total) +
        bl(unver,"Unverifiable","var(--unver)","var(--unver-bar)",total)
    )

    by_cat = stats["by_cat"]
    max_vol = max((d["total"] for d in by_cat.values()), default=1)
    issue_rows = ""
    for c, d in sorted(by_cat.items(), key=lambda x: x[1]["total"], reverse=True):
        label = CATEGORY_META.get(c, {"label": c})["label"]
        vol_pct = round(d["total"] / max_vol * 100)
        kept_pct = d.get("keep_rate")
        kept_w = kept_pct if kept_pct is not None else 0
        if kept_pct is not None:
            rate_color = "var(--kept)" if kept_pct >= 60 else "var(--partial)" if kept_pct >= 35 else "var(--broken)"
            rate_str = f'<span style="color:{rate_color}">{kept_pct}%</span>'
        else:
            rate_str = '<span style="color:var(--ink4)">—</span>'
        issue_rows += f"""<div class="issue-score-row">
          <span class="is-label">{esc(label)}</span>
          <div class="is-bar-wrap">
            <div class="is-bar-vol" style="width:{vol_pct}%"></div>
            <div class="is-bar-kept" style="width:{kept_w}%;background:var(--kept-bar)"></div>
          </div>
          <span class="is-count">{d['total']} promises</span>
          <span class="is-rate">{rate_str}</span>
        </div>"""

    return f"""
<div class="page" id="page-meter">
  <div class="meter-wrap">
    <div class="meter-head-row">
      <h2 class="meter-page-title">The PromiseLog Meter</h2>
      <span class="meter-updated">Updated {now}</span>
    </div>
    <p class="meter-lede">A running accountability score for every tracked commitment. Keep rate is calculated only from scoreable promises — kept, broken, and partial. Promises marked too early or unverifiable are excluded until evidence exists.</p>

    <div class="meter-subject-card">
      <div class="ms-avatar">BBM</div>
      <div>
        <div class="ms-name">Ferdinand Marcos Jr.</div>
        <div class="ms-role">17th President of the Republic of the Philippines · July 2022 – present</div>
      </div>
      <div class="ms-meta">
        <div class="ms-rate-big">{rate}%</div>
        <div class="ms-rate-label">Keep rate · {scoreable} scored</div>
      </div>
    </div>

    <div class="meter-breakdown">
      <div class="meter-section-title">Breakdown — all {total} promises tracked</div>
      <div class="breakdown-bar">
        <div class="bb-seg" style="width:{seg_w(kept)}%;background:var(--kept-bar)"></div>
        <div class="bb-seg" style="width:{seg_w(partial)}%;background:var(--partial-bar)"></div>
        <div class="bb-seg" style="width:{seg_w(broken)}%;background:var(--broken-bar)"></div>
        <div class="bb-seg" style="width:{seg_w(early)}%;background:var(--early-bar)"></div>
        <div class="bb-seg" style="width:{seg_w(unver)}%;background:var(--unver-bar)"></div>
      </div>
      <div class="breakdown-legend">{legend}</div>
    </div>

    <div class="meter-by-issue">
      <div class="meter-section-title">Score by issue — bar shows volume, percentage shows keep rate</div>
      {issue_rows}
    </div>

    <div class="meter-methodology">
      <div class="method-title">How the score is calculated</div>
      {"".join(f'<div class="method-row"><span class="method-badge"><span class="v-badge vb-{v}" style="font-size:9px">{m["symbol"]} {m["label"]}</span></span><span class="method-text">{d}</span></div>' for v,m,d in [
        ("kept", VERDICT_META["kept"], "Counts as 1 in the numerator and denominator."),
        ("broken", VERDICT_META["broken"], "Counts as 0 in the numerator and 1 in the denominator."),
        ("partial", VERDICT_META["partial"], "Counts as 0.5 in the numerator — partial credit."),
        ("too_early", VERDICT_META["too_early"], "Excluded until the deadline passes or evidence emerges."),
        ("unverifiable", VERDICT_META["unverifiable"], "Excluded — no reliable evidence either way."),
      ])}
    </div>
  </div>
</div>"""

def page_issues(promises, stats):
    by_cat = stats["by_cat"]
    max_vol = max((d["total"] for d in by_cat.values()), default=1)
    cards = ""
    for c, d in sorted(by_cat.items(), key=lambda x: x[1]["total"], reverse=True):
        meta = CATEGORY_META.get(c, {"label": c, "icon": "•"})
        vol_pct = round(d["total"] / max_vol * 100)
        kept_pct = d.get("keep_rate")
        kept_w = kept_pct if kept_pct is not None else 0
        rate_display = f"{kept_pct}% kept" if kept_pct is not None else "—"
        rate_color = "var(--kept)" if (kept_pct or 0) >= 60 else "var(--partial)" if (kept_pct or 0) >= 35 else "var(--broken)"
        cards += f"""<div class="issue-card" onclick="goPageWithCat('promises','{c}')">
          <span class="issue-card-icon">{meta['icon']}</span>
          <div class="issue-card-name">{esc(meta['label'])}</div>
          <div class="issue-card-sub">{d['total']} promises tracked</div>
          <div class="issue-vol-bar"><div class="issue-vol-fill" style="width:{vol_pct}%"></div></div>
          <div class="issue-kept-bar"><div class="issue-kept-fill" style="width:{kept_w}%"></div></div>
          <div class="issue-card-footer">
            <span class="issue-rate-label">Keep rate</span>
            <span class="issue-rate-val" style="color:{rate_color}">{rate_display}</span>
          </div>
        </div>"""
    return f"""
<div class="page" id="page-issues">
  <div class="issues-wrap">
    <h2 style="font-family:var(--ff-serif);font-size:28px;font-weight:600;color:var(--ink);margin-bottom:10px">Issues</h2>
    <p class="issues-intro">Browse promises grouped by policy area. Each card shows the total volume of promises tracked in that sector and the current keep rate — how often commitments in that area have been fulfilled.</p>
    <div class="issues-grid">{cards}</div>
  </div>
</div>"""

def page_about(stats):
    now = datetime.utcnow().strftime("%B %d, %Y")
    return f"""
<div class="page" id="page-about">
  <div class="about-wrap">
    <h1 class="about-h1">About PromiseLog</h1>
    <p class="about-lede">PromiseLog is an open-source civic accountability project that automatically tracks political promises made by heads of government. Starting with the Philippines, it is designed to expand to any country or leader. All code, data, and methodology are public.</p>

    <div class="about-section">
      <div class="about-section-title">The problem</div>
      <p class="about-p">Leaders make specific, testable commitments in speeches. Those commitments rarely get tracked systematically. Manual fact-checking organisations like PolitiFact cover a narrow set of countries and rely on human labor that doesn't scale. PromiseLog automates the entire chain — from speech to verdict — and costs under $30/month to run.</p>
    </div>

    <div class="about-section">
      <div class="about-section-title">Verdict definitions</div>
      <div class="verdict-def-grid">
        {"".join(f'<div class="vdef"><div class="vdef-head" style="color:{m["color"]}"><span class="v-badge vb-{v}" style="font-size:10px">{m["symbol"]} {m["label"]}</span></div><div class="vdef-body">{d}</div></div>' for v,m,d in [
          ("kept", VERDICT_META["kept"], "Direct evidence the specific commitment was fulfilled. Requires a source URL."),
          ("broken", VERDICT_META["broken"], "Deadline passed with no action, or the opposite action was taken."),
          ("partial", VERDICT_META["partial"], "Something was done, but falls materially short of the full commitment."),
          ("too_early", VERDICT_META["too_early"], "Deadline has not yet passed, or fewer than 12 months since promise with no deadline."),
          ("unverifiable", VERDICT_META["unverifiable"], "Insufficient public evidence to assess either way. When in doubt, this is the verdict."),
        ])}
      </div>
    </div>

    <div class="about-section">
      <div class="about-section-title">The pipeline</div>
      {"".join(f'<div class="pipeline-item"><div class="pipeline-n">{n}</div><div class="pipeline-content">{t}</div></div>' for n,t in [
        (1,"<strong>Fetcher</strong> — visits the Presidential Communications Office website weekly and saves all speeches as structured JSON. No speech is fetched twice."),
        (2,"<strong>Extractor</strong> — Claude reads each speech and identifies only specific, testable, time-bound promises. Vague aspirations and value statements are excluded."),
        (3,"<strong>Evidence finder</strong> — searches GDELT (global news index) and World Bank indicators for outcomes related to each promise, without any API key."),
        (4,"<strong>Verdict writer</strong> — Claude reads the promise alongside the evidence and assigns a verdict. Every verdict except <em>unverifiable</em> requires a source URL. When uncertain, Claude chooses <em>unverifiable</em>."),
        (5,"<strong>Publisher</strong> — generates this website from all promise JSON files and deploys to GitHub Pages automatically every Sunday night."),
      ])}
    </div>

    <div class="about-section">
      <div class="about-section-title">Data sources &amp; stack</div>
      {"".join(f'<div class="about-data-row"><span class="about-data-key">{k}</span><span class="about-data-val">{v}</span></div>' for k,v in [
        ("Speech source","Presidential Communications Office (pco.gov.ph)"),
        ("News evidence","GDELT Project (free, open)"),
        ("Economic data","World Bank Open Data API"),
        ("AI model","Claude (Anthropic) — extraction &amp; verdicts"),
        ("Hosting","GitHub Pages (free)"),
        ("Language","Python 3"),
        ("Update frequency","Weekly — every Sunday"),
        ("Last updated",now),
        ("License","MIT — all code and data are public"),
      ])}
    </div>

    <div class="about-section">
      <div class="about-section-title">What this project does not do</div>
      <p class="about-p">PromiseLog does not editorialize. It does not rank promises by importance or select which ones to highlight. It does not accept funding from political parties, campaigns, or advocacy groups. The AI pipeline extracts promises strictly on the basis of specificity and testability — not political salience.</p>
      <p class="about-p">A wrong verdict is worse than no verdict. When evidence is thin, ambiguous, or contradictory, the verdict is <em>unverifiable</em> — not a guess.</p>
    </div>
  </div>
</div>"""

def footer_html():
    return """
<footer class="site-footer">
  <div class="footer-upper">
    <div>
      <div class="footer-brand-name">PromiseLog</div>
      <p class="footer-brand-desc">Automated political accountability tracking. Evidence-only verdicts. No editorial agenda.</p>
    </div>
    <div>
      <div class="footer-col-title">Navigate</div>
      <button class="footer-link" onclick="goPage('home')">Home</button>
      <button class="footer-link" onclick="goPage('promises')">Promises</button>
      <button class="footer-link" onclick="goPage('meter')">Meter</button>
      <button class="footer-link" onclick="goPage('issues')">Issues</button>
      <button class="footer-link" onclick="goPage('about')">About</button>
    </div>
    <div>
      <div class="footer-col-title">Data</div>
      <button class="footer-link">Download JSON</button>
      <button class="footer-link">GitHub repository</button>
      <button class="footer-link">Methodology</button>
      <button class="footer-link" onclick="goPage('about')">Our process</button>
    </div>
    <div>
      <div class="footer-col-title">Coverage</div>
      <button class="footer-link">Philippines · Active</button>
      <button class="footer-link" style="opacity:.4;cursor:default">Indonesia · Coming</button>
      <button class="footer-link" style="opacity:.4;cursor:default">Vietnam · Coming</button>
      <button class="footer-link" style="opacity:.4;cursor:default">Thailand · Coming</button>
    </div>
  </div>
  <div style="border-top:1px solid #1f2937;max-width:1160px;margin:0 auto;padding:18px 32px;display:flex;justify-content:space-between;align-items:center">
    <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#4b5563;letter-spacing:.03em">
      © 2026 PromiseLog · MIT License · Data: PCO, GDELT, World Bank · AI: Anthropic Claude
    </span>
    <div style="display:flex;gap:10px">
      <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.08em;padding:3px 9px;border-radius:4px;border:1px solid #374151;color:#6b7280">Open source</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.08em;padding:3px 9px;border-radius:4px;border:1px solid #374151;color:#6b7280">No ads</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.08em;padding:3px 9px;border-radius:4px;border:1px solid #374151;color:#6b7280">Non-partisan</span>
    </div>
  </div>
</footer>"""

# ─────────────────────────────────────────────────────────────────
# JS
# ─────────────────────────────────────────────────────────────────
JS = """
var _activeV = 'all', _activeC = 'all';

function goPage(id) {
  ['home','promises','meter','issues','about'].forEach(function(p) {
    var el = document.getElementById('page-' + p);
    if (el) el.classList.toggle('active', p === id);
    var nl = document.getElementById('nl-' + p);
    if (nl) nl.classList.toggle('active', p === id);
  });
  window.scrollTo(0, 0);
}

function goPageWithCat(page, cat) {
  goPage(page);
  if (page === 'promises') {
    _activeC = cat;
    _activeV = 'all';
    document.querySelectorAll('[id^="chip-v-"]').forEach(function(b){ b.className = 'tb-chip'; });
    var all = document.getElementById('chip-v-all');
    if (all) all.className = 'tb-chip active';
    document.querySelectorAll('[id^="chip-c-"]').forEach(function(b){ b.className = 'tb-chip'; });
    var cc = document.getElementById('chip-c-' + cat);
    if (cc) cc.className = 'tb-chip active';
    applyFilters();
  }
}

function filterV(v, btn) {
  _activeV = v;
  document.querySelectorAll('[id^="chip-v-"]').forEach(function(b){ b.className = 'tb-chip'; });
  btn.className = 'tb-chip active' + (v !== 'all' ? ' active-' + v : '');
  applyFilters();
}

function filterCat(c, btn) {
  if (_activeC === c) {
    _activeC = 'all';
    btn.className = 'tb-chip';
  } else {
    document.querySelectorAll('[id^="chip-c-"]').forEach(function(b){ b.className = 'tb-chip'; });
    _activeC = c;
    btn.className = 'tb-chip active';
  }
  applyFilters();
}

function applyFilters() {
  var cards = document.querySelectorAll('#promise-grid .p-card');
  var vis = 0;
  cards.forEach(function(card) {
    var vOk = _activeV === 'all' || card.dataset.verdict === _activeV;
    var cOk = _activeC === 'all' || card.dataset.cat === _activeC;
    var show = vOk && cOk;
    card.classList.toggle('hidden', !show);
    if (show) vis++;
  });
  var el = document.getElementById('promise-count');
  if (el) el.textContent = vis + ' promise' + (vis !== 1 ? 's' : '');
}
"""

# ─────────────────────────────────────────────────────────────────
# ASSEMBLE
# ─────────────────────────────────────────────────────────────────

def build_site(promises, report):
    stats = compute_stats(promises, report)
    now = datetime.utcnow().strftime("%B %d, %Y")
    nav_ids = """
      <button class="nav-link active" id="nl-home" onclick="goPage('home')">Home</button>
      <button class="nav-link" id="nl-promises" onclick="goPage('promises')">Promises</button>
      <button class="nav-link" id="nl-meter" onclick="goPage('meter')">Meter</button>
      <button class="nav-link" id="nl-issues" onclick="goPage('issues')">Issues</button>
      <button class="nav-link" id="nl-about" onclick="goPage('about')">About</button>
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="description" content="Automated promise tracker for Philippines President Ferdinand Marcos Jr. Every commitment tracked, every verdict sourced.">
<meta property="og:title" content="PromiseLog — Philippines">
<meta property="og:description" content="Every promise Marcos Jr. made. Tracked, sourced, verdicted.">
<title>PromiseLog — Philippines</title>
<style>{CSS}</style>
</head>
<body>
<div class="top-rule"></div>
<nav class="site-nav">
  <div class="nav-inner">
    <div class="nav-brand" onclick="goPage('home')" style="cursor:pointer">
      <div class="nav-brand-mark">
        <svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="6"/></svg>
      </div>
      <span class="nav-brand-name">PromiseLog</span>
    </div>
    <div class="nav-links">{nav_ids}</div>
    <div class="nav-right">
      <div class="nav-tag"><span class="nav-live"></span>Philippines · Live</div>
      <span class="nav-updated">Updated {now}</span>
    </div>
  </div>
</nav>

{page_home(promises, stats)}
{page_promises(promises, stats)}
{page_meter(promises, stats)}
{page_issues(promises, stats)}
{page_about(stats)}
{footer_html()}

<script>{JS}</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("PromiseLog Publisher — Production Build")
    log.info("=" * 60)
    promises = load_promises()
    report   = load_report()
    log.info(f"Promises with verdicts: {len(promises)}")
    if not promises:
        log.warning("No verdicted promises found — building empty site.")
    html = build_site(promises, report)
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    kb = OUTPUT_FILE.stat().st_size // 1024
    log.info(f"Site written: {OUTPUT_FILE} ({kb} KB)")
    log.info(f"Preview: open {OUTPUT_FILE}")
    if AUTO_PUSH:
        for cmd in [["git","add","site/"],["git","commit","-m",f"publish {datetime.utcnow():%Y-%m-%d}"],["git","push"]]:
            r = subprocess.run(cmd, capture_output=True, text=True)
            log.info(("✓" if r.returncode==0 else "✗") + " " + " ".join(cmd))
    else:
        log.info("\nDeploy to GitHub Pages:")
        log.info("  git add site/ && git commit -m 'publish' && git push")
    log.info("=" * 60)

if __name__ == "__main__":
    main()