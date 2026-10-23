"""
Unit & API integration tests for the Family Chore Chart application.
"""
import os
import tempfile
from datetime import date
import pytest

from app import create_app
from scheduler_logic import expand_chore_slots_for_date, is_chore_due_on_date


@pytest.fixture
def client():
    fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(temp_db)

    app = create_app(db_path=temp_db)
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    if os.path.exists(temp_db):
        os.unlink(temp_db)


def test_recurrence_engine_schedules():
    # 1. Twice daily (Walk the dog -> AM and PM slots)
    twice_chore = {
        "frequency_type": "twice_daily",
        "days_of_week": "",
        "time_of_day": "both",
        "anchor_date": "2026-10-18",
    }
    slots = expand_chore_slots_for_date(twice_chore, date(2026, 10, 23))
    assert len(slots) == 2
    assert [s["slot"] for s in slots] == ["AM", "PM"]

    # 2. Weekly on Monday (0) and Thursday (3) (Garbage)
    garbage_chore = {
        "frequency_type": "weekly",
        "days_of_week": "0,3",
        "time_of_day": "evening",
        "anchor_date": "2026-10-18",
    }
    assert is_chore_due_on_date(garbage_chore, date(2026, 10, 19)) is True   # Monday
    assert is_chore_due_on_date(garbage_chore, date(2026, 10, 20)) is False  # Tuesday
    assert is_chore_due_on_date(garbage_chore, date(2026, 10, 22)) is True   # Thursday

    # 3. Biweekly on Sunday (6) (Recycling)
    recycling_chore = {
        "frequency_type": "biweekly",
        "days_of_week": "6",
        "time_of_day": "evening",
        "anchor_date": "2026-10-18",  # Sunday
    }
    assert is_chore_due_on_date(recycling_chore, date(2026, 10, 18)) is True   # Week 0 Sunday
    assert is_chore_due_on_date(recycling_chore, date(2026, 10, 25)) is False  # Week 1 Sunday
    assert is_chore_due_on_date(recycling_chore, date(2026, 11, 1)) is True    # Week 2 Sunday


def test_api_flow_complete_and_leaderboard(client):
    # Fetch daily board (seeds 3 adults + 6 default chores)
    res = client.get("/api/daily?date=2026-10-22")  # A Thursday (Trash is due!)
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["users"]) == 3
    assert len(data["chores"]) >= 6

    user_alex = data["users"][0]
    first_chore = data["chores"][0]

    # Complete a chore slot via 2-tap API
    comp_res = client.post(
        "/api/complete",
        json={
            "chore_id": first_chore["chore_id"],
            "user_id": user_alex["id"],
            "target_date": "2026-10-22",
            "slot": first_chore["slot"],
        },
    )
    assert comp_res.status_code == 200
    assert comp_res.get_json()["ok"] is True

    # Verify leaderboard reflects the completion and crowns Alex
    rep_res = client.get("/api/reports?period=week&date=2026-10-22")
    assert rep_res.status_code == 200
    rep = rep_res.get_json()
    assert rep["champion"]["user"]["id"] == user_alex["id"]
    assert rep["champion"]["points"] == first_chore["points"]
    assert rep["last_place"] is not None
