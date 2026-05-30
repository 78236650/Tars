"""风电智能配载工具 — PortMeta Agent 集成。"""
from typing import Any, Dict, Optional
from ..base import BaseTool, ToolResult


class WindStowageTool(BaseTool):
    name: str = "wind_stowage_solve"
    description: str = (
        "风电智能配载求解：为风电设备（叶片/塔筒/机舱）在重吊船上生成最优配载方案。"
        "默认使用 T110.5-70A 风电组件和 TEST-HEAVYLIFT-01 船型。"
        "返回最优套数、各舱口分布、旁通板使用量和约束校验结果。"
        "触发词：风电配载、wind stowage、叶片配载、船载方案、配载优化。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "cargo_type": {
                "type": "string",
                "description": "风电设备类型，默认 T110.5-70A",
                "default": "T110.5-70A",
            },
            "vessel_name": {
                "type": "string",
                "description": "船型名称，默认 TEST-HEAVYLIFT-01",
                "default": "TEST-HEAVYLIFT-01",
            },
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        try:
            from tars.wind_stowage.solver import solve
            result = solve()
            if result.success:
                return ToolResult(
                    success=True,
                    output=result.message,
                    metadata={
                        "total_sets": result.total_sets,
                        "placement_count": len(result.placements),
                        "solver_time": result.solver_time,
                        "placements": [
                            {
                                "component_no": p.component_no,
                                "layer": p.layer,
                                "x": p.x,
                                "y": p.y,
                                "x_end": p.x_end,
                                "y_end": p.y_end,
                                "direction": p.direction,
                                "tier": p.tier,
                                "hatch_id": p.hatch_id,
                                "bypass_board_id": p.bypass_board_id,
                            }
                            for p in result.placements
                        ],
                    },
                )
            return ToolResult(success=False, output=result.message)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"配载求解失败: {str(e)}")
