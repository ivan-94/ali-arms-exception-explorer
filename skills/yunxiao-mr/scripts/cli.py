#!/usr/bin/env python3
"""Yunxiao Codeup merge request CLI for agents."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CONFIG_PATH = Path(".arms-exceptions") / "yunxiao.json"
DEFAULT_REMOTE = "origin"
TOKEN_ENV = "YUNXIAO_ACCESS_TOKEN"
DEFAULT_LABEL_COLOR = "#3BA630"
DEFAULT_STANDARD_API_DOMAIN = "openapi-rdc.aliyuncs.com"


class CliError(Exception):
    """User-facing error."""


class ApiError(CliError):
    """Yunxiao API error."""


@dataclass(frozen=True)
class RemoteInfo:
    domain: str
    organization_id: str
    repository_path: str
    repository_identity: str


def redact(text: str) -> str:
    patterns = [
        (r"(accessToken=)[^&\s]+", r"\1<redacted>"),
        (r"(x-yunxiao-token:\s*)[^\s]+", r"\1<redacted>"),
        (r"(Authorization:\s*)[^\n]+", r"\1<redacted>"),
        (r"(AccessKeyId=)[^&\s]+", r"\1<redacted>"),
        (r"(AccessKeySecret=)[^&\s]+", r"\1<redacted>"),
        (r"(SecurityToken=)[^&\s]+", r"\1<redacted>"),
        (r"(Signature=)[^&\s]+", r"\1<redacted>"),
    ]
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    token = os.environ.get(TOKEN_ENV)
    if token:
        text = text.replace(token, "<redacted>")
    return text


def read_text_arg(body: str | None, body_file: str | None, field_name: str) -> str:
    if body and body_file:
        raise CliError(f"{field_name} 只能传 --body 或 --body-file 其中一个")
    if body_file:
        return Path(body_file).read_text(encoding="utf-8")
    return body or ""


def run_git(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CliError(f"git {' '.join(args)} 失败: {detail}")
    return completed.stdout.strip()


def find_git_root() -> Path:
    out = run_git(["rev-parse", "--show-toplevel"])
    return Path(out)


def strip_git_suffix(path: str) -> str:
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def parse_codeup_remote(remote_url: str) -> RemoteInfo:
    remote_url = remote_url.strip()
    host = ""
    path = ""

    scp_like = re.match(r"^(?:[^@]+@)?([^:]+):(.+)$", remote_url)
    if scp_like and "://" not in remote_url:
        host = scp_like.group(1)
        path = scp_like.group(2)
    else:
        parsed = urllib.parse.urlparse(remote_url)
        if parsed.scheme not in {"ssh", "https", "http"} or not parsed.netloc:
            raise CliError(f"无法解析 Codeup remote: {remote_url}")
        host = parsed.hostname or parsed.netloc.split("@")[-1]
        path = parsed.path

    if "codeup" not in host.lower():
        raise CliError(
            f"当前 remote 不是可自动推断的 Codeup remote: {remote_url}。"
            f"如使用自定义云效域名，请手动创建 {DEFAULT_CONFIG_PATH}。"
        )

    path = strip_git_suffix(path)
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise CliError(f"Codeup remote 路径至少需要组织和仓库: {remote_url}")
    organization_id = parts[0]
    repository_path = "/".join(parts)
    repository_identity = urllib.parse.quote(repository_path, safe="")
    return RemoteInfo(
        domain=host,
        organization_id=organization_id,
        repository_path=repository_path,
        repository_identity=repository_identity,
    )


def infer_api_domain(git_domain: str) -> str:
    if git_domain.lower() == "codeup.aliyun.com":
        return DEFAULT_STANDARD_API_DOMAIN
    return git_domain


def infer_default_target_branch(remote: str) -> str:
    head = run_git(["symbolic-ref", f"refs/remotes/{remote}/HEAD"], check=False)
    if head:
        prefix = f"refs/remotes/{remote}/"
        if head.startswith(prefix):
            return head[len(prefix) :]
    for name in ("main", "master"):
        ref = run_git(["show-ref", "--verify", f"refs/remotes/{remote}/{name}"], check=False)
        if ref:
            return name
    return "main"


def current_branch() -> str:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        raise CliError("当前处于 detached HEAD，创建 MR 时请传 --head <branch>")
    return branch


def remote_branch_exists(remote: str, branch: str) -> bool:
    ref = run_git(["ls-remote", "--heads", remote, branch], check=False)
    return bool(ref.strip())


class YunxiaoContext:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH, remote: str = DEFAULT_REMOTE) -> None:
        self.git_root = find_git_root()
        self.config_path = config_path if config_path.is_absolute() else self.git_root / config_path
        self.remote = remote
        self.config = self._load_or_infer()

    def _load_or_infer(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if self.config_path.exists():
            try:
                config = json.loads(self.config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise CliError(f"配置文件不是有效 JSON: {self.config_path}: {exc}") from exc
            if not isinstance(config, dict):
                raise CliError(f"配置文件必须是 JSON object: {self.config_path}")

        remote_name = str(config.get("default_remote") or self.remote)
        if not self._has_required_context(config):
            remote_url = run_git(["remote", "get-url", remote_name], cwd=self.git_root)
            info = parse_codeup_remote(remote_url)
            inferred = {
                "version": 1,
                "domain": info.domain,
                "api_domain": infer_api_domain(info.domain),
                "organization_id": info.organization_id,
                "repository_path": info.repository_path,
                "repository_identity": info.repository_identity,
                "default_remote": remote_name,
                "default_target_branch": infer_default_target_branch(remote_name),
            }
            for key, value in inferred.items():
                config.setdefault(key, value)
            self._write_config(config)
        else:
            changed = False
            if "default_target_branch" not in config:
                config["default_target_branch"] = infer_default_target_branch(remote_name)
                changed = True
            if "api_domain" not in config:
                config["api_domain"] = infer_api_domain(str(config["domain"]))
                changed = True
            if changed:
                self._write_config(config)
        return config

    @staticmethod
    def _has_required_context(config: dict[str, Any]) -> bool:
        required = ["domain", "organization_id", "repository_path", "repository_identity"]
        return all(config.get(key) for key in required)

    def _write_config(self, config: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @property
    def domain(self) -> str:
        return str(self.config["domain"])

    @property
    def api_domain(self) -> str:
        return str(self.config.get("api_domain") or infer_api_domain(self.domain))

    @property
    def organization_id(self) -> str:
        return str(self.config["organization_id"])

    @property
    def repository_identity(self) -> str:
        return str(self.config["repository_identity"])

    @property
    def repository_path(self) -> str:
        return str(self.config["repository_path"])

    @property
    def repository_id_or_identity(self) -> str:
        return str(self.config.get("repository_id") or self.repository_identity)

    @property
    def repository_query_identity(self) -> str:
        return str(self.config.get("repository_id") or self.repository_path)

    @property
    def default_target_branch(self) -> str:
        return str(self.config.get("default_target_branch") or "main")

    @property
    def default_remote(self) -> str:
        return str(self.config.get("default_remote") or self.remote)

    def maybe_cache_repository_id(self, repo: dict[str, Any]) -> None:
        repo_id = first_present(repo, ["id", "repositoryId", "projectId"])
        if repo_id and not self.config.get("repository_id"):
            self.config["repository_id"] = repo_id
            self._write_config(self.config)


class YunxiaoClient:
    def __init__(self, context: YunxiaoContext, token: str | None = None, debug: bool = False) -> None:
        self.context = context
        self.token = token if token is not None else os.environ.get(TOKEN_ENV)
        self.debug = debug

    def require_token(self) -> str:
        if not self.token:
            raise CliError(f"缺少 {TOKEN_ENV}。请先 export {TOKEN_ENV}=<personal_access_token>")
        return self.token

    def devops_request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        token = self.require_token()
        params: dict[str, Any] = {
            "organizationId": self.context.organization_id,
            "accessToken": token,
        }
        if query:
            for key, value in query.items():
                if value is not None:
                    params[key] = value
        return self._request(method, path, params, body, headers={})

    def oapi_request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        token = self.require_token()
        clean_query = {key: value for key, value in (query or {}).items() if value is not None}
        return self._request(method, path, clean_query, body, headers={"x-yunxiao-token": token})

    def oapi_repo_path(self, suffix: str = "") -> str:
        return (
            f"/oapi/v1/codeup/organizations/{self.context.organization_id}/repositories/"
            f"{self.context.repository_id_or_identity}{suffix}"
        )

    def oapi_org_path(self, suffix: str = "") -> str:
        return f"/oapi/v1/codeup/organizations/{self.context.organization_id}{suffix}"

    def _request(
        self,
        method: str,
        path: str,
        query: dict[str, Any],
        body: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> Any:
        base = f"https://{self.context.api_domain}"
        url = base + path
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        data = None
        req_headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        req_headers.update(headers)
        request = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
        if self.debug:
            print(redact(f"DEBUG request {method.upper()} {url}"), file=sys.stderr)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            message = self._format_http_error(exc.code, raw)
            raise ApiError(message) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"云效 API 访问失败: {exc.reason}") from exc

        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(f"云效 API 返回非 JSON: {redact(raw[:300])}") from exc
        if isinstance(payload, dict) and payload.get("success") is False:
            code = payload.get("errorCode") or payload.get("code") or "UNKNOWN"
            msg = payload.get("errorMessage") or payload.get("message") or "云效 API 返回失败"
            raise ApiError(f"云效 API 失败: {code}: {msg}")
        return payload

    @staticmethod
    def _format_http_error(status: int, raw: str) -> str:
        hint = ""
        if status in (401, 403):
            hint = "。请检查 YUNXIAO_ACCESS_TOKEN 和代码库权限"
        elif status == 404:
            hint = "。请检查 organization_id、repository_identity/repository_id 和 api_domain"
        body = redact(raw[:500])
        return f"云效 API HTTP {status}{hint}: {body}"

    def get_repository(self) -> dict[str, Any] | None:
        payload = self.oapi_request(
            "GET",
            self.oapi_repo_path(),
        )
        return payload if isinstance(payload, dict) else None

    def create_merge_request(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path("/changeRequests"),
            body=body,
        )
        return ensure_dict(payload, "创建 MR 返回结果")

    def list_merge_requests(self, **query: Any) -> list[dict[str, Any]]:
        payload = self.oapi_request("GET", self.oapi_org_path("/changeRequests"), query=query)
        return coerce_items(payload)

    def get_merge_request(self, local_id: str) -> dict[str, Any]:
        payload = self.oapi_request(
            "GET",
            self.oapi_repo_path(f"/changeRequests/{local_id}"),
        )
        return ensure_dict(payload, "MR 详情")

    def update_merge_request(self, local_id: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = self.oapi_request(
            "PUT",
            self.oapi_repo_path(f"/changeRequests/{local_id}"),
            body=body,
        )
        return ensure_dict(payload, "更新 MR 返回结果")

    def close_merge_request(self, local_id: str) -> dict[str, Any]:
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path(f"/changeRequests/{local_id}/close"),
        )
        return ensure_dict(payload, "关闭 MR 返回结果")

    def reopen_merge_request(self, local_id: str) -> dict[str, Any]:
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path(f"/changeRequests/{local_id}/reopen"),
        )
        return ensure_dict(payload, "重开 MR 返回结果")

    def merge_merge_request(self, local_id: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path(f"/changeRequests/{local_id}/merge"),
            body=body,
        )
        return ensure_dict(payload, "合并 MR 返回结果")

    def list_project_labels(self, search: str | None = None, limit: int = 100, with_counts: bool = False) -> list[dict[str, Any]]:
        payload = self.oapi_request(
            "GET",
            self.oapi_repo_path("/labels"),
            query={
                "search": search,
                "page": 1,
                "per_page": limit,
                "with_counts": str(with_counts).lower(),
            },
        )
        return coerce_items(payload)

    def create_project_label(
        self, name: str, color: str | None = DEFAULT_LABEL_COLOR, description: str | None = None
    ) -> dict[str, Any]:
        body = {"label_name": name, "label_color": color or DEFAULT_LABEL_COLOR}
        if description:
            body["label_description"] = description
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path("/labels"),
            body=body,
        )
        return ensure_dict(payload, "创建类标返回结果")

    def list_merge_request_labels(self, local_id: str) -> list[dict[str, Any]]:
        payload = self.oapi_request(
            "GET",
            self.oapi_repo_path(f"/changeRequests/{local_id}/labels"),
        )
        return coerce_items(payload)

    def link_merge_request_labels(self, local_id: str, label_ids: list[str]) -> Any:
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path(f"/changeRequests/{local_id}/labels"),
            body={"label_id_list": label_ids},
        )
        return payload

    def list_merge_request_comments(self, local_id: str) -> list[dict[str, Any]]:
        try:
            payload = self.oapi_request("GET", self.oapi_repo_path(f"/changeRequests/{local_id}/comments"))
        except ApiError:
            return []
        return coerce_items(payload)

    def create_comment(self, local_id: str, content: str) -> dict[str, Any]:
        payload = self.oapi_request(
            "POST",
            self.oapi_repo_path(f"/changeRequests/{local_id}/comments"),
            body={
                "comment_type": "GLOBAL_COMMENT",
                "content": content,
                "draft": False,
                "resolved": False,
            },
        )
        return ensure_dict(payload, "创建评论返回结果")


def unwrap_result(payload: Any) -> Any:
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload


def ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise ApiError(f"{label}不是对象: {type(value).__name__}")


def coerce_items(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for key in ("list", "items", "data", "records", "result"):
            value = result.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if isinstance(result.get("page"), dict):
            for key in ("list", "items", "data", "records"):
                value = result["page"].get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        if result.get("result") is True:
            return []
    raise ApiError(f"无法识别列表返回结构: {type(result).__name__}")


def first_present(data: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return value
    return None


def label_id(label: dict[str, Any]) -> str:
    value = first_present(label, ["id", "labelId", "label_id"])
    if value is None:
        raise ApiError(f"类标缺少 ID 字段: {label}")
    return str(value)


def label_name(label: dict[str, Any]) -> str:
    return str(first_present(label, ["name", "labelName", "title"]) or "")


def mr_local_id(mr: dict[str, Any]) -> str:
    return str(first_present(mr, ["localId", "iid", "id"]) or "")


def mr_title(mr: dict[str, Any]) -> str:
    return str(first_present(mr, ["title", "name"]) or "")


def mr_status(mr: dict[str, Any]) -> str:
    return str(first_present(mr, ["status", "state"]) or "")


def mr_web_url(mr: dict[str, Any]) -> str:
    return str(first_present(mr, ["webUrl", "detailUrl", "url"]) or "")


def mr_source_branch(mr: dict[str, Any]) -> str:
    return str(first_present(mr, ["sourceBranch", "source_branch"]) or "")


def mr_target_branch(mr: dict[str, Any]) -> str:
    return str(first_present(mr, ["targetBranch", "target_branch"]) or "")


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def print_table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        print("未找到记录。")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    for row in rows:
        print(fmt.format(*row))


def print_mr_summary(mr: dict[str, Any]) -> None:
    print(f"localId: {mr_local_id(mr)}")
    print(f"title: {mr_title(mr)}")
    print(f"status: {mr_status(mr)}")
    source = mr_source_branch(mr)
    target = mr_target_branch(mr)
    if source or target:
        print(f"branches: {source} -> {target}")
    url = mr_web_url(mr)
    if url:
        print(f"webUrl: {url}")


def print_result_summary(result: dict[str, Any]) -> None:
    if mr_local_id(result) or mr_title(result) or mr_web_url(result):
        print_mr_summary(result)
        return
    if "result" in result:
        print(f"result: {result['result']}")
    else:
        print_json(result)


def build_create_body(
    *,
    repository_id: str,
    title: str,
    description: str,
    source_branch: str,
    target_branch: str,
    reviewers: list[str],
    work_item_ids: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "sourceProjectId": repository_id,
        "sourceBranch": source_branch,
        "targetProjectId": repository_id,
        "targetBranch": target_branch,
        "title": title,
        "createFrom": "WEB",
        "description": description,
    }
    if reviewers:
        body["reviewerIds"] = reviewers
    if work_item_ids:
        body["workItemIds"] = work_item_ids
    return body


def state_query_value(state: str) -> str | None:
    mapping = {
        "opened": "opened",
        "closed": "closed",
        "merged": "merged",
        "all": None,
    }
    return mapping[state]


def resolve_label(client: YunxiaoClient, name: str, create_missing: bool) -> dict[str, Any]:
    labels = client.list_project_labels(search=name, limit=100)
    for label in labels:
        if label_name(label) == name:
            return label
    if create_missing:
        return client.create_project_label(name)
    raise CliError(f"未找到类标: {name}。先执行 label create {name}，或加 --create-missing-label")


def ensure_repository_id(context: YunxiaoContext, client: YunxiaoClient, purpose: str) -> str:
    existing = context.config.get("repository_id")
    if existing:
        return str(existing)
    repo = client.get_repository()
    if repo:
        context.maybe_cache_repository_id(repo)
    resolved = context.config.get("repository_id")
    if resolved:
        return str(resolved)
    raise CliError(
        f"{purpose} 需要数字 repository_id，但无法从云效 API 自动解析。"
        f"请在 {context.config_path} 中补充 repository_id。"
    )


def command_doctor(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    print("yunxiao-mr doctor")
    print(f"git_root: {context.git_root}")
    print(f"config: {context.config_path}")
    print(f"domain: {context.domain}")
    print(f"api_domain: {context.api_domain}")
    print(f"organization_id: {context.organization_id}")
    print(f"repository_path: {context.repository_path}")
    print(f"repository_identity: {context.repository_identity}")
    if context.config.get("repository_id"):
        print(f"repository_id: {context.config['repository_id']}")
    print(f"default_target_branch: {context.default_target_branch}")
    if args.skip_api:
        print("api: skipped")
        return 0
    client = YunxiaoClient(context, debug=args.debug)
    client.require_token()
    repo = client.get_repository()
    if repo:
        context.maybe_cache_repository_id(repo)
        print("api: ok")
        if context.config.get("repository_id"):
            print(f"repository_id: {context.config['repository_id']}")
    else:
        labels = client.list_project_labels(limit=1)
        print(f"api: ok (labels={len(labels)})")
    return 0


def command_create(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    repo_id = ensure_repository_id(context, client, "创建 MR")
    head = args.head or current_branch()
    base = args.base or context.default_target_branch
    if not remote_branch_exists(context.default_remote, head):
        raise CliError(f"源分支尚未推送到 {context.default_remote}/{head}。请先执行: git push -u {context.default_remote} {head}")
    description = read_text_arg(args.body, args.body_file, "MR 描述")
    body = build_create_body(
        repository_id=repo_id,
        title=args.title,
        description=description,
        source_branch=head,
        target_branch=base,
        reviewers=args.reviewer or [],
        work_item_ids=args.work_item_ids,
    )
    mr = client.create_merge_request(body)
    labels = []
    for name in args.label or []:
        label = resolve_label(client, name, args.create_missing_label)
        labels.append(label)
    if labels:
        current = client.list_merge_request_labels(mr_local_id(mr))
        ids = sorted({*(label_id(label) for label in current), *(label_id(label) for label in labels)})
        client.link_merge_request_labels(mr_local_id(mr), ids)
    if args.json:
        print_json({"merge_request": mr, "labels": labels})
    else:
        print("MR 已创建。")
        print_mr_summary(mr)
    return 0


def command_list(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    repo_id = ensure_repository_id(context, client, "列举 MR")
    label_ids = None
    if args.label:
        label = resolve_label(client, args.label, False)
        label_ids = label_id(label)
    mrs = client.list_merge_requests(
        page=1,
        pageSize=args.limit,
        projectIds=repo_id,
        state=state_query_value(args.state),
        authorIds=args.author,
        reviewerIds=args.reviewer,
        search=args.search,
        labelIds=label_ids,
    )
    if args.json:
        print_json(mrs)
    else:
        rows = [
            [
                mr_local_id(mr),
                mr_title(mr),
                f"{mr_source_branch(mr)} -> {mr_target_branch(mr)}",
                mr_status(mr),
                mr_web_url(mr),
            ]
            for mr in mrs
        ]
        print_table(rows, ["localId", "title", "source -> target", "status", "webUrl"])
    return 0


def command_view(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    ensure_repository_id(context, client, "查看 MR")
    mr = client.get_merge_request(args.local_id)
    comments = client.list_merge_request_comments(args.local_id) if args.comments else None
    labels = client.list_merge_request_labels(args.local_id)
    if args.json:
        out = {"merge_request": mr, "labels": labels}
        if comments is not None:
            out["comments"] = comments
        print_json(out)
    else:
        print_mr_summary(mr)
        if labels:
            print("labels: " + ", ".join(label_name(label) for label in labels))
        description = str(mr.get("description") or "")
        if description:
            print("\ndescription:")
            print(textwrap.shorten(description.replace("\n", " "), width=500, placeholder="..."))
        if comments is not None:
            print(f"\ncomments: {len(comments)}")
            for comment in comments[:20]:
                content = str(first_present(comment, ["content", "body", "note"]) or "")
                author = first_present(comment, ["authorName", "author", "userName"]) or ""
                print(f"- {author}: {textwrap.shorten(content.replace(chr(10), ' '), width=160, placeholder='...')}")
    return 0


def command_edit(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    ensure_repository_id(context, client, "更新 MR")
    body: dict[str, Any] = {}
    if args.title:
        body["title"] = args.title
    if args.body or args.body_file:
        body["description"] = read_text_arg(args.body, args.body_file, "MR 描述")
    if not body:
        raise CliError("没有可更新字段。请传 --title 或 --body/--body-file")
    mr = client.update_merge_request(args.local_id, body)
    if args.json:
        print_json(mr)
    else:
        print("MR 已更新。")
        print_result_summary(mr)
    return 0


def command_label(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    if args.label_command == "list":
        labels = client.list_project_labels(search=args.search, limit=args.limit)
        if args.json:
            print_json(labels)
        else:
            rows = [[label_id(label), label_name(label), str(label.get("color") or "")] for label in labels]
            print_table(rows, ["id", "name", "color"])
        return 0
    if args.label_command == "create":
        label = client.create_project_label(args.name, color=args.color, description=args.description)
        if args.json:
            print_json(label)
        else:
            print(f"类标已创建: {label_name(label)} ({label_id(label)})")
        return 0
    if args.label_command in {"add", "remove"}:
        current = client.list_merge_request_labels(args.local_id)
        if args.label_command == "add":
            target = resolve_label(client, args.name, args.create_missing_label)
            ids = sorted({*(label_id(label) for label in current), label_id(target)})
            client.link_merge_request_labels(args.local_id, ids)
            result = {"localId": args.local_id, "labelIds": ids}
            if args.json:
                print_json(result)
            else:
                print(f"已关联类标: {args.name}")
            return 0
        remaining = [label for label in current if label_name(label) != args.name]
        if len(remaining) == len(current):
            if args.json:
                print_json({"localId": args.local_id, "noop": True, "message": "label not present"})
            else:
                print(f"MR 未关联类标 {args.name}，无需移除。")
            return 0
        ids = sorted(label_id(label) for label in remaining)
        client.link_merge_request_labels(args.local_id, ids)
        if args.json:
            print_json({"localId": args.local_id, "labelIds": ids})
        else:
            print(f"已移除类标: {args.name}")
        return 0
    raise CliError("未知 label 子命令")


def command_comment(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    content = read_text_arg(args.body, args.body_file, "评论内容")
    if not content.strip():
        raise CliError("评论内容不能为空")
    result = client.create_comment(args.local_id, content)
    if args.json:
        print_json(result)
    else:
        print("评论已创建。")
    return 0


def command_close(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    ensure_repository_id(context, client, "关闭 MR")
    mr = client.close_merge_request(args.local_id)
    if args.json:
        print_json(mr)
    else:
        print("MR 已关闭。")
        print_result_summary(mr)
    return 0


def command_reopen(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    ensure_repository_id(context, client, "重开 MR")
    mr = client.reopen_merge_request(args.local_id)
    if args.json:
        print_json(mr)
    else:
        print("MR 已重开。")
        print_result_summary(mr)
    return 0


def has_failed_merge_requirements(mr: dict[str, Any]) -> str | None:
    conflict = first_present(mr, ["conflictCheckStatus", "hasConflict", "isConflict"])
    if isinstance(conflict, bool) and conflict:
        return "MR 存在冲突"
    if isinstance(conflict, str) and conflict.upper() in {"CONFLICT", "HAS_CONFLICT", "FAILED"}:
        return f"MR 冲突检查未通过: {conflict}"
    requirements = mr.get("allRequirementsPass")
    if requirements is False:
        return "MR 卡点未全部通过"
    return None


def command_merge(args: argparse.Namespace) -> int:
    context = YunxiaoContext(Path(args.config), args.remote)
    client = YunxiaoClient(context, debug=args.debug)
    ensure_repository_id(context, client, "合并 MR")
    mr = client.get_merge_request(args.local_id)
    reason = has_failed_merge_requirements(mr)
    if reason and not args.force:
        raise CliError(f"{reason}。如确认云效允许合并，可加 --force")
    body: dict[str, Any] = {"mergeType": args.method}
    if args.delete_branch:
        body["removeSourceBranch"] = True
    merged = client.merge_merge_request(args.local_id, body)
    if args.json:
        print_json(merged)
    else:
        print("MR 已合并。")
        print_result_summary(merged)
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置缓存路径")
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help="Git remote 名称")
    parser.add_argument("--debug", action="store_true", help="输出脱敏调试信息")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yunxiao-mr",
        description="管理阿里云云效 Codeup 合并请求。",
    )
    add_common(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查本地配置和云效 API 权限")
    doctor.add_argument("--skip-api", action="store_true", help="跳过云效 API 调用")
    doctor.set_defaults(func=command_doctor)

    create = subparsers.add_parser("create", help="创建合并请求")
    create.add_argument("--title", required=True, help="MR 标题")
    create.add_argument("--body", help="MR 描述")
    create.add_argument("--body-file", help="从文件读取 MR 描述")
    create.add_argument("--head", help="源分支，默认当前分支")
    create.add_argument("--base", help="目标分支，默认配置的 default_target_branch")
    create.add_argument("--reviewer", action="append", help="评审人 ID，可重复")
    create.add_argument("--work-item-ids", help="关联工作项 ID，多个用逗号分隔")
    create.add_argument("--label", action="append", help="创建成功后关联类标，可重复")
    create.add_argument("--create-missing-label", action="store_true", help="类标不存在时自动创建")
    create.add_argument("--json", action="store_true", help="输出 JSON")
    create.set_defaults(func=command_create)

    list_parser = subparsers.add_parser("list", help="列举合并请求")
    list_parser.add_argument("--state", choices=["opened", "merged", "closed", "all"], default="opened")
    list_parser.add_argument("--author", help="作者 ID")
    list_parser.add_argument("--reviewer", help="评审人 ID")
    list_parser.add_argument("--search", help="搜索关键词")
    list_parser.add_argument("--label", help="按类标名过滤")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=command_list)

    view = subparsers.add_parser("view", help="查看合并请求详情")
    view.add_argument("local_id")
    view.add_argument("--comments", action="store_true", help="同时列举评论")
    view.add_argument("--json", action="store_true")
    view.set_defaults(func=command_view)

    edit = subparsers.add_parser("edit", help="更新合并请求")
    edit.add_argument("local_id")
    edit.add_argument("--title")
    edit.add_argument("--body")
    edit.add_argument("--body-file")
    edit.add_argument("--json", action="store_true")
    edit.set_defaults(func=command_edit)

    label = subparsers.add_parser("label", help="管理项目类标和 MR 类标")
    label_sub = label.add_subparsers(dest="label_command", required=True)
    label_list = label_sub.add_parser("list", help="列举项目类标")
    label_list.add_argument("--search")
    label_list.add_argument("--limit", type=int, default=100)
    label_list.add_argument("--json", action="store_true")
    label_list.set_defaults(func=command_label)
    label_create = label_sub.add_parser("create", help="创建项目类标")
    label_create.add_argument("name")
    label_create.add_argument("--color", default=DEFAULT_LABEL_COLOR)
    label_create.add_argument("--description")
    label_create.add_argument("--json", action="store_true")
    label_create.set_defaults(func=command_label)
    label_add = label_sub.add_parser("add", help="给 MR 添加类标")
    label_add.add_argument("local_id")
    label_add.add_argument("name")
    label_add.add_argument("--create-missing-label", action="store_true")
    label_add.add_argument("--json", action="store_true")
    label_add.set_defaults(func=command_label)
    label_remove = label_sub.add_parser("remove", help="移除 MR 类标")
    label_remove.add_argument("local_id")
    label_remove.add_argument("name")
    label_remove.add_argument("--json", action="store_true")
    label_remove.set_defaults(func=command_label)

    comment = subparsers.add_parser("comment", help="创建 MR 评论")
    comment.add_argument("local_id")
    comment.add_argument("--body")
    comment.add_argument("--body-file")
    comment.add_argument("--json", action="store_true")
    comment.set_defaults(func=command_comment)

    close = subparsers.add_parser("close", help="关闭 MR")
    close.add_argument("local_id")
    close.add_argument("--json", action="store_true")
    close.set_defaults(func=command_close)

    reopen = subparsers.add_parser("reopen", help="重开 MR")
    reopen.add_argument("local_id")
    reopen.add_argument("--json", action="store_true")
    reopen.set_defaults(func=command_reopen)

    merge = subparsers.add_parser("merge", help="合并 MR")
    merge.add_argument("local_id")
    merge.add_argument("--method", choices=["no-fast-forward", "squash", "rebase", "ff-only"], default="squash")
    merge.add_argument("--delete-branch", action="store_true")
    merge.add_argument("--force", action="store_true", help="跳过本地可见的冲突/卡点预检查")
    merge.add_argument("--json", action="store_true")
    merge.set_defaults(func=command_merge)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(f"错误: {redact(str(exc))}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
