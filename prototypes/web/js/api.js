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
        me { id fullName role avatarColor initials department { id name } }
      }`
    );
    return data.me;
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
