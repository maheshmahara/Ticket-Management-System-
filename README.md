# HNBG Task Management System

Hokkaido Nepal Business Group (HNBG) enterprise Task Management System.
This repository holds both the **UI design phase** deliverables (static
HTML/CSS prototypes, a production-ready React component, brand assets) and
the **backend design/scaffold** (FastAPI + GraphQL + PostgreSQL) — organized
so it can be dropped straight into a git repository and picked up by CI/CD.

> Status: **Frontend design locked.** `prototypes/` and `components/`
> represent the approved visual direction — treat them as reference
> implementations, don't silently redesign them. `backend/` is an active
> design/scaffold, not yet implemented (see its README for what's stubbed).

---

## What's in here

| Folder | Purpose |
|---|---|
| [`prototypes/web/`](./prototypes/web) | Clickable desktop web prototype (login → dashboard → tasks → task detail → create task) |
| [`prototypes/mobile/`](./prototypes/mobile) | iOS-style mobile app screens (Dashboard, My Tasks) in a phone frame |
| [`components/react/`](./components/react) | Standalone, production-ready React + Tailwind `CreateTaskForm` component, plus a browser preview |
| [`backend/`](./backend) | FastAPI + Strawberry GraphQL + PostgreSQL API scaffold (models, GraphQL schema, RBAC, Docker Compose) |
| [`assets/branding/`](./assets/branding) | Source HNBG logo files (original, transparent, cropped mark) |
| [`docs/`](./docs) | Design system, component inventory, backend architecture, structure notes, changelog |
| `.github/workflows/` | Starter CI workflow for linting/building/deploying the prototype as a static site |

## Quick start (viewing the prototypes)

No build step is required for `prototypes/` — they're plain HTML/CSS.

```bash
# from the repo root
cd prototypes/web
python3 -m http.server 8000
# open http://localhost:8000/index.html
```

For the React component preview:

```bash
cd components/react
python3 -m http.server 8000
# open http://localhost:8000/create-task-preview.html
```

(The preview loads React, Tailwind, and Lucide from a CDN and transpiles
`CreateTaskForm.jsx` in-browser — no npm install needed just to look at it.)

## Using the React component in a real app

`components/react/CreateTaskForm.jsx` has no build-tool dependencies beyond
Tailwind CSS and `lucide-react`. Drop it into any React app:

```bash
npm install lucide-react
```

```jsx
import CreateTaskForm from "./CreateTaskForm";

<CreateTaskForm
  onSubmit={(task) => saveTask(task)}
  onCancel={() => setModalOpen(false)}
/>
```

## Design system

See [`docs/DESIGN_SYSTEM.md`](./docs/DESIGN_SYSTEM.md) for the full color
palette, typography, spacing, and border tokens (all sourced from the HNBG
logo's blue/red identity).

## Backend

See [`docs/BACKEND_ARCHITECTURE.md`](./docs/BACKEND_ARCHITECTURE.md) for the
full design: ERD, GraphQL schema, RBAC matrix, and rationale. The scaffold
in [`backend/`](./backend) — models, GraphQL types/queries/mutations, auth
scaffolding, Docker Compose — has been verified to import and build a valid
GraphQL schema; resolver bodies are marked `TODO`/`NotImplementedError`
where real business logic (DB queries, JWT issuing) still needs writing.

## Next steps (suggested pipeline)

1. **Frontend design** — *(this repo, locked)*
2. **Backend implementation** — fill in the `TODO`s in `backend/app/graphql/`
   and `backend/app/services/`, write the initial Alembic migration, add
   `tests/`.
3. **Component library** — port `prototypes/` screens into real framework
   components (React/Vue/etc.), using `components/react/CreateTaskForm.jsx`
   as the pattern to follow for the rest of the form/UI components.
4. **API integration** — connect the frontend to the GraphQL API for auth,
   tasks CRUD, and user/assignee data.
5. **CI/CD** — the `.github/workflows/deploy.yml` starter lints and deploys
   the static prototype; extend it with a backend job (`pytest`, migration
   dry-run, Docker build) once `backend/` has real code in it.

## License / ownership

Internal design asset for Hokkaido Nepal Business Group. Not for external
distribution.
