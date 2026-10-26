import asyncio

from tests.integration.conftest import profile, project_payload


async def _owner_with_project(make_client, **kw):
    owner = await make_client().register("owner")
    await owner.put("/api/v1/profiles/me", profile({"React": 3}, primary_roles=["Frontend"]))
    r = await owner.post("/api/v1/projects", project_payload(**kw))
    assert r.status_code == 201, r.text
    return owner, r.json()


async def _student(make_client, name, skills, **kw):
    s = await make_client().register(name)
    r = await s.put("/api/v1/profiles/me", profile(skills, **kw))
    assert r.status_code == 200, r.text
    return s


async def test_create_project_normalises_and_derives_positions(make_client):
    owner, p = await _owner_with_project(make_client)
    assert [r["skill"] for r in p["requirements"]] == ["React", "Machine Learning", "Node.js", "PostgreSQL"]
    assert p["open_positions"] == 3 and p["members"][0]["is_owner"]
    assert p["viewer"]["is_owner"] is True


async def test_project_validation(make_client):
    owner = await make_client().register("owner")
    bad = [
        project_payload(requirements=[]),
        project_payload(requirements=[{"skill": "nodejs", "importance": 2, "desired_proficiency": 2},
                                      {"skill": "Node.js", "importance": 1, "desired_proficiency": 1}]),
        project_payload(requirements=[{"skill": "React", "importance": 4, "desired_proficiency": 2}]),
        project_payload(synchronous=True, min_shared_slots=0),
        project_payload(availability_mandatory=True),
        project_payload(target_size=1),
    ]
    for body in bad:
        r = await owner.post("/api/v1/projects", body)
        assert r.status_code in (400, 422), (body, r.text)


async def test_only_owner_can_edit_with_version_check(make_client):
    owner, p = await _owner_with_project(make_client)
    other = await make_client().register("other")
    body = {**project_payload(title="Renamed project"), "version": p["version"], "status": "open"}
    assert (await other.put(f"/api/v1/projects/{p['id']}", body)).status_code == 403
    r = await owner.put(f"/api/v1/projects/{p['id']}", body)
    assert r.status_code == 200 and r.json()["title"] == "Renamed project"
    assert (await owner.put(f"/api/v1/projects/{p['id']}", body)).status_code == 409  # stale version


async def test_discovery_filters(make_client):
    owner, p = await _owner_with_project(make_client)
    await owner.post("/api/v1/projects", project_payload(title="Robot arm", opportunity_type="research",
                                                         requirements=[{"skill": "Arduino", "importance": 3, "desired_proficiency": 2}]))
    await owner.post("/api/v1/projects", project_payload(title="Secret", visibility="private"))
    c = make_client()
    titles = lambda r: {i["title"] for i in r.json()["items"]}  # noqa: E731
    assert titles(await c.get("/api/v1/projects")) == {"Placement prep platform", "Robot arm"}
    assert titles(await c.get("/api/v1/projects", params={"opportunity_type": "research"})) == {"Robot arm"}
    assert titles(await c.get("/api/v1/projects", params={"skill": "postgres"})) == {"Placement prep platform"}
    assert titles(await c.get("/api/v1/projects", params={"q": "robot"})) == {"Robot arm"}
    page = (await c.get("/api/v1/projects", params={"limit": 1})).json()
    assert page["total"] == 2 and len(page["items"]) == 1


async def test_private_project_hidden(make_client):
    owner, p = await _owner_with_project(make_client, visibility="private")
    c = await make_client().register("stranger")
    assert (await c.get(f"/api/v1/projects/{p['id']}")).status_code == 404


async def test_invite_accept_updates_team_and_roles(make_client):
    owner, p = await _owner_with_project(make_client)
    s = await _student(make_client, "sam", {"Node.js": 3}, primary_roles=["Backend"])
    r = await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"], "role": "backend"})
    assert r.status_code == 201 and r.json()["role"] == "Backend"
    dup = await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})
    assert dup.status_code == 409
    inbox = (await s.get("/api/v1/invitations")).json()
    assert len(inbox) == 1
    assert (await owner.post(f"/api/v1/invitations/{inbox[0]['id']}/accept")).status_code == 403
    r = await s.post(f"/api/v1/invitations/{inbox[0]['id']}/accept")
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    proj = (await owner.get(f"/api/v1/projects/{p['id']}")).json()
    assert proj["open_positions"] == 2 and "Backend" not in proj["vacant_roles"]
    assert {m["handle"] for m in proj["members"]} == {"owner", "sam"}
    hist = (await s.get(f"/api/v1/projects/{p['id']}/history")).json()
    assert [h["type"] for h in hist] == ["created", "joined"]


async def test_decline_cancel_and_join_request(make_client):
    owner, p = await _owner_with_project(make_client)
    s = await _student(make_client, "sam", {"Node.js": 3})
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})).json()
    assert (await s.post(f"/api/v1/invitations/{inv['id']}/decline")).json()["status"] == "declined"
    assert (await s.post(f"/api/v1/invitations/{inv['id']}/accept")).status_code == 409
    req = (await s.post(f"/api/v1/projects/{p['id']}/join-requests", {"message": "I can do the backend"})).json()
    assert req["kind"] == "request"
    assert (await s.post(f"/api/v1/invitations/{req['id']}/accept")).status_code == 403  # requester cannot accept own
    assert (await owner.post(f"/api/v1/invitations/{req['id']}/accept")).json()["status"] == "accepted"


async def test_concurrent_acceptance_cannot_exceed_target(make_client, db):
    owner, p = await _owner_with_project(make_client, target_size=2)
    students = [await _student(make_client, f"stud{i}", {"Node.js": 2}) for i in range(4)]
    invs = []
    for s in students:
        r = await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})
        invs.append(r.json())
    results = await asyncio.gather(*(s.post(f"/api/v1/invitations/{i['id']}/accept") for s, i in zip(students, invs)))
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409, 409, 409]
    proj = (await owner.get(f"/api/v1/projects/{p['id']}")).json()
    assert len(proj["members"]) == 2 and proj["open_positions"] == 0
    statuses = sorted([i["status"] async for i in db.invitations.find({})])
    assert statuses.count("accepted") == 1 and "accepting" not in statuses and "pending" not in statuses


async def test_full_team_rejects_new_invitations_and_recommendations(make_client):
    owner, p = await _owner_with_project(make_client, target_size=2)
    s = await _student(make_client, "sam", {"Node.js": 3})
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})).json()
    await s.post(f"/api/v1/invitations/{inv['id']}/accept")
    t = await _student(make_client, "tia", {"PostgreSQL": 3})
    assert (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": t.user["id"]})).status_code == 409
    rec = (await owner.get(f"/api/v1/projects/{p['id']}/recommendations")).json()
    assert rec["status"] == "team_full" and rec["candidates"] == []


async def test_leave_and_remove_reopen_positions(make_client):
    owner, p = await _owner_with_project(make_client)
    s = await _student(make_client, "sam", {"Node.js": 3})
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"], "role": "Backend"})).json()
    await s.post(f"/api/v1/invitations/{inv['id']}/accept")
    other = await make_client().register("other")
    assert (await other.delete(f"/api/v1/projects/{p['id']}/members/{s.user['id']}")).status_code == 403
    assert (await owner.delete(f"/api/v1/projects/{p['id']}/members/{owner.user['id']}")).status_code == 400
    r = await s.delete(f"/api/v1/projects/{p['id']}/members/{s.user['id']}")
    assert r.status_code == 200
    assert r.json()["open_positions"] == 3 and "Backend" in r.json()["vacant_roles"]


async def test_one_team_per_event(make_client):
    owner, p = await _owner_with_project(make_client, event_key="SIH-2026")
    owner2 = await make_client().register("owner2")
    p2 = (await owner2.post("/api/v1/projects", project_payload(title="Rival team", event_key="sih-2026"))).json()
    s = await _student(make_client, "sam", {"Node.js": 3})
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})).json()
    await s.post(f"/api/v1/invitations/{inv['id']}/accept")
    r = await owner2.post(f"/api/v1/projects/{p2['id']}/invitations", {"candidate_id": s.user["id"]})
    assert r.status_code == 409
    rec = (await owner2.get(f"/api/v1/projects/{p2['id']}/recommendations")).json()
    assert s.user["id"] not in {c["profile"]["user_id"] for c in rec["candidates"]}
    # sam and the first team's creator are both committed to that event
    assert rec["pool"]["excluded_by_reason"].get("COMMITTED_TO_EVENT_TEAM") == 2


async def test_cannot_invite_hidden_or_unknown(make_client):
    owner, p = await _owner_with_project(make_client)
    s = await _student(make_client, "sam", {"Node.js": 3}, visible=False)
    assert (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})).status_code == 404
    assert (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": "zzz"})).status_code == 404
