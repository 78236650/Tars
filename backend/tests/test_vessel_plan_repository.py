from tars.database.base import Database
from tars.vessel_plan.repository import VesselPlanRepository
from tars.vessel_plan.seed import seed_demo_port


def test_list_berths_empty():
    db = Database(":memory:")
    repo = VesselPlanRepository(db, tenant_id="default")
    assert repo.list_berths() == []


def test_seed_demo_populates_berths_and_voyages():
    db = Database(":memory:")
    seed_demo_port(db, tenant_id="default")
    repo = VesselPlanRepository(db, tenant_id="default")
    assert len(repo.list_berths()) == 6
    assert len(repo.horizon_voyages(hours=48)) >= 8
