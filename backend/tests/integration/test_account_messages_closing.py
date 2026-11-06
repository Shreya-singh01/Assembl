from bson import ObjectId

from tests.integration.conftest import profile, project_payload


async def test_admin_list_is_applied_and_synced(make_client, db, monkeypatch):
    from app.core import admins

    a = await make_client().register("sshreya", email="sshreya.singh054@gmail.com")
    assert a.user["role"] == "admin"
    s = await make_client().register("student1")
    assert s.user["role"] == "student"
    # adding an existing account to the list promotes it on its next request
    monkeypatch.setattr(admins, "ADMIN_EMAILS", admins.ADMIN_EMAILS | {"student1@example.edu"})
    assert (await s.get("/api/v1/auth/me")).json()["user"]["role"] == "admin"
    # removing it demotes it again
    monkeypatch.setattr(admins, "ADMIN_EMAILS", admins.ADMIN_EMAILS - {"student1@example.edu"})
    assert (await s.get("/api/v1/auth/me")).json()["user"]["role"] == "student"
    assert (await db.users.find_one({"_id": ObjectId(s.user["id"])}))["role"] == "student"


def test_configured_admins():
    from app.core.admins import ADMIN_EMAILS, role_for

    assert {"sshreya.singh054@gmail.com", "saieshamittal.17@gmail.com", "aroravidhi342@gmail.com"} <= ADMIN_EMAILS
    assert role_for("SAIESHAMITTAL.17@gmail.com".lower(), "student") == "admin"
    assert role_for("someone@x.edu", "rater") == "rater"
    assert role_for("admin_demo@demo.assembl.example", "admin") == "admin"


async def test_change_display_name_and_handle(make_client):
    a = await make_client().register("asha")
    await make_client().register("bilal")
    r = await a.put("/api/v1/auth/me", {"display_name": "Asha K", "handle": "asha_k"})
    assert r.status_code == 200 and r.json()["display_name"] == "Asha K" and r.json()["handle"] == "asha_k"
    assert (await a.put("/api/v1/auth/me", {"handle": "BILAL"})).status_code == 409  # case-insensitive
    assert (await a.put("/api/v1/auth/me", {"handle": "no"})).status_code == 422
    assert (await a.put("/api/v1/auth/me", {"handle": "Asha_K"})).status_code == 200  # own handle, new case


async def test_edit_and_delete_own_messages(make_client, db):
    a = await make_client().register("asha")
    b = await make_client().register("bilal")
    await b.put("/api/v1/profiles/me", profile({"React": 3}))
    conv = (await a.post("/api/v1/conversations", {"user_id": b.user["id"]})).json()
    base = f"/api/v1/conversations/{conv['id']}/messages"
    m = (await a.post(base, {"body": "helo"})).json()

    assert (await b.put(f"{base}/{m['id']}", {"body": "hijack"})).status_code == 403
    r = await a.put(f"{base}/{m['id']}", {"body": "hello"})
    assert r.status_code == 200 and r.json()["body"] == "hello" and r.json()["edited_at"]
    assert (await b.get("/api/v1/conversations")).json()[0]["last_message_preview"] == "hello"

    assert (await b.delete(f"{base}/{m['id']}")).status_code == 403
    r = await a.delete(f"{base}/{m['id']}")
    assert r.status_code == 200 and r.json()["deleted"] is True and r.json()["body"] == ""
    stored = await db.messages.find_one({"_id": ObjectId(m["id"])})
    assert stored["body"] == ""  # text removed from the database
    assert (await a.put(f"{base}/{m['id']}", {"body": "again"})).status_code == 400
    assert (await b.get("/api/v1/conversations")).json()[0]["last_message_preview"] == "Message deleted"

    outsider = await make_client().register("chen")
    assert (await outsider.delete(f"{base}/{m['id']}")).status_code == 404


async def test_closing_project_expires_pending_invitations(make_client, db):
    owner = await make_client().register("owner")
    p = (await owner.post("/api/v1/projects", project_payload())).json()
    s = await make_client().register("sam")
    await s.put("/api/v1/profiles/me", profile({"Node.js": 3}))
    t = await make_client().register("tia")
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": s.user["id"]})).json()
    req = (await t.post(f"/api/v1/projects/{p['id']}/join-requests", {})).json()

    body = {**project_payload(), "version": p["version"], "status": "closed"}
    assert (await owner.put(f"/api/v1/projects/{p['id']}", body)).status_code == 200
    for i in (inv, req):
        doc = await db.invitations.find_one({"_id": ObjectId(i["id"])})
        assert doc["status"] == "expired" and doc["reason"] == "project_closed"
    assert (await s.post(f"/api/v1/invitations/{inv['id']}/accept")).status_code == 409
