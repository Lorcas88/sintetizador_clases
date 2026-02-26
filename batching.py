"""Batch organization and processing for multiple transcripts."""
import os

from cleaning_functions import clean_transcript
from file_functions import merge_parts
from prompting import build_batch_prompt
from splitting import (
    MAX_TOTAL_TOKENS_PER_REQUEST,
    OUTPUT_TOKEN_BUDGET_PER_CLASS,
    split_transcript_for_limit,
)
from token_utils import count_tokens

OUTPUT_FOLDER = "notebooklm_output"

def build_class_items(client, model_name, grouped, merge_dir, clean_dir):
    """Merge, clean, and token-split grouped transcripts; expand items if needed for limits."""
    class_items = []
    # Iterates through the dictionary
    for class_key, part_entries in grouped.items():
        # Merged the classes that contains more than one file and turn it into a one file
        merged_text = merge_parts(part_entries)
        if not merged_text:
            continue

        merged_file = os.path.join(merge_dir, f"{class_key}.txt")
        with open(merged_file, "w", encoding="utf-8") as f:
            f.write(merged_text + "\n")
        
        cleaned = clean_transcript(merged_text)
        if not cleaned:
            continue
        
        clean_path = os.path.join(clean_dir, f"{class_key}.clean.txt")
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(cleaned + "\n")
        
        parts = split_transcript_for_limit(client, model_name, class_key, cleaned)
        print(parts)
        return
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
    """Greedily pack class items into batches respecting token budget constraints."""
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
    """Write per-item Markdown files; fallback to batch_fallback_XX.md on parse errors."""
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