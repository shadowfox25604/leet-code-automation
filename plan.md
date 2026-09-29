# 🤖 Autonomous LeetCode Solver Agent — Plan

## What Is This?

A **single-command** Python agent that autonomously:

1. Fetches a LeetCode problem (by URL/slug **or** the daily challenge)
2. Sends it to **Google Gemini AI** to generate a Python solution
3. Saves the solution locally as an organized file
4. Submits the solution to LeetCode via your session cookie
5. Reports the verdict (Accepted / Wrong Answer / TLE, etc.)
6. **Self-heals** — if a submission fails, it feeds the error back to Gemini and retries (up to 3 times)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER COMMAND                             │
│                                                                 │
│   python solve.py two-sum          # specific problem           │
│   python solve.py --daily          # today's daily challenge    │
│   python solve.py two-sum --no-submit  # just save locally      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      solve.py (Entry Point)                      │
│                                                                  │
│  1. Parses command-line arguments                                │
│  2. Decides: daily challenge vs specific problem                 │
│  3. Orchestrates the full pipeline                               │
│  4. Handles retry loop on submission failure                     │
└───────┬──────────────────────┬───────────────────────┬──────────┘
        │                      │                       │
        ▼                      ▼                       ▼
┌───────────────┐  ┌────────────────────┐  ┌──────────────────────┐
│  config.py    │  │ leetcode_client.py │  │  gemini_solver.py    │
│               │  │                    │  │                      │
│ • Loads .env  │  │ • Fetch problem    │  │ • Generate solution  │
│ • API keys    │  │ • Fetch daily      │  │ • Retry with error   │
│ • Constants   │  │ • Submit solution  │  │   feedback           │
│               │  │ • Check verdict    │  │ • Clean code output  │
└───────────────┘  └────────────────────┘  └──────────────────────┘
```

### Data Flow

```
User Input (slug/URL/--daily)
        │
        ▼
┌─ LeetCode GraphQL API ─────────────────────────────┐
│  Fetches: title, description, examples,             │
│           constraints, code template, question ID   │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─ Gemini AI ─────────────────────────────────────────┐
│  Receives: Full problem context + system prompt     │
│  Returns:  Clean Python Solution class              │
└─────────────────────────┬───────────────────────────┘
                          │
                    ┌─────┴─────┐
                    ▼           ▼
            ┌───────────┐ ┌──────────────────────────┐
            │ Save to   │ │ Submit to LeetCode       │
            │ solutions/│ │ via GraphQL API           │
            │ slug.py   │ │                           │
            └───────────┘ └────────────┬──────────────┘
                                       │
                                       ▼
                                ┌──────────────┐
                                │   Verdict    │
                                │  Accepted?   │
                                └──────┬───────┘
                                       │
                              ┌────────┴────────┐
                              │ YES             │ NO
                              ▼                 ▼
                         🎉 Done!         🔄 Retry
                                      (feed error back
                                       to Gemini, up to
                                       3 attempts)
```

---

## Project Structure

```
leetcode/
├── plan.md               # 📋 This file — the full plan
├── solve.py              # 🎯 Main entry point — run this!
├── config.py             # ⚙️  Configuration & environment variables
├── leetcode_client.py    # 🔗 LeetCode GraphQL API interactions
├── gemini_solver.py      # 🧠 Gemini AI solution generator
├── requirements.txt      # 📦 Python dependencies (just 3!)
├── .env.example          # 📝 Template for your secrets
├── .env                  # 🔑 Your actual secrets (gitignored)
├── .gitignore            # 🚫 Ignores .env, __pycache__, etc.
└── solutions/            # 💾 Auto-created folder for saved solutions
    ├── two-sum.py
    ├── valid-parentheses.py
    └── ...
```

---

## File-by-File Breakdown

### 1. `config.py` — Configuration

**Purpose:** Loads all secrets and settings from a `.env` file so nothing is hardcoded.

**What it contains:**

| Variable              | Source          | Description                                   |
|-----------------------|-----------------|-----------------------------------------------|
| `GEMINI_API_KEY`      | `.env`          | Your Google Gemini API key                    |
| `LEETCODE_SESSION`    | `.env`          | Your LeetCode session cookie                  |
| `LEETCODE_CSRF_TOKEN` | `.env`          | Your LeetCode CSRF token                      |
| `LEETCODE_GRAPHQL_URL`| Hardcoded       | `https://leetcode.com/graphql`                |
| `GEMINI_MODEL`        | Hardcoded       | `gemini-2.5-flash` (free tier)                |
| `MAX_RETRIES`         | Hardcoded       | `3` (auto-retry attempts on failure)          |
| `SOLUTIONS_DIR`       | Hardcoded       | `solutions` (folder for saved solutions)      |

---

### 2. `leetcode_client.py` — LeetCode API Client

**Purpose:** All communication with LeetCode's unofficial GraphQL API.

**Functions:**

| Function                           | What It Does                                              |
|------------------------------------|-----------------------------------------------------------|
| `fetch_problem(slug)`              | Fetches full problem details by its URL slug              |
| `fetch_daily_challenge()`          | Gets today's daily challenge, then fetches its details    |
| `submit_solution(slug, question_id, code)` | Submits Python code to LeetCode for judging      |
| `check_submission(submission_id)`  | Polls LeetCode until the verdict is ready                 |

**How problem fetching works:**

- Sends a POST request to `https://leetcode.com/graphql`
- Uses this GraphQL query:
  ```graphql
  query getQuestionDetail($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
      questionId
      title
      titleSlug
      content           # HTML description
      difficulty
      exampleTestcaseInput
      codeSnippets {    # code templates for each language
        lang
        langSlug
        code
      }
      topicTags { name }
    }
  }
  ```
- Extracts the Python3 code template from the `codeSnippets` array
- Strips HTML tags from the `content` field to get clean text
- Returns a dictionary with all problem data

**How submission works:**

1. POST to `https://leetcode.com/problems/{slug}/submit/` with:
   - `lang`: `"python3"`
   - `question_id`: the problem's numeric ID
   - `typed_code`: the generated solution
2. Receives a `submission_id` in the response
3. Polls `https://leetcode.com/submissions/detail/{id}/check/` every 2 seconds
4. Returns the verdict once status is no longer `"PENDING"`

**Authentication headers (required for submission):**

```python
headers = {
    "Content-Type": "application/json",
    "Cookie": f"LEETCODE_SESSION={session}; csrftoken={csrf}",
    "x-csrftoken": csrf,
    "Referer": f"https://leetcode.com/problems/{slug}/",
}
```

---

### 3. `gemini_solver.py` — AI Solution Generator

**Purpose:** Sends the problem to Google Gemini and extracts a clean, submission-ready Python solution.

**Functions:**

| Function                                        | What It Does                                     |
|-------------------------------------------------|--------------------------------------------------|
| `generate_solution(problem)`                    | First attempt — generates a solution from scratch |
| `generate_solution_with_feedback(problem, error)` | Retry — fixes a failed solution using error info |

**System prompt (the key to quality solutions):**

The system prompt instructs Gemini to:

1. Act as an expert competitive programmer
2. Return ONLY the `Solution` class with the required method
3. NOT include imports (unless absolutely necessary), test code, print statements, or markdown
4. Optimize for both correctness and efficiency
5. Handle edge cases carefully

**How the user prompt is built:**

```
Solve this LeetCode problem:

Title: Two Sum
Difficulty: Easy

Description:
Given an array of integers nums and an integer target, return
indices of the two numbers such that they add up to target...

Code Template:
class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:

Return ONLY the complete Solution class.
```

**How retry with feedback works:**

When a submission fails, the agent sends a NEW prompt to Gemini:

```
Your previous solution was WRONG.

Error: Wrong Answer
Expected: [0, 1]
Got: [1, 0]

Previous solution:
<the code that failed>

Fix the solution. Think step by step about what went wrong.
Return ONLY the corrected Solution class.
```

This feedback loop is what makes the agent "self-healing."

---

### 4. `solve.py` — Main Entry Point

**Purpose:** The one file you actually run. Parses arguments, orchestrates the full pipeline.

**Usage:**

```bash
# Solve a specific problem by slug
python solve.py two-sum

# Solve from a full LeetCode URL
python solve.py https://leetcode.com/problems/two-sum/

# Solve today's daily challenge
python solve.py --daily

# Just generate & save — don't submit to LeetCode
python solve.py two-sum --no-submit

# Allow more retry attempts (default: 3)
python solve.py two-sum --retries 5
```

**The main flow (step by step):**

```
1. Parse command-line arguments (argparse)
       │
2. Determine the problem
   ├── If --daily  → call fetch_daily_challenge()
   └── If slug/URL → extract slug → call fetch_problem(slug)
       │
3. Print: "🎯 Solving: Two Sum (Easy)"
       │
4. Call Gemini to generate the solution
       │
5. Save the solution to solutions/<slug>.py
   Print: "💾 Saved to: solutions/two-sum.py"
       │
6. If --no-submit → Done!
   Otherwise → Submit to LeetCode
       │
7. Check the verdict:
   ├── ✅ Accepted → Print runtime & memory stats → Done!
   ├── ❌ Wrong Answer / Runtime Error → 
   │     Feed error details back to Gemini
   │     Generate a new solution
   │     Save & re-submit (up to MAX_RETRIES times)
   └── ⚠️ Other errors → Print error details
```

---

## Dependencies

Only **3 external packages** are needed:

| Package         | Version   | Purpose                                    |
|-----------------|-----------|--------------------------------------------|
| `google-genai`  | ≥ 1.0.0   | Official Google Gemini SDK                 |
| `requests`      | ≥ 2.31.0  | HTTP requests to LeetCode's GraphQL API    |
| `python-dotenv` | ≥ 1.0.0   | Loads `.env` file into environment vars    |

Install with:
```bash
pip install -r requirements.txt
```

---

## Setup Instructions

### Step 1: Get a Gemini API Key (1 minute)

1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **"Create API Key"**
3. Copy the key
4. You'll paste it into `.env` in Step 3

### Step 2: Get Your LeetCode Session Cookie (2 minutes)

1. Open **Chrome** and go to [https://leetcode.com](https://leetcode.com)
2. **Log in** to your LeetCode account
3. Press `F12` to open DevTools
4. Go to the **Application** tab
5. In the left sidebar, expand **Cookies** → click on `https://leetcode.com`
6. Find these two cookies and copy their values:

   | Cookie Name        | What It Looks Like                    |
   |--------------------|---------------------------------------|
   | `LEETCODE_SESSION` | A very long alphanumeric string       |
   | `csrftoken`        | A shorter alphanumeric string         |

7. You'll paste these into `.env` in Step 3

> **Note:** The `LEETCODE_SESSION` cookie expires after a few weeks. If submissions stop working, just repeat this step to get a fresh one.

### Step 3: Configure Your `.env` File (30 seconds)

```bash
# Copy the template
copy .env.example .env
```

Then open `.env` in any editor and paste your keys:

```env
GEMINI_API_KEY=AIzaSy...your_key_here
LEETCODE_SESSION=eyJ0eX...your_session_here
LEETCODE_CSRF_TOKEN=abc123...your_csrf_here
```

### Step 4: Install Dependencies (30 seconds)

```bash
pip install -r requirements.txt
```

### Step 5: Run It! 🚀

```bash
python solve.py two-sum
```

---

## Example Output

```
$ python solve.py two-sum

🎯 Solving: Two Sum (Easy)
📝 Generating solution with Gemini...
💾 Saved to: solutions/two-sum.py
📤 Submitting to LeetCode...
⏳ Waiting for verdict...
🎉 Accepted!
   Runtime: 48 ms (beats 95.2%)
   Memory: 17.6 MB (beats 82.1%)
```

Failed attempt with auto-retry:

```
$ python solve.py container-with-most-water

🎯 Solving: Container With Most Water (Medium)
📝 Generating solution with Gemini...
💾 Saved to: solutions/container-with-most-water.py
📤 Submitting to LeetCode...
⏳ Waiting for verdict...
❌ Wrong Answer (attempt 1/3)
   Expected: 49, Got: 36

🔄 Retrying with error feedback...
📝 Generating improved solution with Gemini...
💾 Updated: solutions/container-with-most-water.py
📤 Re-submitting to LeetCode...
⏳ Waiting for verdict...
🎉 Accepted!
   Runtime: 156 ms (beats 78.4%)
   Memory: 18.2 MB (beats 65.7%)
```

---

## How the Self-Healing Retry Works

This is the "secret sauce" that makes the agent reliable:

```
Attempt 1: Gemini generates a solution from the problem description
    │
    ├── ✅ Accepted → Done!
    │
    └── ❌ Failed → Extract error details:
                    - Status (Wrong Answer / TLE / Runtime Error)
                    - Failed test case input
                    - Expected output vs actual output
                    │
Attempt 2: Gemini gets the ORIGINAL problem + PREVIOUS code + ERROR details
    │          "Your solution failed because... fix it."
    │
    ├── ✅ Accepted → Done!
    │
    └── ❌ Failed again → Same process...
                    │
Attempt 3: Final attempt with accumulated context
    │
    ├── ✅ Accepted → Done!
    │
    └── ❌ Failed → Print final error, suggest manual review
```

Each retry gives Gemini **more context** about what went wrong, so successive attempts are increasingly likely to be correct.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Direct GraphQL** over browser automation | 10x faster, no browser dependencies, simpler code |
| **Gemini 2.5 Flash** as default model | Free tier available, fast, excellent at code generation |
| **Only 4 Python files** | Simplicity — easy to understand, modify, and debug |
| **`.env` for secrets** | Industry standard, prevents accidental commits |
| **Auto-retry with error feedback** | Dramatically improves solve rate vs. single attempt |
| **Save solutions locally** | You keep a copy even if LeetCode is down; builds a personal library |
| **HTML stripping** for problem text | Gemini works better with clean text than raw HTML |
| **`argparse`** for CLI | Built-in Python — no extra dependencies |

---

## Limitations & Notes

- **Session cookie expires**: LeetCode's `LEETCODE_SESSION` cookie expires after a few weeks. You'll need to re-extract it from your browser.
- **Rate limiting**: LeetCode may rate-limit if you submit too many solutions too quickly. The agent includes a 2-second delay between submission polls.
- **Unofficial API**: LeetCode doesn't have a public API. If they change their GraphQL schema, the client may need updates.
- **Not 100% solve rate**: While Gemini is excellent, some hard problems (especially dynamic programming or advanced graph theory) may require manual intervention.
- **Python only**: Solutions are generated in Python. Can be extended to other languages by modifying the system prompt and code template extraction.
