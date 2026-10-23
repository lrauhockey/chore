"""
Chore scheduling recurrence engine, badge evaluation, streaks, and report aggregations.
"""
from datetime import date, datetime, timedelta


WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_iso_date(date_str):
    """Parse YYYY-MM-DD into a datetime.date object."""
    if isinstance(date_str, date):
        return date_str
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def is_chore_due_on_date(chore, target_date):
    """
    Determine whether a chore row is scheduled on `target_date` (datetime.date).
    Supported frequency_type values:
      - 'daily': every day (1x)
      - 'twice_daily': every day (2x: Morning AM & Evening PM)
      - 'weekly': specific weekday numbers in `days_of_week` (e.g. "0,3" for Mon & Thu)
      - 'biweekly': every 2 weeks on specific weekday numbers in `days_of_week`,
                    anchored to the ISO week of `anchor_date`.
    """
    target_date = parse_iso_date(target_date)
    freq = (chore["frequency_type"] or "daily").lower()

    if freq in ("daily", "twice_daily"):
        return True

    raw_days = str(chore["days_of_week"] or "").strip()
    if not raw_days:
        allowed_weekdays = {0}  # default Monday if none specified
    else:
        allowed_weekdays = {
            int(x.strip()) for x in raw_days.split(",") if x.strip().isdigit()
        }

    if target_date.weekday() not in allowed_weekdays:
        return False

    if freq == "weekly":
        return True

    if freq == "biweekly":
        anchor_str = chore["anchor_date"] or "2026-10-18"
        try:
            anchor = parse_iso_date(anchor_str)
        except ValueError:
            anchor = date(2026, 10, 18)

        # Align both dates to the Monday of their respective weeks so multi-day
        # biweekly rules stay in the same 14-day cadence.
        anchor_monday = anchor - timedelta(days=anchor.weekday())
        target_monday = target_date - timedelta(days=target_date.weekday())
        weeks_diff = (target_monday - anchor_monday).days // 7
        return (weeks_diff % 2) == 0

    return True


def expand_chore_slots_for_date(chore, target_date):
    """
    Return a list of slot dicts for `chore` on `target_date`.
    Each slot has:
      - slot: 'AM', 'PM', or 'ANY'
      - slot_label: 'Morning', 'Evening', or 'Anytime'
      - time_group: 'morning', 'anytime', or 'evening'
    """
    if not is_chore_due_on_date(chore, target_date):
        return []

    freq = (chore["frequency_type"] or "daily").lower()
    tod = (chore["time_of_day"] or "any").lower()

    if freq == "twice_daily" or tod == "both":
        return [
            {"slot": "AM", "slot_label": "Morning", "time_group": "morning"},
            {"slot": "PM", "slot_label": "Evening", "time_group": "evening"},
        ]

    if tod == "morning":
        return [{"slot": "AM", "slot_label": "Morning", "time_group": "morning"}]
    if tod == "evening":
        return [{"slot": "PM", "slot_label": "Evening", "time_group": "evening"}]

    return [{"slot": "ANY", "slot_label": "Anytime", "time_group": "anytime"}]


def format_frequency_summary(chore):
    """Return a human-friendly description of a chore's schedule."""
    freq = (chore["frequency_type"] or "daily").lower()
    tod = (chore["time_of_day"] or "any").lower()
    raw_days = str(chore["days_of_week"] or "").strip()
    day_Indices = [int(x.strip()) for x in raw_days.split(",") if x.strip().isdigit()]
    day_names = ", ".join(WEEKDAY_NAMES[i] for i in sorted(day_Indices) if 0 <= i < 7)

    tod_suffix = ""
    if tod == "morning":
        tod_suffix = " (Morning)"
    elif tod == "evening":
        tod_suffix = " (Evening)"

    if freq == "twice_daily":
        return "2x Daily (Morning & Evening)"
    if freq == "daily":
        return f"Daily{tod_suffix}"
    if freq == "weekly":
        return f"Weekly on {day_names or 'Mon'}{tod_suffix}"
    if freq == "biweekly":
        return f"Every 2 Weeks on {day_names or 'Sun'}{tod_suffix}"
    return "Daily"


def build_daily_board(chores, users_by_id, completions_for_date, target_date):
    """
    Build the full list of scheduled chore instances for `target_date`,
    enriched with completion status and user metadata.
    """
    completion_map = {
        (c["chore_id"], c["slot"]): c for c in completions_for_date
    }

    instances = []
    for chore in chores:
        if not chore["active"]:
            continue
        slots = expand_chore_slots_for_date(chore, target_date)
        assigned_user = users_by_id.get(chore["assigned_user_id"]) if chore["assigned_user_id"] else None

        for s in slots:
            comp = completion_map.get((chore["id"], s["slot"]))
            completed_by = users_by_id.get(comp["user_id"]) if comp else None

            instances.append(
                {
                    "chore_id": chore["id"],
                    "name": chore["name"],
                    "icon": chore["icon"],
                    "category": chore["category"],
                    "points": chore["points"],
                    "frequency_type": chore["frequency_type"],
                    "frequency_label": format_frequency_summary(chore),
                    "slot": s["slot"],
                    "slot_label": s["slot_label"],
                    "time_group": s["time_group"],
                    "target_date": parse_iso_date(target_date).isoformat(),
                    "assigned_user": assigned_user,
                    "completed": bool(comp),
                    "completion_id": comp["id"] if comp else None,
                    "completed_by": completed_by,
                    "completed_at": comp["completed_at"] if comp else None,
                    "points_earned": comp["points_earned"] if comp else chore["points"],
                    "was_stolen": bool(comp["was_stolen"]) if comp else False,
                }
            )

    return instances


def compute_user_streak(user_id, completion_dates_set, reference_date=None):
    """
    Calculate consecutive days a user has completed at least 1 chore,
    counting backward from `reference_date` (or `reference_date - 1 day` if today
     isn't completed yet).
    """
    ref = parse_iso_date(reference_date or date.today())
    streak = 0
    cursor = ref

    # If the user hasn't checked off a chore yet today, check if their streak was alive yesterday
    if cursor.isoformat() not in completion_dates_set:
        cursor = cursor - timedelta(days=1)

    while cursor.isoformat() in completion_dates_set:
        streak += 1
        cursor -= timedelta(days=1)

    return streak


def compute_badges_for_user(user_stats, streak):
    """
    Return a list of earned playful badges for a user based on their completion stats.
    `user_stats` keys:
      - total_count, total_points
      - category_counts: dict of category -> count
      - stolen_count: int
      - morning_count: int
      - evening_count: int
    """
    badges = []
    cats = user_stats.get("category_counts", {})

    poop_count = cats.get("poop", 0)
    dog_count = cats.get("dog", 0) + poop_count
    trash_count = cats.get("trash", 0)
    kitchen_count = cats.get("kitchen", 0)
    stolen_count = user_stats.get("stolen_count", 0)
    total_count = user_stats.get("total_count", 0)

    if poop_count >= 1:
        tier = "Gold" if poop_count >= 10 else ("Silver" if poop_count >= 5 else "Bronze")
        badges.append({
            "id": "poop_patrol",
            "icon": "💩",
            "name": f"Poop Patrol ({tier})",
            "desc": f"Scooped the yard {poop_count} time{'s' if poop_count != 1 else ''}!",
        })

    if dog_count >= 3:
        badges.append({
            "id": "dog_whisperer",
            "icon": "🐕",
            "name": "Certified Dog Whisperer",
            "desc": f"Completed {dog_count} dog care duties!",
        })

    if trash_count >= 2:
        badges.append({
            "id": "trash_titan",
            "icon": "🗑️",
            "name": "Trash & Curb Titan",
            "desc": f"Hauler of {trash_count} trash & recycling runs!",
        })

    if kitchen_count >= 3:
        badges.append({
            "id": "kitchen_commander",
            "icon": "🧽",
            "name": "Kitchen Commander",
            "desc": f"Sparkling counters {kitchen_count} times!",
        })

    if stolen_count >= 1:
        badges.append({
            "id": "chore_pirate",
            "icon": "🏴‍☠️",
            "name": "Chore Pirate / Lifesaver",
            "desc": f"Covered or stole {stolen_count} assigned chore{'s' if stolen_count != 1 else ''}!",
        })

    if streak >= 3:
        badges.append({
            "id": "streak_royalty",
            "icon": "🔥",
            "name": f"{streak}-Day Streak Machine",
            "desc": f"Completed chores {streak} days in a row!",
        })

    if total_count >= 10:
        badges.append({
            "id": "house_mvp",
            "icon": "🏆",
            "name": "House MVP Centurion",
            "desc": f"Crushed {total_count} total chores!",
        })

    return badges
