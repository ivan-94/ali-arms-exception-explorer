# 云效 MR API 参考

## 鉴权

旧版 DevOps OpenAPI 使用 `accessToken` query 参数；新版 Codeup OAPI 使用 `x-yunxiao-token` 请求头。CLI 统一从 `YUNXIAO_ACCESS_TOKEN` 读取 token，并在输出中脱敏。

## DevOps API

这些接口以 `https://{domain}` 为 base URL，并带 query：

- `organizationId`
- `accessToken`

常用路径：

| 能力 | Method | Path |
| --- | --- | --- |
| 查询仓库 | `GET` | `/repository/get` |
| 创建 MR | `POST` | `/api/v4/projects/{repositoryId}/merge_requests` |
| 查询 MR 列表 | `GET` | `/api/v4/projects/merge_requests/advanced_search` |
| 查询 MR 详情 | `GET` | `/api/v4/projects/{repositoryId}/merge_requests/{localId}/detail` |
| 更新 MR | `PUT` | `/api/v4/projects/{repositoryId}/merge_requests/{localId}` |
| 关闭 MR | `POST` | `/api/v4/projects/{repositoryId}/merge_requests/{localId}/close` |
| 重开 MR | `POST` | `/api/v4/projects/{repositoryId}/merge_requests/{localId}/reopen` |
| 合并 MR | `POST` | `/api/v4/projects/{repositoryId}/merge_requests/{localId}/merge` |
| 列举项目类标 | `GET` | `/api/v4/projects/labels` |
| 创建项目类标 | `POST` | `/api/v4/projects/labels` |
| 列举 MR 类标 | `GET` | `/api/v4/projects/merge_requests/labels` |
| 关联 MR 类标 | `POST` | `/api/v4/projects/merge_requests/link_labels` |
| 列举 MR 评论 | `POST` | `/api/v4/projects/merge_requests/comments/list_comments` |

## Codeup OAPI

全局评论使用新版 OAPI：

```text
POST /oapi/v1/codeup/organizations/{organizationId}/repositories/{repositoryId}/changeRequests/{localId}/comments
```

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
  "organization_id": "685a564391483e233edca392",
  "repository_path": "685a564391483e233edca392/sharge-web/test",
  "repository_identity": "685a564391483e233edca392%2Fsharge-web%2Ftest"
}
```

部分接口文档标注 `repositoryId` 为数字代码库 ID。CLI 会优先调用 `/repository/get` 尝试把 `repository_path` 解析成数字 `repository_id` 并缓存；解析失败时对支持路径身份的接口仍然继续运行。query 参数中的 `repositoryIdentity` 使用未编码全路径，URL path 中的仓库身份才使用 URL encode 后的 `repository_identity`。

## Label Semantics

`LinkMergeRequestLabel` 是覆盖式更新。调用时必须传入完整目标类标 ID 列表。实现 `label add/remove` 时必须：

1. 读取当前 MR 已有关联类标。
2. 计算完整目标类标 ID 列表。
3. 调用 link 接口重写完整列表。

不要只传新增或删除的一个类标。

## Known Limits

- `edit` 只支持更新标题和描述；云效 `UpdateMergeRequest` 官方接口不支持修改目标分支。
- `comment` 使用新版 Codeup OAPI；如果企业域名或仓库版本不支持，命令会失败并给出 MR URL。
- `merge` 默认会先读取 MR 详情，若能看到冲突或卡点未通过字段则提前失败。
