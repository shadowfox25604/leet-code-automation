"""
Gemini AI solution generator.

Sends LeetCode problems to Google Gemini and extracts clean,
submission-ready Python solutions.
"""

import re
from google import genai
from google.genai import types

import config


def _get_client():
    """Create and return a Gemini client."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "Missing GEMINI_API_KEY in .env\n"
            "Get one free at: https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=config.GEMINI_API_KEY)


SYSTEM_PROMPT = """You are an expert competitive programmer.
You solve LeetCode problems in Python.

RULES:
1. Return ONLY the Solution class with the required method.
2. Do NOT include any imports unless absolutely necessary (e.g., from typing import List is already available on LeetCode).
3. Do NOT include test code, print statements, or if __name__ == '__main__' blocks.
4. Do NOT include markdown formatting, code fences, or explanations.
5. Optimize for both correctness and efficiency.
6. Handle edge cases carefully (empty arrays, single elements, negative numbers, etc.).
7. Use Pythonic solutions when possible.
8. If you need to import something (like collections, heapq, bisect, etc.), put imports ABOVE the class.

Your output should be ONLY valid Python code that can be directly submitted to LeetCode."""


def _clean_code(raw_response):
    """
    Strip markdown code fences and any non-code text from Gemini's response.
    Returns clean Python code ready for submission.
    """
    text = raw_response.strip()

    # Remove markdown code fences: ```python ... ``` or ``` ... ```
    text = re.sub(r"^```(?:python|python3)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)

    # Remove any leading/trailing backticks that might remain
    text = text.strip("`").strip()

    return text


def generate_solution(problem):
    """
    Generate a Python solution for a LeetCode problem using Gemini.

    Args:
        problem: A dict from leetcode_client.fetch_problem() containing
                 title, content, difficulty, python_template, topicTags, etc.

    Returns:
        Clean Python code string ready for submission.
    """
    client = _get_client()

    user_prompt = f"""Solve this LeetCode problem:

Title: {problem['title']}
Difficulty: {problem['difficulty']}
Topics: {', '.join(problem.get('topicTags', []))}

Description:
{problem['content']}

Example Test Cases:
{problem.get('exampleTestcases', 'N/A')}

Code Template (you MUST use this exact class and method signature):
{problem['python_template']}

Return ONLY the complete Solution class with the implemented method."""

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
        ),
    )

    return _clean_code(response.text)


def generate_solution_with_feedback(problem, previous_code, error_info):
    """
    Generate a corrected solution after a failed submission.

    Sends the original problem, the failed code, and the error details
    to Gemini so it can reason about what went wrong and fix it.

    Args:
        problem: The original problem dict.
        previous_code: The Python code that failed.
        error_info: A dict from leetcode_client.submit_solution() with
                    status, input, expected_output, code_output, etc.

    Returns:
        Clean Python code string ready for re-submission.
    """
    client = _get_client()

    # Build a detailed error description
    error_parts = [f"Status: {error_info.get('status', 'Unknown')}"]

    if error_info.get("total_correct") is not None:
        error_parts.append(
            f"Passed: {error_info['total_correct']}/{error_info.get('total_testcases', '?')} test cases"
        )
    if error_info.get("input"):
        error_parts.append(f"Failed Input: {error_info['input']}")
    if error_info.get("expected_output"):
        error_parts.append(f"Expected Output: {error_info['expected_output']}")
    if error_info.get("code_output"):
        error_parts.append(f"Your Output: {error_info['code_output']}")
    if error_info.get("runtime_error"):
        error_parts.append(f"Runtime Error: {error_info['runtime_error']}")
    if error_info.get("compile_error"):
        error_parts.append(f"Compile Error: {error_info['compile_error']}")

    error_description = "\n".join(error_parts)

    user_prompt = f"""Your previous solution to this LeetCode problem was WRONG. Fix it.

Problem: {problem['title']} ({problem['difficulty']})

Description:
{problem['content']}

Code Template (you MUST use this exact class and method signature):
{problem['python_template']}

Your PREVIOUS (WRONG) solution:
{previous_code}

Error Details:
{error_description}

Think step by step about what went wrong and why.
Then return ONLY the corrected Solution class.
Make sure to handle the failing test case correctly."""

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
        ),
    )

    return _clean_code(response.text)
