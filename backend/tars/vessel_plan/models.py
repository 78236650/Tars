from dataclasses import dataclass
from typing import Optional


@dataclass
class Berth:
    id: str
    name: str
    length_m: float
    depth_m: float
    crane_count: int
    yard_zone: str
    position_x: float
    position_y: float


@dataclass
class Voyage:
    id: str
    vessel_id: str
    vessel_name: str
    eta: str
    etd_est: Optional[str]
    cargo_teu: int
    target_yard_zone: str
    service_hours: float
    status: str
    length_m: float
    draft_m: float
    priority: int


@dataclass
class Assignment:
    voyage_id: str
    berth_id: Optional[str]
    etb: Optional[str]
    etd: Optional[str]
    wait_min: float
    yard_penalty: float
    score: float
    source: str
    locked: bool
