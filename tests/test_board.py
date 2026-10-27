from __future__ import annotations

from datetime import date, timedelta


def _jobs(client, **params):
    response = client.get("/api/jobs", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_curated_feed_uses_saved_roles_and_years(client, insert_job):
    insert_job(
        title="Machine learning engineer",
        company="Fit Co",
        location="Bengaluru",
        description="Requirements\n3 years of experience building models in production.",
        external_id="fit",
    )
    insert_job(
        title="Machine learning engineer",
        company="Range Co",
        location="Bengaluru",
        description="Requirements\n3-7 years of experience with Python and model training.",
        external_id="range",
    )
    insert_job(
        title="Machine learning engineer",
        company="Open Co",
        location="Bengaluru",
        description="Requirements\nPython and PyTorch. This posting states no years of experience.",
        external_id="open",
    )
    insert_job(
        title="Machine learning engineer",
        company="Senior Co",
        location="Bengaluru",
        description="Requirements\n8+ years of experience leading a team and shipping models.",
        external_id="senior",
    )
    insert_job(
        title="Data scientist",
        company="Other Co",
        location="Bengaluru",
        description="Requirements\n3 years of experience in statistics and reporting.",
        external_id="other",
    )

    before = _jobs(client, status="feed", curated="1")
    assert before["jobs"] == []

    saved = client.put(
        "/api/profile",
        json={"roles": ["Machine learning engineer"], "yoe_min": 2, "yoe_max": 3},
    )
    assert saved.status_code == 200

    feed = _jobs(client, status="feed", curated="1")
    assert {job["company"] for job in feed["jobs"]} == {"Fit Co", "Range Co", "Open Co"}

    found = _jobs(client, status="feed", curated="1", q="Other Co")
    assert [job["company"] for job in found["jobs"]] == ["Other Co"]


def test_same_role_on_two_boards_is_one_card(client, insert_job):
    description = "Requirements\n3 years of experience building models in production."
    job_id, kind = insert_job(
        title="Machine learning engineer",
        company="Twin Co",
        location="Bengaluru",
        description=description,
        source="greenhouse",
        external_id="gh-1",
        apply_url="https://boards.example/gh",
    )
    assert kind == "added"
    assert client.post(f"/api/jobs/{job_id}/applied").status_code == 200

    merged_id, merged_kind = insert_job(
        title="Machine learning engineer",
        company="Twin Co",
        location="Bengaluru",
        description=description + " The second board has the same role.",
        source="lever",
        external_id="lv-1",
        apply_url="https://jobs.example/lv",
    )
    assert merged_kind == "merged"
    assert merged_id == job_id

    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "applied"
    assert body["referred"] is False
    assert {link["source"] for link in body["links"]} == {"greenhouse", "lever"}


def test_discard_and_restore(client, insert_job):
    job_id, _kind = insert_job(
        title="Machine learning engineer",
        company="Hide Co",
        location="Bengaluru",
        description="Requirements\n3 years of experience building models in production.",
        external_id="hide",
    )
    discarded = client.post(
        f"/api/jobs/{job_id}/discard",
        json={"reason": "company", "note": "Not a fit", "hide_company": True, "hide_phrase": ""},
    )
    assert discarded.status_code == 200
    assert _jobs(client, status="feed")["jobs"] == []
    assert [job["id"] for job in _jobs(client, status="discarded")["jobs"]] == [job_id]
    rules = client.get("/api/rules")
    assert rules.status_code == 200
    assert any(rule["kind"] == "company" and rule["value"] == "Hide Co" for rule in rules.json())

    assert client.post(f"/api/jobs/{job_id}/restore").status_code == 200
    assert [job["id"] for job in _jobs(client, status="feed")["jobs"]] == [job_id]
    assert client.get("/api/rules").json() == []


def test_mark_sent_moves_job_to_outreach(client, insert_job):
    job_id, _kind = insert_job(
        title="Machine learning engineer",
        company="Mail Co",
        location="Bengaluru",
        description="Requirements\n3 years of experience building models in production.",
        external_id="mail",
    )
    created = client.post(f"/api/jobs/{job_id}/messages", json={"kind": "referral"})
    assert created.status_code == 200
    draft = created.json()
    sent = client.patch(
        f"/api/messages/{draft['id']}",
        json={"subject": draft["subject"], "body": draft["body"], "status": "sent"},
    )
    assert sent.status_code == 200
    assert sent.json()["follow_up_on"] == (date.today() + timedelta(days=5)).isoformat()
    assert [job["id"] for job in _jobs(client, status="outreach")["jobs"]] == [job_id]
    assert _jobs(client, status="feed")["jobs"] == []


def test_got_referred_files_under_applied_with_referral(client, insert_job):
    job_id, _kind = insert_job(
        title="Machine learning engineer",
        company="Refer Co",
        location="Bengaluru",
        description="Requirements\n3 years of experience building models in production.",
        external_id="refer",
    )
    assert client.post(f"/api/jobs/{job_id}/referred").status_code == 200
    body = _jobs(client, status="applied")
    assert body["jobs"][0]["id"] == job_id
    assert body["jobs"][0]["referred"] is True
    assert body["counts"]["applied_referred"] == 1
    assert body["counts"]["applied_direct"] == 0


def test_mark_applied_files_under_applied_without_referral(client, insert_job):
    job_id, _kind = insert_job(
        title="Machine learning engineer",
        company="Direct Co",
        location="Bengaluru",
        description="Requirements\n3 years of experience building models in production.",
        external_id="direct",
    )
    assert client.post(f"/api/jobs/{job_id}/applied").status_code == 200
    body = _jobs(client, status="applied")
    assert body["jobs"][0]["id"] == job_id
    assert body["jobs"][0]["referred"] is False
    assert body["counts"]["applied_referred"] == 0
    assert body["counts"]["applied_direct"] == 1


def test_removed_routes_stay_gone_and_paste_remains(client):
    assert (
        client.post(
            "/api/companies", json={"name": "Acme", "board_type": "greenhouse", "board_token": "acme"}
        ).status_code
        == 405
    )
    assert client.post("/api/watchlists/india").status_code == 404
    assert client.get("/api/suggestions").status_code == 404
    assert client.post("/api/suggestions/refresh").status_code == 404
    assert client.post("/api/import").status_code == 404
    pasted = client.post(
        "/api/import/posting",
        json={
            "title": "Machine learning engineer",
            "company": "Paste Co",
            "location": "Bengaluru",
            "description": "Too short",
            "source": "linkedin",
        },
    )
    assert pasted.status_code == 400


def test_hosted_copy_keeps_fetch_and_model_calls_local(client, monkeypatch):
    monkeypatch.setattr("app.main.using_hosted_database", lambda: True)
    assert client.post("/api/fetch").status_code == 403
    assert client.post("/api/profile/roles/compare").status_code == 403
    asked = client.post("/api/jobs/1/ask", json={"question": "Is this remote?"})
    assert asked.status_code == 403
