import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).with_name("cli.py")
SPEC = importlib.util.spec_from_file_location("yunxiao_mr_cli", MODULE_PATH)
cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = cli
SPEC.loader.exec_module(cli)


class chdir:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.old = Path.cwd()

    def __enter__(self) -> None:
        os.chdir(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        os.chdir(self.old)


def run(cmd, cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def make_git_repo(path: Path, remote_url: str) -> None:
    run(["git", "init"], path)
    run(["git", "config", "user.email", "codex@example.com"], path)
    run(["git", "config", "user.name", "Codex"], path)
    (path / "README.md").write_text("test\n", encoding="utf-8")
    run(["git", "add", "README.md"], path)
    run(["git", "commit", "-m", "init"], path)
    run(["git", "remote", "add", "origin", remote_url], path)


class RemoteParsingTests(unittest.TestCase):
    def test_parse_scp_codeup_remote(self) -> None:
        info = cli.parse_codeup_remote("git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git")
        self.assertEqual(info.domain, "codeup.aliyun.com")
        self.assertEqual(info.organization_id, "685a564391483e233edca392")
        self.assertEqual(info.repository_path, "685a564391483e233edca392/sharge-web/test")
        self.assertEqual(info.repository_identity, "685a564391483e233edca392%2Fsharge-web%2Ftest")

    def test_parse_https_codeup_remote(self) -> None:
        info = cli.parse_codeup_remote("https://codeup.aliyun.com/685a564391483e233edca392/aiservice/ai_glass.git")
        self.assertEqual(info.domain, "codeup.aliyun.com")
        self.assertEqual(info.repository_path, "685a564391483e233edca392/aiservice/ai_glass")

    def test_rejects_non_codeup_remote_for_auto_inference(self) -> None:
        with self.assertRaises(cli.CliError):
            cli.parse_codeup_remote("git@github.com:ivan-94/ali-arms-exception-explorer.git")


class ConfigTests(unittest.TestCase):
    def test_first_run_writes_yunxiao_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            make_git_repo(repo, "git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git")
            with chdir(repo):
                context = cli.YunxiaoContext()
            config_path = repo / ".arms-exceptions" / "yunxiao.json"
            self.assertTrue(config_path.exists())
            self.assertEqual(context.config["api_domain"], "openapi-rdc.aliyuncs.com")
            self.assertEqual(context.config["organization_id"], "685a564391483e233edca392")
            self.assertEqual(context.config["repository_identity"], "685a564391483e233edca392%2Fsharge-web%2Ftest")
            self.assertEqual(context.config["default_target_branch"], "main")

    def test_existing_config_preserves_manual_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            make_git_repo(repo, "git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git")
            config_dir = repo / ".arms-exceptions"
            config_dir.mkdir()
            (config_dir / "yunxiao.json").write_text(
                '{"version":1,"domain":"custom.example.com","organization_id":"org",'
                '"repository_path":"org/group/repo","repository_identity":"org%2Fgroup%2Frepo",'
                '"default_target_branch":"develop","repository_id":123}',
                encoding="utf-8",
            )
            with chdir(repo):
                context = cli.YunxiaoContext()
            self.assertEqual(context.domain, "custom.example.com")
            self.assertEqual(context.api_domain, "custom.example.com")
            self.assertEqual(context.default_target_branch, "develop")
            self.assertEqual(context.config["repository_id"], 123)


class CommandLogicTests(unittest.TestCase):
    def test_create_body_uses_expected_yunxiao_fields(self) -> None:
        body = cli.build_create_body(
            repository_id="123",
            title="title",
            description="body",
            source_branch="feature/x",
            target_branch="main",
            reviewers=["42"],
            work_item_ids="wi-1,wi-2",
        )
        self.assertEqual(body["sourceProjectId"], "123")
        self.assertEqual(body["targetProjectId"], "123")
        self.assertEqual(body["sourceBranch"], "feature/x")
        self.assertEqual(body["targetBranch"], "main")
        self.assertEqual(body["title"], "title")
        self.assertEqual(body["description"], "body")
        self.assertEqual(body["reviewerIds"], ["42"])
        self.assertEqual(body["workItemIds"], "wi-1,wi-2")

    def test_state_filter_conversion(self) -> None:
        self.assertEqual(cli.state_query_value("opened"), "opened")
        self.assertIsNone(cli.state_query_value("all"))

    def test_redact_masks_tokens(self) -> None:
        with patch.dict(os.environ, {cli.TOKEN_ENV: "secret-token"}):
            text = cli.redact("accessToken=secret-token x-yunxiao-token: secret-token")
        self.assertNotIn("secret-token", text)
        self.assertIn("<redacted>", text)

    def test_create_fails_when_branch_not_pushed(self) -> None:
        fake_context = type(
            "FakeContext",
            (),
            {
                "default_remote": "origin",
                "default_target_branch": "main",
                "config": {"repository_id": "123"},
                "repository_id_or_identity": "123",
            },
        )()
        args = Namespace(
            config=".arms-exceptions/yunxiao.json",
            remote="origin",
            debug=False,
            head="feature/x",
            base=None,
            body="body",
            body_file=None,
            title="title",
            reviewer=[],
            work_item_ids=None,
            label=[],
            create_missing_label=False,
            json=False,
        )
        with patch.object(cli, "YunxiaoContext", return_value=fake_context), patch.object(
            cli, "YunxiaoClient"
        ), patch.object(cli, "remote_branch_exists", return_value=False):
            with self.assertRaises(cli.CliError) as ctx:
                cli.command_create(args)
        self.assertIn("git push -u origin feature/x", str(ctx.exception))


class ClientRequestTests(unittest.TestCase):
    def make_client(self):
        fake_context = type(
            "FakeContext",
            (),
            {
                "domain": "codeup.aliyun.com",
                "api_domain": "openapi-rdc.aliyuncs.com",
                "organization_id": "org",
                "repository_identity": "org%2Fgroup%2Frepo",
                "repository_path": "org/group/repo",
                "repository_query_identity": "org/group/repo",
                "repository_id_or_identity": "123",
            },
        )()
        client = cli.YunxiaoClient(fake_context, token="token")
        calls = []

        def fake_request(method, path, query=None, body=None, headers=None):
            calls.append((method, path, query, body, headers))
            if path.endswith("/labels") and method == "GET":
                return {"success": True, "result": []}
            return {"success": True, "result": {"result": True}}

        client._request = fake_request
        return client, calls

    def test_label_queries_use_repository_id_when_available(self) -> None:
        client, calls = self.make_client()
        client.list_project_labels()
        self.assertEqual(
            calls[0][1],
            "/oapi/v1/codeup/organizations/org/repositories/123/labels",
        )

    def test_close_reopen_merge_use_post(self) -> None:
        client, calls = self.make_client()
        client.close_merge_request("1")
        client.reopen_merge_request("1")
        client.merge_merge_request("1", {"mergeType": "squash"})
        self.assertEqual([call[0] for call in calls], ["POST", "POST", "POST"])

    def test_create_label_uses_default_color(self) -> None:
        client, calls = self.make_client()
        client.create_project_label("HAT-Ready")
        self.assertEqual(calls[0][3]["label_color"], cli.DEFAULT_LABEL_COLOR)


class LabelCommandTests(unittest.TestCase):
    def make_args(self, label_command: str, **kwargs):
        data = {
            "config": ".arms-exceptions/yunxiao.json",
            "remote": "origin",
            "debug": False,
            "label_command": label_command,
            "local_id": "12",
            "name": "HAT-Ready",
            "create_missing_label": False,
            "json": True,
        }
        data.update(kwargs)
        return Namespace(**data)

    def test_label_add_rewrites_full_label_set(self) -> None:
        fake_client = Mock()
        fake_client.list_merge_request_labels.return_value = [{"id": "a", "name": "existing"}]
        fake_client.list_project_labels.return_value = [{"id": "b", "name": "HAT-Ready"}]
        with patch.object(cli, "YunxiaoContext"), patch.object(cli, "YunxiaoClient", return_value=fake_client):
            with redirect_stdout(StringIO()):
                cli.command_label(self.make_args("add"))
        fake_client.link_merge_request_labels.assert_called_once_with("12", ["a", "b"])

    def test_label_remove_rewrites_remaining_labels(self) -> None:
        fake_client = Mock()
        fake_client.list_merge_request_labels.return_value = [
            {"id": "a", "name": "existing"},
            {"id": "b", "name": "HAT-Ready"},
        ]
        with patch.object(cli, "YunxiaoContext"), patch.object(cli, "YunxiaoClient", return_value=fake_client):
            with redirect_stdout(StringIO()):
                cli.command_label(self.make_args("remove"))
        fake_client.link_merge_request_labels.assert_called_once_with("12", ["a"])


if __name__ == "__main__":
    unittest.main()
