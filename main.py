import os
from dotenv import load_dotenv
from google import genai
from functions import generate_markdown
from cleaning_functions import clean_transcript
from rate_limiter import GeminiRateLimiter

load_dotenv()  # loads variables from .env

DEFAULT_MODEL = "gemini-2.5-flash"
INPUT_FOLDER = "transcripts"
OUTPUT_FOLDER = "notebooklm_output"
SUPPORTED_SUFFIXES = (".txt", ".md")

def main():
    # api_key = os.getenv("GEMINI_API_KEY")
    # if not api_key:
    #     raise SystemExit(
    #         "Missing GEMINI_API_KEY environment variable. "
    #         "Set it or create a .env and load it before running."
    #     )

    # os.environ["GOOGLE_API_KEY"] = api_key

    # client = genai.Client()
    # limiter = GeminiRateLimiter(
    #     requests_per_minute=5,
    #     input_tokens_per_minute=250000,
    #     requests_per_day=20,
    # )

    # Check folders and create them if they don't exist
    input_dir = INPUT_FOLDER
    output_dir = OUTPUT_FOLDER
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    clean_dir = os.path.join(output_dir, "_clean")
    os.makedirs(clean_dir, exist_ok=True)

    all_files = []
    for root, _, names in os.walk(input_dir):
        for name in names:
            if name.lower().endswith(SUPPORTED_SUFFIXES):
                all_files.append(os.path.join(root, name))

    all_files.sort()
    if not all_files:
        raise SystemExit(
            f"No transcript files found in {input_dir}. "
            "Add .txt or .md files and retry."
        )

    for file_path in all_files:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # Save all the text of teh file into transcript variable
            transcript = f.read().strip()
            if not transcript:
                continue

            filename = os.path.splitext(os.path.basename(file_path))[0]
            title = filename.replace("_", " ").strip() or "Clase"
            cleaned = clean_transcript(transcript)
            if not cleaned:
                continue

        clean_path = os.path.join(clean_dir, f"{filename}.clean.txt")
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(cleaned + "\n")

    #     outputs = generate_markdown(
    #         client,
    #         DEFAULT_MODEL,
    #         title,
    #         cleaned,
    #         limiter,
    #     )

    #     if len(outputs) == 1:
    #         out_name = f"{filename}.notebooklm.md"
    #         out_path = os.path.join(output_dir, out_name)
    #         with open(out_path, "w", encoding="utf-8") as f:
    #             f.write(outputs[0] + "\n")
    #     else:
    #         for index, text in enumerate(outputs, start=1):
    #             out_name = f"{filename}.parte_{index:02d}.notebooklm.md"
    #             out_path = os.path.join(output_dir, out_name)
    #             with open(out_path, "w", encoding="utf-8") as f:
    #                 f.write(text + "\n")

    # print(f"Processed {len(all_files)} file(s). Output in: {output_dir}")

if __name__ == "__main__":
    main()
