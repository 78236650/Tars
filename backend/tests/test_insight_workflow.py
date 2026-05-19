"""InsightWorkflowService tests (INS-2.0)."""
from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.store import InsightProfileRunStore
from tars.insight.workflow_service import InsightWorkflowService, show_workflow_strip


def test_show_workflow_strip_needs_forge():
    assert show_workflow_strip("needs_forge", "idle") is True


def test_show_workflow_strip_ready_idle():
    assert show_workflow_strip("ready", "idle") is False


def test_show_workflow_strip_no_source():
    assert show_workflow_strip("ready", "no_source") is True


def test_get_composite_ready():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "wf-ds", "postgresql", "postgresql://localhost/x")
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "ready")

    composite = wf.get_composite(ds.id, "default")
    assert composite["datasource_state"] == "ready"
    assert composite["show_workflow_strip"] is False


def test_session_bind_and_composite():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "wf-ds2", "mysql", "mysql://localhost/y")
    session = db.create_session(tenant_id="default")
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "ready")
    wf.bind_session_datasource(session.id, "default", ds.id)

    composite = wf.get_composite(ds.id, "default", session.id)
    assert composite["session_state"] == "idle"
    assert composite["show_workflow_strip"] is False


def test_llm_context_bundle_shape():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "wf-ds3", "mysql", "mysql://localhost/z")
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "forging")

    bundle = wf.get_llm_context_bundle(ds.id, "default")
    assert "insight_workflow" in bundle
    inner = bundle["insight_workflow"]
    assert inner["datasource_state"] == "forging"
    assert inner["datasource_name"] == "wf-ds3"


def test_profile_complete_transitions_to_ready():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "wf-ds4", "postgresql", "postgresql://localhost/a")
    run_store = InsightProfileRunStore(db)
    run = run_store.create(ds.id, "default", "INS-2.0.0", {})
    run_store.complete(run.id, "default", insight_snapshot={})

    wf = InsightWorkflowService(db)
    wf.transition_on_profile_complete(ds.id, "default")
    assert wf.get_datasource_state(ds.id, "default") == "ready"
