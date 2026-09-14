import json
import os
import time
from datetime import date, datetime
import streamlit as st
from groq import Groq
from streamlit.errors import StreamlitSecretNotFoundError
from concurrent.futures import ThreadPoolExecutor
from analysis_utils import (
    action_plan_validation_issues,
    assess_mineralogical_readiness,
    calculate_economic_snapshot,
    calculate_sensitivity,
    extract_json_object,
    is_price_reference_stale,
    parse_custom_metal_prices,
    parse_gross_value_from_grades,
    render_action_plan_html,
    render_key_value_sections,
    render_model_output_html,
    should_block_analysis,
)

RUN_COOLDOWN_SECONDS = 8
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def get_app_setting(name: str, default=None):
    """Read configuration without requiring a local Streamlit secrets file."""
    environment_value = os.getenv(name)
    if environment_value:
        return environment_value
    try:
        return st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        return default

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TailingsValue Pro",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0e0e0e;
    color: #e8e0d0;
}

.stApp {
    background-color: #0e0e0e;
}

h1, h2, h3 {
    font-family: 'IBM Plex Mono', monospace;
    color: #c8a96e;
    letter-spacing: -0.5px;
}

.hero {
    border-left: 3px solid #c8a96e;
    padding: 1.2rem 1.5rem;
    margin-bottom: 2rem;
    background: linear-gradient(90deg, rgba(200,169,110,0.07) 0%, transparent 100%);
}

.hero h1 {
    font-size: 2.2rem;
    margin: 0 0 0.3rem 0;
}

.hero p {
    color: #9a9080;
    font-size: 0.95rem;
    margin: 0;
    font-family: 'IBM Plex Mono', monospace;
}

.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #c8a96e;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid #2a2520;
    padding-bottom: 0.4rem;
}

.score-box {
    background: #1a1510;
    border: 1px solid #c8a96e;
    border-radius: 4px;
    padding: 1.5rem;
    text-align: center;
    margin-bottom: 1rem;
}

.score-number {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 4rem;
    font-weight: 600;
    color: #c8a96e;
    line-height: 1;
}

.score-label {
    font-size: 0.8rem;
    color: #9a9080;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 0.5rem;
}

.output-card {
    background: #141210;
    border: 1px solid #2a2520;
    border-radius: 4px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}

.output-card h4 {
    font-family: 'IBM Plex Mono', monospace;
    color: #c8a96e;
    font-size: 0.8rem;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin: 0 0 0.8rem 0;
}

.sensitivity-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
}

.sensitivity-table th {
    background: #1a1510;
    color: #c8a96e;
    padding: 0.6rem 0.8rem;
    text-align: left;
    border: 1px solid #2a2520;
    font-weight: 600;
}

.sensitivity-table td {
    padding: 0.5rem 0.8rem;
    border: 1px solid #1e1c18;
    color: #c8d0b0;
}

.sensitivity-table tr:nth-child(even) td {
    background: #111008;
}

.sensitivity-table .base-row td {
    background: #1a1f10;
    color: #a8d080;
    font-weight: 600;
}

.stButton > button {
    background: #c8a96e;
    color: #0e0e0e;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    letter-spacing: 1px;
    border: none;
    padding: 0.7rem 2rem;
    font-size: 0.85rem;
    width: 100%;
    border-radius: 3px;
    transition: all 0.2s;
}

.stButton > button:hover {
    background: #e0bf80;
    color: #0e0e0e;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    background: #141210 !important;
    border: 1px solid #2a2520 !important;
    color: #e8e0d0 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    border-radius: 3px !important;
}

.stSelectbox > div > div > div {
    color: #e8e0d0 !important;
}

label {
    color: #9a9080 !important;
    font-size: 0.82rem !important;
    font-family: 'IBM Plex Mono', monospace !important;
    letter-spacing: 0.5px;
}

.warning-box {
    background: #1a1008;
    border: 1px solid #8b5e2a;
    border-radius: 3px;
    padding: 0.8rem 1rem;
    color: #c8904e;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    margin-bottom: 1rem;
}

.stSpinner > div {
    border-color: #c8a96e !important;
}

div[data-testid="stExpander"] {
    background: #141210;
    border: 1px solid #2a2520;
    border-radius: 4px;
}

footer {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #4a4540;
    text-align: center;
    padding: 2rem 0 1rem;
    letter-spacing: 1px;
}

.output-copy {
    color: #e8e0d0;
    line-height: 1.7;
    font-size: 0.98rem;
}

.output-copy h2,
.output-copy h3,
.output-copy h4,
.output-copy h5 {
    font-family: 'IBM Plex Mono', monospace;
    color: #e8e0d0;
    font-size: 1rem;
    letter-spacing: 0.5px;
    margin: 0.2rem 0 0.8rem 0;
}

.output-copy p {
    margin: 0 0 0.9rem 0;
}

.output-copy ul,
.output-copy ol {
    margin: 0 0 1rem 1.2rem;
    padding-left: 1rem;
}

.output-copy li {
    margin-bottom: 0.55rem;
}

.output-copy code {
    font-family: 'IBM Plex Mono', monospace;
    color: #c8d0b0;
}

.structured-block {
    margin-bottom: 1rem;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid #2a2520;
}

.structured-block:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
}

.structured-label {
    font-family: 'IBM Plex Mono', monospace;
    color: #c8a96e;
    font-size: 0.78rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 0.45rem;
}
</style>
""", unsafe_allow_html=True)

# ── Metal price reference table ─────────────────────────────────────────────────
METAL_PRICES = {
    "Cu":  {"price": 14326,   "unit": "USD/t",   "name": "Copper"},
    "Au":  {"price": 141.82,  "unit": "USD/g",   "name": "Gold"},
    "Ag":  {"price": 2.10,    "unit": "USD/g",   "name": "Silver"},
    "Mo":  {"price": 51000,   "unit": "USD/t",   "name": "Molybdenum"},
    "Zn":  {"price": 3875,    "unit": "USD/t",   "name": "Zinc"},
    "Pb":  {"price": 1855,    "unit": "USD/t",   "name": "Lead"},
    "Ni":  {"price": 16751,   "unit": "USD/t",   "name": "Nickel"},
    "Co":  {"price": 33069,   "unit": "USD/t",   "name": "Cobalt"},
    "Li":  {
        "price": 47900,
        "unit": "USD/t",
        "name": "Lithium",
        "basis": "elemental Li-equivalent proxy derived from battery-grade lithium carbonate",
    },
    "REE": {
        "price": 2500,
        "unit": "USD/t",
        "name": "Rare Earth Elements",
        "basis": "conservative undifferentiated basket-equivalent screening proxy",
    },
}

PRICE_REF_DATE = "2026-09-14"
PRICE_OBSERVATION_LABEL = (
    "August 2026 monthly averages for Cu, Pb, Ni, Zn, Au and Ag; "
    "2025 USGS estimates for Mo, Co and Li; conservative REE proxy"
)
PRICE_SOURCE_LABEL = "World Bank Pink Sheet and USGS Mineral Commodity Summaries 2026"

# ── Screening-evidence rubric ───────────────────────────────────────────────────
SCORE_RUBRIC = {
    "grade": {
        "label": "Grade Evidence",
        "weight": 0.30,
        "criteria": (
            "1 = no usable quantitative grade data\n"
            "2 = numerical grades with no sampling or QA/QC support stated\n"
            "3 = grades supported by representative sampling information\n"
            "4 = QA/QC-supported grades with spatial variability characterised\n"
            "5 = independently verified grade model suitable for advanced study"
        ),
    },
    "tonnage": {
        "label": "Inventory Evidence",
        "weight": 0.20,
        "criteria": (
            "1 = no usable tonnage estimate\n"
            "2 = numerical inventory stated with no estimation method or density support\n"
            "3 = surveyed volume or sampling basis described\n"
            "4 = representative drilling and density model reported\n"
            "5 = independently verified inventory estimate suitable for advanced study"
        ),
    },
    "mineralogy": {
        "label": "Mineralogical Evidence",
        "weight": 0.20,
        "criteria": (
            "Deterministically calculated from analytical methods, quantitative modal mineralogy, "
            "metal deportment, liberation evidence, and spatial representativeness."
        ),
    },
    "infrastructure": {
        "label": "Infrastructure Evidence",
        "weight": 0.20,
        "criteria": (
            "1 = no infrastructure information\n"
            "2 = assets listed without capacity, condition, availability, or compatibility evidence\n"
            "3 = some asset capacity or condition information supplied\n"
            "4 = engineering review indicates adequate capacity and compatibility\n"
            "5 = verified infrastructure demonstrated suitable for the candidate process"
        ),
    },
    "oxidation": {
        "label": "Material Condition Evidence",
        "weight": 0.10,
        "criteria": (
            "1 = material condition or oxidation state unknown\n"
            "2 = broad age or oxidation category stated without analytical verification\n"
            "3 = analytical confirmation supplied for selected samples\n"
            "4 = representative spatial variability in material condition characterised\n"
            "5 = material-condition evidence linked to validated recovery performance"
        ),
    },
}

# ── Groq API calls ────────────────────────────────────────────────────────────
def call_groq(
    client: Groq,
    system: str,
    user: str,
    max_tokens: int = 1500,
    response_format: dict | None = None,
) -> str:
    try:
        request = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "reasoning_effort": "low",
        }
        if response_format:
            request["response_format"] = response_format
        response = client.chat.completions.create(**request)
        return response.choices[0].message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"Groq API error: {exc}") from exc


def get_feasibility_score(client, inputs: dict, mineral_readiness: dict) -> tuple:
    criteria_block = "\n\n".join(
        f'{key.upper()} ({info["label"]}, weight {int(info["weight"] * 100)}%):\n{info["criteria"]}'
        for key, info in SCORE_RUBRIC.items()
        if key != "mineralogy"
    )
    system = """You are scoring the readiness of evidence supplied for preliminary tailings screening.
This is not a feasibility, profitability, or recovery score. Score each requested factor only from the exact evidence criteria."""
    user = f"""Score these tailings. Return grade, tonnage, infrastructure, and oxidation as integers from 1 to 5.

TAILINGS:
- Source: {inputs['source']}
- Grades: {inputs['grades']}
- Tonnage: {inputs['tonnage']:,} tonnes
- Mineralogy: {inputs['mineralogy']}
- Mineralogical characterization: {inputs['mineral_characterization']}
- Oxidation state: {inputs['oxidation']}
- Location: {inputs['location']}
- Infrastructure: {inputs['infrastructure']}

SCORING CRITERIA:
{criteria_block}

Mineralogy is scored separately by deterministic evidence checks and must not be returned."""
    score_keys = ["grade", "tonnage", "infrastructure", "oxidation"]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "screening_evidence_scores",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    key: {"type": "integer"}
                    for key in score_keys
                },
                "required": score_keys,
                "additionalProperties": False,
            },
        },
    }
    result = call_groq(client, system, user, response_format=response_format)
    try:
        sub_scores = extract_json_object(result)
        for key in score_keys:
            sub_scores[key] = max(1, min(5, int(sub_scores[key])))
        sub_scores["mineralogy"] = mineral_readiness["sub_score"]
        weighted = sum(sub_scores[k] * SCORE_RUBRIC[k]["weight"] for k in SCORE_RUBRIC)
        score = round(weighted * 20)
        return score, sub_scores, False
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        fallback = {k: 2 for k in SCORE_RUBRIC}
        fallback["mineralogy"] = mineral_readiness["sub_score"]
        return 0, fallback, True


def get_feasibility_report(
    client,
    inputs: dict,
    metal_prices_text: str,
    gross_value: float,
    estimated_recovered_value: float,
    recovery_pct: int,
) -> str:
    system = """You are a senior mining engineer and mineralogist writing a preliminary screening assessment.
Use only entered facts and fixed calculations. A mineral name establishes reported presence only; it does not establish
abundance, target-metal hosting, deportment, liberation, locking, recovery, or process suitability. Treat missing or
unverified information as unknown, not absent. Describe process methods as test candidates and never classify the
project as feasible, viable, profitable, or technically proven. Use Markdown headings and hyphen bullets only. Do not
use tables, HTML, LaTeX, bold-only headings, or horizontal rules. Keep the response under 550 words."""
    user = f"""Write a preliminary screening assessment for secondary metal recovery from these tailings:

INPUTS:
- Source: {inputs['source']}
- Metal grades: {inputs['grades']}
- Tonnage: {inputs['tonnage']:,} tonnes
- Mineralogy: {inputs['mineralogy']}
- Mineralogical characterization: {inputs['mineral_characterization']}
- Mineralogical evidence status: {inputs['mineral_readiness_summary']}
- Oxidation state: {inputs['oxidation']}
- Location: {inputs['location']}
- Infrastructure: {inputs['infrastructure']}
- Metal prices used: {metal_prices_text}
- Gross in-situ value calculated from entered grades, tonnage, and prices: USD {gross_value:,.0f}
- Selected uniform recovery scenario, not testwork-validated: {recovery_pct}%
- Indicative recovered metal value: USD {estimated_recovered_value:,.0f}

STRUCTURE YOUR REPORT:
## Grade and Value Screen
## Mineralogical Evidence
## Characterization Gaps
## Candidate Testwork
## Infrastructure Evidence
## Screening Summary

Do not invent external grade thresholds, mineral proportions, recoveries, costs, or infrastructure benefits."""
    return call_groq(client, system, user)


def get_processing_strategy(client, inputs: dict, recovery_pct: int) -> str:
    system = """You are a metallurgist specialising in tailings reprocessing.
Provide an evidence-first characterization and comparative-testwork strategy, not a selected plant design. Do not
infer target-metal hosts, mineral abundance, liberation, locking, recovery, route suitability, or reagent demand from
mineral names or a broad oxidation category. Use the exact labels requested, plain text, and hyphen bullets. Do not use
Markdown emphasis, tables, HTML, LaTeX, or horizontal rules. Keep the response under 350 words."""
    user = f"""Prepare a screening testwork strategy for:

Source: {inputs['source']}
Grades: {inputs['grades']}
Mineralogy: {inputs['mineralogy']}
Mineralogical characterization: {inputs['mineral_characterization']}
Evidence gaps: {inputs['mineral_readiness_summary']}
Oxidation state: {inputs['oxidation']}
Infrastructure available: {inputs['infrastructure']}
Location: {inputs['location']}
Selected uniform recovery scenario: {recovery_pct}% (not a testwork result)

Format:
SCREENING STRATEGY: Characterization-led comparative testwork
RATIONALE: [explain why unresolved evidence prevents route selection]
CANDIDATE TESTS:
- [test and the uncertainty it addresses]
ROUTE SELECTION STATUS: Deferred until representative characterization and metallurgical testwork are complete."""
    return call_groq(client, system, user)


def get_action_plan(client, inputs: dict) -> str:
    system = """You are a mining project development consultant.
Write a concise two-phase screening investigation plan. Do not extend into feasibility engineering, permitting,
finance, construction, or production because this tool only screens whether further investigation is justified.
Do not invent sample masses, recovery thresholds, costs, plant capacities, or test results. Use every requested label
exactly, plain text and hyphen bullets only. Do not use Markdown emphasis, tables, HTML, LaTeX, or horizontal rules."""
    user = f"""Write a two-phase screening investigation plan for these tailings:

Source: {inputs['source']}
Tonnage: {inputs['tonnage']:,} tonnes
Location: {inputs['location']}
Infrastructure: {inputs['infrastructure']}
Mineralogical characterization: {inputs['mineral_characterization']}
Current evidence gaps: {inputs['mineral_readiness_summary']}

Use this exact structure for both phases:
Phase 1: Investigation & Sampling (duration estimate)
Key activities:
- activity
Key deliverables:
- deliverable
Decision Gate 1: evidence-based criterion for proceeding

Phase 2: Mineralogical Characterization & Testwork (duration estimate)
Key activities:
- activity
Key deliverables:
- deliverable
Decision Gate 2: decide whether the evidence justifies a separate feasibility study

End with: SCOPE LIMIT: Later project-development phases are outside this screening tool."""
    result = call_groq(client, system, user, max_tokens=1800)
    issues = action_plan_validation_issues(result)
    if not issues:
        return result
    retry = user + "\n\nCorrect these structural problems: " + "; ".join(issues)
    result = call_groq(client, system, retry, max_tokens=1800)
    issues = action_plan_validation_issues(result)
    if issues:
        raise RuntimeError("The generated screening plan remained incomplete after retrying: " + "; ".join(issues))
    return result


def get_economic_summary(
    client,
    inputs: dict,
    gross_value: float,
    estimated_revenue: float,
    recovery_pct: int,
    metal_prices_text: str,
) -> str:
    system = """You are a mining economist specialising in preliminary tailings screening.
Interpret only fixed values calculated from entered inputs. Do not estimate CAPEX, OPEX, throughput, project life,
cash flow, payback, NPV, IRR, or economic viability when those inputs are absent. Gross and recovered metal value are
not revenue, income, cash flow, or profit. Use short Markdown headings and hyphen bullets only. Do not use tables,
HTML, LaTeX, bold-only headings, or horizontal rules. Keep the response under 300 words."""
    recoverable_value_per_tonne = estimated_revenue / inputs["tonnage"] if inputs["tonnage"] else 0
    user = f"""Provide an economic screening interpretation for this tailings project.

INPUTS:
- Source: {inputs['source']}
- Total tonnage: {inputs['tonnage']:,} tonnes
- Grades: {inputs['grades']}
- Location: {inputs['location']}
- Infrastructure available: {inputs['infrastructure']}
- Metal prices used: {metal_prices_text}
- Gross in-situ metal value calculated from entered inputs: USD {gross_value:,.0f}
- Selected uniform recovery scenario, not testwork-validated: {recovery_pct}%
- Indicative recovered metal value: USD {estimated_revenue:,.0f}
- Indicative recovered metal value per tonne: USD {recoverable_value_per_tonne:,.2f}/t
- Throughput, project life, CAPEX, OPEX, payability, and commercial terms: not provided

Use exactly these headings:
## Value Screen
## Missing Economic Inputs
## Assessment Limit

State that a techno-economic viability conclusion is not available until the missing inputs are supplied. If multiple
metals are listed, note that one uniform recovery factor is only a simplifying scenario."""
    return call_groq(client, system, user)


def _safe_result(future):
    """Return (result, is_error). Catches RuntimeError so one failed call doesn't discard the rest."""
    try:
        return future.result(), False
    except RuntimeError as exc:
        return str(exc), True


def render_output_card(title: str, body_html: str):
    st.markdown(
        f"""
        <div class="output-card">
            <h4>{title}</h4>
            {body_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Hero ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>⛏ TailingsValue Pro</h1>
  <p>Preliminary Tailings Screener · Mineralogical evidence and value scenarios</p>
</div>
""", unsafe_allow_html=True)

# ── Secrets setup ────────────────────────────────────────────────────────────────
api_key = get_app_setting("GROQ_API_KEY")
GROQ_MODEL = get_app_setting("GROQ_MODEL", DEFAULT_GROQ_MODEL)
if not api_key:
    st.markdown("""
    <div class="warning-box">
        GROQ_API_KEY is not configured in Streamlit secrets or the environment. AI-supported analysis is unavailable.
    </div>
    """, unsafe_allow_html=True)

# ── Inputs ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Tailings Characterisation</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    source = st.text_input(
        "Tailings Source",
        placeholder="e.g. copper porphyry flotation tailings",
    )
    grades = st.text_input(
        "Metal Grades",
        placeholder="e.g. Cu: 0.18%, Au: 0.5 ppm, Mo: 0.02%",
        help="Use %, ppm, or g/t. Separate metals with commas."
    )
    tonnage = st.number_input(
        "Tonnage Available (tonnes)",
        min_value=1,
        value=1,
        step=1000,
        format="%d",
        help="Enter the estimated tonnage available for reprocessing. Smaller deposits can be entered directly; the field is not limited to large projects.",
    )
    mineralogy = st.text_area(
        "Mineralogy",
        placeholder="e.g. chalcopyrite, molybdenite, pyrite, quartz",
        height=80,
        help="List reported minerals only. Use the structured section below for analytical evidence.",
    )

with col2:
    oxidation = st.selectbox(
        "Tailings Age & Oxidation State",
        options=[
            "Fresh / unoxidised (< 5 years)",
            "Partially oxidised (5–20 years)",
            "Heavily oxidised / supergene (> 20 years)",
            "Unknown",
        ]
    )
    location = st.text_input(
        "Location",
        placeholder="e.g. Arizona, USA",
    )
    infrastructure = st.text_area(
        "Infrastructure Available",
        placeholder="e.g. existing mill, grid power, water access, tailings dam in place",
        height=80,
        help="List known assets and include capacity, condition, availability, or compatibility evidence where available.",
    )

    if not infrastructure:
        st.markdown("""
        <div class="warning-box" style="margin-top:0.4rem;">
            Infrastructure is optional, but leaving it blank limits the infrastructure evidence assessment.
        </div>
        """, unsafe_allow_html=True)

# Structured characterization evidence supplements the free-text mineral list.
with st.expander("Mineralogical Characterization Evidence", expanded=True):
    st.caption(
        "Enter only evidence that is already available. Mineral names alone do not establish "
        "abundance, metal hosting, liberation, or recoverability."
    )
    mineral_col1, mineral_col2 = st.columns(2)
    with mineral_col1:
        characterization_methods = st.multiselect(
            "Methods used",
            options=[
                "XRD",
                "SEM-EDS",
                "QEMSCAN / MLA",
                "Hyperspectral imaging",
                "Bulk chemical assay",
                "Other documented method",
            ],
            help="Select completed analytical methods, not planned work.",
        )
        modal_mineralogy = st.selectbox(
            "Modal mineralogy",
            options=[
                "Not provided",
                "Qualitative mineral identification",
                "Quantitative modal mineralogy",
            ],
        )
        metal_deportment = st.selectbox(
            "Target-metal host and deportment",
            options=[
                "Not provided",
                "Inferred from mineral names",
                "Target-metal hosts identified",
                "Quantitative deportment measured",
            ],
        )
    with mineral_col2:
        liberation = st.selectbox(
            "Liberation and locking evidence",
            options=[
                "Not provided",
                "Qualitative observations",
                "Measured by size fraction",
            ],
        )
        spatial_coverage = st.selectbox(
            "Sampling coverage",
            options=[
                "Not provided",
                "Single sample",
                "Multiple locations or depths",
                "Representative spatial programme",
            ],
        )
        characterization_notes = st.text_area(
            "Characterization notes",
            placeholder="e.g. method, sample coverage, modal %, host phases, liberation size",
            height=96,
        )

mineral_characterization = {
    "methods": characterization_methods,
    "modal_mineralogy": modal_mineralogy,
    "metal_deportment": metal_deportment,
    "liberation": liberation,
    "spatial_coverage": spatial_coverage,
    "notes": characterization_notes.strip(),
}
mineral_readiness = assess_mineralogical_readiness(mineral_characterization)

# Metal prices
st.markdown('<div class="section-label">Metal Prices</div>', unsafe_allow_html=True)
custom_price_errors = []
price_mode = st.radio(
    "Price source",
    options=["Use reference prices (built-in)", "Enter custom prices"],
    horizontal=True,
    label_visibility="collapsed",
)

if price_mode == "Enter custom prices":
    custom_prices = st.text_input(
        "Custom prices",
        placeholder="e.g. Cu: 9500, Au: 70, Mo: 60000  (USD/t for base metals, USD/g for Au/Ag)"
    )
    metal_prices_text = f"Custom prices entered: {custom_prices}"
    prices_used, custom_price_errors = parse_custom_metal_prices(custom_prices, METAL_PRICES)
else:
    price_ref_stale, price_ref_age_days = is_price_reference_stale(
        PRICE_REF_DATE,
        today=date.today(),
    )
    price_ref_label = datetime.fromisoformat(PRICE_REF_DATE).strftime("%B %d, %Y")
    price_table = " | ".join(
        f"{m}: {v['price']} {v['unit']}" + (f" ({v['basis']})" if v.get("basis") else "")
        for m, v in METAL_PRICES.items()
    )
    if price_ref_stale:
        st.markdown(
            f'<div class="warning-box">Reference price set last reviewed {price_ref_label} '
            f'({price_ref_age_days} days old). Review before decision-making. Basis: {PRICE_OBSERVATION_LABEL}. '
            f'Source: {PRICE_SOURCE_LABEL}.<br>{price_table}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="warning-box">Reference price set last reviewed {price_ref_label} '
            f'({price_ref_age_days} days old). Basis: {PRICE_OBSERVATION_LABEL}. '
            f'Source: {PRICE_SOURCE_LABEL}.<br>{price_table}</div>',
            unsafe_allow_html=True,
        )
    metal_prices_text = (
        f"Reference set reviewed {price_ref_label}; basis: {PRICE_OBSERVATION_LABEL}; "
        f"source: {PRICE_SOURCE_LABEL}: "
    ) + ", ".join(
        f"{v['name']}: {v['price']} {v['unit']}" + (f" ({v['basis']})" if v.get("basis") else "")
        for v in METAL_PRICES.values()
    )
    prices_used = METAL_PRICES

# ── Recovery scenario ───────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Recovery Scenario</div>', unsafe_allow_html=True)
recovery_pct = st.slider(
    "Uniform Screening Recovery (%)",
    min_value=10,
    max_value=95,
    value=70,
    step=5,
    help="A user-selected value scenario applied uniformly to all metals. It is not a testwork result or recovery prediction.",
)

# ── Run button ──────────────────────────────────────────────────────────────────
st.markdown("---")
run = st.button("▶  RUN SCREENING ANALYSIS")

# ── Analysis ────────────────────────────────────────────────────────────────────
if run:
    now = time.time()
    last_run_at = st.session_state.get("last_run_at", 0.0)
    seconds_remaining = RUN_COOLDOWN_SECONDS - (now - last_run_at)
    if seconds_remaining > 0:
        st.error(
            f"Please wait {seconds_remaining:.1f} more seconds before running another analysis."
        )
        st.stop()

    # Validation
    missing = []
    if not source: missing.append("Tailings Source")
    if not grades: missing.append("Metal Grades")
    if not tonnage: missing.append("Tonnage")
    if not mineralogy: missing.append("Mineralogy")
    if not location: missing.append("Location")

    if missing:
        st.error(f"Please fill in: {', '.join(missing)}")
        st.stop()

    if price_mode == "Enter custom prices" and not custom_prices.strip():
        st.error("Enter at least one custom price or select the built-in reference prices.")
        st.stop()

    if custom_price_errors:
        error_lines = "\n".join(
            f"- `{item['entry']}`: {item['reason']}"
            for item in custom_price_errors
        )
        st.error("Please correct the custom price entries:\n" + error_lines)
        st.stop()

    if not api_key:
        st.error("GROQ_API_KEY is not configured in Streamlit secrets or the environment.")
        st.stop()

    client = Groq(api_key=api_key)

    methods_text = ", ".join(mineral_readiness["methods"]) or "Not provided"
    characterization_text = (
        f"Methods: {methods_text}; modal mineralogy: {modal_mineralogy}; "
        f"metal deportment: {metal_deportment}; liberation: {liberation}; "
        f"sampling coverage: {spatial_coverage}; notes: {characterization_notes or 'Not provided'}"
    )
    readiness_summary = (
        f"{mineral_readiness['status']} ({mineral_readiness['score']}/100 completeness). "
        f"Gaps: {'; '.join(mineral_readiness['gaps']) or 'No core gaps identified from the selected fields.'}"
    )
    inputs = {
        "source": source,
        "grades": grades,
        "tonnage": tonnage,
        "mineralogy": mineralogy,
        "mineral_characterization": characterization_text,
        "mineral_readiness_summary": readiness_summary,
        "oxidation": oxidation,
        "location": location,
        "infrastructure": infrastructure or "None specified",
    }

    # Python calculates gross value — no AI needed
    gross_value, parsed_metals, skipped_entries = parse_gross_value_from_grades(grades, tonnage, prices_used)

    if gross_value == 0:
        st.error(
            "Could not parse any recognised metal grades from your input. "
            "No analysis has been run.\n\n"
            f"**You entered:** `{grades}`\n\n"
            "**Accepted formats:**\n"
            "- `Cu: 0.18%, Au: 0.5 ppm, Mo: 0.02%`\n"
            "- `Cu 0.18%, Au 0.5 ppm` (no colon)\n"
            "- `0.18% Cu, 500 ppb Au` (reversed)\n"
            "- `Au: 500 ppb` (ppb supported — converted to ppm automatically)\n\n"
            "**Recognised symbols:** Cu, Au, Ag, Mo, Zn, Pb, Ni, Co, Li, REE. "
            "Note: use REE for rare earths, not TREO."
        )
        st.stop()

    if should_block_analysis(parsed_metals, skipped_entries):
        skipped_lines = "\n".join(
            f"- `{item['entry']}` → {item['reason']}"
            for item in skipped_entries
        )
        st.error(
            "Some grade entries were recognised, but others were not. "
            "No analysis has been run because that would produce incomplete economics.\n\n"
            "**Parsed successfully:** "
            + ", ".join(m["symbol"] for m in parsed_metals)
            + "\n\n"
            "**Please correct these entries:**\n"
            + skipped_lines
            + "\n\n"
            "**Accepted formats:**\n"
            "- `Cu: 0.18%, Au: 0.5 ppm, Mo: 0.02%`\n"
            "- `Cu 0.18%, Au 0.5 ppm` (no colon)\n"
            "- `0.18% Cu, 500 ppb Au` (reversed)"
        )
        st.stop()

    st.session_state["last_run_at"] = now
    econ_snapshot = calculate_economic_snapshot(gross_value, recovery_pct, tonnage)
    estimated_revenue = econ_snapshot["estimated_revenue"]

    st.markdown("---")
    st.markdown('<div class="section-label">Analysis Results</div>', unsafe_allow_html=True)

    # Fire all five independent AI-support calls in parallel.
    with st.spinner("Running analysis (all modules in parallel)..."):
        with ThreadPoolExecutor(max_workers=5) as pool:
            f_score = pool.submit(get_feasibility_score, client, inputs, mineral_readiness)
            f_report = pool.submit(
                get_feasibility_report,
                client,
                inputs,
                metal_prices_text,
                gross_value,
                estimated_revenue,
                recovery_pct,
            )
            f_route = pool.submit(get_processing_strategy, client, inputs, recovery_pct)
            f_plan   = pool.submit(get_action_plan,        client, inputs)
            f_econ   = pool.submit(
                get_economic_summary,
                client,
                inputs,
                gross_value,
                estimated_revenue,
                recovery_pct,
                metal_prices_text,
            )

    # Collect each result independently — one failure does not discard the rest
    try:
        score, sub_scores, score_fallback = f_score.result()
    except RuntimeError:
        score = 0
        sub_scores = {k: 2 for k in SCORE_RUBRIC}
        sub_scores["mineralogy"] = mineral_readiness["sub_score"]
        score_fallback = True

    report, report_err = _safe_result(f_report)
    route,  route_err  = _safe_result(f_route)
    plan,   plan_err   = _safe_result(f_plan)
    econ,   econ_err   = _safe_result(f_econ)

    left, right = st.columns([1, 2])

    with left:
        if score_fallback:
            st.markdown("""
            <div class="warning-box" style="text-align:center; padding:1.5rem;">
                <div style="font-size:1rem; margin-bottom:0.4rem;">SCORE UNAVAILABLE</div>
                <div style="font-size:0.8rem;">The AI-supported evidence score is unavailable.
                Deterministic value and mineralogical-readiness results remain available below.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Score colour
            if score >= 70:
                score_colour = "#7ec87e"
            elif score >= 45:
                score_colour = "#c8a96e"
            else:
                score_colour = "#c87e7e"

            st.markdown(f"""
            <div class="score-box">
                <div class="score-number" style="color:{score_colour}">{score}</div>
                <div class="score-label">Screening Evidence Score / 100</div>
            </div>
            """, unsafe_allow_html=True)

            # Sub-score breakdown
            breakdown_rows = "".join(
                f'<tr><td>{SCORE_RUBRIC[k]["label"]}</td>'
                f'<td style="text-align:center;color:#c8a96e;">{sub_scores[k]}/5</td>'
                f'<td style="text-align:right;color:#9a9080;font-size:0.75rem;">{int(SCORE_RUBRIC[k]["weight"]*100)}%</td></tr>'
                for k in SCORE_RUBRIC
            )
            st.markdown(f"""
            <div class="output-card">
                <h4>Score Breakdown</h4>
                <table class="sensitivity-table">
                    <tr><th>Factor</th><th style="text-align:center;">Score</th><th style="text-align:right;">Weight</th></tr>
                    {breakdown_rows}
                </table>
                <div style="margin-top:0.9rem; padding-top:0.8rem; border-top:1px solid #2a2520;">
                    <div style="font-size:0.72rem; color:#9a9080; font-family:'IBM Plex Mono',monospace; letter-spacing:1px; text-transform:uppercase; margin-bottom:0.6rem;">
                        Evidence Band Definitions
                    </div>
                    <div style="font-size:0.78rem; color:#c8d0b0; line-height:1.65;">
                        <strong>1/5:</strong> evidence absent
                        <br><strong>2/5:</strong> preliminary evidence
                        <br><strong>3/5:</strong> partial supporting evidence
                        <br><strong>4/5:</strong> representative evidence
                        <br><strong>5/5:</strong> advanced-study evidence
                    </div>
                    <div style="font-size:0.74rem; color:#9a9080; margin-top:0.7rem; line-height:1.6;">
                        This measures input evidence readiness, not project feasibility, recovery, or profitability.
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        gap_items = "".join(f"<li>{gap}</li>" for gap in mineral_readiness["gaps"])
        next_step_items = "".join(f"<li>{step}</li>" for step in mineral_readiness["next_steps"])
        render_output_card(
            "Mineralogical Evidence Readiness",
            f"""
            <div class="output-copy">
                <p><strong>{mineral_readiness['status']}</strong>: {mineral_readiness['score']}/100 completeness.</p>
                <div class="structured-label">Evidence Gaps</div>
                <ul>{gap_items or '<li>No core gaps identified from the selected fields.</li>'}</ul>
                <div class="structured-label">Next Characterization Steps</div>
                <ul>{next_step_items or '<li>Proceed to independent review of the supplied evidence.</li>'}</ul>
            </div>
            """,
        )

        # Gross value, per-metal breakdown, estimated revenue
        metal_rows = "".join(
            f'<tr><td>{m["symbol"]}</td>'
            f'<td style="text-align:right;color:#9a9080;">{m["grade"]}</td>'
            f'<td style="text-align:right;color:#c8d0b0;">USD {m["value_usd"]:,.0f}</td>'
            f'<td style="text-align:right;color:#9a9080;">{m["value_usd"]/gross_value*100:.1f}%</td></tr>'
            for m in parsed_metals
        )
        st.markdown(f"""
        <div class="output-card">
            <h4>Gross In-Situ Value</h4>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:1.4rem; color:#a8d080;">
                USD {gross_value:,.0f}
            </div>
            <div style="font-size:0.75rem; color:#9a9080; margin-top:0.3rem;">
                Raw contained metal value before recovery losses and project costs
            </div>
            <table class="sensitivity-table" style="margin-top:0.8rem;">
                <tr>
                    <th>Metal</th>
                    <th style="text-align:right;">Grade</th>
                    <th style="text-align:right;">Value (USD)</th>
                    <th style="text-align:right;">Share</th>
                </tr>
                {metal_rows}
            </table>
            <div style="margin-top:0.8rem; padding-top:0.8rem; border-top:1px solid #2a2520;">
                <div style="font-size:0.72rem; color:#9a9080; font-family:'IBM Plex Mono',monospace; letter-spacing:1px; text-transform:uppercase;">
                    Indicative Recovered Metal Value @ {recovery_pct}% Screening Scenario
                </div>
                <div style="font-family:'IBM Plex Mono',monospace; font-size:1.1rem; color:#c8d0b0; margin-top:0.3rem;">
                    USD {estimated_revenue:,.0f}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if skipped_entries:
            skipped_rows = "".join(
                f'<tr><td>{item["entry"]}</td><td style="text-align:right;color:#c8904e;">{item["reason"]}</td></tr>'
                for item in skipped_entries
            )
            st.markdown(f"""
            <div class="warning-box">
                Some grade entries were not included in the gross-value calculation.
                <table class="sensitivity-table" style="margin-top:0.8rem;">
                    <tr>
                        <th>Skipped Entry</th>
                        <th style="text-align:right;">Reason</th>
                    </tr>
                    {skipped_rows}
                </table>
            </div>
            """, unsafe_allow_html=True)

        # Sensitivity table
        st.markdown('<div class="output-card"><h4>Sensitivity Analysis</h4>', unsafe_allow_html=True)
        rows = calculate_sensitivity(gross_value)
        table_html = '<table class="sensitivity-table"><tr><th>Scenario</th><th>Gross Value (USD)</th></tr>'
        for row in rows:
            row_class = 'class="base-row"' if row["base"] else ""
            table_html += f'<tr {row_class}><td>{row["scenario"]}</td><td>{row["value"]:,.0f}</td></tr>'
        table_html += "</table></div>"
        st.markdown(table_html, unsafe_allow_html=True)

    with right:
        if report_err:
            render_output_card("Preliminary Screening Assessment", f'<div class="warning-box">{report}<br>Re-run the analysis to retry.</div>')
        else:
            render_output_card("Preliminary Screening Assessment", render_model_output_html(report, mode="generic"))

    # Characterization-led testwork strategy and bounded investigation plan
    col_a, col_b = st.columns(2)
    with col_a:
        if route_err:
            render_output_card("Screening Testwork Strategy", f'<div class="warning-box">{route}<br>Re-run the analysis to retry.</div>')
        else:
            render_output_card(
                "Screening Testwork Strategy",
                render_key_value_sections(
                    route,
                    ["SCREENING STRATEGY:", "RATIONALE:", "CANDIDATE TESTS:", "ROUTE SELECTION STATUS:"],
                ),
            )

    with col_b:
        if plan_err:
            render_output_card("Screening Investigation Plan", f'<div class="warning-box">{plan}<br>Re-run the analysis to retry.</div>')
        else:
            render_output_card("Screening Investigation Plan", render_action_plan_html(plan))

    # Economic summary
    if econ_err:
        render_output_card("Economic Summary", f'<div class="warning-box">{econ}<br>Re-run the analysis to retry.</div>')
    else:
        economic_snapshot_html = f"""
        <table class="sensitivity-table" style="margin-bottom:0.9rem;">
            <tr><th>Metric</th><th style="text-align:right;">Value</th></tr>
            <tr><td>Indicative Recovered Metal Value</td><td style="text-align:right;">USD {estimated_revenue:,.0f}</td></tr>
            <tr><td>Uniform Recovery Scenario</td><td style="text-align:right;">{recovery_pct}%</td></tr>
            <tr><td>Recovered Value per Tonne</td><td style="text-align:right;">USD {econ_snapshot["recoverable_value_per_tonne"]:,.2f}/t</td></tr>
            <tr><td>Throughput and Project Life</td><td style="text-align:right;">Not provided</td></tr>
        </table>
        """
        render_output_card("Economic Summary", economic_snapshot_html + render_model_output_html(econ, mode="economic_summary"))

    st.markdown("""
    <footer>
    TAILINGSVALUE PRO · FOR PRELIMINARY ASSESSMENT ONLY · NOT A SUBSTITUTE FOR PROFESSIONAL ENGINEERING STUDY
    </footer>
    """, unsafe_allow_html=True)
