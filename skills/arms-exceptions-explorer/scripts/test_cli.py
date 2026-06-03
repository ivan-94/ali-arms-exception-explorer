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
    def __init__(self, *, arms_sls_config=None) -> None:
        self.commands: list[str] = []
        self.sls_queries: list[dict[str, object]] = []
        self.arms_sls_config = arms_sls_config

    def is_installed(self) -> bool:
        return True

    def version(self) -> str:
        return "3.3.18"

    def sls_available(self) -> bool:
        return True

    def list_trace_apps(self, *, region: str, search=None, page_size=100, max_pages=20):
        return [
            app.AppInfo(name="ai-service-dev", region=region, pid="pid-1", app_id="app-1", app_type="TRACE"),
            app.AppInfo(name="ai-service-dev-celery-worker", region=region, pid="pid-2", app_id="app-2", app_type="TRACE"),
        ]

    def search_error_traces_by_page(self, **kwargs):
        return {"PageBean": {"Total": 0, "TraceInfos": []}}

    def get_sls_logs(self, **kwargs):
        self.sls_queries.append(kwargs)
        return [
            {
                "__time__": 1780453500,
                "_source_": "stderr",
                "_pod_name_": "ai-service-dev-6f6d8d654c",
                "content": json.dumps(
                    {
                        "log.level": "ERROR",
                        "message": "bsasr_gpt_stream error: transcribe is empty",
                        "log.original": "app_websocket_asr_gpt.py:275 in bsasr_gpt_stream",
                        "trace_id": "trace-1",
                        "request_id": "req-1",
                    }
                ),
            }
        ]

    def list_sls_projects(self, *, size=100):
        return ["ai-service-logs"]

    def list_sls_logstores(self, *, project: str, endpoint: str, size=200):
        return ["app-log"]

    def get_trace_app_config(self, *, pid: str):
        if self.arms_sls_config is None:
            return {"Data": {}}
        return {"Data": self.arms_sls_config}


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

    def write_config_with_sls(self, path: Path) -> None:
        config = app.ProjectConfig.empty()
        config.add_or_update_target(
            target_name="ai-service-dev",
            branch="dev",
            default_window="24h",
            services=[
                app.ServiceConfig(
                    name="ai-service-dev-celery-worker",
                    sls=app.SlsConfig(
                        project="ai-service-logs",
                        logstore="app-log",
                        endpoint="cn-beijing.log.aliyuncs.com",
                    ),
                )
            ],
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

    def write_group_with_occurrence(self, db_path: Path, group_id: str = "45d39c79b8f10f94") -> None:
        repository = app.TraceRepository(db_path)
        try:
            repository.conn.execute(
                """
                insert into error_groups (
                    group_key, target_name, service_name, operation_name, exception_type, message,
                    occurrence_count, first_seen_ms, last_seen_ms, sample_trace_id, sample_span_id, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    "ai-service-dev",
                    "ai-service-dev-celery-worker",
                    "run/task",
                    "ValueError",
                    "boom",
                    1,
                    1780453500000,
                    1780453500000,
                    "trace-1",
                    "span-1",
                    app._now(),
                ),
            )
            repository.conn.execute(
                """
                insert into error_occurrences (
                    group_key, trace_id, span_id, event_index, timestamp_ms, target_name, service_name, operation_name
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (group_id, "trace-1", "span-1", -1, 1780453500000, "ai-service-dev", "ai-service-dev-celery-worker", "run/task"),
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

    def test_sls_projects_json_lists_projects(self) -> None:
        with mock.patch.object(app, "build_client", return_value=FakeClient()):
            code, stdout, stderr = self.run_main(["sls", "projects", "--json"])

        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload, {"projects": [{"project": "ai-service-logs"}]})

    def test_sls_without_subcommand_prints_sls_help(self) -> None:
        code, stdout, stderr = self.run_main(["sls"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("列出当前 aliyun 默认凭证可见的 SLS Project", stdout)
        self.assertIn("projects", stdout)
        self.assertIn("logstores", stdout)

    def test_sls_projects_text_lists_projects(self) -> None:
        with mock.patch.object(app, "build_client", return_value=FakeClient()):
            code, stdout, stderr = self.run_main(["sls", "projects"])

        self.assertEqual(code, 0, stderr)
        self.assertIn("project", stdout)
        self.assertIn("ai-service-logs", stdout)

    def test_sls_logstores_json_lists_logstores(self) -> None:
        with mock.patch.object(app, "build_client", return_value=FakeClient()):
            code, stdout, stderr = self.run_main(
                [
                    "sls",
                    "logstores",
                    "--project",
                    "ai-service-logs",
                    "--endpoint",
                    "cn-beijing.log.aliyuncs.com",
                    "--json",
                ]
            )

        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(
            payload,
            {
                "project": "ai-service-logs",
                "endpoint": "cn-beijing.log.aliyuncs.com",
                "logstores": ["app-log"],
            },
        )

    def test_sls_logstores_requires_project_and_endpoint(self) -> None:
        code, stdout, stderr = self.run_main(["sls", "logstores", "--project", "ai-service-logs"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("缺少必需参数", stderr)
        self.assertIn("--endpoint", stderr)

    def test_sync_requires_target_or_service_and_lists_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            self.write_config(config_path)

            code, _stdout, stderr = self.run_main(["--config", str(config_path), "sync"])

        self.assertEqual(code, 1)
        self.assertIn("sync 需要指定 --target 或 --service", stderr)
        self.assertIn("ai-service-dev-celery-worker", stderr)
        self.assertIn("下一步", stderr)

    def test_sync_defaults_to_fresh_and_removes_old_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config(config_path)
            self.write_group(db_path, group_id="old-group")

            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "sync", "--service", "ai-service-dev-celery-worker"]
                )

            repository = app.TraceRepository(db_path)
            try:
                groups = repository.list_groups(target_name="ai-service-dev", service_names=["ai-service-dev-celery-worker"])
            finally:
                repository.close()

        self.assertEqual(code, 0, stderr)
        self.assertIn("fresh: true", stdout)
        self.assertEqual([row["group_key"] for row in groups], [])

    def test_sync_keep_old_data_preserves_old_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config(config_path)
            self.write_group(db_path, group_id="old-group")

            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, stdout, stderr = self.run_main(
                    [
                        "--config",
                        str(config_path),
                        "--db",
                        str(db_path),
                        "sync",
                        "--service",
                        "ai-service-dev-celery-worker",
                        "--keep-old-data",
                    ]
                )

            repository = app.TraceRepository(db_path)
            try:
                groups = repository.list_groups(target_name="ai-service-dev", service_names=["ai-service-dev-celery-worker"])
            finally:
                repository.close()

        self.assertEqual(code, 0, stderr)
        self.assertIn("fresh: false", stdout)
        self.assertEqual([row["group_key"] for row in groups], ["old-group"])

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

    def test_show_includes_related_sls_logs_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)
            fake_client = FakeClient()

            with mock.patch.object(app, "build_client", return_value=fake_client):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "show", "45d39c79b8f10f94"]
                )

        self.assertEqual(code, 0, stderr)
        self.assertIn("related_logs: ok", stdout)
        self.assertIn("project: ai-service-logs", stdout)
        self.assertIn("query: trace-1", stdout)
        self.assertIn("bsasr_gpt_stream error: transcribe is empty", stdout)
        self.assertIn("log_original=app_websocket_asr_gpt.py:275 in bsasr_gpt_stream", stdout)
        self.assertEqual(fake_client.sls_queries[0]["query"], "trace-1")
        self.assertEqual(fake_client.sls_queries[0]["line"], 50)

    def test_show_no_logs_skips_sls_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)
            fake_client = FakeClient()

            with mock.patch.object(app, "build_client", return_value=fake_client):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "show", "45d39c79b8f10f94", "--no-logs"]
                )

        self.assertEqual(code, 0, stderr)
        self.assertIn("related_logs: skipped", stdout)
        self.assertEqual(fake_client.sls_queries, [])

    def test_show_log_limit_overrides_service_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)
            fake_client = FakeClient()

            with mock.patch.object(app, "build_client", return_value=fake_client):
                code, _stdout, stderr = self.run_main(
                    [
                        "--config",
                        str(config_path),
                        "--db",
                        str(db_path),
                        "show",
                        "45d39c79b8f10f94",
                        "--log-limit",
                        "20",
                    ]
                )

        self.assertEqual(code, 0, stderr)
        self.assertEqual(fake_client.sls_queries[0]["line"], 20)

    def test_logs_command_prints_related_sls_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)
            fake_client = FakeClient()

            with mock.patch.object(app, "build_client", return_value=fake_client):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "logs", "45d39c79b8f10f94"]
                )

        self.assertEqual(code, 0, stderr)
        self.assertIn("related_logs: ok", stdout)
        self.assertIn("bsasr_gpt_stream error: transcribe is empty", stdout)
        self.assertEqual(fake_client.sls_queries[0]["query"], "trace-1")

    def test_logs_command_returns_one_when_sls_query_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)
            fake_client = FakeClient()
            fake_client.get_sls_logs = mock.Mock(side_effect=RuntimeError("ProjectNotExist: missing project"))  # type: ignore[method-assign]

            with mock.patch.object(app, "build_client", return_value=fake_client):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "logs", "45d39c79b8f10f94"]
                )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertIn("related_logs: failed", stdout)
        self.assertIn("ProjectNotExist", stdout)

    def test_show_returns_zero_when_sls_query_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)
            fake_client = FakeClient()
            fake_client.get_sls_logs = mock.Mock(side_effect=RuntimeError("ProjectNotExist: missing project"))  # type: ignore[method-assign]

            with mock.patch.object(app, "build_client", return_value=fake_client):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "show", "45d39c79b8f10f94"]
                )

        self.assertEqual(code, 0, stderr)
        self.assertIn("group_id: 45d39c79b8f10f94", stdout)
        self.assertIn("related_logs: failed", stdout)

    def test_show_reports_related_logs_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config(config_path)
            self.write_group_with_occurrence(db_path)

            code, stdout, stderr = self.run_main(
                ["--config", str(config_path), "--db", str(db_path), "show", "45d39c79b8f10f94"]
            )

        self.assertEqual(code, 0, stderr)
        self.assertIn("related_logs: not_configured", stdout)
        self.assertIn("service 未配置 SLS", stdout)

    def test_show_json_includes_raw_logs_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            db_path = Path(tmp) / ".arms-exceptions" / "data" / "exceptions.sqlite3"
            self.write_config_with_sls(config_path)
            self.write_group_with_occurrence(db_path)

            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, stdout, stderr = self.run_main(
                    ["--config", str(config_path), "--db", str(db_path), "show", "45d39c79b8f10f94", "--json"]
                )
            compact_payload = json.loads(stdout)

            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                raw_code, raw_stdout, raw_stderr = self.run_main(
                    [
                        "--config",
                        str(config_path),
                        "--db",
                        str(db_path),
                        "show",
                        "45d39c79b8f10f94",
                        "--json",
                        "--raw-logs",
                    ]
                )
            raw_payload = json.loads(raw_stdout)

        self.assertEqual(code, 0, stderr)
        self.assertEqual(raw_code, 0, raw_stderr)
        compact_item = compact_payload["related_logs"]["queries"][0]["items"][0]
        raw_item = raw_payload["related_logs"]["queries"][0]["items"][0]
        self.assertNotIn("raw", compact_item)
        self.assertIn("raw", raw_item)
        self.assertEqual(raw_item["raw"]["_source_"], "stderr")

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

    def test_init_noninteractive_writes_sls_config_to_all_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            with mock.patch.object(app, "build_client", return_value=FakeClient()):
                code, _stdout, stderr = self.run_main(
                    [
                        "--config",
                        str(config_path),
                        "init",
                        "--target",
                        "ai-service-dev",
                        "--service",
                        "ai-service-dev",
                        "--service",
                        "ai-service-dev-celery-worker",
                        "--sls-project",
                        "ai-service-logs",
                        "--sls-logstore",
                        "app-log",
                        "--sls-endpoint",
                        "cn-beijing.log.aliyuncs.com",
                    ]
                )

            payload = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0, stderr)
        for service in payload["targets"][0]["services"]:
            self.assertEqual(
                service["sls"],
                {
                    "project": "ai-service-logs",
                    "logstore": "app-log",
                    "endpoint": "cn-beijing.log.aliyuncs.com",
                    "default_before_seconds": 120,
                    "default_after_seconds": 120,
                    "default_limit": 50,
                },
            )

    def test_init_interactive_can_configure_sls_from_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            answers = iter(["", "", "1", "", "", "", "y", "1", "", "1"])
            with (
                mock.patch.object(app, "build_client", return_value=FakeClient()),
                mock.patch("builtins.input", side_effect=lambda _prompt: next(answers)),
            ):
                code, stdout, stderr = self.run_main(["--config", str(config_path), "init"])

            payload = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0, stderr)
        self.assertIn("SLS", stdout)
        self.assertEqual(payload["targets"][0]["services"][0]["sls"]["project"], "ai-service-logs")
        self.assertEqual(payload["targets"][0]["services"][0]["sls"]["logstore"], "app-log")
        self.assertEqual(payload["targets"][0]["services"][0]["sls"]["endpoint"], "cn-beijing.log.aliyuncs.com")

    def test_init_interactive_can_import_existing_arms_sls_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".arms-exceptions" / "config.json"
            answers = iter(["", "", "1", "", "", "", "y", ""])
            fake_client = FakeClient(
                arms_sls_config={
                    "profiler.SLS.regionId": "cn-beijing",
                    "profiler.SLS.project": "arms-project",
                    "profiler.SLS.logStore": "arms-logstore",
                    "profiler.SLS.index": "trace_id",
                }
            )
            with (
                mock.patch.object(app, "build_client", return_value=fake_client),
                mock.patch("builtins.input", side_effect=lambda _prompt: next(answers)),
            ):
                code, stdout, stderr = self.run_main(["--config", str(config_path), "init"])

            payload = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0, stderr)
        self.assertIn("ARMS", stdout)
        self.assertEqual(payload["targets"][0]["services"][0]["sls"]["project"], "arms-project")
        self.assertEqual(payload["targets"][0]["services"][0]["sls"]["logstore"], "arms-logstore")
        self.assertEqual(payload["targets"][0]["services"][0]["sls"]["endpoint"], "cn-beijing.log.aliyuncs.com")
        self.assertNotIn("arms_index", payload["targets"][0]["services"][0]["sls"])

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
        self.assertIn("sls_api_available: true", stdout)
        self.assertIn("sls_configured_services: 0", stdout)

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
