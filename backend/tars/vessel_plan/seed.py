from datetime import datetime, timedelta, timezone

from .models import Berth
from .repository import VesselPlanRepository


def seed_demo_port(db, tenant_id: str = "default") -> dict:
    repo = VesselPlanRepository(db, tenant_id=tenant_id)
    repo.clear_demo_data()

    berths = [
        Berth("b1", "1号泊位", 350, 15.5, 3, "A", 0, 0),
        Berth("b2", "2号泊位", 320, 14.0, 2, "A", 120, 0),
        Berth("b3", "3号泊位", 400, 16.0, 4, "B", 240, 0),
        Berth("b4", "4号泊位", 280, 13.5, 2, "B", 360, 0),
        Berth("b5", "5号泊位", 300, 14.5, 2, "C", 480, 0),
        Berth("b6", "6号泊位", 260, 12.5, 1, "C", 600, 0),
    ]
    for b in berths:
        repo.upsert_berth(b)

    vessels = [
        ("COSCO123", "COSCO123", "UN1234567", 366, 13.2, 2),
        ("MAERSK88", "MAERSK88", "UN2345678", 340, 12.8, 1),
        ("EVER101", "EVER GIVEN", "UN3456789", 400, 15.0, 0),
        ("HLC456", "HLC456", "UN4567890", 295, 11.5, 0),
        ("OOCL789", "OOCL789", "UN5678901", 320, 12.0, 1),
        ("YML222", "YML222", "UN6789012", 280, 10.5, 0),
        ("PIL333", "PIL333", "UN7890123", 260, 10.0, 0),
        ("WHL444", "WHL444", "UN8901234", 310, 11.8, 0),
        ("SITC555", "SITC555", "UN9012345", 240, 9.5, 0),
        ("ZIM666", "ZIM666", "UN0123456", 330, 12.5, 1),
        ("ONE777", "ONE777", "UN1122334", 350, 13.0, 2),
        ("CMA888", "CMA888", "UN2233445", 300, 11.0, 0),
    ]
    zones = ["A", "A", "B", "B", "C", "C"]
    now = datetime.now(timezone(timedelta(hours=8)))
    for i, (vid, name, imo, loa, draft, pri) in enumerate(vessels):
        db.execute(
            "INSERT INTO vp_vessels (id, tenant_id, name, imo, length_m, draft_m, priority) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vid, tenant_id, name, imo, loa, draft, pri),
        )
        eta = (now + timedelta(hours=4 + i * 3.5)).isoformat()
        db.execute(
            "INSERT INTO vp_voyages (id, tenant_id, vessel_id, eta, etd_est, cargo_teu, "
            "target_yard_zone, service_hours, status) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, 'pending')",
            (
                f"v{i + 1}",
                tenant_id,
                vid,
                eta,
                600 + i * 50,
                zones[i % 6],
                8 + (i % 3) * 2,
            ),
        )
    return {"berths": 6, "voyages": 12, "terminal": "元洪 Demo 码头"}
