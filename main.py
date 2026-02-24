"""Batch pipeline to convert transcript files into Markdown notes via Gemini.

- Discovers and merges multi-part transcripts
- Cleans and token-splits content
- Builds token-safe batches and writes Markdown outputs
"""
import os

from dotenv import load_dotenv
from google import genai

from functions import generate_batch
from file_functions import collect_transcript_files, group_class_files
from batch_functions import build_class_items, build_batches, write_batch_outputs
from rate_limiter import GeminiRateLimiter

# Load environment variables from .env file for API credentials
load_dotenv()

# Gemini model to use for generating markdown (adjust version as needed)
DEFAULT_MODEL = "gemini-2.5-flash"
# Directory where transcript files are stored (scanned recursively)
INPUT_FOLDER = "transcripts"
# Directory where generated markdown outputs are saved
OUTPUT_FOLDER = "notebooklm_output"

def main():
    """Run the end-to-end transcript -> Markdown batch pipeline.

    Validates credentials, prepares directories, processes transcripts in token-safe
    batches, and writes outputs to OUTPUT_FOLDER.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing GEMINI_API_KEY environment variable. "
            "Set it or create a .env and load it before running."
        )

    os.environ["GOOGLE_API_KEY"] = api_key

    # Initialize Gemini API client with credentials
    input_dir = INPUT_FOLDER
    output_dir = OUTPUT_FOLDER
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    clean_dir = os.path.join(output_dir, "_clean")
    os.makedirs(clean_dir, exist_ok=True)

    # Initialize API client and rate limiter
    client = genai.Client()
    limiter = GeminiRateLimiter(
        requests_per_minute=5,
        input_tokens_per_minute=250000,
        requests_per_day=20,
    )

    # Collect all transcript files from input directory
    all_files = collect_transcript_files(input_dir)
    if not all_files:
        raise SystemExit(
            f"No transcript files found in {input_dir}. "
            "Add .txt or .md files and retry."
        )

    # Group files by class and process them
    grouped = group_class_files(all_files)
    class_items = build_class_items(client, DEFAULT_MODEL, grouped, clean_dir)
    if not class_items:
        raise SystemExit("No usable content found after cleaning.")

    # Partition into batches and process via API
    batches = build_batches(client, DEFAULT_MODEL, class_items)

    batch_index = 1
    for batch in batches:
        batch_items = [{"title": c["title"], "text": c["text"]} for c in batch]
        parsed, raw_response = generate_batch(
            client,
            DEFAULT_MODEL,
            batch_items,
            limiter,
        )
        write_batch_outputs(output_dir, batch, parsed, raw_response, batch_index)
        batch_index += 1

    print(f"Processed {len(class_items)} class item(s). Output in: {output_dir}")


if __name__ == "__main__":
    main()
