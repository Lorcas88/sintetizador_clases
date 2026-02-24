
from cleaning_functions import clean_transcript
from file_functions import merge_parts
from functions import (
    MAX_TOTAL_TOKENS_PER_REQUEST,
    OUTPUT_TOKEN_BUDGET_PER_CLASS,
    build_batch_prompt,
    count_tokens,
    split_transcript_for_limit,
)

def build_class_items(client, model_name, grouped, clean_dir):
    """Merge, clean, and token-split grouped transcripts into "class items".

    Each returned item has: title, text, output_path. A class may expand into
    multiple items if it must be split to fit token limits.
    """
    class_items = []
    for class_key, part_entries in grouped.items():
        merged_text = merge_parts(part_entries)
        if not merged_text:
            continue

        cleaned = clean_transcript(merged_text)
        if not cleaned:
            continue

        clean_path = os.path.join(clean_dir, f"{class_key}.clean.txt")
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(cleaned + "\n")

        parts = split_transcript_for_limit(client, model_name, class_key, cleaned)
        if len(parts) == 1:
            class_items.append(
                {
                    "title": class_key,
                    "text": parts[0],
                    "output_path": os.path.join(OUTPUT_FOLDER, f"{class_key}.md"),
                }
            )
        else:
            total_parts = len(parts)
            for index, part in enumerate(parts, start=1):
                title = f"{class_key} (Parte {index} de {total_parts})"
                out_name = f"{class_key}.parte_{index:02d}.md"
                class_items.append(
                    {
                        "title": title,
                        "text": part,
                        "output_path": os.path.join(OUTPUT_FOLDER, out_name),
                    }
                )

    return class_items


def build_batches(client, model_name, class_items):
    """Greedily pack class items into batches that fit the token budget.

    Budget = input_tokens(prompt) + OUTPUT_TOKEN_BUDGET_PER_CLASS * n_items.
    """
    batches = []
    current = []

    for item in class_items:
        tentative = current + [item]
        prompt = build_batch_prompt(
            [{"title": c["title"], "text": c["text"]} for c in tentative]
        )
        input_tokens = count_tokens(client, model_name, prompt)
        output_budget = OUTPUT_TOKEN_BUDGET_PER_CLASS * len(tentative)
        if input_tokens + output_budget <= MAX_TOTAL_TOKENS_PER_REQUEST:
            current.append(item)
        else:
            if current:
                batches.append(current)
            current = [item]

    if current:
        batches.append(current)

    return batches


def write_batch_outputs(output_dir, batch, parsed, raw_response, batch_index):
    """Write per-item Markdown files from a batch response.

    If a section is missing/unparseable, write a `batch_fallback_XX.md` with the
    raw API response for debugging.
    """
    if parsed:
        for item in batch:
            content = parsed.get(item["title"])
            if content:
                with open(item["output_path"], "w", encoding="utf-8") as f:
                    f.write(content + "\n")
            else:
                print(
                    f"Warning: Missing section for {item['title']}. "
                    "Writing batch fallback."
                )
                fallback = os.path.join(output_dir, f"batch_fallback_{batch_index:02d}.md")
                with open(fallback, "w", encoding="utf-8") as f:
                    f.write(raw_response + "\n")
                break
    else:
        fallback = os.path.join(output_dir, f"batch_fallback_{batch_index:02d}.md")
        with open(fallback, "w", encoding="utf-8") as f:
            f.write(raw_response + "\n")