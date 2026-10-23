# 🏆 House HQ Chore Quest (Family Chore Chart & iPad Kiosk)

A standalone Python Flask web app and full-screen iPad Kiosk (Progressive Web App) for tracking household chores with points, streaks, badges, and weekly/monthly leaderboards.

---

## ✨ Features Included
- **2-Tap iPad Kiosk Check-Off:** Tap any chore card, then tap your avatar—no passwords needed on the kitchen iPad. Tap a completed chore to undo.
- **Smart Recurrence Engine:**
  - **Once a Day (`daily`):** e.g., *Clean the Kitchen*, *Pick Up Dog Poop*.
  - **2x a Day (`twice_daily`):** Automatically splits into **Morning (AM)** and **Evening (PM)** slots (e.g., *Walk the Dog*, *Feed the Dog*).
  - **Weekly on Specific Days (`weekly`):** e.g., *Take Out the Trash* on Monday & Thursday nights.
  - **Every 2 Weeks on Specific Days (`biweekly`):** e.g., *Take Out Recyclables* every other Sunday night.
- **Assignment Modes:** Support both **"Up for Grabs / Jump Ball"** and **Assigned to a Specific Adult** (with a *"Covered / Stolen!"* pirate badge if a teammate jumps in to do it).
- **Gamification & Reports:**
  - **👑 Crowned Champion** & **🍕 Last Place Penalty Banner** (customizable in Admin).
  - **Playful Badges:** *Poop Patrol*, *Certified Dog Whisperer*, *Trash & Curb Titan*, *Kitchen Commander*, *Chore Pirate*, and *Streak Machine*.
  - **Weekly Grid** & **Week / Month / All-Time Progress Reports**.

---

## 🚀 Quick Start (Mac or Windows PC)

### 1. Create a Virtual Environment & Install Dependencies
```bash
cd "/Volumes/Crucial X9/myfolder/lrau/chore"
python3 -m venv venv
source venv/bin/activate        # On Windows PC: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Server
```bash
python app.py
```
By default, the server listens on **`http://0.0.0.0:5050`** so any device on your local home Wi-Fi can reach it.

### 3. Run the Automated Tests
```bash
pytest -v
```

---

## 📱 Setting Up the Kitchen iPad / iPhone (Full-Screen App Mode)
1. Find your PC's local IP address (e.g., `192.168.1.xxx`).
2. On the iPad or iPhone, open **Safari** and visit `http://<YOUR-PC-IP>:5050`.
3. Tap the **Share** button (square with arrow pointing up) → tap **"Add to Home Screen"**.
4. Launch **Chore Quest** from your iPad Home Screen—it will run full-screen like a native iOS app without browser toolbars!
