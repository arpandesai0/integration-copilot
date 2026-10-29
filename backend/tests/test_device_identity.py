from uuid import uuid4


def test_device_id_owns_chat_history(client):
    first = str(uuid4())
    second = str(uuid4())
    created = client.post(
        "/api/v1/chats",
        json={"prompt": "Slack"},
        headers={"X-Device-ID": first},
    )
    assert created.status_code == 201
    workspace = created.json()

    assert (
        client.get(
            f"/api/v1/chats/{workspace['id']}",
            headers={"X-Device-ID": first},
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/chats/{workspace['id']}",
            headers={"X-Device-ID": second},
        ).status_code
        == 404
    )


def test_invalid_device_id_is_rejected(client):
    response = client.get(
        "/api/v1/chats", headers={"X-Device-ID": "not-a-device-id"}
    )
    assert response.status_code == 400
