import asyncio

from tars.database.base import Database
from tars.orchestration.orchestration_memory import OrchestrationMemory


def test_task_lifecycle():
    om = OrchestrationMemory(db=Database(":memory:"))
    tid = om.start_task(session_id="s1", goal="安排COSCO123靠泊")
    om.record_output(tid, agent_type="berth", subtask="选泊位", output="3号泊位空闲")
    om.record_output(tid, agent_type="yard", subtask="选堆场", output="A区可用")
    om.set_shared(tid, "berth_choice", {"berth": "3号"}, by="berth")
    outs = om.get_outputs(tid)
    assert len(outs) == 2
    assert om.get_shared(tid)["berth_choice"]["berth"] == "3号"
    om.finish_task(tid, status="done")
    assert om.get_task(tid)["status"] == "done"


def test_parallel_persists_outputs():
    db = Database(":memory:")
    om = OrchestrationMemory(db=db)
    tid = om.start_task("s1", "并行选泊位和堆场")
    from tars.agent.subagent_manager import SubAgentManager

    mgr = SubAgentManager()
    asyncio.run(mgr.run_parallel_tasks(
        [{"agent_type": "research", "task": "查3号泊位状态"}],
        orch_mem=om, task_id=tid))
    assert len(om.get_outputs(tid)) >= 1
