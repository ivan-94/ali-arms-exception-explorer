from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from arms_exceptions import app


class FakeClient:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def is_installed(self) -> bool:
        return True

    def version(self) -> str:
        return "3.3.18"

    def list_trace_apps(self, *, region: str, search=None, page_size=100, max_pages=20):
        return [
            app.AppInfo(name="ai-service-dev", region=region, pid="pid-1", app_id="app-1", app_type="TRACE"),
            app.AppInfo(name="ai-service-dev-celery-worker", region=region, pid="pid-2", app_id="app-2", app_type="TRACE"),
        ]


class CliTests(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = app.main(argv)
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_config(self, path: Path) -> None:
        config = app.ProjectConfig.empty()
        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="24h",
            services=[app.ServiceConfig(name="ai-service-dev"), app.ServiceConfig(name="ai-service-dev-celery-worker")],
        )
        config.save(path)

    def write_group(self, db_path: Path, group_id: str = "45d39c79b8f10f94") -> None:
        repository = app.TraceRepository(db_path)
        try:
            repository.conn.execute(
                """
                insert into error_groups (
                    group_key, target_name, service_name, operation_name, exception_type, message, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (group_id, "ai-service-dev", "ai-service-dev-celery-worker", "run/task", "ValueError", "boom", app._now()),
            )
            repository.commit()
        finally:
            repository.close()

    def test_no_args_prints_friendly_help(self) -> None:
        code, stdout, stderr = self.run_main([])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("ARMS Exceptions Explorer", stdout)
        self.assertIn("常用流程", stdout)
        self.assertIn("doctor", stdout)
        self.assertIn("sync --target ai-service-dev", stdout)

    def test_subcommand_help_contains_examples(self) -> None:
        code, stdout, stderr = self.run_main(["sync", "--help"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("示例", stdout)
        self.assertIn("--target ai-service-dev", stdout)
        self.assertIn("--max-traces", stdout)

    def test_ambiguous_option_prints_friendly_help(self) -> None:
        code, stdout, stderr = self.run_main(["groups", "--target", "ai-service-dev", "--s"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("参数 --s 不明确", stderr)
        self.assertIn("--service", stderr)
        self.assertIn("--since", stderr)
        self.assertIn("完整帮助", stderr)
        self.assertIn("groups --help", stderr)
        self.assertIn("示例", stderr)

    def test_unknown_command_prints_friendly_help(self) -> None:
        code, stdout, stderr = self.run_main(["bad-command"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("未知命令", stderr)
        self.assertIn("可用命令", stderr)
        self.assertIn("完整帮助", stderr)
        self.assertIn("doctor", stderr)
        self.assertIn("sync", stderr)

    def test_mutually_exclusive_scope_error_prints_help(self) -> None:
        code, stdout, stderr = self.run_main(["groups", "--target", "a", "--service", "b"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("不能和", stderr)
        self.assertIn("完整帮助", stderr)
        self.assertIn("--target", stderr)
        self.assertIn("--service", stderr)

    def test_missing_positional_error_prints_help(self) -> None:
        code, stdout, stderr = self.run_main(["show", "--target", "ai-service-dev"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("缺少必需参数: group_id", stderr)
        self.assertIn("完整帮助", stderr)
        self.assertIn("show <group_id>", stderr)

    def test_unknown_option_error_prints_help(self) -> None:
        code, stdout, stderr = self.run_main(["groups", "--target", "ai-service-dev", "--bad"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("无法识别参数: --bad", stderr)
        self.assertIn("完整帮助", stderr)
        self.assertIn("groups --help", stderr)

    def test_sync_requires_target_or_service_and_lists_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            self.write_config(config_path)

            code, _stdout, stderr = self.run_main(["--config", str(config_path), "sync"])

        self.assertEqual(code, 1)
        self.assertIn("sync 需要指定 --target 或 --service", stderr)
        self.assertIn("ai-service-dev-celery-worker", stderr)
        self.assertIn("下一步", stderr)

    def test_show_uses_unique_group_id_without_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config(config_path)
            self.write_group(db_path)

            code, stdout, stderr = self.run_main(
                ["--config", str(config_path), "--db", str(db_path), "show", "45d39c79b8f10f94"]
            )

        self.assertEqual(code, 0, stderr)
        self.assertIn("group_id: 45d39c79b8f10f94", stdout)
        self.assertIn("target: ai-service-dev", stdout)
        self.assertIn("service: ai-service-dev-celery-worker", stdout)

    def test_show_missing_group_without_scope_guides_sync_not_scope_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config(config_path)

            code, stdout, stderr = self.run_main(["--config", str(config_path), "--db", str(db_path), "show", "missing"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("未找到异常组: missing", stderr)
        self.assertIn("show 会在本地 SQLite 中按 group_id 精确查找", stderr)
        self.assertIn("groups --target ai-service-dev", stderr)
        self.assertIn("sync --target ai-service-dev", stderr)
        self.assertNotIn("show 需要指定 --target 或 --service", stderr)

    def test_init_noninteractive_writes_service_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, stdout, stderr = self.run_main(
                    [
                        "--config",
                        str(config_path),
                        "init",
                        "--target",
                        "ai-service-dev",
                        "--branch",
                        "dev",
                        "--service",
                        "ai-service-dev",
                        "--service",
                        "ai-service-dev-celery-worker",
                    ]
                )

            payload = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0, stderr)
        self.assertIn("已写入配置", stdout)
        self.assertEqual(payload["targets"][0]["services"][0]["pid"], "pid-1")
        self.assertEqual(payload["targets"][0]["services"][1]["app_id"], "app-2")

    def test_doctor_without_config_is_not_ready_and_guides_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, stdout, stderr = self.run_main(["--config", str(config_path), "doctor"])

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertIn("app_list_api: ok", stdout)
        self.assertIn("configured_service_api: not_configured", stdout)
        self.assertIn("下一步", stdout)
        self.assertIn("init", stdout)
        self.assertIn("status: false", stdout)

    def test_next_steps_use_actual_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            argv0 = ".agents/skills/arms-exceptions-explorer/scripts/cli.py"
            with (
                mock.patch.object(app, "build_client", return_value=FakeClient()),
                mock.patch("sys.argv", [argv0, "--config", str(config_path), "doctor"]),
            ):
                code, stdout, _stderr = self.run_main(["--config", str(config_path), "doctor"])

        self.assertEqual(code, 1)
        self.assertIn(f"{argv0} init", stdout)
        self.assertNotIn("python3 skills/arms-exceptions-explorer/scripts/cli.py init", stdout)

    def test_doctor_skip_api_is_ok_without_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, stdout, stderr = self.run_main(["--config", str(config_path), "doctor", "--skip-api"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("app_list_api: skipped", stdout)
        self.assertIn("status: true", stdout)

    def test_aliyun_commands_do_not_include_profile(self) -> None:
        client = app.AliyunCliClient()
        with mock.patch.object(client, "_run_json", return_value={"PageBean": {"TraceApps": []}}) as run_json:
            client.search_trace_apps_by_page(region="cn-beijing", page_number=1, page_size=10)

        command = run_json.call_args.args[0]
        self.assertNotIn("--profile", command)

    def test_sanitize_redacts_sensitive_fields(self) -> None:
        text = "AccessKeyId=abc&SecurityToken=token&Signature=sig Authorization: Bearer aaa"

        sanitized = app._sanitize(text)

        self.assertNotIn("abc", sanitized)
        self.assertNotIn("token", sanitized)
        self.assertNotIn("sig", sanitized)
        self.assertNotIn("aaa", sanitized)


if __name__ == "__main__":
    unittest.main()
