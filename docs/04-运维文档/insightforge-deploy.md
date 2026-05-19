# InsightForge 部署说明（INS-2.0）

## SSE 与多 Worker（H1）

`GET /api/insight/datasources/{id}/forge/events` 使用**进程内**环形缓冲保存最近 100 条事件。多 `uvicorn` worker 时，断线重连的 `Last-Event-ID` 可能落在其他 worker 上而失效。

**GA 环境任选其一：**

1. **单 worker**：`uvicorn tars.main:app --workers 1`
2. **Ingress sticky session**：同一 `datasource_id` 的请求固定到同一 pod/worker

失效时客户端应回退到 `GET /api/insight/datasources/{id}/workflow` 全量同步状态。

## 连接限制

- 每数据源最多 **50** 路 SSE 连接，超出返回 `429` / `INSIGHT_SSE_RATE_LIMITED`

## 特性开关

`backend/config/insight.yaml`：

```yaml
feature_flags:
  chat_first_enabled: true    # GA 默认开启；可改为 false 回滚灰度
```
