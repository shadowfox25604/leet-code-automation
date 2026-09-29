"""
Autonomous LeetCode Solver Agent

Usage:
    python solve.py two-sum                           # Solve by slug
    python solve.py https://leetcode.com/problems/two-sum/  # Solve by URL
    python solve.py --daily                           # Solve today's daily challenge
    python solve.py two-sum --retries 5               # More retry attempts
    python solve.py --batch 5                         # Solve 5 problems in a row
    python solve.py --continuous                      # Solve continuously until stopped
    python solve.py --batch 10 --difficulty easy      # Solve 10 Easy problems
"""

import argparse
import os
import re
import sys
import time

import config
from leetcode_client import (
    fetch_problem,
    fetch_daily_challenge,
    fetch_problem_list,
    submit_solution,
)
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
        return True

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
            return False
        except Exception as e:
            print(f"[WARN] Unexpected error: {e}")
            return False

        status = result.get("status", "Unknown")

        if status == "Accepted":
            runtime_pct = format_percentile(result.get("runtime_percentile"))
            memory_pct = format_percentile(result.get("memory_percentile"))
            print("[ACCEPTED] Accepted!")
            print(f"   Runtime: {result.get('runtime', 'N/A')}{runtime_pct}")
            print(f"   Memory:  {result.get('memory', 'N/A')}{memory_pct}")
            return True

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
            return False

    return False


def run_batch(count=None, difficulty=None, no_submit=False, retries=None, delay=3, skip_solved=True):
    """
    Solve problems in batch or continuous mode.

    Args:
        count: Max number of problems to solve (None = continuous).
        difficulty: Optional difficulty filter ("easy", "medium", "hard").
        no_submit: If True, generate & save locally without submitting.
        retries: Max retry attempts per problem.
        delay: Delay in seconds between problems.
        skip_solved: If True, skip problems already in solutions/.
    """
    mode_str = f"Continuous mode (press Ctrl+C to stop)" if count is None else f"Batch mode ({count} problems)"
    diff_str = f" [Difficulty: {difficulty.upper()}]" if difficulty else ""
    print(f"\n[START] {mode_str}{diff_str}")
    print(f"[CONFIG] Delay: {delay}s | Skip already solved: {skip_solved}")
    print("=" * 60)

    solved_count = 0
    failed_count = 0
    skipped_count = 0
    skip_offset = 0
    page_size = 50

    try:
        while True:
            if count is not None and solved_count >= count:
                break

            questions = fetch_problem_list(
                limit=page_size,
                skip=skip_offset,
                difficulty=difficulty,
            )

            if not questions:
                print("\n[INFO] No more problems found in problemset.")
                break

            skip_offset += len(questions)

            for q in questions:
                if count is not None and solved_count >= count:
                    break

                slug = q["titleSlug"]
                solution_path = os.path.join(config.SOLUTIONS_DIR, f"{slug}.py")

                if skip_solved and os.path.exists(solution_path):
                    skipped_count += 1
                    continue

                target_label = f"{solved_count + 1}/{count}" if count else f"{solved_count + 1}"
                print(f"\n{'=' * 60}")
                print(f"[QUEUE] Problem #{target_label}: {q['title']} ({q['difficulty']})")
                print(f"{'=' * 60}")

                try:
                    success = run_agent(
                        slug=slug,
                        no_submit=no_submit,
                        retries=retries,
                    )
                    if success:
                        solved_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    print(f"[ERROR] Failed to process {slug}: {e}")
                    failed_count += 1

                # Delay before next problem to respect rate limits
                if (count is None or solved_count < count) and delay > 0:
                    print(f"\n[WAIT] Waiting {delay}s before next problem...")
                    time.sleep(delay)

    except KeyboardInterrupt:
        print("\n\n[STOPPED] Execution interrupted by user (Ctrl+C).")

    print("\n" + "=" * 60)
    print("[SUMMARY] Batch Run Completed:")
    print(f"   Problems solved:  {solved_count}")
    print(f"   Problems failed:  {failed_count}")
    print(f"   Problems skipped: {skipped_count} (already had solutions)")
    print("=" * 60)


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
  python solve.py --batch 5 --no-submit
  python solve.py --batch 10 --difficulty easy
  python solve.py --continuous --no-submit
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
        "--limit",
        "-l",
        type=int,
        default=None,
        metavar="N",
        help=f"Number of problems to solve (default from .env/config: {config.DEFAULT_BATCH_LIMIT})",
    )
    parser.add_argument(
        "--batch",
        "-b",
        type=int,
        nargs="?",
        const=config.DEFAULT_BATCH_LIMIT,
        default=None,
        metavar="N",
        help=f"Solve N problems sequentially (defaults to {config.DEFAULT_BATCH_LIMIT} if N is omitted)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously, solving problems one after another until stopped (Ctrl+C)",
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard", "EASY", "MEDIUM", "HARD"],
        default=None,
        help="Filter batch/continuous problems by difficulty (easy, medium, hard)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=config.DEFAULT_DELAY,
        help=f"Delay in seconds between problems in batch mode (default: {config.DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-solve problems even if they already exist in solutions/",
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

    # Determine batch limit
    batch_count = None
    if args.limit is not None:
        batch_count = args.limit
    elif args.batch is not None:
        batch_count = args.batch

    is_batch_or_continuous = (batch_count is not None) or args.continuous

    # Interactive fallback if run without arguments in a terminal
    if not args.problem and not args.daily and not is_batch_or_continuous:
        if sys.stdin.isatty():
            print("\n=== LeetCode Autonomous Solver ===")
            print("No problem specified. Choose what to do:")
            print("  1. Solve a specific problem (enter slug or URL)")
            print("  2. Solve today's Daily Challenge (--daily)")
            print(f"  3. Batch solve problems (default limit: {config.DEFAULT_BATCH_LIMIT})")
            print("  4. Continuous mode (solve until stopped)")
            choice = input("\nEnter choice [1/2/3/4] (default: 3): ").strip()

            if choice == "1":
                args.problem = input("Enter problem slug or URL: ").strip()
            elif choice == "2":
                args.daily = True
            elif choice == "4":
                args.continuous = True
                is_batch_or_continuous = True
            else:
                raw_lim = input(f"How many problems would you like to solve? [default: {config.DEFAULT_BATCH_LIMIT}]: ").strip()
                batch_count = int(raw_lim) if raw_lim.isdigit() else config.DEFAULT_BATCH_LIMIT
                is_batch_or_continuous = True
        else:
            parser.print_help()
            print(f"\n[ERROR] Please specify a problem slug, --daily, --limit <N>, or --continuous")
            sys.exit(1)

    if is_batch_or_continuous:
        count = None if args.continuous else batch_count
        run_batch(
            count=count,
            difficulty=args.difficulty,
            no_submit=args.no_submit,
            retries=args.retries,
            delay=args.delay,
            skip_solved=not args.force,
        )
    else:
        run_agent(
            slug=args.problem,
            daily=args.daily,
            no_submit=args.no_submit,
            retries=args.retries,
        )


if __name__ == "__main__":
    main()
