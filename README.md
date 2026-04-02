# TailingsValue Pro

**Secondary Resource Recovery Evaluator**  
Powered by Llama 3.3 70b via Groq · Built with Streamlit

---

## Overview

TailingsValue Pro is a Streamlit project for early-stage screening of mine tailings reprocessing opportunities. It combines deterministic Python calculations with structured LLM outputs to help a user assess whether historical tailings may be worth investigating for secondary metal recovery.

TailingsValue Pro is designed as a **preliminary assessment tool** for screening and concept evaluation. It is **not** a substitute for metallurgical testwork, engineering design, or a formal feasibility study.

---

## What The App Produces

Given tailings inputs such as source, grades, tonnage, mineralogy, oxidation state, location, infrastructure, and recovery assumption, the app generates:

- Feasibility score out of 100
- Technical feasibility assessment
- Recommended processing route
- Phased action plan
- Economic summary
- Gross in-situ value
- Sensitivity analysis

---

## Current Approach

The app uses a hybrid approach:

- **Python** handles the structured parts:
  - grade parsing
  - gross in-situ value calculation
  - recoverable revenue calculation
  - sensitivity analysis
  - validation and partial-failure handling
- **Groq / Llama 3.3 70b** handles the narrative parts:
  - feasibility explanation
  - processing route explanation
  - action plan narrative
  - economic interpretation

This makes the app much more reliable than a pure prompt-based implementation while keeping the interface fast and flexible for preliminary screening.

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

## Configure The Groq API Key

This app now reads the API key from **Streamlit secrets**.

For local use, create:

```text
.streamlit/secrets.toml
```

With:

```toml
GROQ_API_KEY = "gsk_..."
```

For Streamlit Community Cloud, add the same key in:

`App Settings -> Secrets`

The app will not ask end users to paste an API key.

---

## Deploy To Streamlit Community Cloud

### 1. Push The Project To GitHub

Make sure your repository includes:

- `app.py`
- `analysis_utils.py`
- `requirements.txt`
- `README.md`
- `tests/test_analysis_utils.py`

Do **not** commit:

- `venv/`
- `__pycache__/`
- `.streamlit/secrets.toml`

### 2. Create The App In Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **New app**
4. Select your repository
5. Choose branch `main`
6. Set the main file path to `app.py`
7. Click **Deploy**

### 3. Add Secrets

In the deployed app:

1. Open **Settings**
2. Open **Secrets**
3. Add:

   ```toml
   GROQ_API_KEY = "gsk_..."
   ```

4. Save and redeploy if needed

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
Recovery Assumption: 70%
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
Recovery Assumption: 45%
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
Recovery Assumption: 75%
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

- The economic summary is still partly narrative and should be treated as indicative
- Capital and operating cost logic is still screening-level, not engineering-grade
- Model output quality can vary between runs
- The tool assumes user inputs are high-level rather than lab-certified datasets

---

## Disclaimer

**For preliminary assessment only. Not a substitute for metallurgical testwork, professional engineering analysis, or a formal feasibility study.**
