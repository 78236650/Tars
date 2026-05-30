"""风电智能配载数据模型。"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class CargoData:
    """风电货物组件定义。"""
    component_no: int          # 组件编号 1-6
    name: str                  # 组件名称
    length: float              # 长度 mm
    width: float               # 宽度 mm
    height: float              # 高度 mm
    weight: float              # 重量 t
    direction: int = 1         # 1=纵向(x长) 0=横向(y长)
    tier: int = 1              # 默认层数

    @property
    def footprint_area(self) -> float:
        """占地面积 m²"""
        return self.length * self.width / 1e6


@dataclass
class HatchData:
    """舱口数据。"""
    hatch_id: str
    x_start: float
    x_end: float
    y_start: float
    y_end: float
    max_height: float          # 该舱口最大堆高 mm
    max_load: float = 3.0      # 最大载荷 t/m²

    @property
    def area(self) -> float:
        return (self.x_end - self.x_start) * (self.y_end - self.y_start) / 1e6


@dataclass
class BypassBoard:
    """旁通板。"""
    board_id: str
    layer: int                 # 所在层 (2 或 3)
    x_start: float
    x_end: float
    y_start: float
    y_end: float
    hatch_id: str

    @property
    def area(self) -> float:
        return (self.x_end - self.x_start) * (self.y_end - self.y_start) / 1e6


@dataclass
class VesselConfig:
    """船舶配置。"""
    vessel_name: str
    hatches: List[HatchData] = field(default_factory=list)
    bypass_boards: List[BypassBoard] = field(default_factory=list)
    max_bypass_count: int = 18
    x_gap: float = 500         # x 向最小间隙 mm
    y_gap: float = 100         # y 向最小间隙 mm
    max_deck_load: float = 3.0 # 甲板最大载荷 t/m²


@dataclass
class CargoPlacement:
    """单个货物放置方案。"""
    component_no: int
    layer: int                 # 1-4
    x: float
    y: float
    direction: int             # 0=横向 1=纵向
    tier: int                  # 层数 1/2
    hatch_id: Optional[str] = None
    bypass_board_id: Optional[str] = None

    @property
    def x_end(self) -> float:
        cargo = T110_CARGO[self.component_no - 1]
        return self.x + (cargo.length if self.direction == 1 else cargo.width)

    @property
    def y_end(self) -> float:
        cargo = T110_CARGO[self.component_no - 1]
        return self.y + (cargo.width if self.direction == 1 else cargo.length)

    @property
    def total_height(self) -> float:
        cargo = T110_CARGO[self.component_no - 1]
        return cargo.height * self.tier


@dataclass
class StowageResult:
    """配载结果。"""
    total_sets: int
    success: bool
    placements: List[CargoPlacement] = field(default_factory=list)
    solver_time: float = 0.0
    message: str = ""


# T110.5-70A 风电组件参数（6 个组件）
T110_CARGO: List[CargoData] = [
    CargoData(1, "叶片 Blade 1",   length=75000, width=4200,  height=4200,  weight=35.0, direction=1, tier=1),
    CargoData(2, "叶片 Blade 2",   length=75000, width=4200,  height=4200,  weight=35.0, direction=1, tier=1),
    CargoData(3, "叶片 Blade 3",   length=75000, width=4200,  height=4200,  weight=35.0, direction=1, tier=1),
    CargoData(4, "塔筒 Tower 1",   length=30000, width=4500,  height=4500,  weight=80.0, direction=1, tier=2),
    CargoData(5, "塔筒 Tower 2",   length=30000, width=4500,  height=4500,  weight=80.0, direction=1, tier=2),
    CargoData(6, "机舱 Nacelle",   length=12000, width=5000,  height=5000,  weight=120.0, direction=1, tier=1),
]


# 默认测试船型（4 个舱口）
DEFAULT_VESSEL = VesselConfig(
    vessel_name="TEST-HEAVYLIFT-01",
    hatches=[
        HatchData("H1", x_start=0,    x_end=28000, y_start=0,  y_end=22000, max_height=20000),
        HatchData("H2", x_start=29000, x_end=57000, y_start=0,  y_end=22000, max_height=20000),
        HatchData("H3", x_start=58000, x_end=86000, y_start=0,  y_end=22000, max_height=20000),
        HatchData("H4", x_start=87000, x_end=115000, y_start=0, y_end=22000, max_height=20000),
        HatchData("H5", x_start=116000, x_end=144000, y_start=0, y_end=22000, max_height=20000),
        HatchData("H6", x_start=145000, x_end=174000, y_start=0, y_end=22000, max_height=20000),
        HatchData("H7", x_start=175000, x_end=204000, y_start=0, y_end=22000, max_height=20000),
        HatchData("H8", x_start=205000, x_end=234000, y_start=0, y_end=22000, max_height=20000),
    ],
    bypass_boards=[
        BypassBoard("B2_H1_1", 2, x_start=2000,  x_end=26000, y_start=2000, y_end=18000, hatch_id="H1"),
        BypassBoard("B2_H2_1", 2, x_start=31000, x_end=55000, y_start=2000, y_end=18000, hatch_id="H2"),
        BypassBoard("B2_H3_1", 2, x_start=60000, x_end=84000, y_start=2000, y_end=18000, hatch_id="H3"),
        BypassBoard("B2_H4_1", 2, x_start=89000, x_end=113000, y_start=2000, y_end=18000, hatch_id="H4"),
        BypassBoard("B2_H5_1", 2, x_start=118000, x_end=142000, y_start=2000, y_end=20000, hatch_id="H5"),
        BypassBoard("B2_H6_1", 2, x_start=147000, x_end=172000, y_start=2000, y_end=20000, hatch_id="H6"),
        BypassBoard("B2_H7_1", 2, x_start=177000, x_end=202000, y_start=2000, y_end=20000, hatch_id="H7"),
        BypassBoard("B2_H8_1", 2, x_start=207000, x_end=232000, y_start=2000, y_end=20000, hatch_id="H8"),
    ],
    max_bypass_count=18,
)
