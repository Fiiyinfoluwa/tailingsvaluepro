import json
import time
from datetime import date, datetime
import streamlit as st
from groq import Groq
from concurrent.futures import ThreadPoolExecutor
from analysis_utils import (
    calculate_economic_snapshot,
    calculate_sensitivity,
    extract_json_object,
    is_price_reference_stale,
    parse_gross_value_from_grades,
    render_action_plan_html,
    render_key_value_sections,
    render_model_output_html,
    should_block_analysis,
)

RUN_COOLDOWN_SECONDS = 8

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
    "Cu":  {"price": 9200,    "unit": "USD/t",   "name": "Copper"},
    "Au":  {"price": 65,      "unit": "USD/g",   "name": "Gold"},
    "Ag":  {"price": 0.85,    "unit": "USD/g",   "name": "Silver"},
    "Mo":  {"price": 55000,   "unit": "USD/t",   "name": "Molybdenum"},
    "Zn":  {"price": 2800,    "unit": "USD/t",   "name": "Zinc"},
    "Pb":  {"price": 2100,    "unit": "USD/t",   "name": "Lead"},
    "Ni":  {"price": 16500,   "unit": "USD/t",   "name": "Nickel"},
    "Co":  {"price": 33000,   "unit": "USD/t",   "name": "Cobalt"},
    "Li":  {"price": 13000,   "unit": "USD/t",   "name": "Lithium"},
    "REE": {"price": 2500,    "unit": "USD/t",   "name": "Rare Earth Elements"},
}

PRICE_REF_DATE = "2026-03-01"

# ── Feasibility scoring rubric ──────────────────────────────────────────────────
SCORE_RUBRIC = {
    "grade": {
        "label": "Grade Quality",
        "weight": 0.30,
        "criteria": (
            "1 = sub-economic at current prices, no viable recovery route\n"
            "2 = marginal — borderline economic, high sensitivity to price\n"
            "3 = low but potentially economic with efficient low-OPEX processing\n"
            "4 = economic with standard processing at current prices\n"
            "5 = strong grade, clearly economic across a range of prices"
        ),
    },
    "tonnage": {
        "label": "Tonnage Scale",
        "weight": 0.20,
        "criteria": (
            "1 = < 500,000 t\n"
            "2 = 500,000 – 2 million t\n"
            "3 = 2 – 10 million t\n"
            "4 = 10 – 50 million t\n"
            "5 = > 50 million t"
        ),
    },
    "mineralogy": {
        "label": "Mineralogy & Processability",
        "weight": 0.20,
        "criteria": (
            "1 = complex mixed oxides/sulfides, refractory, penalty elements\n"
            "2 = moderately complex — mixed or partially refractory\n"
            "3 = moderate complexity — some gangue complications\n"
            "4 = relatively simple — primary sulfides, well-understood processing\n"
            "5 = simple — single dominant mineral, standard processing applies"
        ),
    },
    "infrastructure": {
        "label": "Infrastructure",
        "weight": 0.20,
        "criteria": (
            "1 = remote, no existing infrastructure\n"
            "2 = minimal — only power or only water available\n"
            "3 = partial — some infrastructure present\n"
            "4 = good — mill or major processing equipment available\n"
            "5 = excellent — existing mill + grid power + water access"
        ),
    },
    "oxidation": {
        "label": "Oxidation State",
        "weight": 0.10,
        "criteria": (
            "1 = heavily oxidised/supergene — complex processing, low recoveries\n"
            "2 = significantly oxidised — additional treatment required\n"
            "3 = partially oxidised — mixed processing requirements\n"
            "4 = mostly fresh — minor oxidation impact\n"
            "5 = fresh/unoxidised — standard processing, best recoveries"
        ),
    },
}

# ── Groq API calls ────────────────────────────────────────────────────────────
def call_groq(client: Groq, system: str, user: str) -> str:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=1500,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"Groq API error: {exc}") from exc


def get_feasibility_score(client, inputs: dict) -> tuple:
    criteria_block = "\n\n".join(
        f'{key.upper()} ({info["label"]}, weight {int(info["weight"] * 100)}%):\n{info["criteria"]}'
        for key, info in SCORE_RUBRIC.items()
    )
    system = """You are a senior mining engineer scoring tailings reprocessing feasibility.
Score each factor using ONLY the exact band criteria provided. Output valid JSON only — no other text."""
    user = f"""Score these tailings. Output a JSON object with exactly these keys: grade, tonnage, mineralogy, infrastructure, oxidation. Each value must be an integer 1–5.

TAILINGS:
- Source: {inputs['source']}
- Grades: {inputs['grades']}
- Tonnage: {inputs['tonnage']:,} tonnes
- Mineralogy: {inputs['mineralogy']}
- Oxidation state: {inputs['oxidation']}
- Location: {inputs['location']}
- Infrastructure: {inputs['infrastructure']}

SCORING CRITERIA:
{criteria_block}

Example output: {{"grade": 3, "tonnage": 4, "mineralogy": 3, "infrastructure": 5, "oxidation": 4}}
Output ONLY the JSON object. No explanation."""
    result = call_groq(client, system, user)
    try:
        sub_scores = extract_json_object(result)
        for key in SCORE_RUBRIC:
            sub_scores[key] = max(1, min(5, int(sub_scores.get(key, 3))))
        weighted = sum(sub_scores[k] * SCORE_RUBRIC[k]["weight"] for k in SCORE_RUBRIC)
        score = round(weighted * 20)
        return score, sub_scores, False
    except (ValueError, TypeError, json.JSONDecodeError):
        fallback = {k: 3 for k in SCORE_RUBRIC}
        return 60, fallback, True


def get_feasibility_report(client, inputs: dict, metal_prices_text: str) -> str:
    system = """You are a senior mining engineer and metallurgist specialising in tailings reprocessing.
Write a clear, structured technical feasibility assessment. Use headings. Be specific.
Do not hallucinate grades or figures — only use values provided by the user.
Flag any missing data that would affect the assessment."""
    user = f"""Write a technical feasibility assessment for secondary metal recovery from these tailings:

INPUTS:
- Source: {inputs['source']}
- Metal grades: {inputs['grades']}
- Tonnage: {inputs['tonnage']:,} tonnes
- Mineralogy: {inputs['mineralogy']}
- Oxidation state: {inputs['oxidation']}
- Location: {inputs['location']}
- Infrastructure: {inputs['infrastructure']}
- Metal prices used: {metal_prices_text}

STRUCTURE YOUR REPORT:
1. Grade Assessment — evaluate whether grades are economic
2. Mineralogy & Processing Implications — how mineralogy affects recovery options
3. Oxidation State Impact — how oxidation state affects the recommended process route
4. Infrastructure Assessment — what existing infrastructure reduces CAPEX/OPEX
5. Key Risks — list 3-4 specific technical or economic risks
6. Overall Verdict — one paragraph summary

Be direct. Use bullet points where appropriate."""
    return call_groq(client, system, user)


def get_processing_route(client, inputs: dict) -> str:
    system = """You are a metallurgist specialising in tailings reprocessing.
Recommend a specific processing route. Always include:
- Primary recommended route with rationale
- Why 1-2 alternative routes were rejected (contraindications)
- Expected recovery range (%)
Be specific to the mineralogy and oxidation state provided."""
    user = f"""Recommend a processing route for:

Source: {inputs['source']}
Grades: {inputs['grades']}
Mineralogy: {inputs['mineralogy']}
Oxidation state: {inputs['oxidation']}
Infrastructure available: {inputs['infrastructure']}
Location: {inputs['location']}

Format:
RECOMMENDED ROUTE: [name]
RATIONALE: [why this route suits the mineralogy/oxidation state]
EXPECTED RECOVERY: [range %]
ALTERNATIVES REJECTED:
- [Route A]: [why not suitable]
- [Route B]: [why not suitable]"""
    return call_groq(client, system, user)


def get_action_plan(client, inputs: dict) -> str:
    system = """You are a mining project development consultant.
Write a phased action plan for developing a tailings reprocessing project.
Be specific about durations, key deliverables, and decision gates."""
    user = f"""Write a phased action plan for reprocessing these tailings:

Source: {inputs['source']}
Tonnage: {inputs['tonnage']:,} tonnes
Location: {inputs['location']}
Infrastructure: {inputs['infrastructure']}

Phases:
1. Investigation & Sampling (months + key activities)
2. Metallurgical Testwork (months + key activities)
3. Feasibility Study (months + key activities)
4. Permitting & Finance (months + key activities)
5. Construction & Commissioning (months + key activities)
6. Production

Include key decision gates between phases."""
    return call_groq(client, system, user)


def get_economic_summary(
    client,
    inputs: dict,
    gross_value: float,
    estimated_revenue: float,
    recovery_pct: int,
    metal_prices_text: str,
    annual_processing_rate: int,
    project_life_years: float,
) -> str:
    system = """You are a mining economist specialising in tailings reprocessing projects.
Be realistic and conservative. Never compress multi-year cashflows into a single-year payback calculation."""
    user = f"""Provide an economic summary for this tailings reprocessing project.

INPUTS:
- Source: {inputs['source']}
- Total tonnage: {inputs['tonnage']:,} tonnes
- Grades: {inputs['grades']}
- Location: {inputs['location']}
- Infrastructure available: {inputs['infrastructure']}
- Metal prices used: {metal_prices_text}
- Gross in-situ metal value (Python-calculated): USD {gross_value:,.0f}
- Recovery factor (user-set): {recovery_pct}%
- Estimated recoverable revenue (Python-calculated): USD {estimated_revenue:,.0f}
- Annual processing rate assumption (Python-calculated): {annual_processing_rate:,.0f} tonnes/year
- Project life (Python-calculated): {project_life_years:.1f} years

RULES — follow exactly:
- Do NOT recalculate gross in-situ value or estimated revenue. Both are fixed inputs above.
- Do NOT choose a different recovery factor. The user has set it at {recovery_pct}%.
- Do NOT choose a different annual processing rate or project life. Use {annual_processing_rate:,.0f} tonnes/year and {project_life_years:.1f} years exactly.
- For payback: use the fixed annual processing rate above, then calculate simple payback = net CAPEX / annual net cash flow. Show each step.
- Payback must be expressed in years against the stated project life — not compressed into months.

PROVIDE:
1. CAPEX estimate range — show infrastructure credit applied and net CAPEX
2. OPEX estimate (USD/tonne processed) with brief justification
3. Estimated total revenue: USD {estimated_revenue:,.0f} (at {recovery_pct}% recovery — already calculated, confirm and use)
4. Annual processing rate assumption and derived project life (years): confirm {annual_processing_rate:,.0f} tonnes/year and {project_life_years:.1f} years
5. Annual net cash flow (annual revenue minus annual OPEX)
6. Simple payback period = net CAPEX / annual net cash flow (in years)
7. Economic verdict: viable / marginal / not viable — one sentence with the key reason

IMPORTANT: Write all dollar amounts as e.g. "USD 23 million" or "23M USD" — do NOT use the $ symbol as it breaks rendering."""
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
  <p>Secondary Resource Recovery Evaluator · Powered by Llama 3.3 70b via Groq</p>
</div>
""", unsafe_allow_html=True)

# ── Secrets setup ────────────────────────────────────────────────────────────────
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.markdown("""
    <div class="warning-box">
        GROQ_API_KEY is not configured in Streamlit secrets. Add it before sharing this demo.
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
        help="Infrastructure strongly affects CAPEX, OPEX, and the feasibility score. Include any existing mill, power, water, roads, permits, or tailings facilities if known.",
    )

    if not infrastructure:
        st.markdown("""
        <div class="warning-box" style="margin-top:0.4rem;">
            Infrastructure is optional, but leaving it blank reduces confidence in the economic summary and feasibility score.
        </div>
        """, unsafe_allow_html=True)

# Metal prices
st.markdown('<div class="section-label">Metal Prices</div>', unsafe_allow_html=True)
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
    # Parse custom prices into prices_used so Python calc uses them
    prices_used = dict(METAL_PRICES)  # start from reference, override with custom
    if custom_prices:
        # Build reverse map: uppercase key -> original key
        upper_to_key = {k.upper(): k for k in prices_used}
        for match in re.finditer(r'([A-Za-z]+)\s*:\s*([\d.]+)', custom_prices):
            symbol_upper = match.group(1).upper()
            price_val = float(match.group(2))
            if symbol_upper in upper_to_key:
                orig_key = upper_to_key[symbol_upper]
                prices_used[orig_key] = dict(prices_used[orig_key])
                prices_used[orig_key]["price"] = price_val
else:
    price_ref_stale, price_ref_age_days = is_price_reference_stale(
        PRICE_REF_DATE,
        today=date.today(),
    )
    price_ref_label = datetime.fromisoformat(PRICE_REF_DATE).strftime("%B %Y")
    price_table = " | ".join([f"{m}: {v['price']} {v['unit']}" for m, v in METAL_PRICES.items()])
    if price_ref_stale:
        st.markdown(
            f'<div class="warning-box">Reference prices last updated {price_ref_label} '
            f'({price_ref_age_days} days old). Review and refresh before using them for decision-making: {price_table}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="warning-box">Reference prices last updated {price_ref_label} '
            f'({price_ref_age_days} days old): {price_table}</div>',
            unsafe_allow_html=True,
        )
    metal_prices_text = f"Reference prices as of {price_ref_label}: " + ", ".join([f"{v['name']}: {v['price']} {v['unit']}" for v in METAL_PRICES.values()])
    prices_used = METAL_PRICES

# ── Recovery assumption ─────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Recovery Assumption</div>', unsafe_allow_html=True)
recovery_pct = st.slider(
    "Expected Metal Recovery (%)",
    min_value=10,
    max_value=95,
    value=70,
    step=5,
    help="Estimated fraction of in-situ metal value recoverable after processing. Typical range: 50–85% for flotation of sulphide tailings.",
)

# ── Run button ──────────────────────────────────────────────────────────────────
st.markdown("---")
run = st.button("▶  RUN FEASIBILITY ANALYSIS")

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

    if not api_key:
        st.error("GROQ_API_KEY is not configured in Streamlit secrets.")
        st.stop()

    client = Groq(api_key=api_key)

    inputs = {
        "source": source,
        "grades": grades,
        "tonnage": tonnage,
        "mineralogy": mineralogy,
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

    # Fire all 5 API calls in parallel — they are fully independent
    with st.spinner("Running analysis (all modules in parallel)..."):
        with ThreadPoolExecutor(max_workers=5) as pool:
            f_score  = pool.submit(get_feasibility_score,  client, inputs)
            f_report = pool.submit(get_feasibility_report, client, inputs, metal_prices_text)
            f_route  = pool.submit(get_processing_route,   client, inputs)
            f_plan   = pool.submit(get_action_plan,        client, inputs)
            f_econ   = pool.submit(
                get_economic_summary,
                client,
                inputs,
                gross_value,
                estimated_revenue,
                recovery_pct,
                metal_prices_text,
                econ_snapshot["annual_processing_rate"],
                econ_snapshot["project_life_years"],
            )

    # Collect each result independently — one failure does not discard the rest
    try:
        score, sub_scores, score_fallback = f_score.result()
    except RuntimeError:
        score, sub_scores, score_fallback = 60, {k: 3 for k in SCORE_RUBRIC}, True

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
                <div style="font-size:0.8rem;">The scoring model returned an unexpected response.
                Re-run the analysis to retry. The assessment below is still valid.</div>
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
                <div class="score-label">Feasibility Score / 100</div>
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
                        Score Band Definitions
                    </div>
                    <div style="font-size:0.78rem; color:#c8d0b0; line-height:1.65;">
                        <strong>1/5:</strong> poor or high-risk
                        <br><strong>2/5:</strong> weak or marginal
                        <br><strong>3/5:</strong> moderate, possible with constraints
                        <br><strong>4/5:</strong> strong under current conditions
                        <br><strong>5/5:</strong> highly favourable
                    </div>
                    <div style="font-size:0.74rem; color:#9a9080; margin-top:0.7rem; line-height:1.6;">
                        Factor-specific definitions are applied from the internal rubric for grade, tonnage, mineralogy, infrastructure, and oxidation state.
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

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
                    Estimated Revenue @ {recovery_pct}% Recovery
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
            render_output_card("Feasibility Assessment", f'<div class="warning-box">{report}<br>Re-run the analysis to retry.</div>')
        else:
            render_output_card("Feasibility Assessment", render_model_output_html(report, mode="generic"))

    # Processing route
    col_a, col_b = st.columns(2)
    with col_a:
        if route_err:
            render_output_card("Recommended Processing Route", f'<div class="warning-box">{route}<br>Re-run the analysis to retry.</div>')
        else:
            render_output_card(
                "Recommended Processing Route",
                render_key_value_sections(
                    route,
                    ["RECOMMENDED ROUTE:", "RATIONALE:", "EXPECTED RECOVERY:", "ALTERNATIVES REJECTED:"],
                ),
            )

    with col_b:
        if plan_err:
            render_output_card("Action Plan", f'<div class="warning-box">{plan}<br>Re-run the analysis to retry.</div>')
        else:
            render_output_card("Action Plan", render_action_plan_html(plan))

    # Economic summary
    if econ_err:
        render_output_card("Economic Summary", f'<div class="warning-box">{econ}<br>Re-run the analysis to retry.</div>')
    else:
        economic_snapshot_html = f"""
        <table class="sensitivity-table" style="margin-bottom:0.9rem;">
            <tr><th>Metric</th><th style="text-align:right;">Value</th></tr>
            <tr><td>Recoverable Revenue</td><td style="text-align:right;">USD {estimated_revenue:,.0f}</td></tr>
            <tr><td>Recovery Assumption</td><td style="text-align:right;">{recovery_pct}%</td></tr>
            <tr><td>Annual Processing Rate</td><td style="text-align:right;">{econ_snapshot["annual_processing_rate"]:,.0f} t/year</td></tr>
            <tr><td>Project Life</td><td style="text-align:right;">{econ_snapshot["project_life_years"]:.1f} years</td></tr>
        </table>
        """
        render_output_card("Economic Summary", economic_snapshot_html + render_model_output_html(econ, mode="economic_summary"))

    st.markdown("""
    <footer>
    TAILINGSVALUE PRO · FOR PRELIMINARY ASSESSMENT ONLY · NOT A SUBSTITUTE FOR PROFESSIONAL ENGINEERING STUDY
    </footer>
    """, unsafe_allow_html=True)
