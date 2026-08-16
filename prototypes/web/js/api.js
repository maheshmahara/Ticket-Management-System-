/**
 * Minimal GraphQL client wiring these static prototype pages to the
 * real HNBG backend (backend/app/graphql/*). No build step, no
 * framework — plain fetch, matching how the rest of this prototype is
 * written (see create-task.html's inline <script> for the same style).
 *
 * IMPORTANT — how to actually run this:
 *   1. Backend running via `docker-compose up` in backend/ (see
 *      backend/README.md), with the schema migrated and at least one
 *      seeded user given a password via scripts/set_password.py.
 *   2. These HTML files must be served over http://, not opened via
 *      file:// — browsers send `Origin: null` for file:// pages, which
 *      the API's CORS config (backend/.env CORS_ORIGINS) does not
 *      allow by default. From this directory:
 *          python3 -m http.server 5500
 *      then open http://localhost:5500/index.html. If you serve from a
 *      different port, add it to CORS_ORIGINS in backend/.env and
 *      restart the api container.
 */

const API_URL = "http://localhost:8000/graphql";

const TOKEN_KEY = "hnbg_access_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Redirect to login if there's no token on file. Call this at the top
 * of every page except index.html. Doesn't verify the token is still
 * valid server-side (that's what the first real query will do) — it's
 * a fast client-side guard against an obviously-logged-out visitor.
 */
function requireAuth() {
  if (!getToken()) {
    location.href = "index.html";
  }
}

function logout() {
  clearToken();
  location.href = "index.html";
}

/**
 * Light / Dark / System theme picker. "system" is the implicit default
 * (no localStorage entry at all) — matches this app's original,
 * OS-only dark mode behavior exactly, so anyone who never touches the
 * new control sees no change. "light"/"dark" set `data-theme` on
 * <html>, which styles.css's `:root[data-theme="..."]` blocks override
 * the `prefers-color-scheme` media query with, in both directions.
 *
 * The actual flash-of-wrong-theme prevention lives in each page's own
 * inline <head> script (this file loads at the end of <body>, far too
 * late to apply the theme before first paint) — that inline script and
 * applyTheme() below intentionally duplicate the same few lines rather
 * than sharing code, since the whole point is running before this file
 * has even started downloading.
 */
const THEME_KEY = "hnbg_theme";

function getThemeChoice() {
  return localStorage.getItem(THEME_KEY) || "system";
}

function applyTheme(choice) {
  if (choice === "light" || choice === "dark") {
    document.documentElement.dataset.theme = choice;
  } else {
    delete document.documentElement.dataset.theme;
  }
}

function setThemeChoice(choice) {
  localStorage.setItem(THEME_KEY, choice);
  applyTheme(choice);
  syncThemeToggleUI();
}

function syncThemeToggleUI() {
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;
  const current = getThemeChoice();
  toggle.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.themeChoice === current);
  });
}

/**
 * Topbar "Search tickets, people…" — live, debounced, two-group
 * dropdown (Tickets from Api.searchTasks(), People from
 * Api.searchPeople()). Present on dashboard.html and tasks.html today;
 * a page without #topbar-search-input just no-ops via the guard below.
 * A ticket result opens task-detail.html; a person result opens
 * create-task.html with them pre-selected as assignee — same
 * ?assigneeId= prefill the Org Structure mind map's member nodes use
 * (see create-task.html's loadFormOptions()).
 */
function initTopbarSearch() {
  const input = document.getElementById("topbar-search-input");
  const results = document.getElementById("topbar-search-results");
  if (!input || !results) return;

  let debounceTimer = null;

  function closeResults() {
    results.style.display = "none";
    results.innerHTML = "";
  }

  function renderResults(tickets, people) {
    if (tickets.length === 0 && people.length === 0) {
      results.innerHTML = '<div class="search-empty">No matches.</div>';
      results.style.display = "";
      return;
    }
    let html = "";
    if (tickets.length) {
      html += '<div class="search-group-label">Tickets</div>';
      html += tickets
        .map(
          (t) => `
        <div class="search-result-row" onclick="location.href='task-detail.html?id=${t.id}'">
          <span class="search-result-ticket">${t.ticketNo}</span>
          <span class="search-result-title">${t.title}</span>
        </div>`
        )
        .join("");
    }
    if (people.length) {
      html += '<div class="search-group-label">People</div>';
      html += people
        .map(
          (p) => `
        <div class="search-result-row" onclick="location.href='create-task.html?assigneeId=${p.id}'">
          <div class="avatar-sm" style="background:${p.avatarColor}">${p.initials}</div>
          <span class="search-result-title">${p.fullName}</span>
        </div>`
        )
        .join("");
    }
    results.innerHTML = html;
    results.style.display = "";
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const query = input.value.trim();
    if (!query) {
      closeResults();
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        const [tickets, people] = await Promise.all([Api.searchTasks(query), Api.searchPeople(query)]);
        // The debounce can let an older request resolve after a newer
        // one if the network is slow — bail if the input has since
        // changed, so a stale response doesn't overwrite fresher results.
        if (input.value.trim() !== query) return;
        renderResults(tickets, people);
      } catch (err) {
        results.innerHTML = '<div class="search-empty">Search failed.</div>';
        results.style.display = "";
      }
    }, 250);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeResults();
      input.blur();
    }
  });

  document.addEventListener("click", (e) => {
    if (e.target !== input && !results.contains(e.target)) closeResults();
  });
}

const NOTIFICATION_TRIGGER_LABEL = {
  TASK_CREATED: "New ticket",
  TASK_ASSIGNED: "Assigned to you",
  PRIORITY_ESCALATED: "Priority escalated",
  TASK_OVERDUE: "Overdue",
};

/** "2m ago" / "3h ago" / "5d ago", falling back to a short date past a
 * week — same spirit as formatDuration() above but for a point in time
 * rather than an elapsed span, so it can't reuse that function. */
function formatRelativeTime(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(isoString).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Topbar notification bell. Present on dashboard.html today; a page
 * without #notif-bell-btn just no-ops via the guard below. Fetches
 * once at load to decide whether the unread dot shows at all (compares
 * each notification's createdAt against me.notificationsLastSeenAt —
 * there's no separate unread flag per notification, see
 * Notification's docstring in backend/app/graphql/types.py). Opening
 * the panel calls markNotificationsSeen() immediately — badge clears
 * on open, same as every mainstream notification bell, no separate
 * "mark all read" click needed.
 */
function initNotificationBell() {
  const btn = document.getElementById("notif-bell-btn");
  const panel = document.getElementById("notif-panel");
  const dot = document.getElementById("notif-dot");
  if (!btn || !panel || !dot) return;

  let cachedNotifications = [];

  function renderPanel() {
    if (cachedNotifications.length === 0) {
      panel.innerHTML = '<div class="notif-empty">No notifications yet.</div>';
      return;
    }
    panel.innerHTML = cachedNotifications
      .map(
        (n) => `
      <div class="notif-row" onclick="location.href='task-detail.html?id=${n.task.id}'">
        <div class="notif-row-text">${NOTIFICATION_TRIGGER_LABEL[n.trigger] || "Update"} — <strong>${n.task.ticketNo}</strong>: ${n.task.title}</div>
        <div class="notif-row-time">${formatRelativeTime(n.createdAt)}</div>
      </div>`
      )
      .join("");
  }

  btn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const isOpen = panel.style.display !== "none";
    if (isOpen) {
      panel.style.display = "none";
      return;
    }
    renderPanel();
    panel.style.display = "";
    dot.style.display = "none";
    Api.markNotificationsSeen().catch(() => {});
  });

  document.addEventListener("click", (e) => {
    if (e.target !== btn && !btn.contains(e.target) && !panel.contains(e.target)) {
      panel.style.display = "none";
    }
  });

  Promise.all([Api.myNotifications(), Api.me()])
    .then(([notifications, me]) => {
      cachedNotifications = notifications;
      const lastSeen = me.notificationsLastSeenAt ? new Date(me.notificationsLastSeenAt) : null;
      const hasUnread = notifications.some((n) => !lastSeen || new Date(n.createdAt) > lastSeen);
      dot.style.display = hasUnread ? "" : "none";
    })
    .catch(() => {
      // Non-fatal — the bell just won't show a badge if this fails
      // (e.g. logged out mid-load); clicking it will still try to load.
    });
}

// Runs immediately as this file executes — by the time api.js loads
// (end of <body>), the sidebar-footer markup (including #theme-toggle,
// on every page that has one) is already parsed, so no need to wait
// for DOMContentLoaded. Pages without a #theme-toggle (index.html,
// create-task.html) no-op via the guard inside syncThemeToggleUI().
// initTopbarSearch()/initNotificationBell() themselves are called much
// further down, after `const Api` is actually defined — both reference
// Api.* the moment they run (not just when their event handlers later
// fire), so calling them here would hit Api's temporal dead zone.
syncThemeToggleUI();

/**
 * Runs one GraphQL request. Throws an Error with `.code` (from the
 * typed extensions HNBG's resolvers attach — see
 * backend/app/graphql/errors.py) when the API returns a GraphQL error,
 * so callers can branch on e.g. `err.code === "INVALID_CREDENTIALS"`.
 */
async function gql(query, variables) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // fetch() itself rejects (not just a non-2xx response) when the API is
  // unreachable — no server, DNS failure, CORS block, offline. Left
  // unhandled, that rejection is the browser's own generic wording (e.g.
  // Safari's bare "Load failed"), which surfaces to the user completely
  // unfiltered. Give both failure modes a clear, branded message instead.
  let res;
  try {
    res = await fetch(API_URL, {
      method: "POST",
      headers,
      body: JSON.stringify({ query, variables }),
    });
  } catch (networkErr) {
    console.error("GraphQL request failed:", networkErr);
    throw new Error("Can't reach the HNBG server right now. Check your connection and try again.");
  }

  if (!res.ok) {
    console.error(`GraphQL HTTP ${res.status}`);
    throw new Error("The HNBG server had a problem handling that request. Please try again in a moment.");
  }

  const payload = await res.json();

  if (payload.errors && payload.errors.length > 0) {
    const first = payload.errors[0];
    const err = new Error(first.message);
    err.code = first.extensions && first.extensions.code;
    // An expired/invalid token surfaces as a permission failure from
    // IsAuthenticated, not a distinct "unauthorized" error code — bounce
    // back to login rather than leaving the page stuck.
    if (!token && err.code === "FORBIDDEN") {
      // not logged in at all — let the caller decide (requireAuth
      // already guards most pages, so this is a defensive fallback)
    }
    throw err;
  }

  return payload.data;
}

const Api = {
  async login(email, password) {
    const data = await gql(
      `mutation Login($email: String!, $password: String!) {
        login(email: $email, password: $password) {
          accessToken
          user { id fullName role department { name } }
        }
      }`,
      { email, password }
    );
    setToken(data.login.accessToken);
    return data.login.user;
  },

  async me() {
    const data = await gql(
      `query Me {
        me {
          id email fullName role avatarColor initials department { id name }
          jobTitle phoneNumber photoBase64 profileCompletedAt requestedRole
          notificationsLastSeenAt
        }
      }`
    );
    return data.me;
  },

  /**
   * Self-service: department/job title/phone/photo. `input.photoBase64`
   * is the resized/compressed payload from resizeImageToBase64() in
   * my-profile.html — this method doesn't touch the image itself.
   * Returns the fields my-profile.html needs to redraw itself after a
   * save, including profileCompletedAt (so the page can tell whether
   * onboarding just finished and redirect).
   */
  async updateMyProfile(input) {
    const data = await gql(
      `mutation($input: UpdateMyProfileInput!) {
        updateMyProfile(input: $input) {
          id department { id name } jobTitle phoneNumber photoBase64 profileCompletedAt
        }
      }`,
      { input }
    );
    return data.updateMyProfile;
  },

  /** Pass null to withdraw a pending request. Never changes what's
   * actually enforced — see backend/app/graphql/mutations.py's
   * request_role_change docstring. */
  async requestRoleChange(role) {
    const data = await gql(
      `mutation($role: Role) { requestRoleChange(role: $role) { role requestedRole } }`,
      { role: role || null }
    );
    return data.requestRoleChange;
  },

  async dashboardStats() {
    const data = await gql(
      `query Stats {
        dashboardStats { pending inProgress overdue completed }
      }`
    );
    return data.dashboardStats;
  },

  async departments() {
    const data = await gql(`query Departments { departments { id name } }`);
    return data.departments;
  },

  async users(departmentId) {
    const data = await gql(
      `query Users($departmentId: ID) {
        users(departmentId: $departmentId) { id fullName initials avatarColor role }
      }`,
      { departmentId: departmentId || null }
    );
    return data.users;
  },

  /**
   * Total count for the "My Tasks" sidebar badge. Deliberately excludes
   * DONE, since a finished task isn't something you still need to act
   * on — matches the "things still on your plate" meaning of the badge,
   * not the department-wide `tasks(filter: null)` total (which includes
   * everything ever completed). Non-admins get this pre-scoped to their
   * own department by the `tasks` resolver itself.
   */
  async myTasksBadgeCount() {
    const data = await gql(
      `query MyTasksBadge {
        tasks(filter: { excludeDone: true }, page: { first: 1 }) { totalCount }
      }`
    );
    return data.tasks.totalCount;
  },

  async tasks(filter) {
    const data = await gql(
      `query Tasks($filter: TaskFilterInput) {
        tasks(filter: $filter, page: { first: 50 }) {
          totalCount
          edges {
            node {
              id ticketNo title status priority dueAt isOverdue
              department { name }
              assignee { fullName initials avatarColor }
              reporter { fullName initials avatarColor }
            }
          }
        }
      }`,
      { filter: filter || null }
    );
    return data.tasks;
  },

  /**
   * Lean projection for board.html's Kanban view — decoupled from
   * `Api.tasks()`'s heavier per-row shape (department/reporter, hardcoded
   * page size) since the board just needs enough per card to render it
   * and doesn't paginate. `first: 200` is a flat ceiling, not real
   * pagination — a kanban board has no obvious "page 2" UX, so any single
   * org with more than 200 open+closed tasks in view would silently miss
   * some. Acceptable for this prototype's scale.
   */
  async boardTasks() {
    const data = await gql(
      `query BoardTasks {
        tasks(page: { first: 200 }) {
          edges {
            node {
              id ticketNo title status priority
              assignee { id fullName initials avatarColor }
            }
          }
        }
      }`
    );
    return data.tasks.edges.map(e => e.node);
  },

  /**
   * Every one of the given user's tasks that have a due date — powers
   * calendar.html's Month/Week grids. Fetched once per page load and
   * grouped by date client-side (same "fetch everything, group in JS"
   * approach board.html already uses for its status columns) rather
   * than re-querying per month/week navigation. Tasks with no dueAt are
   * still returned here (the filter doesn't exclude them) since a task
   * genuinely has no calendar date to place it on — the caller is
   * expected to skip those when grouping, not this method.
   */
  async myCalendarTasks(userId) {
    const data = await gql(
      `query MyCalendarTasks($assigneeId: ID) {
        tasks(filter: { assigneeId: $assigneeId }, page: { first: 300 }) {
          edges {
            node { id ticketNo title status priority dueAt durationMinutes }
          }
        }
      }`,
      { assigneeId: userId }
    );
    return data.tasks.edges.map(e => e.node);
  },

  /**
   * Powers timeline.html's Gantt view. No filter argument, same as
   * boardTasks() — the tasks() resolver's own RBAC scoping already
   * gives Admins everything and everyone else their department plus
   * anything they're personally assigned/reporting, which is exactly
   * the "team-wide for managers/members, org-wide for admins" scope
   * the timeline needs. Fetched once and grouped/laid out client-side.
   */
  async timelineTasks() {
    const data = await gql(
      `query TimelineTasks {
        tasks(page: { first: 300 }) {
          edges {
            node {
              id ticketNo title status priority dueAt startDate durationMinutes createdAt
              assignee { id fullName initials avatarColor }
              department { id name }
            }
          }
        }
      }`
    );
    return data.tasks.edges.map(e => e.node);
  },

  /**
   * Powers the board's inline assignee picker: every candidate assignee
   * plus their current platform-wide open-ticket count, so you can see
   * who's already busy before reassigning. `departmentId` only narrows
   * which people are returned as candidates — the workload count itself
   * is always org-wide (see queries.py's user_workloads resolver).
   */
  async userWorkloads(departmentId) {
    const data = await gql(
      `query UserWorkloads($departmentId: ID) {
        userWorkloads(departmentId: $departmentId) {
          openTaskCount
          user { id fullName initials avatarColor }
        }
      }`,
      { departmentId: departmentId || null }
    );
    return data.userWorkloads;
  },

  async task(id) {
    const data = await gql(
      `query Task($id: ID!) {
        task(id: $id) {
          id ticketNo title description status priority dueAt isOverdue createdAt
          department { name }
          assignee { id fullName initials avatarColor }
          reporter { id fullName initials avatarColor }
          comments { id body createdAt author { fullName initials avatarColor } }
        }
      }`,
      { id }
    );
    return data.task;
  },

  async createTask(input) {
    const data = await gql(
      `mutation CreateTask($input: CreateTaskInput!) {
        createTask(input: $input) { id ticketNo }
      }`,
      { input }
    );
    return data.createTask;
  },

  async changeTaskStatus(id, status) {
    const data = await gql(
      `mutation($id: ID!, $status: TaskStatus!) {
        changeTaskStatus(id: $id, status: $status) { id status }
      }`,
      { id, status }
    );
    return data.changeTaskStatus;
  },

  async assignTask(id, assigneeId) {
    const data = await gql(
      `mutation($id: ID!, $assigneeId: ID) {
        assignTask(id: $id, assigneeId: $assigneeId) { id assignee { id fullName } }
      }`,
      { id, assigneeId: assigneeId || null }
    );
    return data.assignTask;
  },

  /**
   * Partial-success: some selected tasks may not be editable by the
   * caller (e.g. a cross-department task a Manager can view but not
   * edit) — those come back in `failures`, not as a thrown error, so a
   * mostly-valid bulk action doesn't get blocked by one stray row.
   */
  async bulkUpdateTasks(ids, input) {
    const data = await gql(
      `mutation($ids: [ID!]!, $input: BulkTaskUpdateInput!) {
        bulkUpdateTasks(ids: $ids, input: $input) {
          successCount
          failures { id reason }
          tasks { id status priority assignee { id fullName initials avatarColor } }
        }
      }`,
      { ids, input }
    );
    return data.bulkUpdateTasks;
  },

  async addComment(taskId, body) {
    const data = await gql(
      `mutation AddComment($taskId: ID!, $body: String!) {
        addComment(taskId: $taskId, body: $body) {
          id body createdAt author { fullName initials avatarColor }
        }
      }`,
      { taskId, body }
    );
    return data.addComment;
  },

  /**
   * Gated server-side with permission_classes=[IsManagerOrAdmin], not
   * IsAdmin — Managers get their own department only (a strict match,
   * not the OR-with-own-tasks scope dashboardStats/tasks use), Admins
   * get every department. `start`/`end` are ISO datetime strings; `end`
   * is exclusive, so callers building a "through today" range need to
   * pass midnight of the day *after*.
   */
  async kpiReport(start, end) {
    const data = await gql(
      `query KpiReport($start: DateTime!, $end: DateTime!) {
        kpiReport(start: $start, end: $end) {
          departments { departmentId departmentName avgResolutionSeconds completedCount }
          fastestResolvers { userId fullName avatarColor initials avgResolutionSeconds closedCount }
          mostTicketsClosed { userId fullName avatarColor initials avgResolutionSeconds closedCount }
        }
      }`,
      { start, end }
    );
    return data.kpiReport;
  },

  // --- Admin panel (all resolvers below are gated server-side with
  // permission_classes=[IsAdmin] — a non-admin token gets a FORBIDDEN
  // GraphQL error, not a silently empty result) ---

  /** Full staff directory with every admin-editable field, as opposed to
   * the slim Api.users() used by the assignee dropdown elsewhere. */
  async adminUsers() {
    const data = await gql(
      `query AdminUsers {
        users {
          id fullName email role isActive jobTitle phoneNumber
          notifyEmail notifySms initials avatarColor
          department { id name }
          branch { id name businessUnit { id name } }
        }
      }`
    );
    return data.users;
  },

  async businessUnits() {
    const data = await gql(
      `query BusinessUnits {
        businessUnits { id name branches { id name isActive businessUnit { id name } } }
      }`
    );
    return data.businessUnits;
  },

  /**
   * Powers the Org Structure mind map (admin.html). Distinct from
   * users() (used by Create Task's assignee list, which only needs
   * avatar fields) — the mind map also needs each person's department
   * *and* branch to synthesize the Business Unit -> Branch ->
   * Department -> Member tree client-side (Branch and Department are
   * independent attributes on User, not nested in the schema itself).
   */
  async orgMembers() {
    const data = await gql(
      `query OrgMembers {
        users {
          id fullName initials avatarColor role jobTitle
          department { id name }
          branch { id name businessUnit { id name } }
        }
      }`
    );
    return data.users;
  },

  /** Topbar search's "Tickets" half — TaskFilterInput.search is a plain
   * ilike on title, already used server-side, just never wired to a UI
   * before now. Small page (6) — this is a live-typing dropdown, not a
   * results page. */
  async searchTasks(query) {
    const data = await gql(
      `query SearchTasks($q: String!) {
        tasks(filter: { search: $q }, page: { first: 6 }) {
          edges { node { id ticketNo title status priority } }
        }
      }`,
      { q: query }
    );
    return data.tasks.edges.map(e => e.node);
  },

  /** Topbar search's "People" half — no backend search filter exists
   * for users (unlike tasks), and at ~40 staff there's no need for
   * one: reuse orgMembers() and filter client-side. */
  async searchPeople(query) {
    const members = await Api.orgMembers();
    const q = query.toLowerCase();
    return members.filter(u => u.fullName.toLowerCase().includes(q)).slice(0, 6);
  },

  /** Topbar notification bell — see Notification's docstring in
   * backend/app/graphql/types.py for why there's no separate "unread"
   * field on each row; the caller compares createdAt against
   * me.notificationsLastSeenAt itself (see initNotificationBell()). */
  async myNotifications() {
    const data = await gql(
      `query MyNotifications {
        myNotifications { id trigger createdAt task { id ticketNo title } }
      }`
    );
    return data.myNotifications;
  },

  async markNotificationsSeen() {
    const data = await gql(`mutation { markNotificationsSeen { id notificationsLastSeenAt } }`);
    return data.markNotificationsSeen;
  },

  async createDepartment(name) {
    const data = await gql(`mutation($name: String!) { createDepartment(name: $name) { id name } }`, { name });
    return data.createDepartment;
  },

  async createBusinessUnit(name) {
    const data = await gql(`mutation($name: String!) { createBusinessUnit(name: $name) { id name } }`, { name });
    return data.createBusinessUnit;
  },

  async createBranch(input) {
    const data = await gql(
      `mutation($input: CreateBranchInput!) {
        createBranch(input: $input) { id name isActive businessUnit { id name } }
      }`,
      { input }
    );
    return data.createBranch;
  },

  async updateBranch(id, input) {
    const data = await gql(
      `mutation($id: ID!, $input: UpdateBranchInput!) {
        updateBranch(id: $id, input: $input) { id name isActive businessUnit { id name } }
      }`,
      { id, input }
    );
    return data.updateBranch;
  },

  async createUser(input) {
    const data = await gql(
      `mutation($input: CreateUserInput!) {
        createUser(input: $input) { id fullName email role isActive }
      }`,
      { input }
    );
    return data.createUser;
  },

  async updateUser(id, input) {
    const data = await gql(
      `mutation($id: ID!, $input: UpdateUserInput!) {
        updateUser(id: $id, input: $input) {
          id fullName email role isActive jobTitle phoneNumber notifyEmail notifySms
          department { id name }
          branch { id name businessUnit { id name } }
        }
      }`,
      { id, input }
    );
    return data.updateUser;
  },

  async resetUserPassword(id, newPassword) {
    const data = await gql(
      `mutation($id: ID!, $newPassword: String!) { resetUserPassword(id: $id, newPassword: $newPassword) }`,
      { id, newPassword }
    );
    return data.resetUserPassword;
  },

  async pendingRoleRequests() {
    const data = await gql(
      `query { pendingRoleRequests {
        id fullName email role requestedRole initials avatarColor department { name }
      } }`
    );
    return data.pendingRoleRequests;
  },

  async respondToRoleRequest(userId, approve) {
    const data = await gql(
      `mutation($userId: ID!, $approve: Boolean!) {
        respondToRoleRequest(userId: $userId, approve: $approve) { id role requestedRole }
      }`,
      { userId, approve }
    );
    return data.respondToRoleRequest;
  },
};

// --- Shared render helpers (status/priority -> the CSS classes already
// defined in styles.css, so dynamically-rendered rows look identical to
// the original static mockups) ---

const STATUS_CLASS = { PENDING: "pending", IN_PROGRESS: "progress", REVIEW: "review", DONE: "done" };
const STATUS_LABEL = { PENDING: "Pending", IN_PROGRESS: "In Progress", REVIEW: "Review", DONE: "Done" };
const PRIORITY_CLASS = { LOW: "priority-low", MEDIUM: "priority-medium", HIGH: "priority-high", URGENT: "priority-urgent" };
const PRIORITY_LABEL = { LOW: "Low", MEDIUM: "Medium", HIGH: "High", URGENT: "Urgent" };

function formatDueDate(dueAt, isOverdue) {
  if (!dueAt) return "<span class=\"due-date\">No due date</span>";
  const d = new Date(dueAt);
  const label = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return isOverdue
    ? `<span class="due-date overdue">${label} · Overdue</span>`
    : `<span class="due-date">${label}</span>`;
}

function avatarInitials(person) {
  return person ? person.initials : "?";
}

function avatarColor(person) {
  return person ? person.avatarColor : "var(--neutral)";
}

/**
 * Fills the sidebar's #sidebar-avatar chip for the logged-in user — real
 * photo if they've uploaded one (me.photoBase64, set via my-profile.html),
 * colored initials otherwise. Shared across every page with a sidebar so
 * "upload a photo" actually shows up everywhere you navigate, not just on
 * the profile page itself.
 */
function setSidebarAvatar(me) {
  const el = document.getElementById("sidebar-avatar");
  if (!el) return;
  if (me.photoBase64) {
    el.style.background = "transparent";
    el.innerHTML = `<img src="data:image/jpeg;base64,${me.photoBase64}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block" alt="" />`;
  } else {
    el.style.background = me.avatarColor;
    el.textContent = me.initials;
  }
}

/** Seconds -> "2d 4h" / "3h 15m" / "42m" for the KPI panel's resolution-time
 * displays. Drops to the next-smaller unit rather than showing both when
 * the larger unit dominates (e.g. "2d 4h", not "2d 4h 12m") to keep the
 * table scannable. */
function formatDuration(seconds) {
  if (seconds == null) return "—";
  const totalMinutes = Math.round(seconds / 60);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

// Must run after `const Api` above — both call Api.* immediately (not
// just from a later event handler), so calling them any earlier in
// this file hits Api's temporal dead zone. Each no-ops on a page
// without the relevant markup (see the guards inside both).
initTopbarSearch();
initNotificationBell();
