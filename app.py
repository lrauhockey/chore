"""
Family Chore Chart — Flask Web & iPad Kiosk Server
Runs standalone on PC/Mac and serves a touch-friendly PWA for iPad, iPhone, and Web.
"""
import os
from datetime import date, datetime, timedelta
from flask import Flask, jsonify, render_template, request

from database import get_db_connection, init_db
from scheduler_logic import (
    WEEKDAY_NAMES,
    build_daily_board,
    compute_badges_for_user,
    compute_user_streak,
    format_frequency_summary,
    parse_iso_date,
)


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    # Initialize SQLite database & default seed data
    init_db(db_path)

    def db():
        return get_db_connection(app.config.get("DB_PATH"))

    def fetch_users_dict(conn, include_inactive=False):
        sql = "SELECT * FROM users" if include_inactive else "SELECT * FROM users WHERE active = 1"
        rows = conn.execute(sql + " ORDER BY id ASC").fetchall()
        return {
            r["id"]: {
                "id": r["id"],
                "name": r["name"],
                "avatar": r["avatar"],
                "color": r["color"],
                "active": bool(r["active"]),
            }
            for r in rows
        }

    def fetch_settings(conn):
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def build_user_streaks(conn, users_by_id, ref_date=None):
        rows = conn.execute("SELECT user_id, target_date FROM completions GROUP BY user_id, target_date").fetchall()
        dates_by_user = {uid: set() for uid in users_by_id}
        for r in rows:
            if r["user_id"] in dates_by_user:
                dates_by_user[r["user_id"]].add(r["target_date"])
        return {
            uid: compute_user_streak(uid, dset, ref_date or date.today())
            for uid, dset in dates_by_user.items()
        }

    # ------------------------------------------------------------------
    # Frontend Entry Point & PWA Manifest
    # ------------------------------------------------------------------
    @app.route("/")
    def index():
        return render_template("index.html")

    # ------------------------------------------------------------------
    # Daily Kiosk Board API
    # ------------------------------------------------------------------
    @app.route("/api/daily")
    def api_daily():
        date_str = request.args.get("date") or date.today().isoformat()
        try:
            target = parse_iso_date(date_str)
        except ValueError:
            target = date.today()
        target_iso = target.isoformat()

        conn = db()
        users_by_id = fetch_users_dict(conn, include_inactive=False)
        all_users_by_id = fetch_users_dict(conn, include_inactive=True)
        streaks = build_user_streaks(conn, users_by_id, target)

        for uid, u in users_by_id.items():
            u["streak"] = streaks.get(uid, 0)

        chores = conn.execute("SELECT * FROM chores WHERE active = 1 ORDER BY points DESC, id ASC").fetchall()
        completions = conn.execute(
            "SELECT * FROM completions WHERE target_date = ?", (target_iso,)
        ).fetchall()

        board = build_daily_board(chores, all_users_by_id, completions, target)

        # Calculate quick daily summary & today's points per user
        today_points_by_user = {uid: 0 for uid in users_by_id}
        for item in board:
            if item["completed"] and item["completed_by"]:
                uid = item["completed_by"]["id"]
                if uid in today_points_by_user:
                    today_points_by_user[uid] += item["points_earned"]

        for uid, u in users_by_id.items():
            u["today_points"] = today_points_by_user.get(uid, 0)

        total_slots = len(board)
        completed_slots = sum(1 for item in board if item["completed"])
        settings = fetch_settings(conn)
        conn.close()

        return jsonify(
            {
                "date": target_iso,
                "display_date": target.strftime("%A, %b %d, %Y"),
                "is_today": target == date.today(),
                "prev_date": (target - timedelta(days=1)).isoformat(),
                "next_date": (target + timedelta(days=1)).isoformat(),
                "today_date": date.today().isoformat(),
                "settings": settings,
                "users": list(users_by_id.values()),
                "chores": board,
                "progress": {
                    "completed": completed_slots,
                    "total": total_slots,
                    "percent": round((completed_slots / total_slots) * 100) if total_slots else 100,
                },
            }
        )

    # ------------------------------------------------------------------
    # Toggle / Claim / Undo Chore Completion (2-Tap Kiosk Action)
    # ------------------------------------------------------------------
    @app.route("/api/complete", methods=["POST"])
    def api_complete():
        data = request.get_json(force=True) or {}
        chore_id = int(data.get("chore_id", 0))
        user_id = int(data.get("user_id", 0))
        target_date = data.get("target_date") or date.today().isoformat()
        slot = (data.get("slot") or "ANY").upper()

        conn = db()
        chore = conn.execute("SELECT * FROM chores WHERE id = ?", (chore_id,)).fetchone()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not chore or not user:
            conn.close()
            return jsonify({"error": "Invalid chore or user"}), 400

        was_stolen = 0
        if chore["assigned_user_id"] and int(chore["assigned_user_id"]) != user_id:
            was_stolen = 1

        points = int(chore["points"])
        conn.execute(
            """
            INSERT INTO completions (chore_id, user_id, target_date, slot, points_earned, was_stolen, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chore_id, target_date, slot)
            DO UPDATE SET
                user_id = excluded.user_id,
                points_earned = excluded.points_earned,
                was_stolen = excluded.was_stolen,
                completed_at = CURRENT_TIMESTAMP
            """,
            (chore_id, user_id, target_date, slot, points, was_stolen),
        )
        conn.commit()
        conn.close()

        return jsonify(
            {
                "ok": True,
                "chore_name": chore["name"],
                "user_name": user["name"],
                "user_avatar": user["avatar"],
                "points_earned": points,
                "was_stolen": bool(was_stolen),
            }
        )

    @app.route("/api/uncomplete", methods=["POST"])
    def api_uncomplete():
        data = request.get_json(force=True) or {}
        chore_id = int(data.get("chore_id", 0))
        target_date = data.get("target_date") or date.today().isoformat()
        slot = (data.get("slot") or "ANY").upper()

        conn = db()
        conn.execute(
            "DELETE FROM completions WHERE chore_id = ? AND target_date = ? AND slot = ?",
            (chore_id, target_date, slot),
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Weekly Calendar Grid ("Week at a Glance")
    # ------------------------------------------------------------------
    @app.route("/api/weekly")
    def api_weekly():
        date_str = request.args.get("date") or date.today().isoformat()
        try:
            ref = parse_iso_date(date_str)
        except ValueError:
            ref = date.today()

        monday = ref - timedelta(days=ref.weekday())
        sunday = monday + timedelta(days=6)

        conn = db()
        all_users_by_id = fetch_users_dict(conn, include_inactive=True)
        chores = conn.execute("SELECT * FROM chores WHERE active = 1 ORDER BY points DESC, id ASC").fetchall()
        completions = conn.execute(
            "SELECT * FROM completions WHERE target_date BETWEEN ? AND ?",
            (monday.isoformat(), sunday.isoformat()),
        ).fetchall()

        comps_by_date = {}
        for c in completions:
            comps_by_date.setdefault(c["target_date"], []).append(c)

        days_payload = []
        for offset in range(7):
            d = monday + timedelta(days=offset)
            d_iso = d.isoformat()
            day_items = build_daily_board(
                chores, all_users_by_id, comps_by_date.get(d_iso, []), d
            )
            days_payload.append(
                {
                    "date": d_iso,
                    "day_short": WEEKDAY_NAMES[offset],
                    "day_num": d.strftime("%d"),
                    "month_short": d.strftime("%b"),
                    "is_today": d == date.today(),
                    "chores": day_items,
                    "completed_count": sum(1 for x in day_items if x["completed"]),
                    "total_count": len(day_items),
                }
            )

        conn.close()
        return jsonify(
            {
                "week_start": monday.isoformat(),
                "week_end": sunday.isoformat(),
                "week_label": f"{monday.strftime('%b %d')} – {sunday.strftime('%b %d, %Y')}",
                "prev_week": (monday - timedelta(days=7)).isoformat(),
                "next_week": (monday + timedelta(days=7)).isoformat(),
                "days": days_payload,
            }
        )

    # ------------------------------------------------------------------
    # Leaderboard, Badges & Progress Reports (Week / Month / All-Time)
    # ------------------------------------------------------------------
    @app.route("/api/reports")
    def api_reports():
        period = (request.args.get("period") or "week").lower()
        ref_str = request.args.get("date") or date.today().isoformat()
        try:
            ref = parse_iso_date(ref_str)
        except ValueError:
            ref = date.today()

        if period == "week":
            start_date = ref - timedelta(days=ref.weekday())
            end_date = start_date + timedelta(days=6)
            period_label = f"This Week ({start_date.strftime('%b %d')} – {end_date.strftime('%b %d')})"
        elif period == "month":
            start_date = ref.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_date = next_month - timedelta(days=1)
            period_label = ref.strftime("%B %Y")
        else:
            start_date = date(2020, 1, 1)
            end_date = date(2099, 12, 31)
            period_label = "All-Time Hall of Fame"

        conn = db()
        users_by_id = fetch_users_dict(conn, include_inactive=False)
        streaks = build_user_streaks(conn, users_by_id, ref)
        settings = fetch_settings(conn)

        rows = conn.execute(
            """
            SELECT c.*, ch.name as chore_name, ch.icon as chore_icon, ch.category as chore_category
            FROM completions c
            JOIN chores ch ON ch.id = c.chore_id
            WHERE c.target_date BETWEEN ? AND ?
            ORDER BY c.target_date DESC, c.completed_at DESC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

        stats_by_user = {
            uid: {
                "user": u,
                "points": 0,
                "total_count": 0,
                "stolen_count": 0,
                "category_counts": {},
                "streak": streaks.get(uid, 0),
            }
            for uid, u in users_by_id.items()
        }

        daily_trend = {}
        category_breakdown = {}
        recent_history = []

        for r in rows:
            uid = r["user_id"]
            pts = int(r["points_earned"])
            cat = r["chore_category"] or "house"

            category_breakdown[cat] = category_breakdown.get(cat, 0) + pts
            d_iso = r["target_date"]
            daily_trend.setdefault(d_iso, {})
            daily_trend[d_iso][uid] = daily_trend[d_iso].get(uid, 0) + pts

            if uid in stats_by_user:
                st = stats_by_user[uid]
                st["points"] += pts
                st["total_count"] += 1
                st["stolen_count"] += int(r["was_stolen"] or 0)
                st["category_counts"][cat] = st["category_counts"].get(cat, 0) + 1

            if len(recent_history) < 25 and uid in users_by_id:
                recent_history.append(
                    {
                        "chore_name": r["chore_name"],
                        "chore_icon": r["chore_icon"],
                        "user_name": users_by_id[uid]["name"],
                        "user_avatar": users_by_id[uid]["avatar"],
                        "user_color": users_by_id[uid]["color"],
                        "target_date": r["target_date"],
                        "slot": r["slot"],
                        "points_earned": pts,
                        "was_stolen": bool(r["was_stolen"]),
                    }
                )

        total_household_points = sum(st["points"] for st in stats_by_user.values())

        leaderboard = []
        for uid, st in stats_by_user.items():
            badges = compute_badges_for_user(st, st["streak"])
            share_pct = (
                round((st["points"] / total_household_points) * 100, 1)
                if total_household_points > 0
                else 0.0
            )
            leaderboard.append(
                {
                    "user": st["user"],
                    "points": st["points"],
                    "total_count": st["total_count"],
                    "stolen_count": st["stolen_count"],
                    "streak": st["streak"],
                    "share_percent": share_pct,
                    "badges": badges,
                    "category_counts": st["category_counts"],
                }
            )

        leaderboard.sort(key=lambda x: (x["points"], x["total_count"], x["streak"]), reverse=True)

        # Assign ranks, Crowned Champion, and Last Place Penalty
        champion = leaderboard[0] if leaderboard and leaderboard[0]["points"] > 0 else None
        last_place = (
            leaderboard[-1]
            if len(leaderboard) > 1
            and champion
            and leaderboard[-1]["points"] < champion["points"]
            else None
        )

        conn.close()
        return jsonify(
            {
                "period": period,
                "period_label": period_label,
                "total_household_points": total_household_points,
                "total_household_chores": sum(x["total_count"] for x in leaderboard),
                "settings": settings,
                "leaderboard": leaderboard,
                "champion": champion,
                "last_place": last_place,
                "category_breakdown": category_breakdown,
                "recent_history": recent_history,
            }
        )

    # ------------------------------------------------------------------
    # Admin API (Manage Users, Chores, & Household Settings)
    # ------------------------------------------------------------------
    @app.route("/api/admin/data")
    def api_admin_data():
        conn = db()
        users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()]
        chores = [dict(r) for r in conn.execute("SELECT * FROM chores ORDER BY active DESC, id ASC").fetchall()]
        for ch in chores:
            ch["frequency_label"] = format_frequency_summary(ch)
        settings = fetch_settings(conn)
        conn.close()
        return jsonify({"users": users, "chores": chores, "settings": settings})

    @app.route("/api/admin/users", methods=["POST"])
    def api_admin_save_user():
        data = request.get_json(force=True) or {}
        user_id = data.get("id")
        name = (data.get("name") or "").strip()
        avatar = (data.get("avatar") or "😎").strip()
        color = (data.get("color") or "#6366f1").strip()
        active = 1 if data.get("active", True) else 0

        if not name:
            return jsonify({"error": "Name is required"}), 400

        conn = db()
        if user_id:
            conn.execute(
                "UPDATE users SET name = ?, avatar = ?, color = ?, active = ? WHERE id = ?",
                (name, avatar, color, active, int(user_id)),
            )
        else:
            conn.execute(
                "INSERT INTO users (name, avatar, color, active) VALUES (?, ?, ?, ?)",
                (name, avatar, color, active),
            )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
    def api_admin_delete_user(user_id):
        conn = db()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/admin/chores", methods=["POST"])
    def api_admin_save_chore():
        data = request.get_json(force=True) or {}
        chore_id = data.get("id")
        name = (data.get("name") or "").strip()
        icon = (data.get("icon") or "✨").strip()
        category = (data.get("category") or "house").strip()
        points = int(data.get("points") or 10)
        frequency_type = (data.get("frequency_type") or "daily").strip()
        days_of_week = (data.get("days_of_week") or "").strip()
        time_of_day = (data.get("time_of_day") or "any").strip()
        anchor_date = (data.get("anchor_date") or date.today().isoformat()).strip()
        assigned_user_id = data.get("assigned_user_id")
        assigned_user_id = int(assigned_user_id) if assigned_user_id not in (None, "", 0, "0") else None
        active = 1 if data.get("active", True) else 0

        if not name:
            return jsonify({"error": "Chore name is required"}), 400

        if frequency_type == "twice_daily":
            time_of_day = "both"

        conn = db()
        if chore_id:
            conn.execute(
                """
                UPDATE chores
                SET name = ?, icon = ?, category = ?, points = ?, frequency_type = ?,
                    days_of_week = ?, time_of_day = ?, anchor_date = ?, assigned_user_id = ?, active = ?
                WHERE id = ?
                """,
                (
                    name,
                    icon,
                    category,
                    points,
                    frequency_type,
                    days_of_week,
                    time_of_day,
                    anchor_date,
                    assigned_user_id,
                    active,
                    int(chore_id),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO chores
                (name, icon, category, points, frequency_type, days_of_week, time_of_day, anchor_date, assigned_user_id, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    icon,
                    category,
                    points,
                    frequency_type,
                    days_of_week,
                    time_of_day,
                    anchor_date,
                    assigned_user_id,
                    active,
                ),
            )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/admin/chores/<int:chore_id>", methods=["DELETE"])
    def api_admin_delete_chore(chore_id):
        conn = db()
        conn.execute("DELETE FROM chores WHERE id = ?", (chore_id,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/admin/settings", methods=["POST"])
    def api_admin_save_settings():
        data = request.get_json(force=True) or {}
        conn = db()
        for key in ("household_name", "champion_reward", "last_place_penalty"):
            if key in data:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(data[key]).strip()),
                )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 Family Chore Chart Kiosk running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
