import React, { useState, useRef } from "react";
import {
  ClipboardList,
  ChevronDown,
  Calendar,
  User,
  AlertCircle,
  Flag,
  X,
} from "lucide-react";

/**
 * CreateTaskForm
 * -----------------------------------------------------------------------
 * A self-contained, production-ready "Create Task" form built on the same
 * Apple HIG–compatible resources as the rest of the prototype
 * (prototypes/web/styles.css, docs/DESIGN_SYSTEM.md): the San Francisco
 * system-font stack, the HNBG brand mapped onto Apple System Colors with
 * distinct light/dark values, the Apple System Fill Color hierarchy for
 * neutral surfaces, floating labels, hairline-divided groups, and quiet
 * micro-interactions.
 *
 * Dark mode uses Tailwind's `dark:` variant, which defaults to the
 * `media` strategy (follows `prefers-color-scheme`) unless the host
 * app's tailwind.config.js sets `darkMode: 'class'` — either works here
 * unmodified.
 *
 * Usage:
 *   <CreateTaskForm
 *     onSubmit={(task) => console.log(task)}
 *     onCancel={() => setOpen(false)}
 *   />
 *
 * Requires Tailwind CSS (JIT, v3.3+ for the peer-[&:not(...)]  variant)
 * and the `lucide-react` icon package.
 * -----------------------------------------------------------------------
 */

const PROJECTS = [
  { value: "", label: "Select a project" },
  { value: "platform-migration", label: "Platform Migration" },
  { value: "q3-marketing", label: "Q3 Marketing Site" },
  { value: "mobile-app-v2", label: "Mobile App v2" },
];

// Avatar accents reuse the same per-person palette as the rest of the
// app (see prototypes/web/*.html avatar-sm examples) — brand blue for
// the primary accent instead of a generic system blue.
const ASSIGNEES = [
  { value: "", label: "Unassigned", initials: "—", color: "#8e8e93" },
  { value: "maria-j", label: "Maria J.", initials: "MJ", color: "#1c4b96" },
  { value: "ravi-k", label: "Ravi K.", initials: "RK", color: "#f2a900" },
  { value: "dan-t", label: "Dan T.", initials: "DT", color: "#1db954" },
  { value: "emma-w", label: "Emma W.", initials: "EW", color: "#e2231c" },
  { value: "sara-l", label: "Sara L.", initials: "SL", color: "#af52de" },
];

// Same neutral → red severity ramp as the dashboard's status cards.
const PRIORITIES = [
  { value: "low", label: "Low", dot: "#8e8e93" },
  { value: "medium", label: "Medium", dot: "#f2a900" },
  { value: "high", label: "High", dot: "#ff6961" },
  { value: "urgent", label: "Urgent", dot: "#e2231c" },
];

const initialState = {
  title: "",
  description: "",
  project: "",
  priority: "medium",
  dueDate: "",
  assignee: "",
};

export default function CreateTaskForm({ onSubmit, onCancel }) {
  const [form, setForm] = useState(initialState);
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const titleRef = useRef(null);

  const errors = {
    title: form.title.trim().length === 0 ? "Task title is required." : "",
  };

  const isValid = Object.values(errors).every((e) => !e);

  const update = (field) => (e) => {
    const value = e && e.target ? e.target.value : e;
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const markTouched = (field) => () =>
    setTouched((prev) => ({ ...prev, [field]: true }));

  const showError = (field) => Boolean(touched[field] && errors[field]);

  const handleSubmit = (e) => {
    e.preventDefault();
    setTouched({ title: true });

    if (!isValid) {
      titleRef.current?.focus();
      return;
    }

    setSubmitting(true);
    Promise.resolve(onSubmit ? onSubmit({ ...form }) : null).finally(() => {
      setSubmitting(false);
    });
  };

  const selectedAssignee =
    ASSIGNEES.find((a) => a.value === form.assignee) || ASSIGNEES[0];

  return (
    <div className="min-h-screen w-full bg-[#f5f5f7] dark:bg-black flex items-center justify-center p-6 font-[-apple-system,BlinkMacSystemFont,'SF_Pro_Text','SF_Pro_Display',sans-serif]">
      <form
        onSubmit={handleSubmit}
        noValidate
        className="w-full max-w-[560px] bg-white dark:bg-[#1c1c1e] rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.12)] dark:shadow-[0_20px_60px_rgba(0,0,0,0.5)] border border-[#d2d2d7] dark:border-white/10 overflow-hidden"
      >
        {/* ---------------- Header ---------------- */}
        <div className="flex items-start justify-between gap-4 px-7 pt-7 pb-5">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#1c4b96]/10 dark:bg-[#4c8bdf]/15 text-[#1c4b96] dark:text-[#4c8bdf]">
              <ClipboardList size={20} strokeWidth={2} />
            </div>
            <div>
              <h1 className="text-[17px] font-semibold tracking-[-0.01em] text-[#1d1d1f] dark:text-[#f5f5f7]">
                Create New Task
              </h1>
              <p className="mt-0.5 text-[13px] text-[#86868b] dark:text-[#6e6e73]">
                Set details, ownership, and target timelines.
              </p>
            </div>
          </div>

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              aria-label="Close"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[#86868b] dark:text-[#98989d] transition-colors duration-150 hover:bg-[#f5f5f7] dark:hover:bg-white/10 hover:text-[#1d1d1f] dark:hover:text-[#f5f5f7] active:bg-[#e8e8ed] dark:active:bg-white/15"
            >
              <X size={15} strokeWidth={2} />
            </button>
          )}
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-7 pb-2">
          {/* ---------------- Task Details Group ---------------- */}
          <fieldset className="rounded-2xl border border-[#d2d2d7] dark:border-white/10 divide-y divide-[#d2d2d7] dark:divide-white/10 overflow-hidden">
            <legend className="sr-only">Task details</legend>

            {/* Task Title (floating label) */}
            <div className="relative px-4 pt-5 pb-2">
              <input
                ref={titleRef}
                id="task-title"
                type="text"
                value={form.title}
                onChange={update("title")}
                onBlur={markTouched("title")}
                placeholder=" "
                aria-invalid={showError("title")}
                aria-describedby={showError("title") ? "task-title-error" : undefined}
                className={`peer w-full bg-transparent text-[15px] text-[#1d1d1f] dark:text-[#f5f5f7] outline-none pt-2 pb-1 placeholder-transparent transition-colors duration-150
                  ${showError("title") ? "border-b border-[#e2231c]" : "border-b border-transparent"}`}
              />
              <label
                htmlFor="task-title"
                className={`pointer-events-none absolute left-4 top-5 text-[15px] transition-all duration-150 ease-out
                  peer-placeholder-shown:top-5 peer-placeholder-shown:text-[15px]
                  peer-focus:top-1 peer-focus:text-[11px]
                  peer-[&:not(:placeholder-shown)]:top-1 peer-[&:not(:placeholder-shown)]:text-[11px]
                  ${showError("title") ? "text-[#e2231c] peer-focus:text-[#e2231c]" : "text-[#86868b] dark:text-[#98989d] peer-focus:text-[#1c4b96] dark:peer-focus:text-[#4c8bdf]"}`}
              >
                Task Title
              </label>

              {showError("title") && (
                <p
                  id="task-title-error"
                  className="mt-1.5 flex items-center gap-1.5 text-[12px] font-medium text-[#e2231c] dark:text-[#ff453a]"
                >
                  <AlertCircle size={13} strokeWidth={2.2} />
                  {errors.title}
                </p>
              )}
            </div>

            {/* Description (floating label, auto-expanding textarea) */}
            <div className="relative px-4 pt-5 pb-2">
              <textarea
                id="task-description"
                rows={1}
                value={form.description}
                onChange={(e) => {
                  update("description")(e);
                  e.target.style.height = "auto";
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                placeholder=" "
                className="peer w-full resize-none overflow-hidden bg-transparent text-[15px] leading-relaxed text-[#1d1d1f] dark:text-[#f5f5f7] outline-none pt-2 pb-1 placeholder-transparent"
              />
              <label
                htmlFor="task-description"
                className="pointer-events-none absolute left-4 top-5 text-[15px] text-[#86868b] dark:text-[#98989d] transition-all duration-150 ease-out
                  peer-placeholder-shown:top-5 peer-placeholder-shown:text-[15px]
                  peer-focus:top-1 peer-focus:text-[11px] peer-focus:text-[#1c4b96] dark:peer-focus:text-[#4c8bdf]
                  peer-[&:not(:placeholder-shown)]:top-1 peer-[&:not(:placeholder-shown)]:text-[11px]"
              >
                Description
              </label>
            </div>
          </fieldset>

          {/* ---------------- Configuration & Metadata Group ---------------- */}
          <fieldset className="mt-5 rounded-2xl border border-[#d2d2d7] dark:border-white/10 divide-y divide-[#d2d2d7] dark:divide-white/10 overflow-hidden">
            <legend className="sr-only">Task configuration</legend>

            {/* Category / Project */}
            <div className="relative px-4 pt-5 pb-2">
              <select
                id="task-project"
                value={form.project}
                onChange={update("project")}
                className="peer w-full appearance-none bg-transparent pt-2 pb-1 pr-6 text-[15px] text-[#1d1d1f] dark:text-[#f5f5f7] outline-none [color-scheme:light] dark:[color-scheme:dark]"
              >
                {PROJECTS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              <label
                htmlFor="task-project"
                className="pointer-events-none absolute left-4 top-1 text-[11px] text-[#86868b] dark:text-[#98989d]"
              >
                Project
              </label>
              <ChevronDown
                size={16}
                strokeWidth={2}
                className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#86868b] dark:text-[#98989d]"
              />
            </div>

            {/* Priority — segmented control */}
            <div className="px-4 py-4">
              <span className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-[#86868b] dark:text-[#98989d]">
                <Flag size={12} strokeWidth={2} />
                Priority
              </span>
              <div
                role="radiogroup"
                aria-label="Priority level"
                className="inline-flex w-full gap-1 rounded-[10px] bg-[rgba(120,120,128,0.08)] dark:bg-[rgba(120,120,128,0.18)] p-1"
              >
                {PRIORITIES.map((p) => {
                  const active = form.priority === p.value;
                  return (
                    <button
                      key={p.value}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => update("priority")(p.value)}
                      className={`flex flex-1 items-center justify-center gap-1.5 rounded-[8px] py-1.5 text-[13px] font-medium transition-all duration-150 ease-out
                        ${
                          active
                            ? "bg-white dark:bg-[#2c2c2e] text-[#1d1d1f] dark:text-[#f5f5f7] shadow-[0_1px_3px_rgba(0,0,0,0.12)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.4)]"
                            : "text-[#6e6e73] dark:text-[#98989d] hover:text-[#1d1d1f] dark:hover:text-[#f5f5f7]"
                        }`}
                    >
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ backgroundColor: p.dot }}
                      />
                      {p.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Due Date & Time */}
            <div className="relative px-4 pt-5 pb-2">
              <input
                id="task-due"
                type="datetime-local"
                value={form.dueDate}
                onChange={update("dueDate")}
                placeholder=" "
                className="peer w-full bg-transparent pt-2 pb-1 pr-8 text-[15px] text-[#1d1d1f] dark:text-[#f5f5f7] outline-none [color-scheme:light] dark:[color-scheme:dark]"
              />
              <label
                htmlFor="task-due"
                className="pointer-events-none absolute left-4 top-1 text-[11px] text-[#86868b] dark:text-[#98989d]"
              >
                Due Date &amp; Time
              </label>
              <Calendar
                size={16}
                strokeWidth={2}
                className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#86868b] dark:text-[#98989d]"
              />
            </div>

            {/* Assignee — with avatar preview */}
            <div className="relative flex items-center gap-3 px-4 py-3.5">
              <div
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white"
                style={{ backgroundColor: selectedAssignee.color }}
              >
                {selectedAssignee.value ? (
                  selectedAssignee.initials
                ) : (
                  <User size={14} strokeWidth={2} />
                )}
              </div>

              <div className="relative flex-1">
                <select
                  id="task-assignee"
                  value={form.assignee}
                  onChange={update("assignee")}
                  className="peer w-full appearance-none bg-transparent pt-3 pb-1 pr-6 text-[15px] text-[#1d1d1f] dark:text-[#f5f5f7] outline-none [color-scheme:light] dark:[color-scheme:dark]"
                >
                  {ASSIGNEES.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </select>
                <label
                  htmlFor="task-assignee"
                  className="pointer-events-none absolute left-0 top-0 text-[11px] text-[#86868b] dark:text-[#98989d]"
                >
                  Assignee
                </label>
                <ChevronDown
                  size={16}
                  strokeWidth={2}
                  className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-[#86868b] dark:text-[#98989d]"
                />
              </div>
            </div>
          </fieldset>
        </div>

        {/* ---------------- Action Footer ---------------- */}
        <div className="flex items-center justify-end gap-2 border-t border-[#d2d2d7] dark:border-white/10 bg-[#fbfbfd] dark:bg-[#232326] px-7 py-4">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full px-4 py-2 text-[14px] font-medium text-[#1d1d1f] dark:text-[#f5f5f7] transition-colors duration-150 hover:bg-[#e8e8ed] dark:hover:bg-white/10 active:bg-[#dcdce1] dark:active:bg-white/15"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={submitting}
            className="rounded-full bg-[#1c4b96] dark:bg-[#4c8bdf] px-5 py-2 text-[14px] font-semibold text-white shadow-[0_1px_2px_rgba(28,75,150,0.35)] transition-all duration-150 ease-out
              hover:bg-[#163c78] dark:hover:bg-[#6ea3e8]
              active:scale-[0.97] active:bg-[#163c78] dark:active:bg-[#3f7bd0]
              disabled:cursor-not-allowed disabled:bg-[#1c4b96]/40 dark:disabled:bg-[#4c8bdf]/40 disabled:shadow-none disabled:active:scale-100"
          >
            {submitting ? "Creating…" : "Create Task"}
          </button>
        </div>
      </form>
    </div>
  );
}
