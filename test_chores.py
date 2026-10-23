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

    # 4. Every Other Day (Run / Empty the Dishwasher)
    dishwasher_chore = {
        "frequency_type": "every_other_day",
        "days_of_week": "",
        "time_of_day": "evening",
        "anchor_date": "2026-10-23",
    }
    assert is_chore_due_on_date(dishwasher_chore, date(2026, 10, 23)) is True   # Day 0
    assert is_chore_due_on_date(dishwasher_chore, date(2026, 10, 24)) is False  # Day 1
    assert is_chore_due_on_date(dishwasher_chore, date(2026, 10, 25)) is True   # Day 2


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


def test_weekly_anytime_and_adhoc_tasks(client):
    # 1. Verify Food Shopping (weekly_anytime) shows up on Monday, and once completed on Monday,
    #    shows as completed on Wednesday of the same week!
    mon_res = client.get("/api/daily?date=2026-10-19").get_json()
    users = mon_res["users"]
    groceries = next(c for c in mon_res["chores"] if "Food Shopping" in c["name"])
    assert groceries["completed"] is False

    # Complete Food Shopping on Monday
    client.post(
        "/api/complete",
        json={
            "chore_id": groceries["chore_id"],
            "user_id": users[1]["id"],
            "target_date": "2026-10-19",
            "slot": groceries["slot"],
        },
    )

    # Check Wednesday of the same week — Food Shopping should show as already completed this week!
    wed_res = client.get("/api/daily?date=2026-10-21").get_json()
    groceries_wed = next(c for c in wed_res["chores"] if "Food Shopping" in c["name"])
    assert groceries_wed["completed"] is True
    assert groceries_wed["completed_by"]["id"] == users[1]["id"]
    assert groceries_wed["slot_label"] == "Done Mon"

    # 2. Test adding an Ad-Hoc task from Today's Board (both custom one-off and extra run of existing chore)
    adhoc_res = client.post(
        "/api/adhoc",
        json={
            "target_date": "2026-10-21",
            "name": "Wash the Car",
            "icon": "🚗",
            "points": 30,
            "category": "house",
            "user_id": None,  # Leave open on Today's Board
        },
    )
    assert adhoc_res.status_code == 200
    wed_after = client.get("/api/daily?date=2026-10-21").get_json()
    assert any(c["name"] == "Wash the Car" and not c["completed"] for c in wed_after["chores"])

