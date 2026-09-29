# Project Context: Autonomous LeetCode AI Solver Agent

> **Agent Directive:** This document serves as the single source of truth for AI agents operating on this repository. Whenever any file or configuration is created, modified, or deleted, or when architectural decisions change, you **MUST** update this file to maintain full context continuity.

---

## 1. Project Overview & Mission

This project is an **Autonomous LeetCode Solving Agent** written in Python. It automatically:
1. Fetches LeetCode problems (via problem slug, full URL, or today's official Daily Challenge).
2. Generates clean, optimal Python solutions using the Google Gemini API.
3. Cleans and extracts raw Python code and saves it to the `solutions/` directory.
4. Submits the code to LeetCode (using browser session cookies) and polls the submission verdict.
5. If the verdict fails (Wrong Answer, Time Limit Exceeded, Runtime Error, Compile Error), it enters a **self-healing retry loop** where error feedback (failing input, expected output, code output, traceback) is fed back into Gemini to fix the solution until accepted or retries are exhausted.
6. Supports a `--no-submit` dry-run mode that generates and saves solutions locally without needing LeetCode login credentials.

---

## 2. Directory & File Structure

```
leetcode/
├── .env                  # Private credentials (GEMINI_API_KEY, LEETCODE_SESSION, LEETCODE_CSRF_TOKEN) [GIT-IGNORED]
├── .env.example          # Safe template with placeholders for new setups
├── .gitignore            # Ignores .env, venv/, __pycache__/, *.pyc, solutions/
├── config.py             # Global constants, env loader, model selection, retry limits
├── leetcode_client.py    # LeetCode GraphQL & REST API client (fetch, submit, poll)
├── gemini_solver.py      # Google Gemini integration, prompt engineering, code cleaner, retry solver
├── solve.py              # Main CLI entry point with argument parsing and execution flow
├── instructions.md       # Setup and onboarding guide for new machines / users
├── context.md            # [THIS FILE] Complete repository memory & state for AI agents
├── requirements.txt      # Python dependencies: google-genai, requests, python-dotenv
├── solutions/            # Directory where solved problems are stored (<slug>.py)
└── venv/                 # Python virtual environment (ignored by Git)
```

---

## 3. Detailed Component Architecture

### `config.py`
- Loads `.env` via `python-dotenv`.
- Exposes:
  - `GEMINI_API_KEY`, `LEETCODE_SESSION`, `LEETCODE_CSRF_TOKEN`
  - `LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"`
  - `GEMINI_MODEL = "gemini-3-flash-preview"`
  - `MAX_RETRIES = 3`
  - `SOLUTIONS_DIR = "solutions"`

### `leetcode_client.py`
- **`fetch_problem(slug)`**: Queries LeetCode GraphQL for `question(titleSlug: ...)`. Returns `title`, `difficulty`, `content` (HTML stripped), `python_template`, `exampleTestcases`, `topicTags`, `questionFrontendId`.
- **`fetch_daily_challenge()`**: Queries LeetCode GraphQL for `activeDailyCodingChallengeQuestion` and retrieves today's challenge.
- **`submit_solution(slug, question_id, code)`**: Sends a POST request to `https://leetcode.com/problems/{slug}/submit/` with authenticated headers. Returns a submission ID.
- **`check_submission(submission_id)`**: Polls `https://leetcode.com/submissions/detail/{submission_id}/check/` every 2 seconds until status changes from `PENDING` / `STARTED` to final status (`SUCCESS`, `Wrong Answer`, etc.).
- **Crucial Request Headers**: LeetCode's API requires `User-Agent`, `Origin`, and `Referer` simulating a modern browser; otherwise, it responds with `400 Bad Request` or `403 Forbidden`.

### `gemini_solver.py`
- Uses `google-genai` SDK (`genai.Client(api_key=...)`).
- System prompt strictly directs the model to output **only valid Python code** implementing LeetCode's `Solution` class without markdown wrappers or prints.
- **`_clean_code(text)`**: Regex utility to strip any residual markdown backticks or fences (` ```python ... ``` `).
- **`generate_solution(problem)`**: Generates the first-pass solution using problem metadata, description, test cases, and code stub.
- **`generate_solution_with_feedback(problem, previous_code, error_info)`**: Formats failed test cases, expected vs actual outputs, or runtime errors into a targeted prompt to guide Gemini in debugging its previous answer.

### `solve.py`
- Command-line interface built with `argparse`.
- Handles URL slug parsing (`extract_slug`), file saving (`save_solution`), and the primary execution loop:
  1. Fetch problem metadata.
  2. Call `generate_solution()`.
  3. Save to `solutions/<slug>.py`.
  4. If `--no-submit`, stop and report success.
  5. Otherwise, check for `LEETCODE_SESSION` in `.env`.
  6. Submit to LeetCode and poll verdict.
  7. If verdict is `Accepted`, report runtime and memory percentiles.
  8. If failed and retries remain, invoke `generate_solution_with_feedback()` and repeat.

---

## 4. Key Learnings, Gotchas & Solved Bugs

1. **Windows Console Unicode Crash (`cp1252`):**
   - Standard Windows Command Prompt / PowerShell defaults to `cp1252` encoding and crashes when printing Unicode emojis.
   - **Resolution:** All emojis in terminal logs were replaced with ASCII tags: `[TARGET]`, `[AI]`, `[SAVED]`, `[DONE]`, `[SUCCESS]`, `[RETRY]`, `[FAILED]`, `[ERROR]`.

2. **LeetCode GraphQL Field Deprecation:**
   - In older APIs, `exampleTestcaseInput` was used. LeetCode now uses `exampleTestcases` and `sampleTestCase`.

3. **Gemini Model Availability & Quotas:**
   - `gemini-2.5-flash`: Deprecated for new API keys (returns `404 NOT_FOUND`).
   - `gemini-3.8-flash`: Frequently encounters high demand (returns `503 UNAVAILABLE`).
   - `gemini-pro-*` / `gemini-3.1-pro-preview`: Returns `429 RESOURCE_EXHAUSTED` under free-tier quota.
   - **Active & Tested Working Models:**
     - **`gemini-3-flash-preview`** (Primary default — optimal balance of reasoning & speed)
     - **`gemini-3.1-flash-lite`** (Fallback — fastest, lowest latency)
     - **`gemini-flash-lite-latest`** (Fallback)

4. **LeetCode Anti-Bot Protections:**
   - Both unauthenticated (fetch) and authenticated (submit) HTTP requests must include `User-Agent: Mozilla/5.0 ...`, `Origin: https://leetcode.com`, and `Referer: https://leetcode.com`.

---

## 5. Development Environment & Execution

- **Platform:** Windows (PowerShell / Command Prompt)
- **Python Version:** 3.14 (compatible with 3.10+)
- **Virtual Environment:** `venv\` located in workspace root

### Common Commands:
```powershell
# Activate venv (PowerShell)
.\venv\Scripts\Activate.ps1

# Dry-run solve without LeetCode submission
.\venv\Scripts\python solve.py two-sum --no-submit

# Solve and submit with LeetCode session
.\venv\Scripts\python solve.py two-sum

# Solve today's daily challenge
.\venv\Scripts\python solve.py --daily

# Custom retry limit
.\venv\Scripts\python solve.py two-sum --retries 5
```

---

## 6. Maintenance Instructions for Future AI Agents

Any future AI agent operating on this project should follow these rules:
1. **Read `context.md` first** before proposing changes or debugging.
2. **Never commit `.env` or personal secrets.** Ensure `.env` remains in `.gitignore`.
3. **Keep console outputs ASCII-friendly** to prevent Windows console encoding crashes.
4. **Update `context.md` immediately** upon:
   - Adding new CLI flags or features.
   - Modifying models in `config.py`.
   - Modifying GraphQL schemas or submission logic.
   - Resolving new edge cases or bugs.
