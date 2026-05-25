#!/usr/bin/env bash
# 知识库深度入库 v4.4 验收脚本
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:8000/api/knowledge}"
TENANT_HEADER=(-H "X-Tenant-Id: default")

echo "== 1. 创建测试集合 =="
COLL_RESP=$(curl -sf "${TENANT_HEADER[@]}" -X POST "$BASE/collections" \
  -H "Content-Type: application/json" \
  -d '{"name":"深度入库验收","description":"acceptance"}')
COLL_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['collection']['id'])" <<< "$COLL_RESP")
echo "collection_id=$COLL_ID"

TMP=$(mktemp /tmp/kb-ingest-XXXX.txt)
echo "本制度规定仓储入库须主管审批，出库须双人复核。" > "$TMP"

echo "== 2. 上传文档（异步 pending） =="
UP=$(curl -sf "${TENANT_HEADER[@]}" -X POST "$BASE/collections/$COLL_ID/documents" \
  -F "file=@$TMP;filename=policy-sample.txt" \
  -F "doc_type=policy")
DOC_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['document']['id'])" <<< "$UP")
echo "doc_id=$DOC_ID status=$(python3 -c "import json,sys; print(json.load(sys.stdin)['document']['status'])" <<< "$UP")"

echo "== 3. 轮询 status（最多 60s） =="
for i in $(seq 1 30); do
  ST=$(curl -sf "${TENANT_HEADER[@]}" "$BASE/collections/$COLL_ID/documents/$DOC_ID/status")
  STATUS=$(python3 -c "import json,sys; print(json.load(sys.stdin)['status'])" <<< "$ST")
  echo "  poll $i: $STATUS"
  if [[ "$STATUS" == "ready" || "$STATUS" == "enrichment_failed" || "$STATUS" == "failed" ]]; then
    break
  fi
  sleep 2
done

echo "== 4. GET profile =="
curl -sf "${TENANT_HEADER[@]}" "$BASE/collections/$COLL_ID/documents/$DOC_ID/profile" | python3 -m json.tool

echo "== 5. ref API（需 X-API-Key，可选 REF_API_KEY 环境变量） =="
if [[ -n "${REF_API_KEY:-}" ]]; then
  curl -sf -H "X-API-Key: $REF_API_KEY" "${TENANT_HEADER[@]}" "$BASE/ref/$DOC_ID" | python3 -m json.tool
else
  echo "跳过 ref API（未设置 REF_API_KEY）"
fi

rm -f "$TMP"

echo "== 6. browse 搜索 =="
curl -sf "${TENANT_HEADER[@]}" -X POST "$BASE/collections/$COLL_ID/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"仓储","top_k":5,"mode":"browse"}' | python3 -m json.tool

echo "== 验收完成 =="
