"""
LeetCode GraphQL API client.

Handles fetching problem details, the daily challenge,
submitting solutions, and polling for submission verdicts.
"""

import re
import time
import requests

import config


def _get_public_headers():
    """Headers for unauthenticated requests (fetching problems)."""
    return {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "Origin": "https://leetcode.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _get_auth_headers(slug):
    """Headers for authenticated requests (submitting solutions)."""
    if not config.LEETCODE_SESSION or not config.LEETCODE_CSRF_TOKEN:
        raise RuntimeError(
            "Missing LEETCODE_SESSION or LEETCODE_CSRF_TOKEN in .env\n"
            "See plan.md Step 2 for instructions on getting these."
        )
    return {
        "Content-Type": "application/json",
        "Cookie": (
            f"LEETCODE_SESSION={config.LEETCODE_SESSION}; "
            f"csrftoken={config.LEETCODE_CSRF_TOKEN}"
        ),
        "x-csrftoken": config.LEETCODE_CSRF_TOKEN,
        "Referer": f"https://leetcode.com/problems/{slug}/",
        "Origin": "https://leetcode.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _strip_html(html_text):
    """Remove HTML tags and decode common HTML entities to get clean text."""
    if not html_text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html_text)
    # Decode common HTML entities
    replacements = {
        "&nbsp;": " ",
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
        "&le;": "≤",
        "&ge;": "≥",
        "&times;": "×",
        "&minus;": "-",
        "&sup2;": "²",
        "&lfloor;": "⌊",
        "&rfloor;": "⌋",
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    # Collapse multiple newlines/spaces
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_python_template(code_snippets):
    """Extract the Python3 code template from the list of code snippets."""
    if not code_snippets:
        return ""
    for snippet in code_snippets:
        if snippet.get("langSlug") == "python3":
            return snippet["code"]
    # Fallback to python (Python 2) if python3 not found
    for snippet in code_snippets:
        if snippet.get("langSlug") == "python":
            return snippet["code"]
    return ""


# ─── Fetch a specific problem ──────────────────────────────────────────

PROBLEM_QUERY = """
query getQuestionDetail($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    title
    titleSlug
    content
    difficulty
    exampleTestcases
    sampleTestCase
    codeSnippets {
      lang
      langSlug
      code
    }
    topicTags {
      name
    }
  }
}
"""


def fetch_problem(slug):
    """
    Fetch full problem details from LeetCode by its URL slug.

    Args:
        slug: The problem's URL slug, e.g. "two-sum"

    Returns:
        A dict with keys: questionId, title, titleSlug, content (clean text),
        difficulty, exampleTestcaseInput, python_template, topicTags
    """
    payload = {
        "query": PROBLEM_QUERY,
        "variables": {"titleSlug": slug},
    }

    resp = requests.post(
        config.LEETCODE_GRAPHQL_URL,
        json=payload,
        headers=_get_public_headers(),
        timeout=15,
    )
    resp.raise_for_status()

    data = resp.json()
    question = data.get("data", {}).get("question")

    if not question:
        raise ValueError(
            f"Problem '{slug}' not found. "
            "Check the slug — it should look like 'two-sum', not '1. Two Sum'."
        )

    return {
        "questionId": question["questionId"],
        "title": question["title"],
        "titleSlug": question["titleSlug"],
        "content": _strip_html(question.get("content", "")),
        "difficulty": question["difficulty"],
        "exampleTestcases": question.get("exampleTestcases", question.get("sampleTestCase", "")),
        "python_template": _extract_python_template(
            question.get("codeSnippets", [])
        ),
        "topicTags": [
            tag["name"] for tag in question.get("topicTags", [])
        ],
    }


# ─── Fetch the daily challenge ─────────────────────────────────────────

DAILY_QUERY = """
query getDailyChallenge {
  activeDailyCodingChallengeQuestion {
    question {
      titleSlug
      title
      difficulty
    }
  }
}
"""


def fetch_daily_challenge():
    """
    Fetch today's daily coding challenge, then return its full problem details.

    Returns:
        Same dict format as fetch_problem().
    """
    payload = {"query": DAILY_QUERY}

    resp = requests.post(
        config.LEETCODE_GRAPHQL_URL,
        json=payload,
        headers=_get_public_headers(),
        timeout=15,
    )
    resp.raise_for_status()

    data = resp.json()
    daily = (
        data.get("data", {})
        .get("activeDailyCodingChallengeQuestion", {})
        .get("question", {})
    )

    if not daily or not daily.get("titleSlug"):
        raise ValueError("Could not fetch today's daily challenge.")

    slug = daily["titleSlug"]
    print(f"[DAILY] Today's daily challenge: {daily['title']} ({daily['difficulty']})")

    return fetch_problem(slug)


def fetch_problem_list(limit=50, skip=0, difficulty=None):
    """
    Fetch a list of problems from the LeetCode problemset.
    Filters out paid-only problems.

    Args:
        limit: Max number of questions to fetch.
        skip: Offset for pagination.
        difficulty: Optional filter - "EASY", "MEDIUM", or "HARD".

    Returns:
        List of dicts with: questionFrontendId, title, titleSlug, difficulty.
    """
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        questions: data {
          questionFrontendId
          title
          titleSlug
          difficulty
          paidOnly: isPaidOnly
        }
      }
    }
    """
    filters = {}
    if difficulty:
        filters["difficulty"] = difficulty.upper()

    payload = {
        "query": query,
        "variables": {
            "categorySlug": "",
            "skip": skip,
            "limit": limit,
            "filters": filters,
        },
    }

    resp = requests.post(
        config.LEETCODE_GRAPHQL_URL,
        json=payload,
        headers=_get_public_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")

    questions = (
        data.get("data", {})
        .get("problemsetQuestionList", {})
        .get("questions", [])
    )
    # Filter out paid-only problems
    return [q for q in questions if not q.get("paidOnly")]



# ─── Submit a solution ─────────────────────────────────────────────────

def submit_solution(slug, question_id, code):
    """
    Submit a Python solution to LeetCode.

    Args:
        slug: Problem URL slug, e.g. "two-sum"
        question_id: The problem's numeric ID (string), e.g. "1"
        code: The full Python solution code

    Returns:
        A dict with: status, runtime, memory, and optionally error details.
    """
    submit_url = f"https://leetcode.com/problems/{slug}/submit/"

    payload = {
        "lang": "python3",
        "question_id": question_id,
        "typed_code": code,
    }

    resp = requests.post(
        submit_url,
        json=payload,
        headers=_get_auth_headers(slug),
        timeout=15,
    )
    resp.raise_for_status()

    submission_id = resp.json().get("submission_id")
    if not submission_id:
        raise RuntimeError("Submission failed — no submission_id received.")

    return _poll_submission(submission_id)


def _poll_submission(submission_id, max_polls=20, interval=2):
    """
    Poll LeetCode for the submission verdict.

    Args:
        submission_id: The submission ID to check
        max_polls: Maximum number of polling attempts
        interval: Seconds between polls

    Returns:
        A dict with: status, runtime, memory, and error details if applicable.
    """
    check_url = f"https://leetcode.com/submissions/detail/{submission_id}/check/"

    for _ in range(max_polls):
        time.sleep(interval)

        resp = requests.get(
            check_url,
            headers=_get_auth_headers(""),
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        state = result.get("state")

        if state == "PENDING" or state == "STARTED":
            continue

        # Build the result dict
        status_msg = result.get("status_msg", "Unknown")
        verdict = {
            "status": status_msg,
            "runtime": result.get("status_runtime", "N/A"),
            "memory": result.get("status_memory", "N/A"),
            "runtime_percentile": result.get("runtime_percentile", "N/A"),
            "memory_percentile": result.get("memory_percentile", "N/A"),
        }

        # Add error details for failed submissions
        if status_msg != "Accepted":
            verdict["total_correct"] = result.get("total_correct")
            verdict["total_testcases"] = result.get("total_testcases")
            verdict["input"] = result.get("input_formatted", result.get("input", ""))
            verdict["expected_output"] = result.get("expected_output", "")
            verdict["code_output"] = result.get("code_output", "")
            verdict["runtime_error"] = result.get("runtime_error", "")
            verdict["compile_error"] = result.get("compile_error", "")
            verdict["full_runtime_error"] = result.get("full_runtime_error", "")
            verdict["full_compile_error"] = result.get("full_compile_error", "")

        return verdict

    raise TimeoutError(
        f"Submission {submission_id} still pending after {max_polls * interval}s."
    )
