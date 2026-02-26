"""API operations for Gemini: generation, parsing, and batch processing."""
import re
import time

from prompting import build_batch_prompt
from splitting import MAX_TOTAL_TOKENS_PER_REQUEST, OUTPUT_TOKEN_BUDGET_PER_CLASS
from token_utils import count_tokens


def generate_with_retry(client, model_name, prompt, limiter, input_tokens):
    """Generate content with quota checks and exponential backoff (up to 5 attempts)."""
    max_attempts = 5
    wait_seconds = 2

    for attempt in range(1, max_attempts + 1):
        limiter.wait_for_quota(input_tokens)
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text.strip()
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(wait_seconds)
            wait_seconds = wait_seconds * 2
        finally:
            limiter.record_request(input_tokens)


def parse_batch_response(response_text, expected_titles):
    """Extract Markdown blocks by title from batch response, optionally filtering."""
    blocks = {}
    pattern = re.compile(r"^# Archivo:\s*(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(response_text))
    if not matches:
        return blocks

    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(response_text)
        blocks[title] = response_text[start:end].strip()

    if expected_titles:
        filtered = {}
        for title in expected_titles:
            if title in blocks:
                filtered[title] = blocks[title]
        return filtered

    return blocks


def generate_batch(client, model_name, class_items, limiter):
    """Generate Markdown for a batch; return parsed blocks dict and raw response."""
    prompt = build_batch_prompt(class_items)
    input_tokens = count_tokens(client, model_name, prompt)
    output_budget = OUTPUT_TOKEN_BUDGET_PER_CLASS * len(class_items)
    if input_tokens + output_budget > MAX_TOTAL_TOKENS_PER_REQUEST:
        raise SystemExit("Batch exceeds token budget.")

    output_text = generate_with_retry(client, model_name, prompt, limiter, input_tokens)
    titles = [item["title"] for item in class_items]
    return parse_batch_response(output_text, titles), output_text
