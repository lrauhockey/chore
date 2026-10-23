/* ==========================================================================
   Family Chore Chart & iPad Kiosk Frontend Logic
   2-Tap Avatar Check-off, Weekly Grid, Leaderboard Badges & Admin Setup
   ========================================================================== */

let currentDailyDate = null;
let currentWeeklyDate = null;
let currentReportPeriod = "week";
let activeUsers = [];
let dailyChoreTemplates = [];
let adminChoresCache = [];
let adminUsersCache = [];
let pendingChoreSelection = null;

document.addEventListener("DOMContentLoaded", () => {
  loadDailyBoard();
});

/* --------------------------------------------------------------------------
   Navigation & Toast Helper
   -------------------------------------------------------------------------- */
function switchTab(tabName) {
  document.querySelectorAll(".view-section").forEach((el) => {
    el.style.display = "none";
  });
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });

  const target = document.getElementById(`view-${tabName}`);
  if (target) target.style.display = "block";

  if (tabName === "daily") loadDailyBoard(currentDailyDate);
  if (tabName === "weekly") loadWeeklyGrid(currentWeeklyDate);
  if (tabName === "reports") loadReports(currentReportPeriod);
  if (tabName === "admin") loadAdminData();
}

function showToast(msg) {
  const banner = document.getElementById("toast-banner");
  banner.textContent = msg;
  banner.classList.add("show");
  setTimeout(() => banner.classList.remove("show"), 2600);
}

/* --------------------------------------------------------------------------
   1. Daily Kiosk Board
   -------------------------------------------------------------------------- */
async function loadDailyBoard(dateStr = null) {
  const url = dateStr ? `/api/daily?date=${encodeURIComponent(dateStr)}` : "/api/daily";
  const res = await fetch(url);
  const data = await res.json();

  currentDailyDate = data.date;
  activeUsers = data.users || [];
  dailyChoreTemplates = data.chore_templates || [];

  if (data.settings && data.settings.household_name) {
    document.getElementById("household-title").textContent = data.settings.household_name;
  }

  document.getElementById("daily-date-label").textContent = data.display_date;
  document.getElementById("daily-today-badge").style.display = data.is_today ? "inline-block" : "none";
  document.getElementById("btn-jump-today").style.display = data.is_today ? "none" : "inline-block";

  const prog = data.progress || { completed: 0, total: 0, percent: 0 };
  document.getElementById("daily-progress-text").textContent =
    `${prog.completed} / ${prog.total} Chores (${prog.percent}%)`;
  document.getElementById("daily-progress-bar").style.width = `${prog.percent}%`;

  renderHeaderUserStrip(activeUsers);
  renderDailySections(data.chores || []);
}

function shiftDailyDate(deltaDays) {
  const base = currentDailyDate ? new Date(currentDailyDate + "T12:00:00") : new Date();
  base.setDate(base.getDate() + deltaDays);
  const iso = base.toISOString().slice(0, 10);
  loadDailyBoard(iso);
}

function renderHeaderUserStrip(users) {
  const strip = document.getElementById("header-user-strip");
  strip.innerHTML = users
    .map(
      (u) => `
      <div class="user-pill" style="border-color: ${u.color}55;">
        <div class="user-pill-avatar" style="background: ${u.color}28;">${u.avatar}</div>
        <span>${escapeHtml(u.name)}</span>
        <span class="user-pill-pts">+${u.today_points || 0} pts today</span>
        ${u.streak > 0 ? `<span class="streak-badge" title="Active Day Streak">🔥 ${u.streak}d</span>` : ""}
      </div>
    `
    )
    .join("");
}

function renderDailySections(chores) {
  const container = document.getElementById("daily-board-content");
  if (!chores.length) {
    container.innerHTML = `
      <div class="panel-card" style="text-align:center; padding:40px;">
        <h2>🎉 No chores scheduled for this date!</h2>
        <p style="color:#94a3b8;">Kick back or add more chores in Admin Setup.</p>
      </div>`;
    return;
  }

  const groups = [
    { key: "morning", title: "🌅 Morning Routine", items: [] },
    { key: "anytime", title: "☀️ Anytime Today", items: [] },
    { key: "evening", title: "🌙 Evening & Night Duty", items: [] },
    { key: "weekly_anytime", title: "📅 Weekly Tasks (Open Anytime This Week)", items: [] },
  ];

  chores.forEach((ch) => {
    const grp = groups.find((g) => g.key === ch.time_group) || groups[1];
    grp.items.push(ch);
  });

  container.innerHTML = groups
    .filter((g) => g.items.length > 0)
    .map(
      (g) => `
      <div class="slot-section">
        <div class="slot-header">${g.title}</div>
        <div class="chore-grid">
          ${g.items.map((item) => renderChoreCard(item)).join("")}
        </div>
      </div>
    `
    )
    .join("");
}

function renderChoreCard(item) {
  const slotClass =
    item.slot === "AM" ? "tag-slot-am" : item.slot === "PM" ? "tag-slot-pm" : "";
  const assignedHtml = item.assigned_user
    ? `<span class="tag tag-assigned">Assigned: ${item.assigned_user.avatar} ${escapeHtml(item.assigned_user.name)}</span>`
    : `<span class="tag tag-open">🟢 Up for Grabs</span>`;

  const stolenHtml = item.was_stolen
    ? `<span class="tag tag-stolen">🏴‍☠️ Covered / Stolen!</span>`
    : "";

  const rightStatusHtml = item.completed && item.completed_by
    ? `
      <div class="completed-stamp">
        <span>${item.completed_by.avatar}</span>
        <span>${escapeHtml(item.completed_by.name)}</span>
        <span>✓</span>
      </div>
      <span style="font-size:0.75rem; color:#94a3b8;">Tap to undo</span>
    `
    : `<div class="points-pill">+${item.points} pts</div>`;

  const payloadAttr = encodeURIComponent(JSON.stringify(item));

  return `
    <div class="chore-card ${item.completed ? "completed" : ""}" onclick="handleChoreTap('${payloadAttr}')">
      <div class="chore-left">
        <div class="chore-icon-box">${item.icon}</div>
        <div class="chore-info">
          <h3>${escapeHtml(item.name)}</h3>
          <div class="chore-tags">
            <span class="tag ${slotClass}">${escapeHtml(item.slot_label)}</span>
            ${assignedHtml}
            ${stolenHtml}
          </div>
        </div>
      </div>
      <div class="chore-right">
        ${rightStatusHtml}
      </div>
    </div>
  `;
}

/* --------------------------------------------------------------------------
   2-Tap Avatar Picker Kiosk Flow
   -------------------------------------------------------------------------- */
async function handleChoreTap(encodedItem, fromWeekly = false) {
  const item = JSON.parse(decodeURIComponent(encodedItem));

  if (item.completed) {
    // Undo completion
    await fetch("/api/uncomplete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chore_id: item.chore_id,
        target_date: item.target_date,
        slot: item.slot,
      }),
    });
    showToast(`↩️ Undid "${item.name}"`);
    if (fromWeekly) loadWeeklyGrid(currentWeeklyDate);
    else loadDailyBoard(currentDailyDate);
    return;
  }

  pendingChoreSelection = { item, fromWeekly };
  document.getElementById("modal-chore-icon").textContent = item.icon;
  document.getElementById("modal-chore-title").textContent =
    `${item.name} (${item.slot_label})`;
  document.getElementById("modal-chore-subtitle").textContent =
    `Tap your avatar to claim +${item.points} points!`;

  const grid = document.getElementById("modal-avatar-grid");
  grid.innerHTML = activeUsers
    .map(
      (u) => `
      <button class="avatar-pick-btn" onclick="confirmChoreCompletion(${u.id})">
        <div class="avatar-pick-circle" style="background: ${u.color}33; border: 2px solid ${u.color};">
          ${u.avatar}
        </div>
        <span>${escapeHtml(u.name)}</span>
      </button>
    `
    )
    .join("");

  document.getElementById("avatar-modal").classList.add("open");
}

function closeAvatarModal(e) {
  document.getElementById("avatar-modal").classList.remove("open");
  pendingChoreSelection = null;
}

async function confirmChoreCompletion(userId) {
  if (!pendingChoreSelection) return;
  const { item, fromWeekly } = pendingChoreSelection;
  closeAvatarModal();

  const res = await fetch("/api/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chore_id: item.chore_id,
      user_id: userId,
      target_date: item.target_date,
      slot: item.slot,
    }),
  });
  const result = await res.json();

  if (result.ok) {
    const stealNote = result.was_stolen ? " (🏴‍☠️ Covered teammate's chore!)" : "";
    showToast(
      `${result.user_avatar} ${result.user_name} earned +${result.points_earned} pts for ${result.chore_name}!${stealNote}`
    );
  }

  if (fromWeekly) loadWeeklyGrid(currentWeeklyDate);
  else loadDailyBoard(currentDailyDate);
}

/* --------------------------------------------------------------------------
   Ad-Hoc / Bonus Chore Modal (From Today's Board)
   -------------------------------------------------------------------------- */
function openAdhocModal() {
  const presetSelect = document.getElementById("adhoc-preset-select");
  presetSelect.innerHTML =
    `<option value="">✨ Custom One-Off Task...</option>` +
    dailyChoreTemplates
      .map(
        (ch) =>
          `<option value="${ch.id}">${ch.icon} ${escapeHtml(ch.name)} (+${ch.points} pts)</option>`
      )
      .join("");

  const userSelect = document.getElementById("adhoc-user-select");
  userSelect.innerHTML =
    `<option value="">🟢 Put on Today's Board (Open for Anyone to Claim)</option>` +
    activeUsers
      .map((u) => `<option value="${u.id}">${u.avatar} Completed right now by ${escapeHtml(u.name)}</option>`)
      .join("");

  document.getElementById("adhoc-name").value = "";
  document.getElementById("adhoc-icon").value = "⚡";
  document.getElementById("adhoc-points").value = "15";
  onAdhocPresetChange();
  document.getElementById("adhoc-modal").classList.add("open");
}

function closeAdhocModal() {
  document.getElementById("adhoc-modal").classList.remove("open");
}

function onAdhocPresetChange() {
  const presetId = document.getElementById("adhoc-preset-select").value;
  const customBox = document.getElementById("adhoc-custom-fields");
  const userSelect = document.getElementById("adhoc-user-select");

  if (presetId) {
    customBox.style.display = "none";
    // When picking an existing recurring chore for an extra ad-hoc run today,
    // default to selecting who completed it (or first adult if open)
    if (!userSelect.value && activeUsers.length > 0) {
      userSelect.value = String(activeUsers[0].id);
    }
  } else {
    customBox.style.display = "block";
    userSelect.value = "";
  }
}

async function submitAdhocTask() {
  const presetId = document.getElementById("adhoc-preset-select").value;
  const userId = document.getElementById("adhoc-user-select").value;

  if (presetId && !userId) {
    showToast("⚠️ Select who completed this extra chore run!");
    return;
  }

  const payload = {
    target_date: currentDailyDate,
    chore_id: presetId ? parseInt(presetId, 10) : null,
    user_id: userId ? parseInt(userId, 10) : null,
    name: document.getElementById("adhoc-name").value.trim(),
    icon: document.getElementById("adhoc-icon").value.trim() || "⚡",
    points: parseInt(document.getElementById("adhoc-points").value || "15", 10),
    category: document.getElementById("adhoc-category").value,
  };

  if (!presetId && !payload.name) {
    showToast("⚠️ Please enter a name for the custom task!");
    return;
  }

  const res = await fetch("/api/adhoc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (data.ok) {
    closeAdhocModal();
    if (data.completed_by) {
      showToast(
        `⚡ ${data.completed_by.avatar} ${data.completed_by.name} logged "${data.chore_name}" (+${data.completed_by.points} pts)!`
      );
    } else {
      showToast(`⚡ Added "${data.chore_name}" to Today's Board!`);
    }
    loadDailyBoard(currentDailyDate);
  }
}

/* --------------------------------------------------------------------------
   2. Weekly Schedule Grid
   -------------------------------------------------------------------------- */
async function loadWeeklyGrid(dateStr = null) {
  const url = dateStr ? `/api/weekly?date=${encodeURIComponent(dateStr)}` : "/api/weekly";
  const res = await fetch(url);
  const data = await res.json();

  currentWeeklyDate = data.week_start;
  document.getElementById("weekly-range-label").textContent = data.week_label;

  const container = document.getElementById("weekly-grid-container");
  container.innerHTML = (data.days || [])
    .map(
      (day) => `
      <div class="week-day-col ${day.is_today ? "today" : ""}">
        <div class="week-day-header">
          <div class="week-day-name">${day.day_short}</div>
          <div class="week-day-num">${day.month_short} ${day.day_num}</div>
          <div style="font-size:0.75rem; color:#94a3b8; margin-top:4px;">
            ${day.completed_count}/${day.total_count} done
          </div>
        </div>
        ${day.chores
          .map((ch) => {
            const payload = encodeURIComponent(JSON.stringify(ch));
            return `
              <div class="week-mini-chore ${ch.completed ? "done" : ""}" onclick="handleChoreTap('${payload}', true)">
                <div style="display:flex; justify-content:space-between; align-items:center; font-weight:800;">
                  <span>${ch.icon} ${escapeHtml(ch.name)}</span>
                  <span style="color:#fbbf24;">+${ch.points}</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.72rem; color:#94a3b8;">
                  <span>${ch.slot_label}</span>
                  <span>
                    ${
                      ch.completed && ch.completed_by
                        ? `${ch.completed_by.avatar} ${escapeHtml(ch.completed_by.name)} ✓`
                        : ch.assigned_user
                        ? `→ ${ch.assigned_user.avatar}`
                        : "Open"
                    }
                  </span>
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    `
    )
    .join("");
}

function shiftWeeklyDate(deltaDays) {
  const base = currentWeeklyDate ? new Date(currentWeeklyDate + "T12:00:00") : new Date();
  base.setDate(base.getDate() + deltaDays);
  loadWeeklyGrid(base.toISOString().slice(0, 10));
}

/* --------------------------------------------------------------------------
   3. Leaderboard, Badges & Progress Reports
   -------------------------------------------------------------------------- */
async function loadReports(period = "week") {
  currentReportPeriod = period;
  const res = await fetch(`/api/reports?period=${encodeURIComponent(period)}`);
  const data = await res.json();

  document.getElementById("report-period-title").textContent =
    `${data.period_label} • ${data.total_household_points} Total Household Points`;

  // Render Crowned Champion & Last Place Penalty Banners
  const bannersEl = document.getElementById("royalty-banners-container");
  let bannersHtml = "";

  if (data.champion) {
    bannersHtml += `
      <div class="banner-card banner-champion">
        <div class="banner-avatar">${data.champion.user.avatar}</div>
        <div class="banner-text">
          <h4>👑 Reigning Chore Royalty (1st Place)</h4>
          <h2>${escapeHtml(data.champion.user.name)} — ${data.champion.points} pts</h2>
          <p>${escapeHtml(data.settings.champion_reward || "Picks Friday Night Takeout!")}</p>
        </div>
      </div>
    `;
  }

  if (data.last_place) {
    bannersHtml += `
      <div class="banner-card banner-penalty">
        <div class="banner-avatar">${data.last_place.user.avatar}</div>
        <div class="banner-text">
          <h4>🍕 Last Place Caboose Alert</h4>
          <h2>${escapeHtml(data.last_place.user.name)} — ${data.last_place.points} pts</h2>
          <p>${escapeHtml(data.settings.last_place_penalty || "On the hook for next coffee/drinks!")}</p>
        </div>
      </div>
    `;
  }
  bannersEl.innerHTML = bannersHtml;

  // Render Leaderboard Rows with Badges & Share Bars
  const lbContainer = document.getElementById("leaderboard-container");
  lbContainer.innerHTML = (data.leaderboard || [])
    .map((entry, idx) => {
      const rankMedal = idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : `#${idx + 1}`;
      const badgesHtml =
        entry.badges && entry.badges.length
          ? entry.badges
              .map(
                (b) => `
              <span class="badge-chip" title="${escapeHtml(b.desc)}">
                <span>${b.icon}</span>
                <span>${escapeHtml(b.name)}</span>
              </span>
            `
              )
              .join("")
          : `<span style="font-size:0.82rem; color:#64748b;">Complete chores to unlock badges!</span>`;

      return `
        <div class="leader-row">
          <div class="leader-top">
            <div class="leader-user">
              <div class="rank-circle">${rankMedal}</div>
              <div class="leader-avatar" style="background:${entry.user.color}30; border:2px solid ${entry.user.color};">
                ${entry.user.avatar}
              </div>
              <div>
                <h3 style="margin:0; font-size:1.25rem;">
                  ${escapeHtml(entry.user.name)}
                  ${entry.streak > 0 ? `<span class="streak-badge">🔥 ${entry.streak}-day streak</span>` : ""}
                </h3>
                <div style="font-size:0.85rem; color:#94a3b8; margin-top:3px;">
                  ${entry.total_count} chores completed • ${entry.share_percent}% of household points
                  ${entry.stolen_count > 0 ? ` • 🏴‍☠️ ${entry.stolen_count} covered` : ""}
                </div>
              </div>
            </div>
            <div class="leader-score">
              <div class="leader-pts">${entry.points} pts</div>
            </div>
          </div>

          <div class="progress-track" style="margin-top:12px; height:10px;">
            <div class="progress-fill" style="width:${entry.share_percent}%; background:${entry.user.color};"></div>
          </div>

          <div class="badge-shelf">${badgesHtml}</div>
        </div>
      `;
    })
    .join("");

  // Category Breakdown
  const catNames = {
    dog: "🐕 Dog Care",
    poop: "💩 Poop Patrol",
    kitchen: "🧽 Kitchen",
    trash: "🗑️ Trash & Recycling",
    house: "🏠 General House",
  };
  const catBox = document.getElementById("category-breakdown-box");
  const cats = Object.entries(data.category_breakdown || {});
  catBox.innerHTML = cats.length
    ? cats
        .map(
          ([cat, pts]) => `
          <div class="admin-list-item">
            <span style="font-weight:700;">${catNames[cat] || cat}</span>
            <span style="color:#fbbf24; font-weight:800;">${pts} pts</span>
          </div>
        `
        )
        .join("")
    : `<p style="color:#94a3b8;">No points logged in this period yet.</p>`;

  // Recent History
  const histBox = document.getElementById("recent-history-box");
  const hist = data.recent_history || [];
  histBox.innerHTML = hist.length
    ? hist
        .slice(0, 10)
        .map(
          (h) => `
          <div class="admin-list-item">
            <div>
              <strong>${h.user_avatar} ${escapeHtml(h.user_name)}</strong> completed
              <strong>${h.chore_icon} ${escapeHtml(h.chore_name)}</strong>
              <div style="font-size:0.76rem; color:#94a3b8;">${h.target_date} (${h.slot})</div>
            </div>
            <span style="color:#10b981; font-weight:800;">+${h.points_earned} pts</span>
          </div>
        `
        )
        .join("")
    : `<p style="color:#94a3b8;">No recent completions yet.</p>`;
}

/* --------------------------------------------------------------------------
   4. Admin Setup Screen (Users, Chores, Settings)
   -------------------------------------------------------------------------- */
async function loadAdminData() {
  const res = await fetch("/api/admin/data");
  const data = await res.json();

  adminUsersCache = data.users || [];
  adminChoresCache = data.chores || [];

  // Populate Settings
  const s = data.settings || {};
  document.getElementById("setting-household-name").value = s.household_name || "";
  document.getElementById("setting-champion-reward").value = s.champion_reward || "";
  document.getElementById("setting-last-penalty").value = s.last_place_penalty || "";

  // Populate Assigned User Select
  const assignSelect = document.getElementById("chore-assigned-user");
  assignSelect.innerHTML =
    `<option value="">🟢 Up for Grabs / Jump Ball (Anyone)</option>` +
    adminUsersCache
      .map((u) => `<option value="${u.id}">${u.avatar} Assigned to ${escapeHtml(u.name)}</option>`)
      .join("");

  // Render Users List
  const usersList = document.getElementById("admin-users-list");
  usersList.innerHTML = adminUsersCache
    .map(
      (u) => `
      <div class="admin-list-item">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.5rem; background:${u.color}33; padding:4px 8px; border-radius:10px;">${u.avatar}</span>
          <strong>${escapeHtml(u.name)}</strong>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn-icon" style="padding:6px 12px; font-size:0.8rem;" onclick="editUser(${u.id})">Edit</button>
          <button class="btn-danger" onclick="deleteUser(${u.id})">Delete</button>
        </div>
      </div>
    `
    )
    .join("");

  // Render Chores List
  const choresList = document.getElementById("admin-chores-list");
  choresList.innerHTML = adminChoresCache
    .map((ch) => {
      const assignee = adminUsersCache.find((u) => u.id === ch.assigned_user_id);
      return `
        <div class="admin-list-item">
          <div>
            <strong style="font-size:1.05rem;">${ch.icon} ${escapeHtml(ch.name)}</strong>
            <span class="tag" style="margin-left:6px; color:#fbbf24;">+${ch.points} pts</span>
            <div style="font-size:0.82rem; color:#94a3b8; margin-top:4px;">
              ${escapeHtml(ch.frequency_label)} •
              ${assignee ? `Assigned to ${assignee.avatar} ${escapeHtml(assignee.name)}` : "🟢 Up for Grabs"}
            </div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn-icon" style="padding:6px 12px; font-size:0.8rem;" onclick="editChore(${ch.id})">Edit</button>
            <button class="btn-danger" onclick="deleteChore(${ch.id})">Delete</button>
          </div>
        </div>
      `;
    })
    .join("");

  if (!document.getElementById("chore-anchor").value) {
    document.getElementById("chore-anchor").value = new Date().toISOString().slice(0, 10);
  }
}

function onFrequencyChange() {
  const freq = document.getElementById("chore-frequency").value;
  const daysGroup = document.getElementById("days-of-week-group");
  const anchorGroup = document.getElementById("anchor-date-group");
  const timeGroup = document.getElementById("time-of-day-group");

  daysGroup.style.display = freq === "weekly" || freq === "biweekly" ? "block" : "none";
  anchorGroup.style.display =
    freq === "biweekly" || freq === "every_other_day" ? "block" : "none";
  timeGroup.style.display =
    freq === "twice_daily" || freq === "weekly_anytime" ? "none" : "block";
}

function toggleDayPill(btn) {
  btn.classList.toggle("selected");
}

function pickQuickEmoji(emoji) {
  document.getElementById("user-avatar").value = emoji;
}

async function saveChore() {
  const selectedDays = Array.from(document.querySelectorAll("#weekday-pills .day-pill.selected"))
    .map((b) => b.dataset.day)
    .join(",");

  const payload = {
    id: document.getElementById("chore-id").value || null,
    name: document.getElementById("chore-name").value.trim(),
    icon: document.getElementById("chore-icon").value.trim() || "✨",
    points: parseInt(document.getElementById("chore-points").value || "10", 10),
    category: document.getElementById("chore-category").value,
    frequency_type: document.getElementById("chore-frequency").value,
    time_of_day: document.getElementById("chore-time").value,
    days_of_week: selectedDays,
    anchor_date: document.getElementById("chore-anchor").value,
    assigned_user_id: document.getElementById("chore-assigned-user").value || null,
  };

  if (!payload.name) {
    showToast("⚠️ Please enter a chore name!");
    return;
  }

  await fetch("/api/admin/chores", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  showToast("✅ Chore saved!");
  resetChoreForm();
  loadAdminData();
}

function editChore(choreId) {
  const ch = adminChoresCache.find((c) => c.id === choreId);
  if (!ch) return;

  document.getElementById("chore-form-title").textContent = `✏️ Edit Chore: ${ch.name}`;
  document.getElementById("chore-id").value = ch.id;
  document.getElementById("chore-name").value = ch.name;
  document.getElementById("chore-icon").value = ch.icon;
  document.getElementById("chore-points").value = ch.points;
  document.getElementById("chore-category").value = ch.category;
  document.getElementById("chore-frequency").value = ch.frequency_type;
  document.getElementById("chore-time").value = ch.time_of_day === "both" ? "any" : ch.time_of_day;
  document.getElementById("chore-anchor").value = ch.anchor_date || "";
  document.getElementById("chore-assigned-user").value = ch.assigned_user_id || "";

  const activeDays = (ch.days_of_week || "").split(",").map((x) => x.trim());
  document.querySelectorAll("#weekday-pills .day-pill").forEach((btn) => {
    btn.classList.toggle("selected", activeDays.includes(btn.dataset.day));
  });

  onFrequencyChange();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetChoreForm() {
  document.getElementById("chore-form-title").textContent = "➕ Add / Edit Chore";
  document.getElementById("chore-id").value = "";
  document.getElementById("chore-name").value = "";
  document.getElementById("chore-icon").value = "✨";
  document.getElementById("chore-points").value = "15";
  document.getElementById("chore-frequency").value = "daily";
  document.getElementById("chore-time").value = "any";
  document.getElementById("chore-assigned-user").value = "";
  document.querySelectorAll("#weekday-pills .day-pill").forEach((btn) => btn.classList.remove("selected"));
  onFrequencyChange();
}

async function deleteChore(choreId) {
  await fetch(`/api/admin/chores/${choreId}`, { method: "DELETE" });
  showToast("🗑️ Chore deleted");
  loadAdminData();
}

async function saveUser() {
  const payload = {
    id: document.getElementById("user-id").value || null,
    name: document.getElementById("user-name").value.trim(),
    avatar: document.getElementById("user-avatar").value.trim() || "😎",
    color: document.getElementById("user-color").value || "#6366f1",
  };
  if (!payload.name) {
    showToast("⚠️ Enter a family member name!");
    return;
  }
  await fetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  document.getElementById("user-id").value = "";
  document.getElementById("user-name").value = "";
  showToast("✅ Family member saved!");
  loadAdminData();
}

function editUser(userId) {
  const u = adminUsersCache.find((x) => x.id === userId);
  if (!u) return;
  document.getElementById("user-id").value = u.id;
  document.getElementById("user-name").value = u.name;
  document.getElementById("user-avatar").value = u.avatar;
  document.getElementById("user-color").value = u.color;
}

async function deleteUser(userId) {
  await fetch(`/api/admin/users/${userId}`, { method: "DELETE" });
  showToast("🗑️ Family member removed");
  loadAdminData();
}

async function saveSettings() {
  const payload = {
    household_name: document.getElementById("setting-household-name").value,
    champion_reward: document.getElementById("setting-champion-reward").value,
    last_place_penalty: document.getElementById("setting-last-penalty").value,
  };
  await fetch("/api/admin/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  showToast("✅ Leaderboard banners updated!");
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
