/**
 * Org Structure mind map — admin.html's "Mind Map" sub-view of the Org
 * Structure tab. Self-contained: owns its own data fetch (Api.businessUnits()
 * + Api.orgMembers()), tree-building, radial layout, and SVG rendering,
 * the same "page module owns its own state" split calendar.html and
 * timeline.html already use rather than threading state through admin.js.
 *
 * Tree shape (synthesized client-side — Branch and Department are
 * independent attributes on User, not nested in the schema):
 *   root (HNBG) -> Business Unit -> Branch -> Department-group -> Member
 *
 * A Department that has people at two different branches legitimately
 * gets two separate nodes (one per branch) — that's the accurate
 * picture of "who's where", not a duplication bug.
 *
 * Layout: a standard collapsible radial tidy-tree. Each node's angular
 * span is proportional to its *visible* leaf-descendant count (a
 * collapsed node counts as one leaf, regardless of how many real
 * people are hidden underneath it) within its parent's own span; radius
 * is fixed per node *type* (not raw tree depth) so the synthetic
 * "Unassigned" branch-equivalent node — attached directly under root
 * for branchless users — still renders on the same ring as real
 * Branches, and its department-groups still land on the Department
 * ring, exactly like a normal Business Unit's branches would.
 */

const ORG_MAP_NS = 'http://www.w3.org/2000/svg';
const ORG_MAP_RADIUS = { root: 0, bu: 130, branch: 250, dept: 370, member: 480 };

let orgTreeRoot = null;

async function renderOrgMindMap() {
  const loadingEl = document.getElementById('org-mindmap-loading');
  const svgEl = document.getElementById('org-mindmap-svg');
  loadingEl.style.display = '';
  loadingEl.textContent = 'Loading the org structure…';
  svgEl.style.display = 'none';

  try {
    const [businessUnits, orgMembers] = await Promise.all([Api.businessUnits(), Api.orgMembers()]);
    orgTreeRoot = buildOrgTree(businessUnits, orgMembers);
    loadingEl.style.display = 'none';
    svgEl.style.display = '';
    layoutAndRenderOrgTree();
  } catch (err) {
    if (err.code === 'FORBIDDEN' || err.message.includes('logged in')) {
      logout();
      return;
    }
    loadingEl.style.display = '';
    loadingEl.innerHTML = `<span style="color:var(--danger)">Couldn't load the org structure: ${err.message}</span>`;
  }
}

function buildOrgTree(businessUnits, orgMembers) {
  const root = { id: 'root', type: 'root', label: 'HNBG', expanded: true, children: [] };

  for (const bu of businessUnits) {
    const buNode = { id: `bu:${bu.id}`, type: 'bu', label: bu.name, expanded: true, children: [] };
    for (const branch of bu.branches) {
      const branchMembers = orgMembers.filter((u) => u.branch && u.branch.id === branch.id);
      // Branches start collapsed (unlike root/bu) — showing every
      // branch's department groups at once, for every branch, is what
      // caused the initial clutter this was tuned against. Root + BU +
      // Branch pill labels are the entire default-visible set (16
      // nodes); a branch's departments only appear once it's clicked.
      const branchNode = { id: `branch:${branch.id}`, type: 'branch', label: branch.name, expanded: false, children: [] };
      branchNode.children = groupMembersByDepartment(branchMembers, branch.id);
      buNode.children.push(branchNode);
    }
    root.children.push(buNode);
  }

  // Branchless users have no Business Unit either — a root-level
  // sibling of the real Business Units, only created if any exist.
  const unassignedMembers = orgMembers.filter((u) => !u.branch);
  if (unassignedMembers.length > 0) {
    const unassignedNode = { id: 'branch:unassigned', type: 'branch', label: 'Unassigned', expanded: false, children: [] };
    unassignedNode.children = groupMembersByDepartment(unassignedMembers, 'unassigned');
    root.children.push(unassignedNode);
  }

  return root;
}

function groupMembersByDepartment(members, branchKey) {
  const groups = new Map();
  for (const u of members) {
    const key = u.department ? u.department.id : 'none';
    if (!groups.has(key)) {
      groups.set(key, {
        id: `dept:${branchKey}:${key}`,
        type: 'dept',
        label: u.department ? u.department.name : 'No Department',
        departmentId: u.department ? u.department.id : null,
        expanded: false,
        children: [],
      });
    }
    groups.get(key).children.push({
      id: `member:${branchKey}:${u.id}`,
      type: 'member',
      label: u.fullName,
      user: u,
      departmentId: u.department ? u.department.id : null,
      expanded: false,
      children: [],
    });
  }
  return [...groups.values()].sort((a, b) => a.label.localeCompare(b.label));
}

/** A collapsed node (or a true leaf) counts as exactly one visible leaf,
 * regardless of how many real descendants are hidden underneath it —
 * this is what keeps a collapsed Branch from eating a huge angular
 * slice just because it happens to have 8 real employees underneath. */
function visibleLeafCount(node) {
  if (node.children.length === 0 || !node.expanded) return 1;
  return node.children.reduce((sum, c) => sum + visibleLeafCount(c), 0);
}

function layoutOrgTree(node, angleStart, angleEnd, visibleNodes, visibleLinks, parent) {
  node.angle = (angleStart + angleEnd) / 2;
  const r = ORG_MAP_RADIUS[node.type];
  node.x = node.type === 'root' ? 0 : r * Math.cos(node.angle);
  node.y = node.type === 'root' ? 0 : r * Math.sin(node.angle);
  visibleNodes.push(node);
  if (parent) visibleLinks.push([parent, node]);

  if (node.children.length === 0 || !node.expanded) return;
  let cursor = angleStart;
  const span = angleEnd - angleStart;
  const total = visibleLeafCount(node);
  for (const child of node.children) {
    const childSpan = span * (visibleLeafCount(child) / total);
    layoutOrgTree(child, cursor, cursor + childSpan, visibleNodes, visibleLinks, node);
    cursor += childSpan;
  }
}

function layoutAndRenderOrgTree() {
  const visibleNodes = [];
  const visibleLinks = [];
  // Starts at -90° (top) with a tiny epsilon off the full 360° so a
  // fully-expanded root's first and last child don't land exactly on
  // top of each other.
  layoutOrgTree(orgTreeRoot, -Math.PI / 2 + 0.001, -Math.PI / 2 + Math.PI * 2 - 0.001, visibleNodes, visibleLinks, null);

  const svg = document.getElementById('org-mindmap-svg');
  svg.innerHTML = '';

  const maxR = Math.max(...visibleNodes.map((n) => ORG_MAP_RADIUS[n.type])) + 160;
  const size = maxR * 2;
  svg.setAttribute('viewBox', `${-maxR} ${-maxR} ${size} ${size}`);
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);

  const linksGroup = document.createElementNS(ORG_MAP_NS, 'g');
  svg.appendChild(linksGroup);
  for (const [parent, child] of visibleLinks) {
    const path = document.createElementNS(ORG_MAP_NS, 'path');
    // Control point pulled toward center — gives the links a soft
    // inward curve (the "mind map" look) rather than straight spokes,
    // with nothing fancier than a scaled midpoint.
    const cx = (parent.x + child.x) * 0.3;
    const cy = (parent.y + child.y) * 0.3;
    path.setAttribute('d', `M ${parent.x} ${parent.y} Q ${cx} ${cy} ${child.x} ${child.y}`);
    path.setAttribute('class', 'org-map-link');
    linksGroup.appendChild(path);
  }

  for (const node of visibleNodes) {
    if (node.type === 'root') renderOrgRootNode(svg, node);
    else if (node.type === 'member') renderOrgMemberNode(svg, node);
    else renderOrgPillNode(svg, node);
  }
}

function renderOrgRootNode(svg, node) {
  const g = document.createElementNS(ORG_MAP_NS, 'g');
  g.setAttribute('transform', `translate(${node.x},${node.y})`);
  const circle = document.createElementNS(ORG_MAP_NS, 'circle');
  circle.setAttribute('r', '38');
  circle.setAttribute('class', 'org-map-root-circle');
  g.appendChild(circle);
  const text = document.createElementNS(ORG_MAP_NS, 'text');
  text.setAttribute('class', 'org-map-root-label');
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('dominant-baseline', 'central');
  text.textContent = node.label;
  g.appendChild(text);
  svg.appendChild(g);
}

/** Business Unit / Branch / Department nodes — text-sized rounded pills.
 * Two-pass: append the text first, measure it with getBBox() (only
 * possible once it's actually in the live SVG DOM), then insert a
 * background rect behind it sized to the measured width. */
function renderOrgPillNode(svg, node) {
  const g = document.createElementNS(ORG_MAP_NS, 'g');
  g.setAttribute('class', `org-map-node org-map-node-${node.type}`);
  g.setAttribute('transform', `translate(${node.x},${node.y})`);

  const text = document.createElementNS(ORG_MAP_NS, 'text');
  text.setAttribute('class', 'org-map-pill-label');
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('dominant-baseline', 'central');
  text.textContent = node.type === 'dept' ? `${node.label} (${node.children.length})` : node.label;
  g.appendChild(text);
  svg.appendChild(g);

  const bbox = text.getBBox();
  const paddingX = 14;
  const paddingY = 8;
  const rect = document.createElementNS(ORG_MAP_NS, 'rect');
  rect.setAttribute('x', bbox.x - paddingX);
  rect.setAttribute('y', bbox.y - paddingY);
  rect.setAttribute('width', bbox.width + paddingX * 2);
  rect.setAttribute('height', bbox.height + paddingY * 2);
  rect.setAttribute('rx', (bbox.height + paddingY * 2) / 2);
  rect.setAttribute('class', 'org-map-pill-rect');
  g.insertBefore(rect, text);

  const canExpand = node.children.length > 0;
  if (canExpand) {
    g.style.cursor = 'pointer';
    g.addEventListener('click', () => {
      node.expanded = !node.expanded;
      layoutAndRenderOrgTree();
    });
  }

  // Department nodes double as an assignment target — a small ticket
  // icon offset from the pill, its own click target so it doesn't
  // collide with the pill's expand/collapse click. Skipped for the
  // "No Department" bucket (departmentId is null there) — there's no
  // real department to hand a ticket to, so no assignment affordance.
  if (node.type === 'dept' && node.departmentId) {
    const iconR = 10;
    const iconOffsetX = bbox.width / 2 + paddingX + iconR + 4;
    const iconGroup = document.createElementNS(ORG_MAP_NS, 'g');
    iconGroup.setAttribute('class', 'org-map-ticket-btn');
    iconGroup.setAttribute('transform', `translate(${iconOffsetX},0)`);
    iconGroup.style.cursor = 'pointer';

    const iconCircle = document.createElementNS(ORG_MAP_NS, 'circle');
    iconCircle.setAttribute('r', String(iconR));
    iconGroup.appendChild(iconCircle);

    const iconPath = document.createElementNS(ORG_MAP_NS, 'path');
    iconPath.setAttribute('d', 'M-4,-1 L4,-1 M0,-4 L0,3');
    iconPath.setAttribute('class', 'org-map-ticket-icon-glyph');
    iconGroup.appendChild(iconPath);

    iconGroup.addEventListener('click', (e) => {
      e.stopPropagation();
      navigateToAssign(node.departmentId, null);
    });
    g.appendChild(iconGroup);
  }
}

function renderOrgMemberNode(svg, node) {
  const g = document.createElementNS(ORG_MAP_NS, 'g');
  g.setAttribute('class', 'org-map-node org-map-node-member');
  g.setAttribute('transform', `translate(${node.x},${node.y})`);
  g.style.cursor = 'pointer';

  const circle = document.createElementNS(ORG_MAP_NS, 'circle');
  circle.setAttribute('r', '15');
  circle.setAttribute('fill', node.user.avatarColor || 'var(--neutral)');
  g.appendChild(circle);

  const initials = document.createElementNS(ORG_MAP_NS, 'text');
  initials.setAttribute('class', 'org-map-member-initials');
  initials.setAttribute('text-anchor', 'middle');
  initials.setAttribute('dominant-baseline', 'central');
  initials.textContent = node.user.initials || '?';
  g.appendChild(initials);

  const name = document.createElementNS(ORG_MAP_NS, 'text');
  name.setAttribute('class', 'org-map-member-name');
  name.setAttribute('text-anchor', 'middle');
  name.setAttribute('y', '30');
  name.textContent = node.user.fullName;
  g.appendChild(name);

  g.addEventListener('click', () => navigateToAssign(node.departmentId, node.user.id));
  svg.appendChild(g);
}

function navigateToAssign(departmentId, assigneeId) {
  const params = new URLSearchParams();
  if (departmentId) params.set('departmentId', departmentId);
  if (assigneeId) params.set('assigneeId', assigneeId);
  location.href = `create-task.html?${params.toString()}`;
}
