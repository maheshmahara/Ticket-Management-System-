/**
 * Admin Panel page logic (admin.html). Kept in its own file rather than
 * an inline <script> like the other pages, since it's meaningfully
 * larger — three tabs, five forms/modals — and inline would make the
 * page source hard to scan.
 *
 * Every mutation this file calls is gated server-side with
 * permission_classes=[IsAdmin] (see backend/app/graphql/mutations.py),
 * so the guard below isn't the only thing stopping a non-admin — it's
 * just a fast client-side redirect so a Member/Manager never sees an
 * admin-shaped page full of FORBIDDEN errors.
 */

requireAuth();

let departmentsCache = [];
let businessUnitsCache = [];
let usersCache = [];
let kpiCache = null;
let kpiRangeMode = "week";

// --- Guard + sidebar bootstrap ---

(async function init() {
  let me;
  try {
    me = await Api.me();
  } catch (err) {
    if (err.code === "FORBIDDEN" || err.message.includes("logged in")) {
      logout();
      return;
    }
    throw err;
  }

  if (me.role !== "ADMIN" && me.role !== "MANAGER") {
    // Not a client-side-only check — every mutation below is also
    // IsAdmin-gated server-side (and kpiReport is IsManagerOrAdmin). This
    // just avoids showing a Member a page that would error on every action.
    location.href = "dashboard.html";
    return;
  }

  document.getElementById("sidebar-name").textContent = me.fullName;
  document.getElementById("sidebar-role").textContent = me.department ? me.department.name : me.role;
  setSidebarAvatar(me);

  Api.myTasksBadgeCount()
    .then((count) => { document.getElementById("nav-mytasks-count").textContent = count; })
    .catch(() => {});

  setupTabs();

  if (me.role === "MANAGER") {
    // Users/Org Structure/Notifications are all IsAdmin-gated mutations —
    // a Manager hitting them would just get a wall of FORBIDDEN errors.
    // The KPI tab is the only one actually meant for them (kpiReport is
    // IsManagerOrAdmin), so land there directly.
    ["users", "org", "notifications"].forEach((t) => {
      document.getElementById(`tab-btn-${t}`).style.display = "none";
    });
    document.querySelectorAll("#admin-tabs .pill").forEach((p) => p.classList.remove("active"));
    document.getElementById("tab-btn-kpi").classList.add("active");
    document.getElementById("tab-users").style.display = "none";
    document.getElementById("tab-kpi").style.display = "";
    await loadKpiTab();
  } else {
    await loadUsersTab();
  }
})();

function setupTabs() {
  document.getElementById("admin-tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".pill");
    if (!btn) return;
    document.querySelectorAll("#admin-tabs .pill").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");

    const tab = btn.dataset.tab;
    document.getElementById("tab-users").style.display = tab === "users" ? "" : "none";
    document.getElementById("tab-org").style.display = tab === "org" ? "" : "none";
    document.getElementById("tab-notifications").style.display = tab === "notifications" ? "" : "none";
    document.getElementById("tab-kpi").style.display = tab === "kpi" ? "" : "none";

    if (tab === "users" && usersCache.length === 0) loadUsersTab();
    if (tab === "org") loadOrgTab();
    if (tab === "notifications") loadNotificationsTab();
    if (tab === "kpi" && kpiCache === null) loadKpiTab();
  });
}

function handleApiError(err, fallbackMessage) {
  if (err.code === "FORBIDDEN" || err.message.includes("logged in")) {
    logout();
    return true;
  }
  alert(fallbackMessage ? `${fallbackMessage}: ${err.message}` : err.message);
  return false;
}

// =========================================================
// USERS TAB
// =========================================================

function renderUserRow(u) {
  const location = [u.department ? u.department.name : null, u.branch ? u.branch.name : null]
    .filter(Boolean)
    .join(" · ") || "<span style=\"color:var(--text-tertiary)\">—</span>";

  return `
    <div class="admin-user-row">
      <div class="assignee-cell">
        <div class="avatar-sm" style="background:${avatarColor(u)}">${avatarInitials(u)}</div>
        <div>
          <div style="font-weight:600">${u.fullName}</div>
          ${u.jobTitle ? `<div style="font-size:11.5px;color:var(--text-tertiary)">${u.jobTitle}</div>` : ""}
        </div>
      </div>
      <div style="font-size:13px;color:var(--text-secondary)">${u.email || "<span style=\"color:var(--text-tertiary)\">No email on file</span>"}</div>
      <span class="role-badge ${u.role.toLowerCase()}">${u.role}</span>
      <div style="font-size:13px">${location}</div>
      <span class="active-tag ${u.isActive ? "is-on" : "is-off"}">● ${u.isActive ? "Active" : "Inactive"}</span>
      <div class="row-actions">
        <button class="icon-action-btn" title="Edit" onclick="openEditUserModal('${u.id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
        </button>
        <button class="icon-action-btn" title="Reset password" onclick="openPasswordModal('${u.id}', '${u.fullName.replace(/'/g, "\\'")}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        </button>
      </div>
    </div>
  `;
}

async function loadUsersTab() {
  const rowsEl = document.getElementById("users-rows");
  rowsEl.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-tertiary)">Loading staff…</div>';
  setTopbarAction('<button class="btn btn-primary" onclick="openAddUserModal()">+ Add User</button>');

  try {
    const [users, departments, businessUnits] = await Promise.all([
      Api.adminUsers(),
      Api.departments(),
      Api.businessUnits(),
    ]);
    usersCache = users;
    departmentsCache = departments;
    businessUnitsCache = businessUnits;

    rowsEl.innerHTML = users.length
      ? users.map(renderUserRow).join("")
      : '<div style="padding:32px;text-align:center;color:var(--text-tertiary)">No staff on file yet.</div>';
  } catch (err) {
    if (handleApiError(err)) return;
    rowsEl.innerHTML = `<div style="padding:32px;text-align:center;color:var(--danger)">Couldn't load staff: ${err.message}</div>`;
  }
}

function setTopbarAction(html) {
  document.getElementById("topbar-actions").innerHTML = html;
}

function populateDepartmentBranchSelects(selectedDeptId, selectedBranchId) {
  const deptSelect = document.getElementById("uf-department");
  deptSelect.innerHTML =
    '<option value="">Unassigned</option>' +
    departmentsCache.map((d) => `<option value="${d.id}" ${d.id === selectedDeptId ? "selected" : ""}>${d.name}</option>`).join("");

  const branchSelect = document.getElementById("uf-branch");
  const allBranches = businessUnitsCache.flatMap((bu) => bu.branches.map((b) => ({ ...b, buName: bu.name })));
  branchSelect.innerHTML =
    '<option value="">Unassigned</option>' +
    allBranches.map((b) => `<option value="${b.id}" ${b.id === selectedBranchId ? "selected" : ""}>${b.buName} — ${b.name}</option>`).join("");
}

let editingUserId = null;

function openAddUserModal() {
  editingUserId = null;
  document.getElementById("user-modal-title").textContent = "Add User";
  document.getElementById("user-form").reset();
  document.getElementById("uf-password-field").style.display = "";
  document.getElementById("uf-password").required = true;
  document.getElementById("uf-active-field").style.display = "none";
  populateDepartmentBranchSelects(null, null);
  hideUserFormError();
  document.getElementById("user-modal").style.display = "flex";
}

function openEditUserModal(id) {
  const u = usersCache.find((x) => x.id === id);
  if (!u) return;
  editingUserId = id;
  document.getElementById("user-modal-title").textContent = "Edit User";
  document.getElementById("uf-fullname").value = u.fullName;
  document.getElementById("uf-email").value = u.email || "";
  document.getElementById("uf-role").value = u.role;
  document.getElementById("uf-jobtitle").value = u.jobTitle || "";
  document.getElementById("uf-phone").value = u.phoneNumber || "";
  document.getElementById("uf-password-field").style.display = "none";
  document.getElementById("uf-password").required = false;
  document.getElementById("uf-active-field").style.display = "";
  document.getElementById("uf-active").checked = u.isActive;
  populateDepartmentBranchSelects(u.department ? u.department.id : null, u.branch ? u.branch.id : null);
  hideUserFormError();
  document.getElementById("user-modal").style.display = "flex";
}

function closeUserModal() {
  document.getElementById("user-modal").style.display = "none";
}

function showUserFormError(msg) {
  document.getElementById("user-form-error-text").textContent = msg;
  document.getElementById("user-form-error").style.display = "flex";
}

function hideUserFormError() {
  document.getElementById("user-form-error").style.display = "none";
}

async function handleUserFormSubmit(e) {
  e.preventDefault();
  hideUserFormError();

  const fullName = document.getElementById("uf-fullname").value.trim();
  const email = document.getElementById("uf-email").value.trim();
  const password = document.getElementById("uf-password").value;
  const role = document.getElementById("uf-role").value;
  const jobTitle = document.getElementById("uf-jobtitle").value.trim();
  const phoneNumber = document.getElementById("uf-phone").value.trim();
  const departmentId = document.getElementById("uf-department").value || null;
  const branchId = document.getElementById("uf-branch").value || null;

  const submitBtn = document.getElementById("user-form-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Saving…";

  try {
    if (editingUserId) {
      await Api.updateUser(editingUserId, {
        fullName, role, departmentId, branchId,
        jobTitle: jobTitle || null,
        phoneNumber: phoneNumber || null,
        isActive: document.getElementById("uf-active").checked,
      });
    } else {
      if (!password || password.length < 6) {
        showUserFormError("Password must be at least 6 characters.");
        return false;
      }
      await Api.createUser({
        fullName, email: email || null, password, role, departmentId, branchId,
        jobTitle: jobTitle || null,
        phoneNumber: phoneNumber || null,
      });
    }
    closeUserModal();
    await loadUsersTab();
  } catch (err) {
    if (handleApiError(err)) return false;
    showUserFormError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Save";
  }
  return false;
}

let resettingUserId = null;

function openPasswordModal(id, name) {
  resettingUserId = id;
  document.getElementById("password-modal-name").textContent = `Setting a new password for ${name}.`;
  document.getElementById("password-form").reset();
  document.getElementById("password-form-error").style.display = "none";
  document.getElementById("password-modal").style.display = "flex";
}

function closePasswordModal() {
  document.getElementById("password-modal").style.display = "none";
}

async function handlePasswordFormSubmit(e) {
  e.preventDefault();
  const newPassword = document.getElementById("pf-password").value;
  const errEl = document.getElementById("password-form-error");
  const errText = document.getElementById("password-form-error-text");

  if (!newPassword || newPassword.length < 6) {
    errText.textContent = "Password must be at least 6 characters.";
    errEl.style.display = "flex";
    return false;
  }

  try {
    await Api.resetUserPassword(resettingUserId, newPassword);
    closePasswordModal();
  } catch (err) {
    if (handleApiError(err)) return false;
    errText.textContent = err.message;
    errEl.style.display = "flex";
  }
  return false;
}

// =========================================================
// ORG STRUCTURE TAB
// =========================================================

async function loadOrgTab() {
  setTopbarAction("");
  const deptPanel = document.getElementById("departments-panel");
  const buList = document.getElementById("business-units-list");
  deptPanel.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-tertiary)">Loading…</div>';
  buList.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-tertiary)">Loading…</div>';

  try {
    const [departments, businessUnits] = await Promise.all([Api.departments(), Api.businessUnits()]);
    departmentsCache = departments;
    businessUnitsCache = businessUnits;
    renderDepartments(departments);
    renderBusinessUnits(businessUnits);
  } catch (err) {
    if (handleApiError(err)) return;
    deptPanel.innerHTML = `<div style="padding:24px;color:var(--danger)">Couldn't load: ${err.message}</div>`;
  }
}

function renderDepartments(departments) {
  const el = document.getElementById("departments-panel");
  el.innerHTML = departments.length
    ? departments.map((d) => `<div class="ticket-row" style="grid-template-columns:1fr;cursor:default"><div>${d.name}</div></div>`).join("")
    : '<div style="padding:24px;text-align:center;color:var(--text-tertiary)">No departments yet.</div>';
}

function renderBusinessUnits(businessUnits) {
  const el = document.getElementById("business-units-list");
  if (!businessUnits.length) {
    el.innerHTML = '<div class="panel" style="padding:24px;text-align:center;color:var(--text-tertiary)">No business units yet.</div>';
    return;
  }

  el.innerHTML = businessUnits
    .map(
      (bu) => `
    <div class="panel bu-card">
      <div class="bu-card-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? '' : 'none'">
        <div>
          <div class="bu-card-title">${bu.name}</div>
          <div class="bu-card-count">${bu.branches.length} branch${bu.branches.length === 1 ? "" : "es"}</div>
        </div>
        <button class="btn btn-secondary" style="padding:6px 12px;font-size:12.5px" onclick="event.stopPropagation(); openAddBranchModal('${bu.id}', '${bu.name.replace(/'/g, "\\'")}')">+ Branch</button>
      </div>
      <div class="bu-branch-list">
        ${
          bu.branches.length
            ? bu.branches
                .map(
                  (b) => `
          <div class="bu-branch-row">
            <span>${b.name}</span>
            <div style="display:flex;align-items:center;gap:10px">
              <span class="active-tag ${b.isActive ? "is-on" : "is-off"}">● ${b.isActive ? "Active" : "Inactive"}</span>
              <button class="icon-action-btn" title="Edit branch" onclick="openEditBranchModal('${b.id}', '${b.name.replace(/'/g, "\\'")}', ${b.isActive})">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              </button>
            </div>
          </div>`
                )
                .join("")
            : '<div class="bu-branch-row" style="color:var(--text-tertiary)">No branches yet.</div>'
        }
      </div>
    </div>
  `
    )
    .join("");
}

async function handleAddDepartment(e) {
  e.preventDefault();
  const input = document.getElementById("new-department-name");
  const name = input.value.trim();
  if (!name) return false;
  try {
    await Api.createDepartment(name);
    input.value = "";
    await loadOrgTab();
  } catch (err) {
    if (handleApiError(err)) return false;
    alert(`Couldn't add department: ${err.message}`);
  }
  return false;
}

async function handleAddBusinessUnit(e) {
  e.preventDefault();
  const input = document.getElementById("new-bu-name");
  const name = input.value.trim();
  if (!name) return false;
  try {
    await Api.createBusinessUnit(name);
    input.value = "";
    await loadOrgTab();
  } catch (err) {
    if (handleApiError(err)) return false;
    alert(`Couldn't add business unit: ${err.message}`);
  }
  return false;
}

let branchModalBusinessUnitId = null;
let editingBranchId = null;

function openAddBranchModal(businessUnitId, businessUnitName) {
  branchModalBusinessUnitId = businessUnitId;
  editingBranchId = null;
  document.getElementById("branch-modal-title").textContent = `Add Branch — ${businessUnitName}`;
  document.getElementById("branch-form").reset();
  document.getElementById("bf-active-field").style.display = "none";
  document.getElementById("branch-form-error").style.display = "none";
  document.getElementById("branch-modal").style.display = "flex";
}

function openEditBranchModal(branchId, branchName, isActive) {
  branchModalBusinessUnitId = null;
  editingBranchId = branchId;
  document.getElementById("branch-modal-title").textContent = "Edit Branch";
  document.getElementById("bf-name").value = branchName;
  document.getElementById("bf-active-field").style.display = "";
  document.getElementById("bf-active").checked = isActive;
  document.getElementById("branch-form-error").style.display = "none";
  document.getElementById("branch-modal").style.display = "flex";
}

function closeBranchModal() {
  document.getElementById("branch-modal").style.display = "none";
}

async function handleBranchFormSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("bf-name").value.trim();
  const errEl = document.getElementById("branch-form-error");
  const errText = document.getElementById("branch-form-error-text");
  if (!name) return false;

  try {
    if (editingBranchId) {
      await Api.updateBranch(editingBranchId, { name, isActive: document.getElementById("bf-active").checked });
    } else {
      await Api.createBranch({ name, businessUnitId: branchModalBusinessUnitId, isActive: true });
    }
    closeBranchModal();
    await loadOrgTab();
  } catch (err) {
    if (handleApiError(err)) return false;
    errText.textContent = err.message;
    errEl.style.display = "flex";
  }
  return false;
}

// =========================================================
// NOTIFICATIONS TAB
// =========================================================

function renderNotifyRow(u) {
  return `
    <div class="admin-user-row" style="grid-template-columns:1.6fr 1fr 1fr 90px 90px" id="notify-row-${u.id}">
      <div class="assignee-cell">
        <div class="avatar-sm" style="background:${avatarColor(u)}">${avatarInitials(u)}</div>
        ${u.fullName}
      </div>
      <div style="font-size:13px;color:var(--text-secondary)">${u.email || "—"}</div>
      <div style="font-size:13px;color:var(--text-secondary)">${u.phoneNumber || "—"}</div>
      <label class="toggle-switch">
        <input type="checkbox" ${u.notifyEmail ? "checked" : ""} onchange="handleNotifyToggle('${u.id}', 'notifyEmail', this)" />
        <span class="toggle-track"></span>
      </label>
      <label class="toggle-switch">
        <input type="checkbox" ${u.notifySms ? "checked" : ""} ${u.phoneNumber ? "" : "disabled"}
          title="${u.phoneNumber ? "" : "Add a phone number first"}"
          onchange="handleNotifyToggle('${u.id}', 'notifySms', this)" />
        <span class="toggle-track"></span>
      </label>
    </div>
  `;
}

async function loadNotificationsTab() {
  setTopbarAction("");
  const rowsEl = document.getElementById("notify-rows");
  rowsEl.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-tertiary)">Loading…</div>';
  try {
    const users = await Api.adminUsers();
    usersCache = users;
    rowsEl.innerHTML = users.length ? users.map(renderNotifyRow).join("") : '<div style="padding:32px;text-align:center;color:var(--text-tertiary)">No staff on file yet.</div>';
  } catch (err) {
    if (handleApiError(err)) return;
    rowsEl.innerHTML = `<div style="padding:32px;text-align:center;color:var(--danger)">Couldn't load: ${err.message}</div>`;
  }
}

async function handleNotifyToggle(userId, field, checkboxEl) {
  const desired = checkboxEl.checked;
  checkboxEl.disabled = true;
  try {
    await Api.updateUser(userId, { [field]: desired });
  } catch (err) {
    checkboxEl.checked = !desired; // revert on failure
    if (handleApiError(err)) return;
    alert(`Couldn't update: ${err.message}`);
  } finally {
    checkboxEl.disabled = false;
  }
}

// =========================================================
// KPI TAB — visible to ADMIN (all departments) and MANAGER (their own
// department only, enforced server-side by kpiReport's IsManagerOrAdmin
// gate + strict department_id scoping, not a client-side filter).
// =========================================================

/**
 * Turns the active range mode into [start, end) ISO strings. `end` is
 * exclusive throughout — Custom's end date gets bumped to midnight of
 * the *next* day so tickets completed on the selected end date are
 * actually included, not silently excluded by an inclusive-looking but
 * actually-exclusive boundary.
 */
function computeRange(mode) {
  const now = new Date();
  if (mode === "week") {
    const start = new Date(now);
    start.setDate(now.getDate() - ((now.getDay() + 6) % 7)); // Monday this week
    start.setHours(0, 0, 0, 0);
    return { start: start.toISOString(), end: now.toISOString() };
  }
  if (mode === "month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    return { start: start.toISOString(), end: now.toISOString() };
  }
  const startInput = document.getElementById("kpi-custom-start").value;
  const endInput = document.getElementById("kpi-custom-end").value;
  if (!startInput || !endInput) return null;
  const start = new Date(`${startInput}T00:00:00`);
  const end = new Date(`${endInput}T00:00:00`);
  end.setDate(end.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

function kpiLeaderboardRow(entry, metric) {
  const metricHtml =
    metric === "speed"
      ? `${formatDuration(entry.avgResolutionSeconds)} avg`
      : `${entry.closedCount} closed`;
  return `
    <div class="ticket-row" style="grid-template-columns:32px 1fr 110px;cursor:default">
      <div class="avatar-sm" style="background:${entry.avatarColor}">${entry.initials}</div>
      <div class="ticket-title">${entry.fullName}</div>
      <div style="font-size:13px;color:var(--text-secondary);text-align:right">${metricHtml}</div>
    </div>
  `;
}

function renderKpiContent(report) {
  const deptRows = report.departments.length
    ? report.departments
        .map(
          (d) => `
        <div class="ticket-row" style="grid-template-columns:1fr 150px 110px;cursor:default">
          <div class="ticket-title">${d.departmentName}</div>
          <div style="font-size:13px;color:var(--text-secondary)">${formatDuration(d.avgResolutionSeconds)} avg</div>
          <div style="font-size:13px;color:var(--text-secondary)">${d.completedCount} closed</div>
        </div>
      `
        )
        .join("")
    : '<div style="padding:24px;text-align:center;color:var(--text-tertiary)">No tickets closed in this range.</div>';

  const fastestHtml = report.fastestResolvers.length
    ? report.fastestResolvers.map((e) => kpiLeaderboardRow(e, "speed")).join("")
    : '<div style="padding:24px;text-align:center;color:var(--text-tertiary)">No data yet.</div>';

  const mostClosedHtml = report.mostTicketsClosed.length
    ? report.mostTicketsClosed.map((e) => kpiLeaderboardRow(e, "count")).join("")
    : '<div style="padding:24px;text-align:center;color:var(--text-tertiary)">No data yet.</div>';

  document.getElementById("kpi-content").innerHTML = `
    <h3 class="admin-section-title">Resolution time by department</h3>
    <div class="table-panel" style="margin-bottom:24px">${deptRows}</div>
    <div class="two-col">
      <div>
        <h3 class="admin-section-title">Fastest average resolvers</h3>
        <div class="table-panel">${fastestHtml}</div>
      </div>
      <div>
        <h3 class="admin-section-title">Most tickets closed</h3>
        <div class="table-panel">${mostClosedHtml}</div>
      </div>
    </div>
  `;
}

async function loadKpiTab() {
  setTopbarAction("");
  const el = document.getElementById("kpi-content");
  const range = computeRange(kpiRangeMode);
  if (!range) {
    el.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-tertiary)">Pick a start and end date.</div>';
    return;
  }

  el.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-tertiary)">Loading KPIs…</div>';
  const controls = document.querySelectorAll("#kpi-range-pills .pill, #kpi-custom-apply");
  controls.forEach((b) => (b.disabled = true));

  try {
    const report = await Api.kpiReport(range.start, range.end);
    kpiCache = report;
    renderKpiContent(report);
  } catch (err) {
    if (handleApiError(err)) return;
    el.innerHTML = `<div style="padding:32px;text-align:center;color:var(--danger)">Couldn't load KPIs: ${err.message}</div>`;
  } finally {
    controls.forEach((b) => (b.disabled = false));
  }
}

document.getElementById("kpi-range-pills").addEventListener("click", (e) => {
  const btn = e.target.closest(".pill");
  if (!btn) return;
  document.querySelectorAll("#kpi-range-pills .pill").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  kpiRangeMode = btn.dataset.range;
  document.getElementById("kpi-custom-range").style.display = kpiRangeMode === "custom" ? "flex" : "none";
  if (kpiRangeMode !== "custom") loadKpiTab();
});
