#!/usr/bin/env python3
"""Feishu/Lark custom bot notification CLI for agents."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(".arms-exceptions") / "lark-notify.local.json"
WEBHOOK_ENV = "ARMS_LARK_WEBHOOK_URL"
MAX_PAYLOAD_BYTES = 20 * 1024
GITIGNORE_LINES = [".arms-exceptions/lark-notify.local.json"]


class CliError(Exception):
    """User-facing error."""


def run_git(args: list[str], check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CliError(f"git {' '.join(args)} 失败: {detail}")
    return completed.stdout.strip()


def project_root() -> Path:
    root = run_git(["rev-parse", "--show-toplevel"], check=False)
    if root:
        return Path(root)
    return Path.cwd()


def resolve_config_path(path: Path | str = DEFAULT_CONFIG_PATH) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return project_root() / raw


def validate_webhook_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("https://"):
        raise CliError("Webhook URL 必须使用 https。下一步: 复制飞书机器人 Webhook 后重试。")
    if "/open-apis/bot/v2/hook/" not in url:
        raise CliError("Webhook URL 看起来不是飞书自定义机器人地址。下一步: 使用群机器人设置里的 Webhook。")
    return url


def mask_webhook(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    prefix = url.split("/open-apis/bot/v2/hook/", 1)[0]
    token = url.rsplit("/", 1)[-1]
    if len(token) <= 8:
        masked = "<redacted>"
    else:
        masked = f"{token[:4]}...{token[-4:]}"
    return f"{prefix}/open-apis/bot/v2/hook/{masked}"


def redact(text: str) -> str:
    patterns = [
        (r"(Authorization\s*[:=]\s*)[^\n\r]+", r"\1<redacted>"),
        (r"(access[_-]?token\s*[:=]\s*)[^\s,;]+", r"\1<redacted>"),
        (r"(AccessKeyId=)[^&\s]+", r"\1<redacted>"),
        (r"(AccessKeySecret=)[^&\s]+", r"\1<redacted>"),
        (r"(SecurityToken=)[^&\s]+", r"\1<redacted>"),
        (r"(Signature=)[^&\s]+", r"\1<redacted>"),
        (r"https://[^\s)]+/open-apis/bot/v2/hook/[^\s)]+", "<lark-webhook-redacted>"),
    ]
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    env_url = os.environ.get(WEBHOOK_ENV)
    if env_url:
        text = text.replace(env_url, "<lark-webhook-redacted>")
    return text


def read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"配置文件不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError(f"配置文件必须是 JSON object: {path}")
    return value


def write_config(path: Path, webhook_url: str) -> None:
    webhook_url = validate_webhook_url(webhook_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"webhook_url": webhook_url}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ensure_project_gitignore(project_root())


def ensure_project_gitignore(root: Path) -> None:
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = set(existing.splitlines())
    missing = [line for line in GITIGNORE_LINES if line not in lines]
    if not missing:
        return
    addition = "\n" if existing and not existing.endswith("\n") else ""
    if existing:
        addition += "\n# Added by lark-notify.\n"
    else:
        addition += "# Added by lark-notify.\n"
    addition += "\n".join(missing) + "\n"
    path.write_text(existing + addition, encoding="utf-8")


def resolve_webhook(config_path: Path) -> tuple[str | None, str]:
    config = read_config(config_path)
    local_url = config.get("webhook_url")
    if isinstance(local_url, str) and local_url.strip():
        return validate_webhook_url(local_url), "local"
    env_url = os.environ.get(WEBHOOK_ENV)
    if env_url:
        return validate_webhook_url(env_url), "env"
    return None, "none"


def load_body(body: str | None, body_file: str | None) -> tuple[str, str | None]:
    if body and body_file:
        raise CliError("只能传 --body 或 --body-file 其中一个")
    if body_file:
        return Path(body_file).read_text(encoding="utf-8"), body_file
    return body or "", None


def text_payload(title: str, body: str) -> dict[str, Any]:
    content = f"{title}\n\n{body}" if body else title
    return {"msg_type": "text", "content": {"text": content}}


def card_payload(title: str, body: str) -> dict[str, Any]:
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"template": "blue", "title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": body}}],
        },
    }


def payload_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def build_payload(
    *,
    title: str,
    body: str,
    fmt: str,
    raw_payload: dict[str, Any] | None = None,
    report_path: str | None = None,
    max_bytes: int = MAX_PAYLOAD_BYTES,
) -> tuple[dict[str, Any], bool]:
    if fmt == "raw":
        if raw_payload is None:
            raise CliError("--format raw 需要 --json-file")
        if payload_size(raw_payload) > max_bytes:
            raise CliError("raw payload 超过飞书自定义机器人 20 KB 限制。下一步: 缩小 JSON 后重试。")
        return raw_payload, False

    clean_title = redact(title)
    clean_body = redact(body)
    builder = text_payload if fmt == "text" else card_payload
    payload = builder(clean_title, clean_body)
    if payload_size(payload) <= max_bytes:
        return payload, False

    note = "\n\n[内容已截断"
    if report_path:
        note += f"，完整报告见: {report_path}"
    note += "]"

    low = 0
    high = len(clean_body)
    best = ""
    while low <= high:
        mid = (low + high) // 2
        candidate = clean_body[:mid].rstrip() + note
        candidate_payload = builder(clean_title, candidate)
        if payload_size(candidate_payload) <= max_bytes:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    if not best:
        minimal_payload = builder(clean_title, note.strip())
        if payload_size(minimal_payload) > max_bytes:
            raise CliError("标题和截断提示仍超过 20 KB。下一步: 缩短标题后重试。")
        return minimal_payload, True
    return builder(clean_title, best), True


def load_raw_payload(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"raw payload 不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError("raw payload 必须是 JSON object")
    if "msg_type" not in value:
        raise CliError("raw payload 必须包含 msg_type")
    return value


def send_webhook(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CliError(f"飞书 Webhook 请求失败: HTTP {exc.code}: {redact(body)}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"飞书 Webhook 无法连接: {exc.reason}") from exc

    if not raw.strip():
        return {"ok": True}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "raw": redact(raw)}
    status_code = result.get("code", result.get("StatusCode"))
    if status_code in (None, 0, "0"):
        return result
    message = result.get("msg") or result.get("StatusMessage") or result.get("message") or result
    raise CliError(f"飞书 Webhook 返回失败: {redact(str(message))}")


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def sanitize_for_output(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [sanitize_for_output(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_for_output(item) for key, item in value.items()}
    return value


def command_config(args: argparse.Namespace) -> int:
    config_path = resolve_config_path(args.config)
    if args.webhook_url:
        write_config(config_path, args.webhook_url)
        payload = {"ok": True, "config": str(config_path), "source": "local", "webhook": mask_webhook(args.webhook_url)}
        if args.json:
            print_json(payload)
        else:
            print("飞书 Webhook 已保存")
            print(f"config: {config_path}")
            print(f"webhook: {payload['webhook']}")
            print("下一步:")
            print(f"  python3 skills/lark-notify/scripts/cli.py send --title \"测试通知\" --body \"hello\" --dry-run")
        return 0

    if args.show:
        webhook, source = resolve_webhook(config_path)
        payload = {
            "configured": webhook is not None,
            "source": source,
            "config": str(config_path),
            "webhook": mask_webhook(webhook or ""),
        }
        if args.json:
            print_json(payload)
        else:
            print(f"configured: {str(payload['configured']).lower()}")
            print(f"source: {source}")
            print(f"config: {config_path}")
            if webhook:
                print(f"webhook: {payload['webhook']}")
            else:
                print("下一步:")
                print("  python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>")
                print(f"  或设置环境变量: export {WEBHOOK_ENV}=<webhook>")
        return 0

    raise CliError("请传 --webhook-url <url> 或 --show")


def command_send(args: argparse.Namespace) -> int:
    config_path = resolve_config_path(args.config)
    webhook, source = resolve_webhook(config_path)
    if webhook is None and not args.dry_run:
        raise CliError(
            "没有配置飞书 Webhook。下一步: "
            "python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook> "
            f"或设置 {WEBHOOK_ENV}。"
        )

    body, body_path = load_body(args.body, args.body_file)
    raw_payload = load_raw_payload(args.json_file)
    if args.format != "raw" and not args.title:
        raise CliError("发送 text/card 需要 --title")
    if args.format != "raw" and not body:
        raise CliError("发送 text/card 需要 --body 或 --body-file")

    payload, truncated = build_payload(
        title=args.title or "",
        body=body,
        fmt=args.format,
        raw_payload=raw_payload,
        report_path=body_path,
    )
    size = payload_size(payload)
    result: dict[str, Any] = {
        "ok": True,
        "dry_run": bool(args.dry_run),
        "format": args.format,
        "source": source,
        "payload_bytes": size,
        "truncated": truncated,
    }

    if args.dry_run:
        if args.json:
            result["payload"] = sanitize_for_output(payload)
            print_json(result)
        else:
            print("dry_run: true")
            print(f"format: {args.format}")
            print(f"source: {source}")
            print(f"payload_bytes: {size}")
            print(f"truncated: {str(truncated).lower()}")
        return 0

    response = send_webhook(webhook, payload)
    result["response"] = response
    if args.json:
        print_json(result)
    else:
        print("飞书通知已发送")
        print(f"format: {args.format}")
        print(f"payload_bytes: {size}")
        print(f"truncated: {str(truncated).lower()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lark-notify",
        description="飞书自定义机器人通知 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="本地 webhook 配置路径")
    parser.add_argument("--json", action="store_true", default=False, help="输出 JSON，可放在命令前或子命令参数里")
    subparsers = parser.add_subparsers(dest="command")

    config = subparsers.add_parser("config", help="配置或查看飞书 Webhook")
    config.add_argument("--webhook-url", help="写入本地飞书机器人 Webhook")
    config.add_argument("--show", action="store_true", help="显示配置状态，不打印完整 webhook")
    config.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")
    config.set_defaults(func=command_config)

    send = subparsers.add_parser("send", help="发送飞书通知")
    send.add_argument("--title", help="通知标题")
    send.add_argument("--body", help="通知正文")
    send.add_argument("--body-file", help="从文件读取通知正文")
    send.add_argument("--json-file", help="raw 格式 JSON payload 文件")
    send.add_argument("--format", choices=["text", "card", "raw"], default="card", help="消息格式")
    send.add_argument("--dry-run", action="store_true", help="只渲染和校验，不发送")
    send.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")
    send.set_defaults(func=command_send)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except CliError as exc:
        print(f"错误: {redact(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
