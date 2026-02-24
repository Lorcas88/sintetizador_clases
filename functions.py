"""Module for generating markdown documentation from transcripts using Gemini API.

Handles prompt building, token counting, API calls with retry logic, and text splitting
for managing token limits across large transcripts.
"""
import re
import time

# Maximum total tokens allowed per API request
MAX_TOTAL_TOKENS_PER_REQUEST = 250000
# Tokens reserved for model output (must be available in budget)
OUTPUT_TOKEN_BUDGET_PER_FILE = 10000
# Maximum tokens available for input (total minus output budget)
MAX_INPUT_TOKENS_PER_REQUEST = MAX_TOTAL_TOKENS_PER_REQUEST - OUTPUT_TOKEN_BUDGET_PER_FILE


def build_prompt(title, transcript, part_number=None, total_parts=None):
    """Build a comprehensive prompt for generating markdown notes from a transcript.
    
    Creates a detailed prompt instructing the API to generate structured markdown
    documentation suitable for junior/trainee programmers based on the transcript.
    Supports splitting transcripts into multiple parts for token management.
    """
    part_suffix = ""
    if part_number and total_parts:
        part_suffix = f" (Parte {part_number} de {total_parts})"

    return f"""
Genera un documento en markdown en espanol orientado a un programador trainee/junior.

Usa unicamente la transcripcion proporcionada como fuente principal.
Si una definicion no aparece explicitamente, infierela con conocimiento tecnico estandar.
No inventes temas que no esten en la clase.

Estilo:
- Tecnico pero claro.
- Preciso en terminologia.
- Sin relleno ni redundancias.
- Enfocado en comprension practica.
- Prioriza utilidad para alguien que esta aprendiendo programacion profesionalmente.

Incluye ejemplos practicos siempre que el concepto sea programable.
Los ejemplos deben:
- Ser realistas.
- Reflejar buenas practicas.
- Tener contexto minimo para entenderlos.
- Usar el lenguaje correspondiente a la clase.
Si no se puede inferir el lenguaje, usa pseudocodigo claro.
Si el concepto no aplica a codigo, no incluyas ejemplo.

Estructura obligatoria:

# Archivo: {title}{part_suffix}

## Resumen
- 4 a 6 bullets con las ideas centrales de la clase.
- Deben reflejar aprendizaje tecnico real, no frases genericas.

## Temas vistos
- Lista estructurada de los temas tratados.
- Cada tema debe tener una descripcion breve pero tecnica (1-2 lineas).

## Conceptos y notas detalladas
Para cada concepto relevante:

- Termino:
  Definicion tecnica clara.
  Explicacion practica (para que se usa, por que importa).
  Posibles errores comunes si aplica.
  Ejemplo practico:

```lenguaje
codigo aqui
```

## Puntos clave
- 6 a 10 bullets con los puntos mas importantes.
- Deben servir como checklist de estudio.
- Evita frases motivacionales o genericas.

Transcripcion:
{transcript}
"""

# Normalize the response of count_tokens to a single integer output.
def extract_total_tokens(count_response):
    """Extract total token count from various API response formats.
    
    Handles multiple response formats that may return total tokens as an attribute,
    dictionary key, or variation.
    
    Args:
        count_response: Response object/dict from count_tokens API call
    
    Returns:
        int: Total tokens in the response
    
    Raises:
        ValueError: If total_tokens cannot be extracted from the response
    """
    # If the response it's an object with total_tokens attribute
    if hasattr(count_response, "total_tokens"):
        return count_response.total_tokens
    # If the response it's a dictionarie with total_tokens key
    if isinstance(count_response, dict) and "total_tokens" in count_response:
        return count_response["total_tokens"]
    # If the response it's a dictionarie with totalTokens key
    if isinstance(count_response, dict) and "totalTokens" in count_response:
        return count_response["totalTokens"]
    raise ValueError("Unable to read total_tokens from count_tokens response.")

# Count input tokens for a given prompt.
def count_tokens(client, model_name, prompt):
    """Count the total number of input tokens for a given prompt.
    
    Used to estimate token usage before making API calls to manage quota limits.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model to use for counting
        prompt (str): The prompt text to count tokens for
    
    Returns:
        int: Number of tokens in the prompt
    """
    response = client.models.count_tokens(model=model_name, contents=prompt)
    return extract_total_tokens(response)


# Generate model output with retry/backoff and quota tracking.
def generate_with_retry(client, model_name, prompt, limiter, input_tokens):
    """Generate API response with exponential backoff retry logic and quota checks.
    
    Attempts to generate content, waiting for rate limiter quota if needed,
    and retries with exponential backoff on failures up to max attempts.
    Records the request in the rate limiter for quota tracking.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model to use
        prompt (str): The prompt to send to the API
        limiter (GeminiRateLimiter): Rate limiter instance for quota management
        input_tokens (int): Number of input tokens (for quota tracking)
    
    Returns:
        str: The text response from the model
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


# Split text into chunks by line boundaries, respecting max_chars when possible.
def split_text_by_lines(text, max_chars):
    """Split text into chunks while respecting line boundaries and character limits.
    
    Attempts to keep text chunks at or under max_chars while preserving complete
    lines. If a single line exceeds max_chars, that line is split independently.
    Used to prepare text for token-limited API calls.
    
    Args:
        text (str): The text to split
        max_chars (int): Maximum characters per chunk (soft limit at line boundaries)
    
    Returns:
        list[str]: List of non-empty text chunks
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
    """Split a transcript to fit within API token limits.
    
    Starts with the full transcript and progressively reduces chunk size until
    each part with its prompt fits within token limits. Uses exponential reduction
    of chunk size to find optimal balance between prompt complexity and chunk count.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model for token counting
        title (str): Title of the class/session for prompt building
        transcript (str): Full transcript to split
    
    Returns:
        list[str]: List of transcript parts, each fitting within token limits
    """
    full_prompt = build_prompt(title, transcript)
    input_tokens = count_tokens(client, model_name, full_prompt)
    if input_tokens + OUTPUT_TOKEN_BUDGET_PER_FILE <= MAX_TOTAL_TOKENS_PER_REQUEST:
        return [transcript]

    ratio = input_tokens / max(1, len(transcript))
    max_chars = int((MAX_INPUT_TOKENS_PER_REQUEST / ratio) * 0.9)
    max_chars = max(1000, max_chars)

    for _ in range(5):
        parts = split_text_by_lines(transcript, max_chars)
        too_large = False
        total_parts = len(parts)
        for i, part in enumerate(parts, start=1):
            part_prompt = build_prompt(title, part, i, total_parts)
            part_tokens = count_tokens(client, model_name, part_prompt)
            if part_tokens + OUTPUT_TOKEN_BUDGET_PER_FILE > MAX_TOTAL_TOKENS_PER_REQUEST:
                too_large = True
                break

        if not too_large:
            return parts

        max_chars = int(max_chars * 0.8)
        if max_chars < 500:
            break

    return split_text_by_lines(transcript, max_chars)


# Generate markdown output for each transcript part.
def generate_markdown(client, model_name, title, transcript, limiter):
    """Generate markdown documentation for a transcript with automatic splitting.
    
    Splits the transcript as needed to fit token limits, generates markdown
    output for each part, and combines results. Handles part numbering when
    transcript is split into multiple chunks.
    
    Args:
        client: Initialized Gemini API client
        model_name (str): Name of the model to use
        title (str): Title of the class/session
        transcript (str): The transcript to process
        limiter (GeminiRateLimiter): Rate limiter for quota management
    
    Returns:
        list[str]: List of generated markdown output (one per transcript part)
    """
    parts = split_transcript_for_limit(client, model_name, title, transcript)
    total_parts = len(parts)
    outputs = []

    for i, part in enumerate(parts, start=1):
        if total_parts > 1:
            prompt = build_prompt(title, part, i, total_parts)
        else:
            prompt = build_prompt(title, part)

        input_tokens = count_tokens(client, model_name, prompt)
        print(input_tokens)
        if input_tokens + OUTPUT_TOKEN_BUDGET_PER_FILE > MAX_TOTAL_TOKENS_PER_REQUEST:
            raise SystemExit(
                "Input exceeds token budget even after splitting. "
                "Consider more aggressive local trimming."
            )

        output_text = generate_with_retry(client, model_name, prompt, limiter, input_tokens)
        outputs.append(output_text)

    return outputs
