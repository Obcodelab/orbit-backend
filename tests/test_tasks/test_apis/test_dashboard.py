from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import _create_org
from tests.test_projects.test_apis.test_project import PROJECTS, _create_project
from tests.test_tasks.test_apis.test_task import _create_task


async def test_dashboard_reports_counts_by_status(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/status",
        json={"status": "done"},
        headers=authenticated_user.headers,
    )
    await _create_task(client, project["project_id"], authenticated_user, "Second")

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/dashboard",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_tasks"] == 2
    assert body["tasks_by_status"]["done"] == 1
    assert body["tasks_by_status"]["todo"] == 1
    assert body["completion_percent"] == 50.0


async def test_dashboard_empty_project_has_zero_completion(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/dashboard",
        headers=authenticated_user.headers,
    )

    assert response.json()["completion_percent"] == 0.0
