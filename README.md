# HNBG Task Management System — Design & Prototype

Hokkaido Nepal Business Group (HNBG) enterprise Task Management System.
This repository holds the **UI design phase** deliverables: static HTML/CSS
prototypes (web + mobile), a production-ready React component, brand assets,
and supporting documentation — organized so it can be dropped straight into
a git repository and picked up by a build/CI pipeline for the next phase
(frontend app development).

> Status: **Design locked.** These prototypes represent the approved visual
> direction. Treat `prototypes/` and `components/` as reference implementations
> when building the real application — do not silently redesign them.

---

## What's in here

| Folder | Purpose |
|---|---|
| [`prototypes/web/`](./prototypes/web) | Clickable desktop web prototype (login → dashboard → tasks → task detail → create task) |
| [`prototypes/mobile/`](./prototypes/mobile) | iOS-style mobile app screens (Dashboard, My Tasks) in a phone frame |
| [`components/react/`](./components/react) | Standalone, production-ready React + Tailwind `CreateTaskForm` component, plus a browser preview |
| [`assets/branding/`](./assets/branding) | Source HNBG logo files (original, transparent, cropped mark) |
| [`docs/`](./docs) | Design system reference, component inventory, folder structure notes, changelog |
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

## Next steps (suggested pipeline)

1. **Design** — *(this repo, locked)*
2. **Component library** — port `prototypes/` screens into real framework
   components (React/Vue/etc.), using `components/react/CreateTaskForm.jsx`
   as the pattern to follow for the rest of the form/UI components.
3. **API integration** — wire up auth, tasks CRUD, and user/assignee data.
4. **CI/CD** — the `.github/workflows/deploy.yml` starter lints and deploys
   the static prototype; extend it once the real app build exists (test →
   build → deploy stages).

## License / ownership

Internal design asset for Hokkaido Nepal Business Group. Not for external
distribution.
