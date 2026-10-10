async def test_health_reports_offline_flag(client, server_settings):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "offline": True}
