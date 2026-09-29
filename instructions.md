# LeetCode AI Solver Agent — Setup & Run Instructions

This guide provides step-by-step instructions to set up and run the autonomous LeetCode AI solver on any new device (Windows, macOS, or Linux).

---

## 1. Prerequisites

Before getting started, make sure your machine has:
- **Python 3.10 or higher** installed. Check via:
  ```bash
  python --version
  ```
- **Git** installed:
  ```bash
  git --version
  ```

---

## 2. Initial Setup

### Step 1: Clone the Repository
Open your terminal / command prompt and clone the project:
```bash
git clone <YOUR_GITHUB_REPO_URL>
cd leetcode
```

---

### Step 2: Create a Virtual Environment

Creating an isolated virtual environment (`venv`) prevents conflicts with other Python packages on your system.

- **On Windows (Command Prompt or PowerShell):**
  ```powershell
  python -m venv venv
  ```

- **On macOS / Linux:**
  ```bash
  python3 -m venv venv
  ```

---

### Step 3: Activate the Virtual Environment

- **Windows (Command Prompt / CMD):**
  ```cmd
  venv\Scripts\activate
  ```

- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  *(Note: If PowerShell displays a script execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then run the activate command again).*

- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

When activated, you will see `(venv)` at the beginning of your terminal prompt.

---

### Step 4: Install Dependencies

With the virtual environment activated, install all required packages:

```bash
pip install -r requirements.txt
```

This installs:
- `google-genai` — Official Google Gemini SDK
- `requests` — HTTP & GraphQL client for LeetCode
- `python-dotenv` — Loads environment variables from `.env`

---

### Step 5: Configure Environment Variables (`.env`)

1. Make a copy of `.env.example` named `.env`:
   - **Windows:**
     ```cmd
     copy .env.example .env
     ```
   - **macOS / Linux:**
     ```bash
     cp .env.example .env
     ```

2. Open `.env` in any text editor and fill in your credentials:

```ini
# Required: Free Google Gemini API Key
# Get one at: https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Only needed if you want automatic submissions to LeetCode
# If using --no-submit, you can leave these blank
LEETCODE_SESSION=your_leetcode_session_cookie_here
LEETCODE_CSRF_TOKEN=your_csrf_token_here

# Batch Solving Limits (optional)
BATCH_LIMIT=5               # Set your default number of problems to solve
DELAY_BETWEEN_PROBLEMS=3    # Seconds to wait between questions
```

#### How to get LeetCode Cookies (For auto-submission):
1. Log in to [leetcode.com](https://leetcode.com) in your browser (Chrome/Edge/Brave).
2. Press `F12` to open **Developer Tools** and switch to the **Application** (or **Storage**) tab.
3. In the left panel, expand **Cookies** -> `https://leetcode.com`.
4. Copy the value of `LEETCODE_SESSION` into `.env`.
5. Copy the value of `csrftoken` into `LEETCODE_CSRF_TOKEN` in `.env`.

---

## 3. How to Run the Project

Always ensure your virtual environment is active before running commands (`venv\Scripts\activate` or `source venv/bin/activate`).

### 1. Solve & Save Locally (No LeetCode login required)
Generate an optimal solution with Gemini and save it locally without submitting:
```bash
python solve.py two-sum --no-submit
```

### 2. Solve by Problem Slug or Name
```bash
python solve.py two-sum
python solve.py reverse-linked-list
python solve.py "Valid Palindrome"
```

### 3. Solve by Full LeetCode URL
You can paste the entire problem link directly from your browser:
```bash
python solve.py https://leetcode.com/problems/longest-substring-without-repeating-characters/
```

### 4. Solve Today's LeetCode Daily Challenge
Automatically fetches today's official daily coding challenge, solves it, and submits:
```bash
python solve.py --daily
```
Or to solve today's challenge without submitting:
```bash
python solve.py --daily --no-submit
```

### 5. Custom Retry Count
If a solution fails on LeetCode's test cases, the agent sends the error back to Gemini to self-heal. You can customize the retry limit (default is 3):
```bash
python solve.py median-of-two-sorted-arrays --retries 5
```

### 6. Batch Solving Mode (Manually Set Your Limit)
You can set how many problems to solve in multiple ways:

- **Via `--limit` or `-l` flag:**
  ```bash
  # Solve exactly 3 problems and stop
  python solve.py -l 3

  # Solve 10 Easy problems without submitting (saves locally)
  python solve.py --limit 10 --difficulty easy --no-submit

  # Solve 5 Medium problems with 5-second delay between problems
  python solve.py --limit 5 --difficulty medium --delay 5
  ```

- **Via `--batch` or `-b` flag:**
  ```bash
  # Uses default limit from .env (BATCH_LIMIT=5)
  python solve.py --batch

  # Or specify any custom number
  python solve.py --batch 8
  ```

- **Interactive Mode (Just run without arguments):**
  ```bash
  python solve.py
  ```
  The agent will prompt you in the terminal to enter your desired problem count!

### 7. Continuous Autonomous Mode
Keeps solving problems one after another automatically until you stop it:
```bash
python solve.py --continuous

# Continuous mode saving all Easy problems locally
python solve.py --continuous --difficulty easy --no-submit
```
*(Press `Ctrl + C` anytime to gracefully stop and view the summary).*

---

## 4. Where Solutions Are Saved

Every generated solution is saved as clean, executable Python code in the `solutions/` folder:
```
solutions/
├── two-sum.py
├── reverse-linked-list.py
└── ...
```

---

## 5. Changing the Gemini Model

The active model is defined in `config.py`. The recommended model is:
```python
GEMINI_MODEL = "gemini-3-flash-preview"
```

Other tested working models you can use:
- `"gemini-3.1-flash-lite"` (Fastest, low latency)
- `"gemini-flash-lite-latest"` (Latest flash lite release)

---

## 6. Troubleshooting

- **PowerShell Execution Policy Error:**
  If activating `venv` fails in Windows PowerShell:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\venv\Scripts\Activate.ps1
  ```

- **`Missing GEMINI_API_KEY in .env`:**
  Make sure you created the `.env` file (not just `.env.example`) and pasted your key without extra spaces or quotes.

- **`503 UNAVAILABLE` / High Server Demand:**
  If a particular Gemini model is busy, open `config.py` and switch `GEMINI_MODEL` to `"gemini-3.1-flash-lite"`.

- **LeetCode 403 / CSRF Error during submission:**
  LeetCode session cookies expire periodically. Open browser DevTools on leetcode.com, re-copy `LEETCODE_SESSION` and `csrftoken`, and update `.env`.
