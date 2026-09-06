#!/usr/bin/env python3
"""Behavioural checks for the MA Evolution Engine.

Every test runs against the mock adapter with replayed fixtures, so the whole
suite is offline and costs nothing. It proves the engine's plumbing: that
overlays apply exactly, that each gate fires on the defect it exists to catch
and stays quiet otherwise, that the write boundary holds, that the neutral
band refuses to be guessed, and that nothing spends without confirmation.

It proves nothing about whether an evolved skill writes a better brief. Only a
real runtime can say that, and keeping those two claims apart is the point.
"""
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evolution"))

import yaml  # noqa: E402

from engine import gates, lineage, tournament  # noqa: E402
from engine.adapters.base import Budget  # noqa: E402
from engine.adapters.mock import MockAdapter, MockJudge  # noqa: E402
from engine.cost import BudgetExceeded, Ledger, Preflight  # noqa: E402
from engine.environment import load_all as load_environments  # noqa: E402
from engine.evidence import EvidenceStore, LiveRetrievalBlocked  # noqa: E402
from engine.genome import Genome, Overlay, OverlayError, load_all as load_genomes  # noqa: E402
from engine.paths import LINEAGES, WriteBoundaryError, assert_writable  # noqa: E402

WORKFLOW = "kol-engagement-brief"   # the workflow used for detailed gate tests
BUDGET = Budget()


def active_workflows():
    spec = yaml.safe_load((ROOT / "evolution/registry/workflows.yaml").read_text())
    return [k for k, v in spec["workflows"].items() if v.get("status") == "active"]


def env(env_id):
    return next(e for e in load_environments(WORKFLOW) if e.environment_id == env_id)


def run(genome_id="kol-engagement-brief/g0", env_id="env-01-routine", defects=()):
    g = load_genomes(WORKFLOW)[genome_id]
    return MockAdapter(defects=defects).run(g, env(env_id), BUDGET, seed=0)


class Genomes(unittest.TestCase):
    def test_every_overlay_applies_and_changes_the_skill(self):
        base = (ROOT / "skills/kol-engagement-brief/SKILL.md").read_text()
        for gid, g in load_genomes(WORKFLOW).items():
            text = g.express()
            if g.overlays:
                self.assertNotEqual(text, base, f"{gid} overlay changed nothing")
            else:
                self.assertEqual(text, base)

    def test_a_missing_anchor_is_an_error_not_a_silent_noop(self):
        """An overlay that quietly did nothing would be scored as a neutral
        variant, and the lineage would record a mutation that never happened."""
        o = Overlay("skill_instruction", "test.yaml", "r", "human",
                    [{"op": "replace", "anchor": "NOT IN THE SKILL", "with": "x"}])
        with self.assertRaises(OverlayError):
            o.apply("some skill text")

    def test_an_ambiguous_anchor_is_refused(self):
        o = Overlay("skill_instruction", "test.yaml", "r", "human",
                    [{"op": "replace", "anchor": "the", "with": "x"}])
        with self.assertRaises(OverlayError):
            o.apply("the cat sat on the mat")

    def test_the_null_control_is_cosmetic_only(self):
        g0 = load_genomes(WORKFLOW)[f"{WORKFLOW}/g0"].express()
        g1d = load_genomes(WORKFLOW)[f"{WORKFLOW}/g1d"].express()
        self.assertNotEqual(g0, g1d)
        self.assertLess(abs(len(g1d) - len(g0)), 40,
                        "the null control must not make a substantive change")


class WriteBoundary(unittest.TestCase):
    def test_engine_may_write_to_its_own_trees(self):
        assert_writable(LINEAGES / WORKFLOW / "lineage.jsonl")

    def test_engine_refuses_to_write_to_a_skill(self):
        for forbidden in ("skills/kol-engagement-brief/SKILL.md",
                          "evolution/constitution/immutable.yaml",
                          "evolution/evaluators/global/safety.yaml",
                          "house-rules/kol-engagement-brief.md"):
            with self.assertRaises(WriteBoundaryError, msg=forbidden):
                assert_writable(ROOT / forbidden)


class Gates(unittest.TestCase):
    def test_a_clean_run_passes_every_gate(self):
        for e in load_environments(WORKFLOW):
            ph = run(env_id=e.environment_id)
            results = gates.run_gates(ph, e)
            failed = [(r.gate, r.findings) for r in results if not r.passed]
            self.assertEqual(failed, [], f"{e.environment_id}: {failed}")

    def test_fabricated_citation_is_extinct(self):
        e = env("env-01-routine")
        r = gates.citation_gate(run(defects=("citation",)), e)
        self.assertFalse(r.passed)
        self.assertEqual(r.outcome, "extinct")
        self.assertTrue(any("99999999" in f for f in r.findings))

    def test_missed_safety_escalation_is_extinct(self):
        e = env("env-02-buried-ae")
        r = gates.safety_gate(run(env_id="env-02-buried-ae", defects=("safety",)), e)
        self.assertFalse(r.passed)
        self.assertEqual(r.outcome, "extinct")
        self.assertTrue(any("ae-grade3-infection" in f for f in r.findings))

    def test_the_ae_environment_actually_contains_the_ae(self):
        """Guards the answer key itself: a must_escalate item whose source text
        is not in the material would make the gate unpassable."""
        e = env("env-02-buried-ae")
        source = e.source_text().lower()
        self.assertIn("grade 3 infection", source)
        self.assertIn("int-2026-014", source)

    def test_unrouted_offlabel_question_is_extinct(self):
        e = env("env-03-offlabel-question")
        r = gates.boundaries_gate(
            run(env_id="env-03-offlabel-question", defects=("boundaries",)), e)
        self.assertFalse(r.passed)
        self.assertEqual(r.outcome, "extinct")

    def test_forbidden_commercial_content_is_extinct(self):
        e = env("env-01-routine")
        ph = run()
        ph.artifact += "\n\nInfluence tier: Tier 1. Prescribing volume trend: up.\n"
        r = gates.boundaries_gate(ph, e)
        self.assertFalse(r.passed)
        self.assertIn("influence tiering", " ".join(r.findings))
        self.assertIn("prescribing data", " ".join(r.findings))

    def test_missing_provenance_is_extinct(self):
        e = env("env-01-routine")
        r = gates.provenance_gate(run(defects=("provenance",)), e)
        self.assertFalse(r.passed)

    def test_unsurfaced_expectation_is_extinct(self):
        e = env("env-04-publication-delta")
        r = gates.science_gate(
            run(env_id="env-04-publication-delta", defects=("science",)), e)
        self.assertFalse(r.passed)

    def test_efficacy_figure_without_design_is_caught(self):
        e = env("env-01-routine")
        ph = run()
        ph.artifact += ("\n\n## LATE ADDITION\n\nThe response rate was 62.5% and "
                        "patients did well over a long period of observation "
                        "with encouraging results reported throughout.\n")
        r = gates.science_gate(ph, e)
        self.assertFalse(r.passed)
        self.assertIn("without design or denominator", " ".join(r.findings))

    def test_a_standing_ae_obligation_is_not_a_fabricated_finding(self):
        """"Any adverse event identified must be reported" is policy text that
        belongs in the deliverable. Firing on it would teach the engine to
        strip a required boundary statement to get past the safety gate."""
        e = env("env-01-routine")
        ph = run()
        ph.artifact += ("\n- Any adverse event identified in this material must "
                        "be reported through the standard route.\n")
        self.assertTrue(gates.safety_gate(ph, e).passed)

    def test_fabricated_safety_finding_is_caught(self):
        """Inventing an AE to look vigilant is a failure, not a safe default."""
        e = env("env-01-routine")
        self.assertEqual(e.expectations.must_escalate, [])
        ph = run()
        ph.artifact += "\n\nAn adverse event was identified in the notes.\n"
        r = gates.safety_gate(ph, e)
        self.assertFalse(r.passed)
        self.assertIn("fabricated", " ".join(r.findings))


class Evidence(unittest.TestCase):
    def test_tools_serve_only_the_authored_corpus(self):
        e = env("env-01-routine")
        store = EvidenceStore(e.evidence)
        out = store.call("pubmed_search", {"query": "discontinuation", "limit": 5})
        self.assertTrue(out["results"])
        for r in out["results"]:
            self.assertIn(str(r["pmid"]), store.known_ids())
        self.assertEqual(store.calls[0]["source"], "fixture")

    def test_live_mode_is_refused_for_a_synthetic_environment(self):
        store = EvidenceStore(env("env-01-routine").evidence, mode="live")
        with self.assertRaises(LiveRetrievalBlocked):
            store.call("pubmed_search", {"query": "x"})

    def test_the_delta_environment_carries_the_new_publication(self):
        ids = EvidenceStore(env("env-04-publication-delta").evidence).known_ids()
        base = EvidenceStore(env("env-01-routine").evidence).known_ids()
        self.assertIn("900004411", ids)
        self.assertNotIn("900004411", base)


class Tournament(unittest.TestCase):
    def test_blinding_strips_candidate_identity(self):
        text = "<!-- mock-quality: 0.7 -->\ngenome_id: g1a\nBrief body."
        out = tournament.blind(text)
        self.assertNotIn("mock-quality", out)
        self.assertNotIn("g1a", out)
        self.assertIn("Brief body.", out)

    def test_band_refuses_too_few_runs(self):
        e = env("env-01-routine")
        runs = {e.environment_id: [run(), run()]}
        with self.assertRaises(ValueError):
            tournament.measure_neutral_band(MockJudge(), runs, {e.environment_id: e}, "p")

    def test_a_genome_does_not_beat_itself_outside_the_band(self):
        """The null hypothesis. If this fails, every result is noise."""
        envs = {e.environment_id: e for e in load_environments(WORKFLOW)}
        runs = {eid: [MockAdapter().run(load_genomes(WORKFLOW)[f"{WORKFLOW}/g0"],
                                        e, BUDGET, seed) for seed in range(4)]
                for eid, e in envs.items()}
        band = tournament.measure_neutral_band(MockJudge(), runs, envs, "p")
        t = tournament.run_tournament(MockJudge(), runs, runs, envs, "p",
                                      "a", "b", repetitions=3)
        self.assertEqual(t.classify(band["value"]), "neutral")

    def test_boundary_win_rate_is_neutral_not_better(self):
        t = tournament.TournamentResult("c", "o")
        m = tournament.Matchup("c", "o", "e")
        m.wins, m.losses = 5, 1          # 5/6
        t.matchups.append(m)
        self.assertEqual(t.classify(1 / 3), "neutral")


class Cost(unittest.TestCase):
    def _preflight(self, **kw):
        est = MockAdapter().estimate(
            load_genomes(WORKFLOW)[f"{WORKFLOW}/g0"], env("env-01-routine"), BUDGET)
        return Preflight(runs=10, per_run=est, **kw)

    def test_nothing_runs_without_confirmation(self):
        pre = self._preflight()
        self.assertFalse(pre.confirm(assume_yes=False, stream=io.StringIO()))

    def test_estimate_over_ceiling_is_refused(self):
        pre = self._preflight(max_usd=1.0)
        with self.assertRaises(BudgetExceeded):
            pre.check_ceiling()

    def test_ledger_aborts_when_the_ceiling_is_reached(self):
        ledger = Ledger(max_usd=1.0)
        ledger.charge(0.65)
        with self.assertRaises(BudgetExceeded):
            ledger.charge(0.65)

    def test_actuals_are_recorded_against_the_estimate(self):
        ledger = Ledger(estimate_usd=10.0)
        for _ in range(10):
            ledger.charge(0.65)
        d = ledger.to_dict()
        self.assertAlmostEqual(d["actual_usd"], 6.5)
        self.assertAlmostEqual(d["estimate_error"], -0.35, places=2)


class Budgets(unittest.TestCase):
    def test_a_run_that_overruns_reports_it_rather_than_hiding_it(self):
        g = load_genomes(WORKFLOW)[f"{WORKFLOW}/g0"]
        ph = MockAdapter().run(g, env("env-01-routine"),
                               Budget(max_external_queries=1), seed=0)
        self.assertEqual(ph.outcome, "budget_exceeded")
        self.assertEqual(ph.budget_breach["limit"], "max_external_queries")


class Environments(unittest.TestCase):
    def test_every_environment_loads_with_its_answer_key(self):
        envs = load_environments(WORKFLOW)
        self.assertGreaterEqual(len(envs), 4)
        for e in envs:
            self.assertTrue(e.target_expert)
            self.assertTrue(e.situation)
            self.assertIsInstance(e.evidence.get("publications"), list)
            self.assertEqual(e.expectations.environment_id, e.environment_id)

    def test_expectation_ids_are_unique_within_an_environment(self):
        for wf in active_workflows():
          for e in load_environments(wf):
            ids = [i["id"] for group in (e.expectations.must_surface,
                                         e.expectations.must_not_say,
                                         e.expectations.must_escalate,
                                         e.expectations.must_route)
                   for i in group]
            self.assertEqual(len(ids), len(set(ids)), e.environment_id)

    def test_source_material_is_marked_synthetic(self):
        for e in load_environments(WORKFLOW):
            self.assertIn("SYNTHETIC", e.source_text().upper(), e.environment_id)

    def test_every_gate_is_exercised_by_at_least_one_environment(self):
        """A gate no environment can trip is a gate nobody has tested."""
        envs = load_environments(WORKFLOW)
        self.assertTrue(any(e.expectations.must_escalate for e in envs), "safety")
        self.assertTrue(any(e.expectations.must_route for e in envs), "boundaries")
        self.assertTrue(any(e.expectations.must_surface for e in envs), "science")
        self.assertTrue(any(e.expectations.must_not_say for e in envs), "science")


class EveryWorkflow(unittest.TestCase):
    """Structural checks that must hold for every active workflow.

    The engine is meant to be workflow-agnostic. These run across all of them
    so that a workflow wired up incorrectly fails here rather than during a
    campaign that has already spent money.
    """

    def test_at_least_two_workflows_are_active(self):
        """One active workflow cannot show whether the engine generalises."""
        self.assertGreaterEqual(len(active_workflows()), 2)

    def test_every_active_workflow_is_completely_wired(self):
        for wf in active_workflows():
            with self.subTest(workflow=wf):
                genomes = load_genomes(wf)
                envs = load_environments(wf)
                self.assertIn(f"{wf}/g0", genomes, "no ancestor")
                self.assertGreaterEqual(len(genomes), 3, "needs candidates")
                self.assertGreaterEqual(len(envs), 2, "needs environments")
                for name in ("profile.yaml", "pairwise.yaml", "rubric.yaml"):
                    self.assertTrue(
                        (ROOT / "evolution/evaluators/workflows" / wf / name).exists(),
                        f"missing {name}")

    def test_every_overlay_applies_in_every_workflow(self):
        for wf in active_workflows():
            base = (ROOT / f"skills/{wf}/SKILL.md").read_text()
            for gid, g in load_genomes(wf).items():
                with self.subTest(genome=gid):
                    text = g.express()          # raises if an anchor is missing
                    if g.overlays:
                        self.assertNotEqual(text, base, "overlay changed nothing")

    def test_every_workflow_has_a_null_control(self):
        """Without one, a broken evaluator is invisible."""
        for wf in active_workflows():
            with self.subTest(workflow=wf):
                nulls = [g for g in load_genomes(wf).values()
                         if g.overlays and "null candidate" in g.overlays[0].rationale]
                self.assertTrue(nulls, "no null control genome")
                base = (ROOT / f"skills/{wf}/SKILL.md").read_text()
                self.assertLess(abs(len(nulls[0].express()) - len(base)), 40,
                                "the null control makes a substantive change")

    def test_a_clean_run_passes_every_gate_in_every_workflow(self):
        for wf in active_workflows():
            genome = load_genomes(wf)[f"{wf}/g0"]
            for e in load_environments(wf):
                with self.subTest(workflow=wf, environment=e.environment_id):
                    ph = MockAdapter().run(genome, e, BUDGET, seed=0)
                    failed = [(r.gate, r.findings)
                              for r in gates.run_gates(ph, e) if not r.passed]
                    self.assertEqual(failed, [], f"{failed}")

    def test_every_workflow_declares_a_valid_profile(self):
        from engine.profiles import ALL_BOUNDARIES, load as load_profile
        for wf in active_workflows():
            with self.subTest(workflow=wf):
                p = load_profile(wf)
                self.assertTrue(p.sections, "profile declares no output sections")
                for b in p.required_boundaries:
                    self.assertIn(b, ALL_BOUNDARIES)

    def test_source_material_is_marked_synthetic_everywhere(self):
        for wf in active_workflows():
            for e in load_environments(wf):
                with self.subTest(workflow=wf, environment=e.environment_id):
                    self.assertIn("SYNTHETIC", e.source_text().upper())

    def test_registry_purpose_and_invariants_are_present(self):
        spec = yaml.safe_load((ROOT / "evolution/registry/workflows.yaml").read_text())
        for wf in active_workflows():
            with self.subTest(workflow=wf):
                entry = spec["workflows"][wf]
                self.assertTrue(entry["purpose"]["statement"].strip())
                self.assertEqual(entry["purpose"]["mutation"], "governed")
                self.assertGreaterEqual(len(entry.get("invariants", [])), 3)


class Promotion(unittest.TestCase):
    def test_proposals_from_different_workflows_do_not_collide(self):
        """Every workflow's first champion is called g1a. Keying the output
        directory on the genome id alone put five proposals in one place and
        left only the last one."""
        import subprocess
        seen = set()
        for wf in active_workflows():
            r = subprocess.run([sys.executable, str(ROOT / "scripts/promote.py"), wf],
                               capture_output=True, text=True)
            if "PROMOTION PROPOSAL" not in r.stdout:
                continue        # no champion recorded yet in this checkout
            path = next(l.split()[-1] for l in r.stdout.splitlines()
                        if "proposal.patch" in l)
            self.assertNotIn(path, seen, f"{wf} reused another workflow's path")
            seen.add(path)


class Constitution(unittest.TestCase):
    def test_level_zero_paths_are_declared_unwritable(self):
        spec = yaml.safe_load((ROOT / "evolution/constitution/immutable.yaml").read_text())
        forbidden = set(spec["engine_permissions"]["forbidden_write"])
        for path in ("skills/", "evolution/constitution/", "evolution/evaluators/global/"):
            self.assertIn(path, forbidden)

    def test_promotion_requires_a_human_merge(self):
        spec = yaml.safe_load((ROOT / "evolution/constitution/immutable.yaml").read_text())
        self.assertIs(spec["promotion"]["requires_human_merge"], True)

    def test_candidates_are_invisible_to_skill_discovery(self):
        """The structural property that stops a mutated skill becoming installable."""
        src = (ROOT / "scripts/validate_skills.py").read_text()
        self.assertNotIn("evolution", src)
        catalog = json.loads((ROOT / "workshop/catalog.json").read_text())
        self.assertNotIn("evolution", json.dumps(catalog))


class Lineage(unittest.TestCase):
    def test_records_append_and_the_tree_roots_orphans(self):
        import tempfile
        from engine import paths
        with tempfile.TemporaryDirectory() as tmp:
            original = paths.LINEAGES
            try:
                paths.LINEAGES = Path(tmp)
                lineage.LINEAGES = Path(tmp)
                paths.WRITABLE = (Path(tmp),)
                lineage.record("w", {"genome_id": "w/g1a", "parent": "w/g0",
                                     "generation": 1, "verdict": "champion"})
                self.assertIn("g1a", lineage.tree("w"))
                self.assertEqual(len(lineage.read("w")), 1)
                self.assertEqual(lineage.champion("w"), "w/g1a")
            finally:
                paths.LINEAGES = original
                lineage.LINEAGES = original
                paths.WRITABLE = (original, paths.EXPERIMENTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
