from sqlalchemy import select
from app import api, database
from app.database import ResearchEvent, ResearchRun, Workspace


def running_workspace(client):
    workspace = client.post("/api/v1/chats", json={"prompt": "Xbox"}).json()
    with database.SessionLocal() as db:
        run = ResearchRun(workspace_id=workspace["id"])
        db.add(run)
        db.commit()
        return workspace, run.id


def test_cancel_stops_task_and_persists_one_terminal_event(client, monkeypatch):
    workspace, run_id = running_workspace(client)

    class Task:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    task = Task()
    monkeypatch.setitem(api._research_tasks, run_id, task)
    response = client.post(f"/api/v1/research-runs/{run_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["timeout_seconds"] == 240
    assert response.json()["started_at"].endswith(("Z", "+00:00"))
    assert task.cancelled
    assert (
        client.post(f"/api/v1/research-runs/{run_id}/cancel").json()["status"]
        == "cancelled"
    )
    with database.SessionLocal() as db:
        assert db.get(ResearchRun, run_id).status == "cancelled"
        assert db.get(Workspace, workspace["id"]).status == "research_cancelled"
        events = list(
            db.scalars(
                select(ResearchEvent).where(ResearchEvent.research_run_id == run_id)
            )
        )
        assert [event.event_type for event in events] == ["research_cancelled"]
    replay = client.get(f"/api/v1/research-runs/{run_id}/events")
    assert "event: research_cancelled" in replay.text


def test_cancel_requires_workspace_ownership(client):
    _, run_id = running_workspace(client)
    client.cookies.clear()
    assert client.post(f"/api/v1/research-runs/{run_id}/cancel").status_code == 404
    with database.SessionLocal() as db:
        assert db.get(ResearchRun, run_id).status == "running"
