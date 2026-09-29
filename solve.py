"""
Autonomous LeetCode Solver Agent

Usage:
    python solve.py two-sum                           # Solve by slug
    python solve.py https://leetcode.com/problems/two-sum/  # Solve by URL
    python solve.py --daily                           # Solve today's daily challenge
    python solve.py two-sum --no-submit               # Generate & save only
    python solve.py two-sum --retries 5               # More retry attempts
"""

import argparse
import os
import re
import sys

import config
from leetcode_client import fetch_problem, fetch_daily_challenge, submit_solution
from gemini_solver import generate_solution, generate_solution_with_feedback


def extract_slug(problem_input):
    """
    Extract the problem slug from user input.
    Handles full URLs, slug strings, and common variations.

    Examples:
        "https://leetcode.com/problems/two-sum/"         -> "two-sum"
        "https://leetcode.com/problems/two-sum/description/" -> "two-sum"
        "two-sum"                                          -> "two-sum"
        "Two Sum"                                          -> "two-sum"
    """
    # Handle full URLs
    url_match = re.search(r"leetcode\.com/problems/([^/]+)", problem_input)
    if url_match:
        return url_match.group(1)

    # Handle "Two Sum" style names -> "two-sum"
    if " " in problem_input:
        return problem_input.lower().strip().replace(" ", "-")

    return problem_input.strip().strip("/").lower()


def save_solution(slug, code):
    """Save the solution to the solutions/ directory."""
    os.makedirs(config.SOLUTIONS_DIR, exist_ok=True)
    filepath = os.path.join(config.SOLUTIONS_DIR, f"{slug}.py")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    return filepath


def format_percentile(value):
    """Format a percentile value for display."""
    if value == "N/A" or value is None:
        return ""
    try:
        return f" (beats {float(value):.1f}%)"
    except (ValueError, TypeError):
        return ""


def run_agent(slug=None, daily=False, no_submit=False, retries=None):
    """
    Main agent logic -- fetch, solve, save, submit.

    Args:
        slug: Problem slug or URL (ignored if daily=True)
        daily: If True, solve today's daily challenge
        no_submit: If True, skip submission
        retries: Max retry attempts (defaults to config.MAX_RETRIES)
    """
    max_retries = retries if retries is not None else config.MAX_RETRIES

    # -- Step 1: Fetch the problem --
    print()
    if daily:
        problem = fetch_daily_challenge()
    else:
        if not slug:
            print("[ERROR] Please provide a problem slug, URL, or use --daily")
            sys.exit(1)
        slug = extract_slug(slug)
        problem = fetch_problem(slug)

    print(f"[TARGET] Solving: {problem['title']} ({problem['difficulty']})")
    if problem.get("topicTags"):
        print(f"[TOPICS] {', '.join(problem['topicTags'])}")
    print()

    # -- Step 2: Generate solution with Gemini --
    print("[AI] Generating solution with Gemini...")
    solution = generate_solution(problem)

    # -- Step 3: Save locally --
    filepath = save_solution(problem["titleSlug"], solution)
    print(f"[SAVED] {filepath}")

    # -- Step 4: Submit (unless --no-submit) --
    if no_submit:
        print()
        print("[DONE] Solution saved (submission skipped).")
        print(f"   Review it at: {filepath}")
        return

    for attempt in range(1, max_retries + 1):
        print()
        print(f"[SUBMIT] Submitting to LeetCode... (attempt {attempt}/{max_retries})")
        print("[WAIT] Waiting for verdict...")

        try:
            result = submit_solution(
                problem["titleSlug"],
                problem["questionId"],
                solution,
            )
        except RuntimeError as e:
            print(f"[WARN] Submission error: {e}")
            if "Missing LEETCODE_SESSION" in str(e):
                print("   Run with --no-submit to just save the solution locally.")
            return
        except Exception as e:
            print(f"[WARN] Unexpected error: {e}")
            return

        status = result.get("status", "Unknown")

        if status == "Accepted":
            runtime_pct = format_percentile(result.get("runtime_percentile"))
            memory_pct = format_percentile(result.get("memory_percentile"))
            print("[ACCEPTED] Accepted!")
            print(f"   Runtime: {result.get('runtime', 'N/A')}{runtime_pct}")
            print(f"   Memory:  {result.get('memory', 'N/A')}{memory_pct}")
            return

        # -- Failed -- show error details --
        print(f"[FAILED] {status} (attempt {attempt}/{max_retries})")

        if result.get("total_correct") is not None:
            print(
                f"   Passed: {result['total_correct']}/{result.get('total_testcases', '?')} test cases"
            )
        if result.get("runtime_error"):
            print(f"   Error: {result['runtime_error']}")
        if result.get("compile_error"):
            print(f"   Error: {result['compile_error']}")

        # -- Retry with error feedback --
        if attempt < max_retries:
            print()
            print("[RETRY] Retrying with error feedback...")
            previous_code = solution
            solution = generate_solution_with_feedback(
                problem, previous_code, result
            )
            filepath = save_solution(problem["titleSlug"], solution)
            print(f"[SAVED] Updated: {filepath}")
        else:
            print()
            print(f"[EXHAUSTED] All {max_retries} attempts failed.")
            print(f"   Last solution saved at: {filepath}")
            print("   You may want to review and fix it manually.")


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous LeetCode Solver Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python solve.py two-sum
  python solve.py https://leetcode.com/problems/two-sum/
  python solve.py --daily
  python solve.py two-sum --no-submit
  python solve.py two-sum --retries 5
        """,
    )

    parser.add_argument(
        "problem",
        nargs="?",
        default=None,
        help="Problem slug or full LeetCode URL (e.g., 'two-sum')",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Solve today's daily coding challenge",
    )
    parser.add_argument(
        "--no-submit",
        action="store_true",
        help="Generate and save the solution without submitting to LeetCode",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=None,
        help=f"Max retry attempts on failure (default: {config.MAX_RETRIES})",
    )

    args = parser.parse_args()

    if not args.problem and not args.daily:
        parser.print_help()
        print("\n[ERROR] Please provide a problem slug or use --daily")
        sys.exit(1)

    run_agent(
        slug=args.problem,
        daily=args.daily,
        no_submit=args.no_submit,
        retries=args.retries,
    )


if __name__ == "__main__":
    main()
