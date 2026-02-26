"""Transcript splitting utilities for managing token limits."""
from prompting import build_batch_prompt
from token_utils import count_tokens

# Maximum total tokens allowed per API request
MAX_TOTAL_TOKENS_PER_REQUEST = 250000
# Tokens reserved for model output per class (for budget estimation)
OUTPUT_TOKEN_BUDGET_PER_CLASS = 10000
# Maximum tokens available for input (total minus all output budgets)
MAX_INPUT_TOKENS_PER_REQUEST = MAX_TOTAL_TOKENS_PER_REQUEST - OUTPUT_TOKEN_BUDGET_PER_CLASS

def split_text_by_lines(text, max_chars):
    """Split text into chunks respecting line boundaries (soft limit on max_chars)."""
    if max_chars <= 0:
        return [text]

    parts = []
    current = []
    current_len = 0
    for line in text.splitlines():
        if len(line) > max_chars:
            if current:
                parts.append("\n".join(current).strip())
                current = []
                current_len = 0

            for i in range(0, len(line), max_chars):
                chunk = line[i : i + max_chars]
                parts.append(chunk.strip())
            continue

        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            parts.append("\n".join(current).strip())
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        parts.append("\n".join(current).strip())

    return [part for part in parts if part]

def split_transcript_for_limit(client, model_name, title, transcript):
    """Iteratively split transcript to fit token limits (up to 5 refinement iterations)."""
    prompt = build_batch_prompt([{"title": title, "text": transcript}])
    with open("test.txt", "a", encoding="utf-8") as file:
        file.write(transcript + "\n")

    # Call the method API to know how many tokens will be used
    input_tokens = count_tokens(client, model_name, prompt)
    if input_tokens + OUTPUT_TOKEN_BUDGET_PER_CLASS <= MAX_TOTAL_TOKENS_PER_REQUEST:
        return [transcript]

    # It use max with 1 and len, in case transcript returns 0
    ratio = input_tokens / max(1, len(transcript))
    print(ratio)
    # return
    max_chars = int((MAX_INPUT_TOKENS_PER_REQUEST / ratio) * 0.9)
    max_chars = max(1000, max_chars)

    for _ in range(5):
        parts = split_text_by_lines(transcript, max_chars)
        too_large = False
        total_parts = len(parts)
        for i, part in enumerate(parts, start=1):
            part_title = f"{title} (Parte {i} de {total_parts})"
            part_prompt = build_batch_prompt([{"title": part_title, "text": part}])
            part_tokens = count_tokens(client, model_name, part_prompt)
            if part_tokens + OUTPUT_TOKEN_BUDGET_PER_CLASS > MAX_TOTAL_TOKENS_PER_REQUEST:
                too_large = True
                break

        if not too_large:
            return parts

        max_chars = int(max_chars * 0.8)
        if max_chars < 500:
            break

    return split_text_by_lines(transcript, max_chars)