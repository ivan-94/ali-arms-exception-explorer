# 云效 MR API 参考

## 鉴权

旧版 DevOps OpenAPI 使用 `accessToken` query 参数；新版 Codeup OAPI 使用 `x-yunxiao-token` 请求头。CLI 统一从 `YUNXIAO_ACCESS_TOKEN` 读取 token，并在输出中脱敏。

## API domain

仓库 remote 里的 `codeup.aliyun.com` 是 Git/页面域名，不是标准版 OpenAPI 服务接入点。CLI 缓存两个域名：

- `domain`: 从 Git remote 推断出的 Codeup 域名，用于仓库身份推断。
- `api_domain`: OpenAPI base host。标准 Codeup remote 默认推断为 `openapi-rdc.aliyuncs.com`；专属域名可在 `.arms-exceptions/yunxiao.json` 中手动覆盖。

请求统一以 `https://{api_domain}` 为 base URL，并使用 `x-yunxiao-token` 请求头。

## Codeup OAPI

常用路径：

| 能力 | Method | Path |
| --- | --- | --- |
| 查询仓库 | `GET` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}` |
| 创建 MR | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests` |
| 查询 MR 列表 | `GET` | `/oapi/v1/codeup/organizations/{organizationId}/changeRequests` |
| 查询 MR 详情 | `GET` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}` |
| 更新 MR | `PUT` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}` |
| 关闭 MR | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/close` |
| 重开 MR | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/reopen` |
| 合并 MR | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/merge` |
| 列举项目类标 | `GET` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/labels` |
| 创建项目类标 | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/labels` |
| 列举 MR 类标 | `GET` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/labels` |
| 关联 MR 类标 | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/labels` |
| 列举 MR 评论 | `GET` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/comments` |
| 创建 MR 评论 | `POST` | `/oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/comments` |

请求头：

```text
x-yunxiao-token: <YUNXIAO_ACCESS_TOKEN>
```

全局评论 body：

```json
{
  "comment_type": "GLOBAL_COMMENT",
  "content": "comment text",
  "draft": false,
  "resolved": false
}
```

## Repository Identity

从 Codeup remote：

```text
git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git
```

推断：

```json
{
  "domain": "codeup.aliyun.com",
  "api_domain": "openapi-rdc.aliyuncs.com",
  "organization_id": "685a564391483e233edca392",
  "repository_path": "685a564391483e233edca392/sharge-web/test",
  "repository_identity": "685a564391483e233edca392%2Fsharge-web%2Ftest"
}
```

部分接口文档标注 `repositoryId` 可以是数字代码库 ID 或 URL encode 后的全路径。CLI 会先用 `repository_identity` 查询仓库，拿到数字 `repository_id` 后写回缓存；后续命令优先使用数字 ID。

## Label Semantics

`LinkMergeRequestLabel` 是覆盖式更新。调用时必须传入完整目标类标 ID 列表。实现 `label add/remove` 时必须：

1. 读取当前 MR 已有关联类标。
2. 计算完整目标类标 ID 列表。
3. 调用 link 接口重写完整列表。

不要只传新增或删除的一个类标。

## Known Limits

- `edit` 只支持更新标题和描述；云效 `UpdateMergeRequest` 官方接口不支持修改目标分支。
- `comment` 使用 Codeup OAPI；如果企业域名或仓库版本不支持，命令会失败并给出可操作错误。
- `merge` 默认会先读取 MR 详情，若能看到冲突或卡点未通过字段则提前失败。
- 真实验收发现：某些个人 token 可读仓库/类标，但对 `CreateChangeRequest`、`CreateProjectLabel` 返回 403 `Current token has no permission to api.`。这属于 token 权限边界，不要把 token 写入配置或尝试降级保存凭证。
