import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "task-skill-router.py"

spec = importlib.util.spec_from_file_location("skill_router", MODULE_PATH)
skill_router = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(skill_router)


def write_skill(root: Path, dirname: str, name: str, description: str, tags: list[str]) -> None:
    skill_dir = root / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f'description: "{description}"',
                f"tags: [{', '.join(tags)}]",
                "---",
                "",
                f"# {name}",
            ]
        ),
        encoding="utf-8",
    )


class SkillRouterTests(unittest.TestCase):
    def test_community_mapping_enriches_installed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            write_skill(
                skills_dir,
                "systematic-debugging",
                "systematic-debugging",
                "Root cause debugging",
                ["investigation"],
            )
            write_skill(
                skills_dir,
                "github-auth",
                "github-auth",
                "GitHub authentication",
                ["auth", "ssh"],
            )
            community = root / "community.yaml"
            community.write_text(
                """
skills:
  systematic-debugging:
    description: "Root cause bugs, failing tests, crashes, errors"
    tags: ["bug", "test", "failure", "fix"]
""".strip(),
                encoding="utf-8",
            )

            result = skill_router.recommend(
                "fix a bug in failing tests",
                skills_dir=str(skills_dir),
                community_path=str(community),
            )

            self.assertTrue(result["matches"])
            self.assertEqual(result["matches"][0]["skill"], "systematic-debugging")
            self.assertTrue(result["matches"][0]["path"].endswith("SKILL.md"))

    def test_config_file_controls_skills_dir_and_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            write_skill(
                skills_dir,
                "design-taste-frontend",
                "design-taste-frontend",
                "Frontend landing page visual design",
                ["ui", "redesign"],
            )
            config = root / "config.yaml"
            config.write_text(
                f"""
skills_dir: "{skills_dir}"
confidence_threshold: 0.05
max_matches: 1
""".strip(),
                encoding="utf-8",
            )

            result = skill_router.recommend(
                "redesign landing page",
                config_path=str(config),
            )

            self.assertEqual(result["num_skills_discovered"], 1)
            self.assertEqual(result["matches"][0]["skill"], "design-taste-frontend")
            self.assertEqual(len(result["matches"]), 1)

    def test_config_file_accepts_multiple_skill_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_skills = root / "codex-skills"
            claude_skills = root / "claude-skills"
            write_skill(
                codex_skills,
                "debug",
                "debug",
                "Root cause bugs and test failures",
                ["debug", "bug"],
            )
            write_skill(
                claude_skills,
                "docs",
                "docs",
                "Write documentation and README files",
                ["docs", "readme"],
            )
            config = root / "config.yaml"
            config.write_text(
                f"""
skills_dirs:
  - "{codex_skills}"
  - "{claude_skills}"
confidence_threshold: 0.01
""".strip(),
                encoding="utf-8",
            )

            result = skill_router.recommend("write README docs", config_path=str(config))

            self.assertEqual(result["num_skills_discovered"], 2)
            self.assertEqual(result["matches"][0]["skill"], "docs")

    def test_high_risk_task_forces_recommend_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            write_skill(
                skills_dir,
                "deploy-helper",
                "deploy-helper",
                "Deploy services",
                ["deploy"],
            )
            config = root / "config.yaml"
            config.write_text(
                f"""
skills_dir: "{skills_dir}"
confidence_threshold: 0.01
mode_overrides:
  deploy-helper: auto-load
""".strip(),
                encoding="utf-8",
            )

            result = skill_router.recommend("deploy config change", config_path=str(config))

            self.assertEqual(result["matches"][0]["skill"], "deploy-helper")
            self.assertEqual(result["matches"][0]["mode"], "recommend")
            self.assertTrue(result["high_risk"])

    def test_missing_community_skill_returns_install_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            skills_dir.mkdir()
            community = root / "community.yaml"
            community.write_text(
                """
skills:
  arxiv:
    description: "Search academic papers and literature"
    tags: ["paper", "research", "literature"]
    install: "Install arxiv into ~/.task-skill-router/skills before literature review tasks."
""".strip(),
                encoding="utf-8",
            )

            result = skill_router.recommend(
                "search research papers",
                skills_dir=str(skills_dir),
                community_path=str(community),
            )

            self.assertEqual(result["matches"][0]["skill"], "arxiv")
            self.assertFalse(result["matches"][0]["installed"])
            self.assertEqual(result["missing_skills"][0]["skill"], "arxiv")
            self.assertIn("Install arxiv", result["matches"][0]["install_hint"])

    def test_cli_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            write_skill(
                skills_dir,
                "docs",
                "docs",
                "Write documentation",
                ["docs", "readme"],
            )
            config = root / "config.yaml"
            config.write_text(
                f'skills_dir: "{skills_dir}"\nconfidence_threshold: 0.01\n',
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(MODULE_PATH), "write docs"],
                check=True,
                capture_output=True,
                env={"TASK_SKILL_ROUTER_CONFIG": str(config)},
                text=True,
            )

            data = json.loads(proc.stdout)
            self.assertEqual(data["matches"][0]["skill"], "docs")

    def test_cli_batch_routes_decomposed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            write_skill(
                skills_dir,
                "debug",
                "debug",
                "Root cause bugs and failing tests",
                ["debug", "bug", "test"],
            )
            community = root / "community.yaml"
            community.write_text(
                """
skills:
  arxiv:
    description: "Search academic papers and literature"
    tags: ["paper", "research", "literature"]
    install: "Install arxiv before literature review tasks."
""".strip(),
                encoding="utf-8",
            )
            config = root / "config.yaml"
            config.write_text(
                f"""
skills_dir: "{skills_dir}"
community_mapping: "{community}"
confidence_threshold: 0.01
""".strip(),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--batch"],
                input="inspect failing tests\nsearch research papers\n",
                check=True,
                capture_output=True,
                env={"TASK_SKILL_ROUTER_CONFIG": str(config)},
                text=True,
            )

            data = json.loads(proc.stdout)
            self.assertTrue(data["batch"])
            self.assertEqual(data["num_tasks"], 2)
            self.assertEqual(data["results"][0]["matches"][0]["skill"], "debug")
            self.assertEqual(data["missing_skills"][0]["skill"], "arxiv")


if __name__ == "__main__":
    unittest.main()
