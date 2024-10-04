async def post_garden(client, garden_data):
    """POST garden data to populate mock DB session.

    NB: this is not a fixture!
    """
    response = await client.post("/gardens", json=garden_data)
    assert response.status_code == 200
    return response.json()


async def post_entrypoints(client, *payloads):
    """POST entrypoint fixture data to populate mock DB session.

    NB: this is not a fixture!
    """
    for entrypoint_json in payloads:
        response = await client.post("/entrypoints", json=entrypoint_json)
        assert response.status_code == 200


async def post_modal_app(client, modal_app_data):
    """POST modal app fixture data to populate mock DB session.

    NB: this is not a fixture!
    """
    response = await client.post("/modal-apps", json=modal_app_data)
    print(response.json())
    assert response.status_code == 200
    return response.json()
