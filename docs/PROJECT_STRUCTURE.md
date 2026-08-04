# Project Structure

```
hnbg-task-management/
├── README.md                     # Start here
├── package.json                  # Placeholder scripts (lint/serve); no framework deps yet
├── .gitignore
├── .github/
│   └── workflows/
│       └── deploy.yml            # CI starter: lint prototype HTML/CSS, deploy as static site
├── docs/
│   ├── DESIGN_SYSTEM.md          # Color tokens, typography, spacing, gradient-border pattern
│   ├── COMPONENTS.md             # Component-by-component inventory with class names
│   ├── PROJECT_STRUCTURE.md      # This file
│   └── CHANGELOG.md              # Chronological log of design decisions/iterations
├── assets/
│   └── branding/
│       ├── hnbg-logo-original.jpg        # Source logo (white bg, with tagline)
│       ├── hnbg-logo-transparent.png     # Background removed, tagline still baked in
│       └── hnbg-mark.png                 # Cropped monogram only — used in the UI
├── prototypes/
│   ├── web/                      # Desktop web prototype (open index.html)
│   │   ├── index.html            # Login
│   │   ├── dashboard.html        # First page after login
│   │   ├── tasks.html            # Task list / table view
│   │   ├── task-detail.html      # Single task detail
│   │   ├── create-task.html      # Apple-style create task form
│   │   ├── styles.css            # Shared design tokens + all component styles
│   │   └── hnbg-mark.png         # Logo asset referenced by the pages above
│   └── mobile/                   # iOS-style mobile prototype
│       ├── mobile-app.html       # Dashboard + My Tasks phone-frame screens
│       └── mobile.css            # Mobile-only styles (layered on prototypes/web/styles.css tokens)
└── components/
    └── react/
        ├── CreateTaskForm.jsx        # Framework-agnostic-ish, drop into any React app
        └── create-task-preview.html  # Zero-build browser preview of the component
```

## Why this layout

- **`prototypes/` vs `components/`** — `prototypes/` is throwaway-safe: plain
  HTML/CSS clickable mockups meant to communicate the design, not to be
  imported into an app. `components/` holds code meant to actually be reused
  ("production-ready" per the original request).
- **Web and mobile are siblings, not nested** — they share design tokens
  (colors, radii, shadows) defined once in `prototypes/web/styles.css`, which
  `prototypes/mobile/mobile.css` assumes is also loaded (see the `<link>`
  order in `mobile-app.html`).
- **`assets/branding/` is the source of truth for the logo** — UI code
  should only ever reference `hnbg-mark.png` (the cropped, backgroundless
  monogram). The other two files exist for provenance / re-export if the
  mark needs to be re-cropped later.
- **Docs are separated by concern** (design system vs. component inventory
  vs. structure vs. history) so each can be updated independently as the
  project moves from design into implementation.

## Where things are NOT yet

- No task/data backend, no auth implementation — these are static mockups
  with hardcoded sample data.
- No design tool source files (Figma/Sketch) are included; this repo *is*
  the design source of truth going forward (HTML/CSS + the React component).
- Board view (mentioned in the task list's view toggle) is not yet built.
