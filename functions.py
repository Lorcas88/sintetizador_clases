"""Module for batch processing transcripts and generating markdown documentation.

Handles prompt building, token counting, API calls with retry logic, text splitting,
and batch response parsing for efficient processing of multiple class transcripts
using Google's Gemini API.
"""
import re
import time

# Maximum total tokens allowed per API request
MAX_TOTAL_TOKENS_PER_REQUEST = 250000
# Tokens reserved for model output per class (for budget estimation)
OUTPUT_TOKEN_BUDGET_PER_CLASS = 10000
# Maximum tokens available for input (total minus all output budgets)
MAX_INPUT_TOKENS_PER_REQUEST = MAX_TOTAL_TOKENS_PER_REQUEST - OUTPUT_TOKEN_BUDGET_PER_CLASS


def build_prompt_instructions():
    """Generate the base instruction prompt for markdown generation.
    
    Creates a reusable instruction block that guides the API to generate
    formatted markdown documents suitable for NotebookLM in Spanish,
    based on programming class transcripts.
    
    Returns:
        str: Instruction text defining output format and requirements
    """
    return (
        "Eres un asistente experto en resumenes de clases de programacion. "
        "Genera un documento en markdown en espanol listo para NotebookLM. "
        "Usa solo el contenido provisto para el resumen principal. "
        "Si una definicion o ejemplo no aparece en clase, infierelo con "
        "conocimiento tecnico estandar. "
        "No inventes temas que no esten en la transcripcion.\n\n"
        "Salida obligatoria por cada clase, con este formato exacto:\n"
        "# Archivo: <nombre>\n"
        "## Resumen\n"
        "- 4 a 6 bullets con las ideas centrales.\n\n"
        "## Temas vistos\n"
        "- Lista de temas vistos con descripcion breve.\n\n"
        "## Terminos de programacion\n"
        "- Termino: definicion. Ejemplo: ejemplo breve.\n\n"
        "## Puntos clave\n"
        "- 6 a 10 bullets con los puntos mas importantes.\n\n"
        "## Notas detalladas\n"
        "- Notas en bullets organizadas por tema.\n\n"
    )


def build_batch_prompt(class_items):
    """Build a batch prompt for processing multiple class transcripts in one API call.
    
    Combines instruction prompt with all class items formatted as separate blocks,
    allowing efficient batch processing of multiple related classes in a single request.
    
    Args:
        class_items (list[dict]): List of dictionaries with 'title' and 'text' keys
                                 (title: class name, text: transcript content)
    
    Returns:
        str: Complete batch prompt ready for API consumption
    """
    header = build_prompt_instructions()
    blocks = []
    for item in class_items:
        blocks.append(
            "===== CLASE =====\n"
            f"Nombre: {item['title']}\n"
            "Transcripcion:\n"
            f"{item['text']}\n"
        )
    return header + "\n".join(blocks)


def extract_total_tokens(count_response):
    """Extract total token count from various Gemini API response formats.
    
    Normalizes token extraction from different response types that may return
    total tokens as an object attribute, dictionary key, or camelCase variant.
    
    Args:
        count_response: Response from count_tokens API (object or dict)
    
    Returns:
        int: Total number of tokens
    
    Raises:
        ValueError: If total_tokens cannot be extracted from the response
    """
    if hasattr(count_response, "total_tokens"):
        return count_response.total_tokens
    if isinstance(count_response, dict) and "total_tokens" in count_response:
        return count_response["total_tokens"]
    if isinstance(count_response, dict) and "totalTokens" in count_response:
        return count_response["totalTokens"]
    raise ValueError("Unable to read total_tokens from count_tokens response.")


def count_tokens(client, model_name, prompt):
    """Count the total number of input tokens for a given prompt.
    
    Used to estimate token usage before making API calls to manage quota limits
    and validate that requests will fit within token budgets.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model to use for counting
        prompt (str): The prompt text to count tokens for
    
    Returns:
        int: Number of tokens in the prompt
    """
    response = client.models.count_tokens(model=model_name, contents=prompt)
    return extract_total_tokens(response)


def generate_with_retry(client, model_name, prompt, limiter, input_tokens):
    """Generate API response with exponential backoff retry logic and quota checks.
    
    Attempts to generate content, waiting for rate limiter quota before attempting,
    then retries with exponential backoff (doubling wait time) on transient failures
    up to a maximum of 5 attempts. Records successful request in the rate limiter.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model to use for generation
        prompt (str): The prompt to send to the API
        limiter (GeminiRateLimiter): Rate limiter instance for quota management
        input_tokens (int): Number of input tokens used (for quota tracking)
    
    Returns:
        str: The generated text response from the model
    
    Raises:
        Exception: If maximum retry attempts exhausted without successful response
    """
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


def split_text_by_lines(text, max_chars):
    """Split text into chunks while respecting line boundaries and character limits.
    
    Attempts to keep text chunks at or under max_chars while preserving complete lines.
    If a single line exceeds max_chars, that line is split independently to ensure
    no data loss. Used to prepare text for token-limited API calls while maintaining
    readability of chunks.
    
    Args:
        text (str): The text to split
        max_chars (int): Maximum characters per chunk (soft limit at line boundaries)
    
    Returns:
        list[str]: List of non-empty text chunks, each at or under max_chars when possible
    """
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
    """Intelligently split a transcript to fit within API token limits.
    
    Starts with the full transcript and progressively reduces chunk size until
    each part with its formatted prompt fits within token limits. Uses token counting
    to estimate suitable chunk sizes and up to 5 iterations of refinement to find
    the optimal balance between prompt complexity and chunk count.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model for token counting
        title (str): Title of the class/session for prompt building
        transcript (str): Full transcript to potentially split
    
    Returns:
        list[str]: List of transcript parts, each fitting within token limits.
                  Returns single-item list if transcript fits without splitting.
    """
    prompt = build_batch_prompt([{"title": title, "text": transcript}])
    input_tokens = count_tokens(client, model_name, prompt)
    if input_tokens + OUTPUT_TOKEN_BUDGET_PER_CLASS <= MAX_TOTAL_TOKENS_PER_REQUEST:
        return [transcript]

    ratio = input_tokens / max(1, len(transcript))
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


def parse_batch_response(response_text, expected_titles):
    """Parse batch API response into individual class documentation blocks.
    
    Extracts separate markdown sections from the API response, matching each
    markdown heading (# Archivo: title) to its corresponding content block.
    Optionally filters results to only include expected titles if provided.
    
    Args:
        response_text (str): Full response text from batch API call containing
                            multiple markdown class sections
        expected_titles (list[str]): Optional list of titles to filter by.
                                    If provided, only matching titles are returned.
                                    If empty/None, all parsed blocks are returned.
    
    Returns:
        dict: Dictionary mapping class titles to their markdown content blocks
    """
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
    """Generate markdown documentation for multiple classes in a single batch request.
    
    Processes a batch of class items together in one API call for efficiency,
    counting tokens first to validate they fit within budget constraints.
    Parses the batch response to extract individual class documentation blocks.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model to use for generation
        class_items (list[dict]): List of class items with 'title' and 'text' keys
        limiter (GeminiRateLimiter): Rate limiter for quota management
    
    Returns:
        tuple: (parsed_blocks_dict, full_response_text)
               - parsed_blocks_dict: Dictionary mapping titles to markdown content
               - full_response_text: Complete raw response from API for debugging
    
    Raises:
        SystemExit: If batch token requirements exceed maximum allowed budget
    """
    prompt = build_batch_prompt(class_items)
    input_tokens = count_tokens(client, model_name, prompt)
    output_budget = OUTPUT_TOKEN_BUDGET_PER_CLASS * len(class_items)
    if input_tokens + output_budget > MAX_TOTAL_TOKENS_PER_REQUEST:
        raise SystemExit("Batch exceeds token budget.")

    output_text = generate_with_retry(client, model_name, prompt, limiter, input_tokens)
    titles = [item["title"] for item in class_items]
    return parse_batch_response(output_text, titles), output_text
