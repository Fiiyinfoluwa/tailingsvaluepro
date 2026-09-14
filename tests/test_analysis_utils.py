import json
import unittest
from datetime import date

from analysis_utils import (
    action_plan_validation_issues,
    assess_mineralogical_readiness,
    calculate_economic_snapshot,
    extract_json_object,
    is_price_reference_stale,
    parse_custom_metal_prices,
    parse_gross_value_from_grades,
    render_action_plan_html,
    render_key_value_sections,
    render_model_output_html,
    should_block_analysis,
)


METAL_PRICES = {
    "Cu":  {"price": 9200, "unit": "USD/t", "name": "Copper"},
    "Au":  {"price": 65, "unit": "USD/g", "name": "Gold"},
    "Mo":  {"price": 55000, "unit": "USD/t", "name": "Molybdenum"},
    "REE": {"price": 2500, "unit": "USD/t", "name": "Rare Earth Elements"},
}


class ExtractJsonObjectTests(unittest.TestCase):
    def test_parses_plain_json_object(self):
        result = extract_json_object('{"grade": 3, "tonnage": 4}')
        self.assertEqual(result["grade"], 3)
        self.assertEqual(result["tonnage"], 4)

    def test_parses_json_wrapped_in_prose(self):
        result = extract_json_object('Here is the score {"grade": 3, "tonnage": 4}')
        self.assertEqual(result["grade"], 3)
        self.assertEqual(result["tonnage"], 4)

    def test_parses_nested_json_object(self):
        payload = '{"grade": 3, "explanation": {"note": "low grade"}}'
        result = extract_json_object(payload)
        self.assertEqual(result["grade"], 3)
        self.assertEqual(result["explanation"]["note"], "low grade")

    def test_raises_when_no_json_object_exists(self):
        with self.assertRaises(json.JSONDecodeError):
            extract_json_object("No structured data returned")


class ParseCustomMetalPricesTests(unittest.TestCase):
    def test_overrides_prices_without_mutating_reference_set(self):
        prices, errors = parse_custom_metal_prices("Mo: 60000, Cu: 9800", METAL_PRICES)

        self.assertEqual(errors, [])
        self.assertEqual(prices["Mo"]["price"], 60000)
        self.assertEqual(prices["Cu"]["price"], 9800)
        self.assertEqual(METAL_PRICES["Mo"]["price"], 55000)

    def test_rejects_malformed_unknown_and_nonpositive_prices(self):
        _, errors = parse_custom_metal_prices("Mo 60000, Xx: 10, Au: 0", METAL_PRICES)

        self.assertEqual(len(errors), 3)
        self.assertEqual(errors[0]["reason"], "Use the format SYMBOL: price")
        self.assertEqual(errors[1]["reason"], "Metal symbol not recognised: Xx")
        self.assertEqual(errors[2]["reason"], "Price must be greater than zero")


class MineralogicalReadinessTests(unittest.TestCase):
    def test_empty_characterization_is_initial_evidence(self):
        result = assess_mineralogical_readiness({})

        self.assertEqual(result["score"], 0)
        self.assertEqual(result["sub_score"], 1)
        self.assertEqual(result["status"], "Initial characterization evidence")
        self.assertEqual(len(result["gaps"]), 5)

    def test_complete_characterization_is_strong_evidence(self):
        result = assess_mineralogical_readiness({
            "methods": ["XRD", "QEMSCAN / MLA"],
            "modal_mineralogy": "Quantitative modal mineralogy",
            "metal_deportment": "Quantitative deportment measured",
            "liberation": "Measured by size fraction",
            "spatial_coverage": "Representative spatial programme",
        })

        self.assertEqual(result["score"], 100)
        self.assertEqual(result["sub_score"], 5)
        self.assertEqual(result["status"], "Strong characterization evidence")
        self.assertEqual(result["gaps"], [])


class ParseGrossValueFromGradesTests(unittest.TestCase):
    def test_parses_supported_formats_and_returns_breakdown(self):
        total, breakdown, skipped = parse_gross_value_from_grades(
            "Cu: 0.18%, 500 ppb Au, Mo-0.02%",
            5_000_000,
            METAL_PRICES,
        )
        self.assertGreater(total, 0)
        self.assertEqual(len(breakdown), 3)
        self.assertEqual(skipped, [])

    def test_reports_unrecognised_and_duplicate_entries(self):
        total, breakdown, skipped = parse_gross_value_from_grades(
            "Cu: 0.18%, copper 0.18 percent, Cu: 0.20%",
            1_000_000,
            METAL_PRICES,
        )
        self.assertGreater(total, 0)
        self.assertEqual(len(breakdown), 1)
        reasons = [item["reason"] for item in skipped]
        self.assertIn("Format not recognised", reasons)
        self.assertIn("Duplicate entry for CU", reasons)

    def test_rejects_negative_grades(self):
        total, breakdown, skipped = parse_gross_value_from_grades(
            "Au: -0.5 ppm",
            1_000_000,
            METAL_PRICES,
        )
        self.assertEqual(total, 0)
        self.assertEqual(breakdown, [])
        self.assertEqual(skipped[0]["reason"], "Negative grades are not allowed")

    def test_returns_zero_when_nothing_is_recognised(self):
        total, breakdown, skipped = parse_gross_value_from_grades(
            "Rare Earth: 150 ppm",
            1_000_000,
            METAL_PRICES,
        )
        self.assertEqual(total, 0)
        self.assertEqual(breakdown, [])
        self.assertEqual(skipped[0]["reason"], "Format not recognised")


class ShouldBlockAnalysisTests(unittest.TestCase):
    def test_blocks_when_some_entries_parse_and_some_are_skipped(self):
        self.assertTrue(
            should_block_analysis(
                [{"symbol": "Copper", "grade": "0.18 %", "value_usd": 16560}],
                [{"entry": "Rare Earth: 150 ppm", "reason": "Format not recognised"}],
            )
        )

    def test_allows_when_everything_parses_cleanly(self):
        self.assertFalse(
            should_block_analysis(
                [{"symbol": "Copper", "grade": "0.18 %", "value_usd": 16560}],
                [],
            )
        )

    def test_allows_when_nothing_parses_because_zero_case_is_handled_elsewhere(self):
        self.assertFalse(should_block_analysis([], [{"entry": "bad", "reason": "Format not recognised"}]))


class PriceReferenceStaleTests(unittest.TestCase):
    def test_marks_recent_reference_as_not_stale(self):
        is_stale, age_days = is_price_reference_stale("2026-03-01", today=date(2026, 3, 29))
        self.assertFalse(is_stale)
        self.assertEqual(age_days, 28)

    def test_marks_old_reference_as_stale(self):
        is_stale, age_days = is_price_reference_stale("2025-10-01", today=date(2026, 3, 29))
        self.assertTrue(is_stale)
        self.assertEqual(age_days, 179)


class EconomicSnapshotTests(unittest.TestCase):
    def test_calculates_value_without_inventing_throughput(self):
        snapshot = calculate_economic_snapshot(300_300_000, 70, 5_000_000)
        self.assertEqual(snapshot["estimated_revenue"], 210_210_000)
        self.assertEqual(snapshot["recoverable_value_per_tonne"], 42.042)
        self.assertNotIn("annual_processing_rate", snapshot)
        self.assertNotIn("project_life_years", snapshot)


class RenderModelOutputHtmlTests(unittest.TestCase):
    def test_renders_headings_paragraphs_and_lists(self):
        html = render_model_output_html(
            "# Heading\n\nParagraph text.\n- First point\n- Second point"
        )
        self.assertIn("<h2>Heading</h2>", html)
        self.assertIn("<p>Paragraph text.</p>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>First point</li>", html)

    def test_normalizes_processing_route_labels(self):
        html = render_model_output_html(
            "RECOMMENDED ROUTE: Flotation RATIONALE: Best fit EXPECTED RECOVERY: 70-85%",
            mode="processing_route",
        )
        self.assertIn("<p>RECOMMENDED ROUTE: Flotation</p>", html)
        self.assertIn("<p>RATIONALE: Best fit</p>", html)

    def test_normalizes_economic_summary_numbering(self):
        html = render_model_output_html(
            "1. CAPEX estimate range: USD 50M\n2. OPEX estimate: USD 10/t",
            mode="economic_summary",
        )
        self.assertIn("<p>CAPEX estimate range: USD 50M</p>", html)
        self.assertIn("<p>OPEX estimate: USD 10/t</p>", html)

    def test_removes_horizontal_rules_and_supports_italic_text(self):
        html = render_model_output_html("Intro\n---\n*Evidence note*<br>Next line")

        self.assertNotIn("---", html)
        self.assertIn("<em>Evidence note</em>", html)
        self.assertIn("Next line", html)


class RenderKeyValueSectionsTests(unittest.TestCase):
    def test_renders_processing_route_sections_as_structured_blocks(self):
        html = render_key_value_sections(
            "RECOMMENDED ROUTE: Flotation\nRATIONALE: Best fit\nEXPECTED RECOVERY: 70-85%\nALTERNATIVES REJECTED:\n- Gravity: too fine",
            ["RECOMMENDED ROUTE:", "RATIONALE:", "EXPECTED RECOVERY:", "ALTERNATIVES REJECTED:"],
        )
        self.assertIn("structured-label", html)
        self.assertIn("RECOMMENDED ROUTE", html)
        self.assertIn("<li>Gravity: too fine</li>", html)

    def test_normalizes_gpt_oss_bold_labels(self):
        html = render_key_value_sections(
            "**SCREENING STRATEGY:** Comparative testwork "
            "**RATIONALE:** Evidence first "
            "**CANDIDATE TESTS:**\n- Deportment study "
            "**ROUTE SELECTION STATUS:** Deferred",
            ["SCREENING STRATEGY:", "RATIONALE:", "CANDIDATE TESTS:", "ROUTE SELECTION STATUS:"],
        )

        self.assertIn("SCREENING STRATEGY", html)
        self.assertIn("<li>Deportment study</li>", html)
        self.assertIn("Deferred", html)


class RenderActionPlanHtmlTests(unittest.TestCase):
    def test_renders_phase_subsections_cleanly(self):
        html = render_action_plan_html(
            "Phase 1: Investigation & Sampling (6 months)\n"
            "Key activities:\n"
            "- Desk study\n"
            "- Site visit\n"
            "Key deliverables:\n"
            "- Sampling report\n"
            "Decision Gate 1: Proceed if economics are viable"
        )
        self.assertIn("<h3>Phase 1: Investigation &amp; Sampling (6 months)</h3>", html)
        self.assertIn("structured-label", html)
        self.assertIn("<li>Desk study</li>", html)
        self.assertIn("<li>Sampling report</li>", html)
        self.assertIn("Decision Gate 1: Proceed if economics are viable", html)

    def test_splits_inline_key_deliverables_out_of_previous_bullet(self):
        html = render_action_plan_html(
            "Phase 2: Metallurgical Testwork (9 months)\n"
            "* Key activities:\n"
            "- Development of a preliminary process flow diagram * Key deliverables:\n"
            "- Metallurgical testwork report"
        )
        self.assertIn('<div class="structured-label">Key activities</div>', html)
        self.assertIn('<div class="structured-label">Key deliverables</div>', html)
        self.assertIn("<li>Development of a preliminary process flow diagram</li>", html)
        self.assertIn("<li>Metallurgical testwork report</li>", html)

    def test_converts_plus_delimiters_into_clean_lists(self):
        html = render_action_plan_html(
            "Phase 1: Investigation & Sampling (6 months)\n"
            "Key activities: + Conduct sampling + Review data\n"
            "Key deliverables: + Report + Plan"
        )
        self.assertIn("<li>Conduct sampling</li>", html)
        self.assertIn("<li>Review data</li>", html)
        self.assertIn("<li>Report</li>", html)
        self.assertIn("<li>Plan</li>", html)

    def test_normalizes_numbered_gpt_oss_phases(self):
        html = render_action_plan_html(
            "1. Investigation & Sampling (3 months)\n"
            "Key activities:\n- Review records\n"
            "Key deliverables:\n- Sampling plan\n"
            "Decision Gate 1: Representative samples available\n"
            "2. Mineralogical Characterization & Testwork (4 months)\n"
            "Key activities:\n- Measure deportment\n"
            "Key deliverables:\n- Characterization report\n"
            "Decision Gate 2: Evidence supports a separate feasibility study"
        )

        self.assertIn("<h3>Phase 1: Investigation &amp; Sampling (3 months)</h3>", html)
        self.assertIn("<h3>Phase 2: Mineralogical Characterization &amp; Testwork (4 months)</h3>", html)

    def test_detects_an_incomplete_two_phase_plan(self):
        incomplete = (
            "Phase 1: Investigation & Sampling\n"
            "Key activities:\n- Sample\n"
            "Key deliverables:\n- Plan\n"
            "Decision Gate 1: Proceed"
        )

        self.assertIn("missing Phase 2", action_plan_validation_issues(incomplete))


if __name__ == "__main__":
    unittest.main()
