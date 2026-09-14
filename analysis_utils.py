import json
import re
from datetime import date
from html import escape


def calculate_sensitivity(gross_value: float):
    """Calculate sensitivity table values — Python does the maths, not the AI."""
    scenarios = [
        ("−20% metal price, −10% grade", 0.80, 0.90),
        ("−20% metal price, base grade",  0.80, 1.00),
        ("Base case",                      1.00, 1.00),
        ("+20% metal price, base grade",   1.20, 1.00),
        ("+20% metal price, +10% grade",   1.20, 1.10),
    ]
    rows = []
    for label, price_mult, grade_mult in scenarios:
        value = gross_value * price_mult * grade_mult
        rows.append({"scenario": label, "value": value, "base": price_mult == 1.0 and grade_mult == 1.0})
    return rows


def extract_json_object(text: str) -> dict:
    """
    Extract the first complete JSON object from a model response.
    Handles nested braces and ignores surrounding prose if present.
    """
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    depth = 0
    in_string = False
    escape = False

    for idx in range(start, len(text)):
        char = text[idx]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:idx + 1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                raise json.JSONDecodeError("JSON payload is not an object", candidate, 0)

    raise json.JSONDecodeError("Incomplete JSON object", text, start)


def parse_custom_metal_prices(custom_prices: str, reference_prices: dict) -> tuple:
    """Apply validated custom-price overrides without mutating the reference set."""
    prices = {key: dict(value) for key, value in reference_prices.items()}
    prices_upper = {key.upper(): key for key in prices}
    errors = []
    seen = set()
    segments = [
        segment.strip()
        for segment in re.split(r"[,;\n]+", custom_prices)
        if segment.strip()
    ]
    price_pattern = re.compile(r"^([A-Za-z]+)\s*:\s*(\d+(?:\.\d+)?)$")

    for segment in segments:
        match = price_pattern.fullmatch(segment)
        if not match:
            errors.append({"entry": segment, "reason": "Use the format SYMBOL: price"})
            continue

        symbol_raw, price_raw = match.groups()
        symbol = symbol_raw.upper()
        if symbol not in prices_upper:
            errors.append({"entry": segment, "reason": f"Metal symbol not recognised: {symbol_raw}"})
            continue
        if symbol in seen:
            errors.append({"entry": segment, "reason": f"Duplicate price for {symbol}"})
            continue

        price = float(price_raw)
        if price <= 0:
            errors.append({"entry": segment, "reason": "Price must be greater than zero"})
            continue

        prices[prices_upper[symbol]]["price"] = price
        seen.add(symbol)

    return prices, errors


def assess_mineralogical_readiness(characterization: dict) -> dict:
    """Assess characterization evidence completeness without inferring recovery."""
    methods = [
        method
        for method in characterization.get("methods", [])
        if method != "Not provided"
    ]
    modal = characterization.get("modal_mineralogy", "Not provided")
    deportment = characterization.get("metal_deportment", "Not provided")
    liberation = characterization.get("liberation", "Not provided")
    spatial = characterization.get("spatial_coverage", "Not provided")

    dimension_scores = {
        "methods": min(len(methods) / 2, 1.0),
        "modal_mineralogy": {
            "Not provided": 0.0,
            "Qualitative mineral identification": 0.5,
            "Quantitative modal mineralogy": 1.0,
        }.get(modal, 0.0),
        "metal_deportment": {
            "Not provided": 0.0,
            "Inferred from mineral names": 0.25,
            "Target-metal hosts identified": 0.65,
            "Quantitative deportment measured": 1.0,
        }.get(deportment, 0.0),
        "liberation": {
            "Not provided": 0.0,
            "Qualitative observations": 0.4,
            "Measured by size fraction": 1.0,
        }.get(liberation, 0.0),
        "spatial_coverage": {
            "Not provided": 0.0,
            "Single sample": 0.25,
            "Multiple locations or depths": 0.65,
            "Representative spatial programme": 1.0,
        }.get(spatial, 0.0),
    }
    score = round(sum(dimension_scores.values()) / len(dimension_scores) * 100)

    gaps = []
    next_steps = []
    if not methods:
        gaps.append("No analytical characterization method is reported.")
        next_steps.append("Record the analytical methods used and their detection or reporting limits.")
    if modal != "Quantitative modal mineralogy":
        gaps.append("Quantitative modal mineral abundances are not available.")
        next_steps.append("Obtain quantitative mineralogy appropriate to the material and target phases.")
    if deportment != "Quantitative deportment measured":
        gaps.append("Target-metal deportment among mineral phases is not quantified.")
        next_steps.append("Measure target-metal deportment rather than inferring hosts from mineral names.")
    if liberation != "Measured by size fraction":
        gaps.append("Liberation and locking are not measured by particle-size fraction.")
        next_steps.append("Characterize liberation, associations, and locking across relevant size fractions.")
    if spatial != "Representative spatial programme":
        gaps.append("Spatial variability and sampling representativeness are not demonstrated.")
        next_steps.append("Design representative sampling across locations, depths, and material domains.")

    if score >= 80:
        status = "Strong characterization evidence"
    elif score >= 50:
        status = "Partial characterization evidence"
    else:
        status = "Initial characterization evidence"

    return {
        "score": score,
        "sub_score": max(1, min(5, (score + 19) // 20)),
        "status": status,
        "methods": methods,
        "gaps": gaps,
        "next_steps": next_steps,
    }


def parse_gross_value_from_grades(grades_text: str, tonnage: float, prices: dict) -> tuple:
    """
    Python calculation of gross in-situ value.
    Accepts multiple grade formats:
      Forward:  Cu: 0.18%  |  Au 0.5 ppm  |  Mo-0.02%
      Reversed: 0.18% Cu   |  500 ppb Au
    Units: %, ppm, g/t, ppb (ppb = 0.001 ppm).
    Returns (total, breakdown, skipped_entries).
    """
    total = 0.0
    breakdown = []
    skipped = []
    matched = set()
    prices_upper = {k.upper(): v for k, v in prices.items()}
    segments = [seg.strip() for seg in re.split(r"[,;\n]+", grades_text) if seg.strip()]

    symbol_first = re.compile(
        r"^([A-Za-z]+)\s*[:\-]?\s*([+-]?\d*\.?\d+)\s*(ppb|ppm|g/t|%)$",
        re.IGNORECASE,
    )
    value_first = re.compile(
        r"^([+-]?\d*\.?\d+)\s*(ppb|ppm|g/t|%)\s+([A-Za-z]+)$",
        re.IGNORECASE,
    )

    for segment in segments:
        match = symbol_first.fullmatch(segment)
        if match:
            metal_raw, value_raw, unit = match.groups()
        else:
            match = value_first.fullmatch(segment)
            if match:
                value_raw, unit, metal_raw = match.groups()
            else:
                skipped.append({
                    "entry": segment,
                    "reason": "Format not recognised",
                })
                continue

        metal = metal_raw.upper()
        if metal not in prices_upper:
            skipped.append({
                "entry": segment,
                "reason": f"Metal symbol not recognised: {metal_raw}",
            })
            continue

        value = float(value_raw)
        if value < 0:
            skipped.append({
                "entry": segment,
                "reason": "Negative grades are not allowed",
            })
            continue

        if metal in matched:
            skipped.append({
                "entry": segment,
                "reason": f"Duplicate entry for {metal}",
            })
            continue

        matched.add(metal)
        unit = unit.lower().strip()
        price_info = prices_upper[metal]
        if unit == "ppb":
            grade_g_per_t = value * 0.001
        elif unit in ("ppm", "g/t"):
            grade_g_per_t = value
        elif unit == "%":
            grade_g_per_t = value * 10000
        else:
            skipped.append({
                "entry": segment,
                "reason": f"Unit not supported: {unit}",
            })
            continue

        contained_metal_g = grade_g_per_t * tonnage
        if price_info["unit"] == "USD/g":
            value_usd = contained_metal_g * price_info["price"]
        else:
            value_usd = (contained_metal_g / 1_000_000) * price_info["price"]
        total += value_usd
        breakdown.append({
            "symbol": price_info.get("name", metal),
            "grade": f"{value} {unit}",
            "value_usd": value_usd,
        })

    return total, breakdown, skipped


def should_block_analysis(parsed_metals: list, skipped_entries: list) -> bool:
    """
    Stop analysis when the grades input is only partially understood.
    This prevents AI outputs from being generated from incomplete economics.
    """
    return bool(parsed_metals) and bool(skipped_entries)


def is_price_reference_stale(reference_date_iso: str, max_age_days: int = 90, today: date | None = None) -> tuple:
    """
    Return (is_stale, age_days) for a YYYY-MM-DD reference date.
    """
    if today is None:
        today = date.today()
    reference_date = date.fromisoformat(reference_date_iso)
    age_days = (today - reference_date).days
    return age_days > max_age_days, age_days


def calculate_economic_snapshot(gross_value: float, recovery_pct: int, tonnage: float) -> dict:
    """
    Deterministic value snapshot used both in the UI and in the model prompt.

    Throughput and project life are not inferred because both require project-
    specific inputs. The recovery percentage remains a screening scenario.
    """
    estimated_revenue = gross_value * (recovery_pct / 100)
    recoverable_value_per_tonne = estimated_revenue / tonnage if tonnage else 0
    return {
        "estimated_revenue": estimated_revenue,
        "recoverable_value_per_tonne": recoverable_value_per_tonne,
    }


def missing_action_plan_phases(text: str) -> list[int]:
    """Return required action-plan phases that are absent from model output."""
    normalized = normalize_model_text(text, mode="action_plan")
    present = {
        int(match)
        for match in re.findall(r"(?im)^\s*Phase\s+([1-2])\s*:", normalized)
    }
    return [phase for phase in range(1, 3) if phase not in present]


def action_plan_validation_issues(text: str) -> list[str]:
    """Return structural issues that make the two-phase screening plan incomplete."""
    normalized = normalize_model_text(text, mode="action_plan")
    issues = [f"missing Phase {phase}" for phase in missing_action_plan_phases(normalized)]
    for phase in range(1, 3):
        phase_match = re.search(
            rf"(?ims)^\s*Phase\s+{phase}\s*:.*?(?=^\s*Phase\s+[1-2]\s*:|\Z)",
            normalized,
        )
        if not phase_match:
            continue
        section = phase_match.group(0)
        if not re.search(r"(?im)^\s*Key activities\s*:", section):
            issues.append(f"Phase {phase} missing Key activities")
        if not re.search(r"(?im)^\s*Key deliverables\s*:", section):
            issues.append(f"Phase {phase} missing Key deliverables")
        if not re.search(rf"(?im)^\s*Decision Gate {phase}\s*:", section):
            issues.append(f"Phase {phase} missing Decision Gate {phase}")
    return issues


def normalize_model_text(text: str, mode: str = "generic") -> str:
    """
    Clean up common model output patterns before rendering.
    """
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*-{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"(?m)^\s*\*\*(Phase\s+[1-2]\s*:[^*]+|Key activities:|Key deliverables:|Decision Gate\s+[1-2]:[^*]+)\*\*\s*$",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )

    if mode == "processing_route":
        labels = [
            "SCREENING STRATEGY:",
            "RECOMMENDED ROUTE:",
            "RATIONALE:",
            "CANDIDATE TESTS:",
            "EXPECTED RECOVERY:",
            "ROUTE SELECTION STATUS:",
            "ALTERNATIVES REJECTED:",
        ]
        for label in labels:
            text = re.sub(
                rf"\*\*\s*{re.escape(label[:-1])}\s*:\s*\*\*",
                label,
                text,
                flags=re.IGNORECASE,
            )
        for label in labels[1:]:
            text = text.replace(f" {label}", f"\n{label}")
            text = text.replace(label, f"\n{label}")
        text = text.lstrip()
    elif mode == "action_plan":
        phase_names = r"Investigation\s*&\s*Sampling|Mineralogical\s+Characterization\s*&\s*Testwork"
        text = re.sub(
            rf"(?m)^\s*([1-2])\.\s+((?:{phase_names})[^\n]*)$",
            r"Phase \1: \2",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            rf"\s+([1-2])\.\s+((?:{phase_names}))",
            r"\nPhase \1: \2",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s+\+\s+", "\n- ", text)
        text = re.sub(r"\s*[*-]\s*(Key activities:)", r"\n\1", text)
        text = re.sub(r"\s*[*-]\s*(Key deliverables:)", r"\n\1", text)
        text = re.sub(r"\s*[*-]\s*(Decision Gate \d+:)", r"\n\1", text)
        text = re.sub(r"\s+(Key activities:)", r"\n\1", text)
        text = re.sub(r"\s+(Key deliverables:)", r"\n\1", text)
        text = re.sub(r"\s+(Decision Gate \d+:)", r"\n\1", text)
        text = re.sub(r"(Key activities:)\s*\n?-?\s*", r"\1\n- ", text)
        text = re.sub(r"(Key deliverables:)\s*\n?-?\s*", r"\1\n- ", text)
        text = re.sub(r"(Decision Gate \d+:)\s*", r"\1 ", text)
        text = text.replace("\n- - ", "\n- ")
        text = text.lstrip()
    elif mode == "economic_summary":
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n([A-Za-z].*?:)\s", r"\n\n\1 ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _format_inline(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_model_output_html(text: str, mode: str = "generic") -> str:
    """
    Render model output into lightweight HTML so the content stays inside the card.
    Supports headings, paragraphs, and simple ordered/unordered lists.
    """
    text = normalize_model_text(text, mode=mode)
    if not text:
        return '<div class="output-copy"><p>No content returned.</p></div>'

    lines = text.split("\n")
    html_parts = ['<div class="output-copy">']
    paragraph = []
    list_items = []
    list_type = None

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph if part.strip())
            if joined:
                html_parts.append(f"<p>{_format_inline(joined)}</p>")
            paragraph = []

    def flush_list():
        nonlocal list_items, list_type
        if list_items:
            tag = "ol" if list_type == "ol" else "ul"
            html_parts.append(f"<{tag}>")
            for item in list_items:
                html_parts.append(f"<li>{_format_inline(item)}</li>")
            html_parts.append(f"</{tag}>")
            list_items = []
            list_type = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = min(len(heading_match.group(1)) + 1, 6)
            html_parts.append(f"<h{level}>{_format_inline(heading_match.group(2).strip())}</h{level}>")
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)$", line)
        if ordered_match:
            flush_paragraph()
            if list_type not in (None, "ol"):
                flush_list()
            list_type = "ol"
            list_items.append(ordered_match.group(1).strip())
            continue

        unordered_match = re.match(r"^[-*•]\s+(.*)$", line)
        if unordered_match:
            flush_paragraph()
            if list_type not in (None, "ul"):
                flush_list()
            list_type = "ul"
            list_items.append(unordered_match.group(1).strip())
            continue

        if list_type:
            list_items[-1] = f"{list_items[-1]} {line}".strip()
        else:
            paragraph.append(line)

    flush_paragraph()
    flush_list()
    html_parts.append("</div>")
    return "".join(html_parts)


def render_key_value_sections(text: str, labels: list[str]) -> str:
    """
    Render label-based sections like processing-route outputs into explicit blocks.
    """
    text = normalize_model_text(text, mode="processing_route")
    positions = []
    for label in labels:
        idx = text.find(label)
        if idx != -1:
            positions.append((idx, label))

    if not positions:
        return render_model_output_html(text, mode="generic")

    positions.sort()
    html_parts = ['<div class="output-copy">']
    for index, (start, label) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        section = text[start:end].strip()
        content = section[len(label):].strip()
        html_parts.append(f'<div class="structured-block"><div class="structured-label">{escape(label.rstrip(":"))}</div>')
        if label in {"CANDIDATE TESTS:", "ALTERNATIVES REJECTED:"}:
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            bullets = []
            paragraph = []
            for line in lines:
                if re.match(r"^[-*•]\s+", line):
                    bullets.append(re.sub(r"^[-*•]\s+", "", line))
                else:
                    paragraph.append(line)
            if paragraph:
                html_parts.append(f"<p>{_format_inline(' '.join(paragraph))}</p>")
            if bullets:
                html_parts.append("<ul>")
                for item in bullets:
                    html_parts.append(f"<li>{_format_inline(item)}</li>")
                html_parts.append("</ul>")
        else:
            html_parts.append(f"<p>{_format_inline(content)}</p>")
        html_parts.append("</div>")
    html_parts.append("</div>")
    return "".join(html_parts)


def render_action_plan_html(text: str) -> str:
    """
    Render action plans with clearer subsection blocks for phases, activities,
    deliverables, and decision gates.
    """
    text = normalize_model_text(text, mode="action_plan")
    if not text:
        return '<div class="output-copy"><p>No content returned.</p></div>'

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    html_parts = ['<div class="output-copy">']
    current_list = []
    in_list = False

    def flush_list():
        nonlocal current_list, in_list
        if current_list:
            html_parts.append("<ul>")
            for item in current_list:
                html_parts.append(f"<li>{_format_inline(item)}</li>")
            html_parts.append("</ul>")
            current_list = []
        in_list = False

    for line in lines:
        if re.match(r"^Phase \d+:", line):
            flush_list()
            html_parts.append(f"<h3>{_format_inline(line)}</h3>")
            continue

        if line in ("Key activities:", "Key deliverables:"):
            flush_list()
            html_parts.append(f'<div class="structured-label">{_format_inline(line.rstrip(":"))}</div>')
            continue

        if re.match(r"^Decision Gate \d+:", line):
            flush_list()
            html_parts.append(f'<div class="structured-label">{_format_inline(line)}</div>')
            continue

        if re.match(r"^[-*•]\s+", line):
            in_list = True
            current_list.append(re.sub(r"^[-*•]\s+", "", line))
            continue

        if in_list:
            current_list[-1] = f"{current_list[-1]} {line}".strip()
        else:
            html_parts.append(f"<p>{_format_inline(line)}</p>")

    flush_list()
    html_parts.append("</div>")
    return "".join(html_parts)
