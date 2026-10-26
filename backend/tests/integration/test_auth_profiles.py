from tests.integration.conftest import profile


async def test_register_login_logout_and_session(make_client):
    a = await make_client().register("asha")
    assert a.user["role"] == "student"
    me = await a.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["user"]["handle"] == "asha"
    assert "password_hash" not in me.text

    r = await a.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert (await a.get("/api/v1/auth/me")).status_code == 401

    r = await a.post("/api/v1/auth/login", {"email": "asha@example.edu", "password": "correct horse battery"})
    assert r.status_code == 200
    a.csrf = r.json()["csrf_token"]
    assert (await a.get("/api/v1/auth/me")).status_code == 200


async def test_session_cookie_flags(make_client):
    c = make_client()
    r = await c.post("/api/v1/auth/register", {"email": "b@example.edu", "password": "correct horse battery",
                                               "display_name": "B", "handle": "bee", "accept_terms": True})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


async def test_duplicate_and_invalid_registration(make_client):
    await make_client().register("asha")
    c = make_client()
    r = await c.post("/api/v1/auth/register", {"email": "ASHA@example.edu", "password": "correct horse battery",
                                               "display_name": "A", "handle": "other", "accept_terms": True})
    assert r.status_code == 409
    r = await c.post("/api/v1/auth/register", {"email": "x@example.edu", "password": "short", "display_name": "X",
                                               "handle": "xx_valid", "accept_terms": True})
    assert r.status_code == 422
    r = await c.post("/api/v1/auth/register", {"email": "x@example.edu", "password": "correct horse battery",
                                               "display_name": "X", "handle": "ASHA", "accept_terms": True})
    assert r.status_code == 409  # handles are case-insensitive


async def test_wrong_password_and_rate_limit(make_client):
    await make_client().register("asha")
    c = make_client()
    codes = [(await c.post("/api/v1/auth/login", {"email": "asha@example.edu", "password": "nope"})).status_code
             for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[-1] == 429


async def test_csrf_required_for_state_changes(make_client):
    a = await make_client().register("asha")
    token = a.csrf
    a.csrf = None
    r = await a.put("/api/v1/profiles/me", profile({"React": 3}))
    assert r.status_code == 403
    a.csrf = "wrong"
    assert (await a.put("/api/v1/profiles/me", profile({"React": 3}))).status_code == 403
    a.csrf = token
    assert (await a.put("/api/v1/profiles/me", profile({"React": 3}))).status_code == 200


async def test_cross_origin_post_rejected(make_client):
    a = await make_client().register("asha")
    r = await a.put("/api/v1/profiles/me", profile({"React": 3}), headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await a.put("/api/v1/profiles/me", profile({"React": 3}), headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200


async def test_protected_endpoints_require_login(make_client):
    c = make_client()
    for url in ["/api/v1/profiles/me", "/api/v1/dashboard", "/api/v1/conversations", "/api/v1/invitations"]:
        assert (await c.get(url)).status_code == 401


async def test_profile_normalisation_and_unknown_vs_absent(make_client):
    a = await make_client().register("asha")
    body = profile({"nodejs": 2, "Node.js": 4, "React Native": 3, "Quantum Weaving": 1},
                   declared_absent=["postgres"], availability=None, primary_roles=["Backend"])
    r = await a.put("/api/v1/profiles/me", body)
    assert r.status_code == 200, r.text
    p = r.json()
    labels = {s["label"]: s["proficiency"] for s in p["skills"]}
    assert labels == {"Node.js": 4, "React Native": 3, "Quantum Weaving": 1}
    assert next(s for s in p["skills"] if s["label"] == "Quantum Weaving")["recognized"] is False
    assert p["declared_absent"] == ["PostgreSQL"]
    assert p["availability"] is None  # not stated, not "no availability"
    assert "Weekly availability" in p["completion"]["missing"]


async def test_profile_validation(make_client):
    a = await make_client().register("asha")
    assert (await a.put("/api/v1/profiles/me", profile({"React": 5}))).status_code == 422
    assert (await a.put("/api/v1/profiles/me", profile({}, availability=["someday"]))).status_code == 422
    assert (await a.put("/api/v1/profiles/me", {**profile({}), "email": "x"})).status_code == 422


async def test_hidden_profile_not_visible_to_strangers(make_client):
    a = await make_client().register("asha")
    b = await make_client().register("bilal")
    await a.put("/api/v1/profiles/me", profile({"React": 3}, visible=False))
    r = await b.get(f"/api/v1/profiles/{a.user['id']}")
    assert r.status_code == 404
    await a.put("/api/v1/profiles/me", profile({"React": 3}, availability=["mon-eve"], visible=True))
    pub = (await b.get(f"/api/v1/profiles/{a.user['id']}")).json()
    assert pub["availability_stated"] is True and "availability" not in pub and "email" not in pub
    assert (await b.get("/api/v1/profiles/not-an-id")).status_code == 404


async def test_admin_role_from_config(make_client):
    admin = await make_client().register("admin", email="admin@example.edu")
    assert admin.user["role"] == "admin"


async def test_delete_account_removes_data(make_client, db):
    a = await make_client().register("asha")
    await a.put("/api/v1/profiles/me", profile({"React": 3}))
    r = await a.post("/api/v1/auth/delete-account", {"password": "correct horse battery", "confirm": "DELETE"})
    assert r.status_code == 204
    from bson import ObjectId

    uid = ObjectId(a.user["id"])
    assert await db.users.find_one({"_id": uid}) is None
    assert await db.profiles.find_one({"_id": uid}) is None
    assert await db.sessions.count_documents({"user_id": uid}) == 0
    assert await db.embeddings.count_documents({"user_id": uid}) == 0


async def test_health(make_client):
    c = make_client()
    assert (await c.get("/api/v1/health")).json() == {"status": "ok"}
    r = await c.get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["database"] is True
