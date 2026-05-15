
## 1. Workflow

### 1. Plan First (When Needed)

- For non-trivial tasks (multi-step, unclear structure, or design decisions), write a short plan before coding.
- Do NOT plan trivial fixes.
- If the current approach is failing, stop and re-plan.

---

### 2. Work in Small, Clear Steps

- Break complex tasks into smaller steps.
- Do not mix multiple concerns in one pass (e.g., parsing + UI + refactoring).
- Keep each change focused and understandable.

---

### 3. Verify Before Done

- Never mark a task as complete without verifying behavior.
- Use:
  - test cases (if available)
  - sample inputs
  - logs / output checks
- If no tests exist, create minimal validation examples.

---

### 4. Fix Root Causes

- Do not apply temporary or superficial fixes.
- Identify why the problem occurs and fix at the correct layer.
- Avoid repeated patching of symptoms.

---

### 5. Prefer Simple and Maintainable Solutions

- Choose the simplest solution that works correctly.
- Avoid over-engineering.
- If a solution feels hacky, consider a cleaner structure before finalizing.

---

### 6. Minimize Impact

- Only change what is necessary.
- Avoid breaking existing behavior.
- Keep compatibility unless explicitly changing behavior.

---

## 2. Task Management

- For non-trivial work:
  - Write a short checklist in `tasks/todo.md`
  - Mark items complete as you go
- After completion:
  - Add a short summary of what changed
- After mistakes or corrections:
  - Record patterns in `tasks/lessons.md`

### Language Policy for Task Documents

- Write project management documents in Korean by default.
- This includes:

  - `tasks/todo.md`
  - `tasks/lessons.md`
  - `README.md`
  - planning notes
  - review summaries
- Use English only when:

  - writing code comments required by the codebase
  - preserving technical terms
  - matching existing English documentation
- Keep task documents concise, practical, and easy to review.

---

## 3. Learning Loop

- When a mistake is corrected:
  - Write a short rule in `tasks/lessons.md`
- Focus on patterns such as:
  - parsing edge cases
  - formatting errors
  - missed requirements
- Reuse these lessons in future tasks.

---

## 4. Output Quality

- Output must be:
  - readable
  - structured
  - consistent
- Prefer:
  - clear sections
  - bullet lists for problem lists
  - aligned lab values when possible

---

## 5. Definition of Done

A task is complete only if:

- behavior works as expected
- edge cases are reasonably handled
- output is readable and consistent
- no obvious regression is introduced
