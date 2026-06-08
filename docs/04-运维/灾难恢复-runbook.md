# 灾难恢复 Runbook (v5.0.5 / P4)

数据库备份、恢复与 schema 版本管理操作手册。

## 备份

### 自动/手动快照
```bash
# 默认保留最近 7 份,写入 backend/data/backups/
python backend/scripts/backup_db.py

# 自定义保留份数
python backend/scripts/backup_db.py --keep 30

# 自定义目录
TARS_BACKUP_DIR=/mnt/backups python backend/scripts/backup_db.py
```
- SQLite:使用在线 `.backup` API,运行中备份安全,快照一致。
- Postgres:调用 `pg_dump --no-owner`,需 `DATABASE_URL` 指向目标库。

### 管理员触发(运行中实例)
```
POST /api/admin/db/backup?keep=7   (需 admin)
GET  /api/admin/db/version          (查当前 schema 版本)
```

### 建议计划
通过 cron 每日快照,异地保留至少 7 份:
```cron
0 3 * * * cd /app/backend && python scripts/backup_db.py --keep 14
```

## 恢复

### SQLite
1. 停止服务(避免写入冲突)。
2. 备份当前损坏库以便取证:`mv data/tars.db data/tars.db.corrupt`
3. 复制快照到位:`cp data/backups/tars-sqlite-<时间戳>.db data/tars.db`
4. 启动服务,确认 `GET /api/admin/db/version` 返回预期版本。

### Postgres
1. 停止服务。
2. 恢复:`psql "$DATABASE_URL" < data/backups/tars-pg-<时间戳>.sql`
   - 全库重建:先 `dropdb`/`createdb` 再导入。
3. 启动服务,核对 schema 版本。

### 恢复后校验清单
- [ ] `GET /health` 返回 200
- [ ] `GET /api/admin/db/version` 版本号与备份时一致
- [ ] 关键表行数抽样核对(users / sessions / memories)
- [ ] 登录冒烟 + 一次工具调用

## Schema 版本管理 (P4)

- 基础表由 `init_schema` 幂等创建(`CREATE TABLE IF NOT EXISTS` + 受保护 `ALTER`)。
- 增量变更走 `tars/database/migrations.py` 的 `MIGRATIONS` 列表:
  追加 `(版本号, 描述, fn)`,版本号取下一个整数。
- 启动时 `apply_migrations` 按版本顺序执行未应用迁移,记录入 `schema_versions`,
  每条恰好执行一次;失败回滚并使启动报错(避免半迁移状态)。
- 查当前版本:`GET /api/admin/db/version` 或 `migrations.current_version(conn)`。

> 回滚迁移:本框架只前滚。降级须从对应版本之前的备份恢复,再按需重放。
