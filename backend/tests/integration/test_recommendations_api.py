from tests.integration.conftest import profile, project_payload


async def _setup(make_client):
    owner = await make_client().register("owner")
    await owner.put("/api/v1/profiles/me", profile({"React": 3}, primary_roles=["Frontend"]))
    p = (await owner.post("/api/v1/projects", project_payload())).json()
    ml = await make_client().register("mira")
    await ml.put("/api/v1/profiles/me", profile({"Machine Learning": 4, "Python": 3}, primary_roles=["ML"]))
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": ml.user["id"], "role": "ML"})).json()
    await ml.post(f"/api/v1/invitations/{inv['id']}/accept")
    return owner, ml, p


async def test_recommendations_rank_gap_filler_first_with_explanations(make_client):
    owner, ml, p = await _setup(make_client)
    fe = await make_client().register("fred")
    await fe.put("/api/v1/profiles/me", profile({"React": 4, "CSS": 4, "TypeScript": 3}, primary_roles=["Frontend"],
                                                 interests=["web development"]))
    be = await make_client().register("bea")
    await be.put("/api/v1/profiles/me", profile({"node js": 3, "PostgreSQL": 2}, primary_roles=["Backend"]))
    hidden = await make_client().register("hid")
    await hidden.put("/api/v1/profiles/me", profile({"Node.js": 4, "PostgreSQL": 4}, visible=False))

    r = await owner.get(f"/api/v1/projects/{p['id']}/recommendations")
    assert r.status_code == 200, r.text
    rec = r.json()
    ids = [c["profile"]["user_id"] for c in rec["candidates"]]
    assert ids[0] == be.user["id"]
    assert hidden.user["id"] not in ids and ml.user["id"] not in ids and owner.user["id"] not in ids
    assert rec["team_coverage"]["overall"] == 0.4  # React + ML covered, Node.js + PostgreSQL not (4/10)
    top = rec["candidates"][0]
    assert top["added_coverage"] == 0.6 and top["features"]["gap"]["value"] == 1.0
    assert "Adds Node.js (essential; stated proficiency 3 of 4)" in top["explanation_text"]
    assert top["explanation_text"].endswith("Proficiency is self-reported.")
    assert "availability" not in top["profile"]  # slots never exposed
    assert rec["omitted_features"] == {"avail": "team_not_synchronous", "work": "team_states_no_commitment_or_mode"}
    assert abs(sum(rec["active_weights"].values()) - 1) < 1e-9
    assert "not probabilities" in rec["notice"]


async def test_recommendations_refresh_after_membership_change(make_client):
    owner, ml, p = await _setup(make_client)
    be = await make_client().register("bea")
    await be.put("/api/v1/profiles/me", profile({"Node.js": 3, "PostgreSQL": 2}, primary_roles=["Backend"]))
    be2 = await make_client().register("ben")
    await be2.put("/api/v1/profiles/me", profile({"Node.js": 3, "PostgreSQL": 2}, primary_roles=["Backend"]))
    before = (await owner.get(f"/api/v1/projects/{p['id']}/recommendations")).json()
    gain_before = {c["profile"]["handle"]: c["added_coverage"] for c in before["candidates"]}
    assert gain_before["ben"] > 0
    inv = (await owner.post(f"/api/v1/projects/{p['id']}/invitations", {"candidate_id": be.user["id"]})).json()
    await be.post(f"/api/v1/invitations/{inv['id']}/accept")
    after = (await owner.get(f"/api/v1/projects/{p['id']}/recommendations")).json()
    assert after["team_coverage"]["complete"] is True
    assert "gap" in after["omitted_features"]
    ben = next(c for c in after["candidates"] if c["profile"]["handle"] == "ben")
    assert ben["added_coverage"] == 0 and ben["features"]["gap"]["value"] is None
    assert ben["explanation_text"].startswith("All listed requirements are already met")


async def test_only_owner_sees_recommendations(make_client):
    owner, ml, p = await _setup(make_client)
    assert (await ml.get(f"/api/v1/projects/{p['id']}/recommendations")).status_code == 403
    stranger = await make_client().register("stranger")
    assert (await stranger.get(f"/api/v1/projects/{p['id']}/recommendations")).status_code == 403
    assert (await stranger.get("/api/v1/projects/000000000000000000000000/recommendations")).status_code == 404


async def test_mandatory_rules_filter_and_report_reasons(make_client):
    owner = await make_client().register("owner")
    body = project_payload(requirements=[{"skill": "Node.js", "importance": 3, "desired_proficiency": 2, "mandatory": True},
                                         {"skill": "React", "importance": 1, "desired_proficiency": 2}],
                           allowed_years=[2, 3])
    p = (await owner.post("/api/v1/projects", body)).json()
    ok = await make_client().register("okay")
    await ok.put("/api/v1/profiles/me", profile({"Node.js": 3}, year=2))
    low = await make_client().register("low")
    await low.put("/api/v1/profiles/me", profile({"Node.js": 1}, year=2))
    unk = await make_client().register("unk")
    await unk.put("/api/v1/profiles/me", profile({"React": 4}, year=3))
    fourth = await make_client().register("fourth")
    await fourth.put("/api/v1/profiles/me", profile({"Node.js": 4}, year=4))
    rec = (await owner.get(f"/api/v1/projects/{p['id']}/recommendations")).json()
    assert [c["profile"]["handle"] for c in rec["candidates"]] == ["okay"]
    reasons = rec["pool"]["excluded_by_reason"]
    assert reasons["MANDATORY_SKILL_NOT_MET"] == 1
    assert reasons["MANDATORY_SKILL_UNVERIFIED"] == 1
    assert reasons["YEAR_NOT_ALLOWED"] == 1


async def test_embeddings_cached_and_invalidated(make_client, db):
    owner, ml, p = await _setup(make_client)
    be = await make_client().register("bea")
    await be.put("/api/v1/profiles/me", profile({"Node.js": 3}))
    await owner.get(f"/api/v1/projects/{p['id']}/recommendations")
    from bson import ObjectId

    first = await db.embeddings.find_one({"user_id": ObjectId(be.user["id"])})
    assert first and first["dim"] == 384
    await owner.get(f"/api/v1/projects/{p['id']}/recommendations")
    assert (await db.embeddings.find_one({"user_id": ObjectId(be.user["id"])}))["created_at"] == first["created_at"]
    await be.put("/api/v1/profiles/me", profile({"Node.js": 3, "Django": 2}))
    await owner.get(f"/api/v1/projects/{p['id']}/recommendations")
    again = await db.embeddings.find_one({"user_id": ObjectId(be.user["id"])})
    assert again["text_hash"] != first["text_hash"]


async def test_coverage_endpoint(make_client):
    owner, ml, p = await _setup(make_client)
    cov = (await ml.get(f"/api/v1/projects/{p['id']}/coverage")).json()
    by = {s["skill"]: s["coverage"] for s in cov["per_skill"]}
    assert by == {"React": 1.0, "Machine Learning": 1.0, "Node.js": 0.0, "PostgreSQL": 0.0}


async def test_dashboard_only_real_data(make_client):
    a = await make_client().register("asha")
    d = (await a.get("/api/v1/dashboard")).json()
    assert d["my_projects"] == [] and d["pending_received"] == [] and d["suggested_projects"] == []
    assert d["profile_completion"]["percent"] == 0
