from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arms_exceptions.app import ProjectConfig, ServiceConfig, SlsConfig


class ConfigTests(unittest.TestCase):
    def test_add_target_with_multiple_services_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".arms-exceptions" / "config.json"
            config = ProjectConfig.empty()

            config.add_or_update_target(
                target_name="ai-service-dev",
                branch="dev",
                default_window="24h",
                services=[
                    ServiceConfig(name="ai-service-dev", region="cn-beijing", pid="pid-1", app_id="app-1"),
                    ServiceConfig(name="ai-service-dev-celery-worker", region="cn-beijing", pid="pid-2", app_id="app-2"),
                ],
            )
            config.save(path)

            loaded = ProjectConfig.load(path)

        target = loaded.get_target("ai-service-dev")
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.branch, "dev")
        self.assertEqual(target.default_window, "24h")
        self.assertEqual([service.name for service in target.services], ["ai-service-dev", "ai-service-dev-celery-worker"])
        self.assertEqual(target.services[0].pid, "pid-1")
        self.assertEqual(target.services[1].app_id, "app-2")

    def test_save_creates_project_gitignore_for_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            config = ProjectConfig.empty()

            config.save(config_path)

            gitignore = config_path.parent / ".gitignore"
            content = gitignore.read_text(encoding="utf-8")

        self.assertIn("data/", content)
        self.assertIn("setup/", content)
        self.assertIn("triage/", content)
        self.assertIn("worktrees/", content)
        self.assertIn("lark-notify.local.json", content)
        self.assertIn("*.sqlite", content)
        self.assertIn("*.sqlite-wal", content)
        self.assertNotIn("config.json", content)

    def test_save_preserves_existing_project_gitignore_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            gitignore = config_path.parent / ".gitignore"
            gitignore.parent.mkdir(parents=True, exist_ok=True)
            gitignore.write_text("custom-local-file\n", encoding="utf-8")

            ProjectConfig.empty().save(config_path)

            content = gitignore.read_text(encoding="utf-8")

        self.assertIn("custom-local-file", content)
        self.assertIn("data/", content)
        self.assertIn("setup/", content)
        self.assertIn("triage/", content)
        self.assertIn("worktrees/", content)
        self.assertIn("lark-notify.local.json", content)
        self.assertIn("*.sqlite3", content)

    def test_existing_target_merges_services_by_default(self) -> None:
        config = ProjectConfig.empty()
        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="24h",
            services=[ServiceConfig(name="ai-service-dev")],
        )

        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="7d",
            services=[ServiceConfig(name="ai-service-dev-celery-worker")],
        )

        target = config.get_target("ai-service-dev")
        assert target is not None
        self.assertEqual(target.default_window, "7d")
        self.assertEqual([service.name for service in target.services], ["ai-service-dev", "ai-service-dev-celery-worker"])

    def test_service_sls_config_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".arms-exceptions" / "config.json"
            config = ProjectConfig.empty()
            config.add_or_update_target(
                target_name="ai-service-dev",
                branch="dev",
                default_window="24h",
                services=[
                    ServiceConfig(
                        name="ai-service-dev",
                        region="cn-beijing",
                        sls=SlsConfig(
                            project="ai-service-logs",
                            logstore="app-log",
                            endpoint="cn-beijing.log.aliyuncs.com",
                            default_before_seconds=180,
                            default_after_seconds=60,
                            default_limit=20,
                        ),
                    )
                ],
            )
            config.save(path)

            loaded = ProjectConfig.load(path)

        target = loaded.get_target("ai-service-dev")
        assert target is not None
        self.assertIsNotNone(target.services[0].sls)
        assert target.services[0].sls is not None
        self.assertEqual(target.services[0].sls.project, "ai-service-logs")
        self.assertEqual(target.services[0].sls.logstore, "app-log")
        self.assertEqual(target.services[0].sls.endpoint, "cn-beijing.log.aliyuncs.com")
        self.assertEqual(target.services[0].sls.default_before_seconds, 180)
        self.assertEqual(target.services[0].sls.default_after_seconds, 60)
        self.assertEqual(target.services[0].sls.default_limit, 20)

    def test_merging_existing_service_preserves_sls_when_new_service_has_none(self) -> None:
        config = ProjectConfig.empty()
        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="24h",
            services=[
                ServiceConfig(
                    name="ai-service-dev",
                    region="cn-beijing",
                    pid="old-pid",
                    sls=SlsConfig(project="ai-service-logs", logstore="app-log", endpoint="cn-beijing.log.aliyuncs.com"),
                )
            ],
        )

        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="24h",
            services=[ServiceConfig(name="ai-service-dev", region="cn-beijing", pid="new-pid")],
        )

        target = config.get_target("ai-service-dev")
        assert target is not None
        self.assertEqual(len(target.services), 1)
        self.assertEqual(target.services[0].pid, "new-pid")
        self.assertIsNotNone(target.services[0].sls)
        assert target.services[0].sls is not None
        self.assertEqual(target.services[0].sls.project, "ai-service-logs")

    def test_replace_target_resets_services(self) -> None:
        config = ProjectConfig.empty()
        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="24h",
            services=[ServiceConfig(name="old")],
        )

        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="main",
            default_window="1h",
            services=[ServiceConfig(name="new")],
            replace=True,
        )

        target = config.get_target("ai-service-dev")
        assert target is not None
        self.assertEqual(target.branch, "main")
        self.assertEqual(target.default_window, "1h")
        self.assertEqual([service.name for service in target.services], ["new"])


if __name__ == "__main__":
    unittest.main()
