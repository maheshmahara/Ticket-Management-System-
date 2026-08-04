# Org structure & staff seed data

The real HNBG staff roster (39 people) was provided as a flat spreadsheet
with six columns: Full Name, Branch, Email, Contact, Department, Business
Unit. This doc records how that got mapped onto the backend schema, and
the judgment calls made along the way, so anyone updating the roster
later understands the intent instead of guessing.

Source data lives at [`../backend/seed_data/staff.json`](../backend/seed_data/staff.json).
Load it with `python backend/scripts/seed_staff.py` (idempotent — safe to
re-run).

## Why the schema changed

The original schema (see `BACKEND_ARCHITECTURE.md`) only had a flat
`Department` (Engineering, Product, Design, ...) — fine for a generic
template, but the real org has three levels:

```
Business Unit  (Overall / Restaurants / Trading)
  └── Branch    (Headoffice, All Restaurants, Hokkaido Sora, ...)
        └── User (with a job title + canonical department)
```

So two new models were added — `BusinessUnit` and `Branch` — and `User`
gained `branch_id` and `job_title`. `Department` was kept as-is rather
than nested under Branch, because in the spreadsheet it behaves less like
"which office you sit in" and more like "which function you do" — see
next section.

## Department vs. job title — the tricky part

For head-office and trading staff, the sheet's "Department" column is a
real functional department: `finance`, `hr`, `marketing`, `admin`,
`inventory and merchandise`. For restaurant staff, the same column is
actually a **job title**: `chef`, `manager`, `gm`, `md`, `driver
delivery`, `manager construction and purchase` — restaurants don't have
"departments" in the office sense, roles fill that role.

Rather than force restaurant job titles into a `Department` they don't
really belong to, every user keeps **both**:

- `department` — a small canonical set (`Finance`, `HR`, `Management`,
  `Operations`, `Marketing`, `Trading`, `Admin`) used for task routing and
  reporting, same as the original design.
- `job_title` — the original text from the sheet, kept verbatim (typos
  fixed to be spelling-correct, not reworded) for anyone who needs the
  literal title.

**Mapping used** (job title/raw department → canonical `Department`):

| Raw value(s) | Canonical department |
|---|---|
| `finance`, `finanace` | Finance |
| `hr` | HR |
| `md`, `gm` | Management |
| `operation`, `opertion`, `manager` (restaurant), `manager construction and purchase`, `chef`, `driver`, `driver delivery`, `inventory and merchandise` | Operations |
| `marketing` | Marketing |
| `trdading` | Trading |
| `admin` | Admin |

**RBAC role assigned** (see `Role` enum in `app/models/user.py`):

- Any job title containing "manager", or exactly `gm`/`md` → `MANAGER`
- Everything else → `MEMBER`
- Nobody was auto-assigned `ADMIN` — that's a deliberate, manual decision
  for whoever HNBG designates as system administrators, not something to
  infer from a job title.

`Sandesh Poudel` (Managing Director, row 4) and `Shankar Singh Thapa`
(GM, row 13) are flagged with a `notes` field in `staff.json` suggesting
they may warrant a manual promotion to `ADMIN` later.

## Data-cleaning decisions

The raw sheet had a few inconsistencies, resolved as follows:

- **Missing emails/phones** (common for restaurant staff) — left `null`
  rather than invented. `User.email` was changed from required+unique to
  nullable+unique for this reason; `password_hash` is also nullable now,
  since these are org-chart entries, not necessarily people who've been
  given login access yet.
- **Row 21** (`Lal Bahadur Lama`) — branch typo `"All Restraunts"`
  normalized to `"All Restaurants"`.
- **Row 25** (`Sagar Magar`) — the sheet put `"Resigned"` in the *Branch*
  column instead of a real branch name. Mapped to `is_active: false`,
  branch left unset, rather than creating a fake "Resigned" branch.
- **Row 37** (`"sunita mam"`) — no branch, email, or phone on file, and an
  informal name rather than a full legal name. Seeded as-is but flagged
  with a note to verify with HR before treating as a real login-eligible
  account.
- **Row 38** (`Udaya Lal Koirala`) — raw job title was `"driver  arjun
  sir"`. Interpreted as job title `driver`, with "Arjun sir" kept as a
  supervisor note rather than folded into the title.

## Business units & branches seeded

| Business Unit | Branches |
|---|---|
| Overall | Headoffice |
| Trading | Janechi/HOMA |
| Restaurants | All Restaurants, Dekkaido Farm House, Hokkaido Ramen House (Parkvillage), Merai Sekai, Hokkaido Sora, Hokkaido Yakitori, Hokkaido Izakaya, Hokkaido Umami, Hokkaido House, Hokkaido Pokhara |

## What this doesn't do yet

- Doesn't create login credentials — `password_hash` stays `null` for
  everyone seeded this way. A future "invite user" flow should set it.
- Doesn't touch `Task` — seeded users aren't assigned any tasks by
  default.
- `ADMIN` role isn't auto-assigned to anyone; assign manually once HNBG
  confirms who the system administrators should be.
