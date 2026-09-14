# TailingsValue Pro

**Secondary Resource Recovery Evaluator**  
AI-supported analysis via Groq · Built with Streamlit

---

## Overview

TailingsValue Pro is a Streamlit project for early-stage screening of mine tailings reprocessing opportunities. It combines deterministic Python calculations with structured LLM outputs to help a user assess whether historical tailings may be worth investigating for secondary metal recovery.

TailingsValue Pro is designed as a **preliminary assessment tool** for screening and concept evaluation. It is **not** a substitute for metallurgical testwork, engineering design, or a formal feasibility study.

---

## What The App Produces

Given tailings inputs such as source, grades, tonnage, mineralogy, characterization evidence, oxidation state, location, infrastructure, and a recovery scenario, the app generates:

- Screening evidence score out of 100
- Deterministic mineralogical evidence-readiness assessment
- Preliminary technical screening narrative
- Characterization-led comparative testwork strategy
- Two-phase screening investigation plan
- Economic value screen and missing-input assessment
- Gross in-situ value
- Sensitivity analysis

---

## Current Approach

The app uses a hybrid approach:

- **Python** handles the structured parts:
  - grade parsing
  - gross in-situ value calculation
  - indicative recovered-metal-value calculation
  - mineralogical evidence completeness and gap identification
  - sensitivity analysis
  - validation and partial-failure handling
- **Groq / GPT-OSS 120B** handles the narrative parts:
  - preliminary screening explanation
  - comparative testwork context
  - investigation-plan narrative
  - economic interpretation

This makes the app much more reliable than a pure prompt-based implementation while keeping the interface fast and flexible for preliminary screening.

The default model is `openai/gpt-oss-120b`. Scoring uses Groq JSON-schema output, while text renderers normalize common Markdown variations so a model-formatting change does not break the result cards.

---

## Key Improvements In This Version

- Python-backed gross in-situ value calculation
- Parsed metal breakdown shown in the UI
- Skipped / invalid grade-entry feedback
- Recovery assumption controlled by the user
- Safer score handling when model output is malformed
- Partial API failure handling without losing the entire page
- Improved rendering of AI output inside structured result cards
- Streamlit secrets support for the Groq API key
- Lightweight test coverage for the core parsing and formatting helpers

### Mineralogical Characterization Evidence

The structured mineralogical section records completed analytical methods, modal-mineralogy quality, target-metal deportment, liberation evidence, and spatial sampling coverage. These fields produce an evidence-completeness score and a list of gaps. They do not automatically select a process route or predict recovery.

### Built-In Price References

The built-in screening price set was reviewed on **September 14, 2026**. Copper, lead, nickel, zinc, gold, and silver use [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) monthly averages for August 2026, published September 2, 2026. Gold and silver are converted from USD per troy ounce to USD per gram.

Molybdenum and cobalt use 2025 estimates from the [USGS *Mineral Commodity Summaries 2026*](https://pubs.usgs.gov/publication/mcs2026). Lithium uses an elemental-lithium-equivalent proxy derived from the USGS battery-grade lithium carbonate estimate. The aggregate REE value remains a conservative, undifferentiated basket-equivalent screening proxy because an aggregate REE grade has no single defensible market price without element distribution, product basis, specification, and payability.

---

## Project Structure

Core files:

- `app.py` — Streamlit UI and orchestration
- `analysis_utils.py` — parsing, formatting, and deterministic helper logic
- `requirements.txt` — Python dependencies
- `tests/test_analysis_utils.py` — unit tests for helper logic

Excluded locally:

- `venv/`
- `__pycache__/`
- `.streamlit/secrets.toml`

---

## Run Locally

From the project root:

```bash
./venv/bin/python -m streamlit run app.py
```

If you are not using the local virtual environment:

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Example Test Inputs

### Copper Tailings Example

```text
Tailings Source: Copper porphyry flotation tailings
Metal Grades: Cu: 0.18%, Au: 0.5 ppm, Mo: 0.02%
Tonnage Available (tonnes): 5000000
Mineralogy: chalcopyrite, molybdenite, pyrite, quartz
Tailings Age & Oxidation State: Fresh / unoxidised (< 5 years)
Location: Arizona, USA
Infrastructure Available: existing mill, grid power, water access, tailings dam in place
Uniform Screening Recovery: 70%
```

### Small Gold Tailings Example

```text
Tailings Source: Small artisanal gold tailings
Metal Grades: Au: 1.2 ppm
Tonnage Available (tonnes): 12000
Mineralogy: quartz, iron oxides, clay
Tailings Age & Oxidation State: Heavily oxidised / supergene (> 20 years)
Location: Kaduna, Nigeria
Infrastructure Available: dirt road access only
Uniform Screening Recovery: 45%
```

### Polymetallic Tailings Example

```text
Tailings Source: Polymetallic flotation tailings
Metal Grades: Cu: 0.22%, Zn: 0.85%, Pb: 0.30%, Ag: 18 ppm, Au: 0.4 ppm
Tonnage Available (tonnes): 45000000
Mineralogy: chalcopyrite, sphalerite, galena, pyrite, quartz
Tailings Age & Oxidation State: Partially oxidised (5–20 years)
Location: Peru
Infrastructure Available: existing mill, paved road, grid power, water pipeline
Uniform Screening Recovery: 75%
```

---

## Testing

Run the helper tests with:

```bash
python3 -m unittest tests.test_analysis_utils
```

These tests cover:

- JSON extraction
- grade parsing
- skipped-entry handling
- formatting helpers
- economic snapshot helpers

---

## Known Limitations

- The economic output is a value screen, not a profitability or viability conclusion
- Route selection and recovery prediction require representative characterization and metallurgical testwork
- CAPEX, OPEX, throughput, payability, and project life are not inferred when absent
- Model output quality can vary between runs
- The tool assumes user inputs are high-level rather than lab-certified datasets

---

## Disclaimer

**For preliminary assessment only. Not a substitute for metallurgical testwork, professional engineering analysis, or a formal feasibility study.**
