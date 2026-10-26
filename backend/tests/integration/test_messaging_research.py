from tests.integration.conftest import profile, project_payload


async def test_direct_messaging_and_access_control(make_client):
    a = await make_client().register("asha")
    b = await make_client().register("bilal")
    c = await make_client().register("chen")
    await b.put("/api/v1/profiles/me", profile({"React": 3}))
    conv = (await a.post("/api/v1/conversations", {"user_id": b.user["id"]})).json()
    again = (await a.post("/api/v1/conversations", {"user_id": b.user["id"]})).json()
    assert conv["id"] == again["id"]
    m = await a.post(f"/api/v1/conversations/{conv['id']}/messages", {"body": "Hi! Interested in our team?"})
    assert m.status_code == 201
    assert (await b.get("/api/v1/conversations")).json()[0]["unread"] == 1
    msgs = (await b.get(f"/api/v1/conversations/{conv['id']}/messages")).json()
    assert [x["body"] for x in msgs] == ["Hi! Interested in our team?"]
    await b.post(f"/api/v1/conversations/{conv['id']}/read")
    assert (await b.get("/api/v1/conversations")).json()[0]["unread"] == 0
    # outsiders get 404, not 403
    assert (await c.get(f"/api/v1/conversations/{conv['id']}/messages")).status_code == 404
    assert (await c.post(f"/api/v1/conversations/{conv['id']}/messages", {"body": "x"})).status_code == 404
    # chen's profile is not visible and unrelated -> cannot be messaged
    assert (await a.post("/api/v1/conversations", {"user_id": c.user["id"]})).status_code == 404


async def test_idempotent_send_and_rate_limit(make_client):
    a = await make_client().register("asha")
    b = await make_client().register("bilal")
    await b.put("/api/v1/profiles/me", profile({"React": 3}))
    conv = (await a.post("/api/v1/conversations", {"user_id": b.user["id"]})).json()
    url = f"/api/v1/conversations/{conv['id']}/messages"
    first = (await a.post(url, {"body": "hello", "client_id": "abcdef123456"})).json()
    dup = (await a.post(url, {"body": "hello", "client_id": "abcdef123456"})).json()
    assert first["id"] == dup["id"]
    codes = [(await a.post(url, {"body": f"m{i}"})).status_code for i in range(6)]
    assert 429 in codes
    assert (await a.post(url, {"body": "   "})).status_code == 422


async def test_team_conversation_tracks_membership(make_client):
    owner = await make_client().register("owner")
    p = (await owner.post("/api/v1/projects", project_payload())).json()
    s = await make_client().register("sam")
    await s.put("/api/v1/profiles/me", profile({"Node.js": 3}))
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})).json()
    await s.post(f"/api/v1/invitations/{inv['id']}/accept")
    team = next(c for c in (await s.get("/api/v1/conversations")).json() if c["kind"] == "team")
    assert {x["handle"] for x in team["participants"]} == {"owner", "sam"}
    await s.delete(f"/api/v1/projects/{p['id']}/members/{s.user['id']}")
    assert (await s.get(f"/api/v1/conversations/{team['id']}/messages")).status_code == 404


async def test_research_status_pending_without_data(make_client):
    a = await make_client().register("asha")
    st = (await a.get("/api/v1/research/status")).json()
    assert st["evaluation_status"] == "pending" and st["scenarios"]["total"] == 0
    assert (await a.post("/api/v1/research/scenarios/synthetic")).status_code == 403


async def test_research_judging_flow(make_client, db):
    admin = await make_client().register("admin", email="admin@example.edu")
    r = await admin.post("/api/v1/research/scenarios/synthetic", params={"seed": 1})
    assert r.status_code == 201
    sid = r.json()["imported"][0]
    st = (await admin.get("/api/v1/research/status")).json()
    assert st["scenarios"]["synthetic"] == 30 and st["scenarios"]["real"] == 0
    assert (await admin.post(f"/api/v1/research/scenarios/{sid}/packet")).status_code == 200

    rater = await make_client().register("rater")
    assert (await rater.get("/api/v1/research/judging/tasks")).status_code == 403
    assert (await admin.post(f"/api/v1/research/raters/{rater.user['id']}")).status_code == 204
    tasks = (await rater.get("/api/v1/research/judging/tasks")).json()
    assert tasks[0]["scenario_id"] == sid
    packet = (await rater.get(f"/api/v1/research/judging/{sid}")).json()
    text = str(packet)
    assert "syn-u" not in text and "score" not in text.lower() and "M5" not in text
    labels = [c["label"] for c in packet["candidates"]]
    assert (await rater.post(f"/api/v1/research/judging/{sid}", {"ratings": {labels[0]: 2}})).status_code == 400
    ok = await rater.post(f"/api/v1/research/judging/{sid}", {"ratings": {lab: 2 for lab in labels}})
    assert ok.status_code == 201
    assert await db.judgments.count_documents({"scenario_id": sid}) == len(labels)
    again = await rater.post(f"/api/v1/research/judging/{sid}", {"ratings": {lab: 1 for lab in labels}})
    assert again.status_code == 409
