"""港航物流领域实体/关系 schema (v4.4.0)。

entities.type 复用现有自由字符串列，无需迁移。

attributes(JSON) 建议字段：
  berth:   {"length_m": 300, "depth_m": 16, "status": "free|occupied|maintenance"}
  crane:   {"model": "QC", "outreach_m": 65, "status": "running|fault|idle"}
  voyage:  {"eta": "ISO8601", "etd": "ISO8601", "direction": "import|export"}
  vessel:  {"loa_m": 366, "imo": "..."}
"""

# 实体类型
ENTITY_TERMINAL = "terminal"        # 码头  e.g. 元洪码头
ENTITY_BERTH = "berth"              # 泊位  e.g. 3号泊位
ENTITY_CRANE = "crane"              # 岸桥  e.g. QC-7
ENTITY_VESSEL = "vessel"            # 船舶  e.g. COSCO PRIDE
ENTITY_VOYAGE = "voyage"            # 航次  e.g. COSCO123
ENTITY_YARD = "yard"                # 堆场  e.g. A区堆场
ENTITY_CARGO_OWNER = "cargo_owner"  # 货主  e.g. 中远海运
ENTITY_CONTAINER = "container"      # 集装箱组/箱

PORT_ENTITY_TYPES = [
    ENTITY_TERMINAL, ENTITY_BERTH, ENTITY_CRANE, ENTITY_VESSEL,
    ENTITY_VOYAGE, ENTITY_YARD, ENTITY_CARGO_OWNER, ENTITY_CONTAINER,
]

# 关系类型 (memory_relations.relation_type)
REL_BERTH_OF = "berth_of"            # 泊位 → 码头
REL_CRANE_SERVES = "crane_serves"    # 岸桥 → 泊位
REL_VOYAGE_OF = "voyage_of"          # 航次 → 船舶
REL_VOYAGE_BERTHS_AT = "berths_at"   # 航次 → 泊位
REL_YARD_OF = "yard_of"              # 堆场 → 码头
REL_CARGO_OF = "cargo_of"            # 货主 → 航次

PORT_RELATION_TYPES = [
    REL_BERTH_OF, REL_CRANE_SERVES, REL_VOYAGE_OF,
    REL_VOYAGE_BERTHS_AT, REL_YARD_OF, REL_CARGO_OF,
]

PORT_ENTITY_TYPE_HINT = (
    f"优先将实体归类为以下港航类型之一（不匹配再用通用类型 person|project|tech|concept|org）："
    f"{', '.join(PORT_ENTITY_TYPES)}"
)

PORT_RELATION_TYPE_HINT = (
    f"港航领域关系优先使用：{', '.join(PORT_RELATION_TYPES)}；"
    f"通用关系仍可用 works_on|uses|colleague_of|part_of"
)
