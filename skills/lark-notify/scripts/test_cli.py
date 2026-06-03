import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("cli.py")
SPEC = importlib.util.spec_from_file_location("lark_notify_cli", MODULE_PATH)
cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = cli
SPEC.loader.exec_module(cli)


WEBHOOK_LOCAL = "https://open.feishu.cn/open-apis/bot/v2/hook/local-token-12345678"
WEBHOOK_ENV = "https://open.feishu.cn/open-apis/bot/v2/hook/env-token-12345678"


class chdir:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.old = Path.cwd()

    def __enter__(self) -> None:
        os.chdir(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        os.chdir(self.old)


class ConfigTests(unittest.TestCase):
    def test_config_writes_local_file_and_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = StringIO()
            with chdir(root), redirect_stdout(stdout):
                exit_code = cli.main(["config", "--webhook-url", WEBHOOK_LOCAL])

            self.assertEqual(exit_code, 0)
            config_path = root / ".arms-exceptions" / "lark-notify.local.json"
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["webhook_url"], WEBHOOK_LOCAL)
            self.assertIn(".arms-exceptions/lark-notify.local.json", (root / ".gitignore").read_text(encoding="utf-8"))

    def test_config_show_masks_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".arms-exceptions" / "lark-notify.local.json"
            config_path.parent.mkdir()
            config_path.write_text(json.dumps({"webhook_url": WEBHOOK_LOCAL}), encoding="utf-8")
            stdout = StringIO()
            with chdir(root), redirect_stdout(stdout):
                exit_code = cli.main(["config", "--show"])

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("configured: true", output)
        self.assertIn("local", output)
        self.assertNotIn("local-token-12345678", output)
        self.assertIn("loca...5678", output)

    def test_env_fallback_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {cli.WEBHOOK_ENV: WEBHOOK_ENV}, clear=True):
            root = Path(tmp)
            with chdir(root):
                webhook, source = cli.resolve_webhook(cli.resolve_config_path())

        self.assertEqual(webhook, WEBHOOK_ENV)
        self.assertEqual(source, "env")

    def test_local_config_has_priority_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {cli.WEBHOOK_ENV: WEBHOOK_ENV}, clear=True):
            root = Path(tmp)
            config_path = root / ".arms-exceptions" / "lark-notify.local.json"
            config_path.parent.mkdir()
            config_path.write_text(json.dumps({"webhook_url": WEBHOOK_LOCAL}), encoding="utf-8")
            with chdir(root):
                webhook, source = cli.resolve_webhook(cli.resolve_config_path())

        self.assertEqual(webhook, WEBHOOK_LOCAL)
        self.assertEqual(source, "local")


class PayloadTests(unittest.TestCase):
    def test_text_payload_shape(self) -> None:
        payload, truncated = cli.build_payload(title="标题", body="正文", fmt="text")
        self.assertFalse(truncated)
        self.assertEqual(payload["msg_type"], "text")
        self.assertEqual(payload["content"]["text"], "标题\n\n正文")

    def test_card_payload_shape(self) -> None:
        payload, truncated = cli.build_payload(title="标题", body="正文", fmt="card")
        self.assertFalse(truncated)
        self.assertEqual(payload["msg_type"], "interactive")
        self.assertEqual(payload["card"]["header"]["title"]["content"], "标题")
        self.assertEqual(payload["card"]["elements"][0]["text"]["content"], "正文")

    def test_raw_payload_requires_json_object_with_msg_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            path.write_text(json.dumps({"msg_type": "text", "content": {"text": "hello"}}), encoding="utf-8")
            payload = cli.load_raw_payload(str(path))

        self.assertEqual(payload["msg_type"], "text")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(["not", "object"]), encoding="utf-8")
            with self.assertRaises(cli.CliError):
                cli.load_raw_payload(str(path))

    def test_oversize_text_payload_truncates_under_limit(self) -> None:
        payload, truncated = cli.build_payload(
            title="标题",
            body="x" * 1000,
            fmt="text",
            report_path=".arms-exceptions/triage/run/summary.md",
            max_bytes=400,
        )

        self.assertTrue(truncated)
        self.assertLessEqual(cli.payload_size(payload), 400)
        self.assertIn("内容已截断", payload["content"]["text"])
        self.assertIn(".arms-exceptions/triage/run/summary.md", payload["content"]["text"])

    def test_redact_masks_credentials_and_webhook(self) -> None:
        text = (
            "Authorization: Bearer abc\n"
            "AccessKeyId=key&AccessKeySecret=secret&SecurityToken=token&Signature=sig "
            f"{WEBHOOK_LOCAL}"
        )
        redacted = cli.redact(text)
        self.assertNotIn("Bearer abc", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn(WEBHOOK_LOCAL, redacted)


class CommandTests(unittest.TestCase):
    def test_dry_run_does_not_send_network_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".arms-exceptions" / "lark-notify.local.json"
            config_path.parent.mkdir()
            config_path.write_text(json.dumps({"webhook_url": WEBHOOK_LOCAL}), encoding="utf-8")
            stdout = StringIO()
            with chdir(root), redirect_stdout(stdout), patch.object(cli, "send_webhook") as send_webhook:
                exit_code = cli.main(["send", "--title", "标题", "--body", "正文", "--format", "card", "--dry-run"])

        self.assertEqual(exit_code, 0)
        send_webhook.assert_not_called()
        self.assertIn("dry_run: true", stdout.getvalue())
        self.assertNotIn("local-token-12345678", stdout.getvalue())

    def test_dry_run_does_not_require_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            stdout = StringIO()
            with chdir(root), redirect_stdout(stdout), patch.object(cli, "send_webhook") as send_webhook:
                exit_code = cli.main(["send", "--title", "标题", "--body", "正文", "--format", "card", "--dry-run"])

        self.assertEqual(exit_code, 0)
        send_webhook.assert_not_called()
        self.assertIn("source: none", stdout.getvalue())

    def test_send_json_dry_run_includes_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".arms-exceptions" / "lark-notify.local.json"
            config_path.parent.mkdir()
            config_path.write_text(json.dumps({"webhook_url": WEBHOOK_LOCAL}), encoding="utf-8")
            stdout = StringIO()
            with chdir(root), redirect_stdout(stdout):
                exit_code = cli.main(
                    ["send", "--title", "标题", "--body", "正文", "--format", "text", "--dry-run", "--json"]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["payload"]["msg_type"], "text")

    def test_raw_json_dry_run_payload_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_path = root / "payload.json"
            raw_path.write_text(
                json.dumps({"msg_type": "text", "content": {"text": f"Authorization: Bearer abc {WEBHOOK_LOCAL}"}}),
                encoding="utf-8",
            )
            stdout = StringIO()
            with chdir(root), redirect_stdout(stdout):
                exit_code = cli.main(["send", "--json-file", str(raw_path), "--format", "raw", "--dry-run", "--json"])

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertNotIn("Bearer abc", output)
        self.assertNotIn("local-token-12345678", output)

    def test_full_webhook_not_printed_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".arms-exceptions" / "lark-notify.local.json"
            config_path.parent.mkdir()
            config_path.write_text(json.dumps({"webhook_url": WEBHOOK_LOCAL}), encoding="utf-8")
            stderr = StringIO()
            with chdir(root), redirect_stderr(stderr):
                exit_code = cli.main(["send", "--title", "标题", "--body", WEBHOOK_LOCAL, "--format", "raw"])

        self.assertEqual(exit_code, 1)
        self.assertNotIn("local-token-12345678", stderr.getvalue())

    def test_no_args_prints_help_and_returns_zero(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = cli.main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("飞书自定义机器人通知 CLI", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
