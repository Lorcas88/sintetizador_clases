import time

MAX_TOTAL_TOKENS_PER_REQUEST = 250000
OUTPUT_TOKEN_BUDGET_PER_FILE = 10000
MAX_INPUT_TOKENS_PER_REQUEST = MAX_TOTAL_TOKENS_PER_REQUEST - OUTPUT_TOKEN_BUDGET_PER_FILE

def build_prompt(title, transcript, part_number=None, total_parts=None):
    part_suffix = ""
    if part_number and total_parts:
        part_suffix = f" (Parte {part_number} de {total_parts})"

    return f"""
Genera un documento en markdown en español orientado a un programador trainee/junior.

Usa únicamente la transcripción proporcionada como fuente principal.
Si una definición no aparece explícitamente, infiérela con conocimiento técnico estándar.
No inventes temas que no estén en la clase.

Estilo:
- Técnico pero claro.
- Preciso en terminología.
- Sin relleno ni redundancias.
- Enfocado en comprensión práctica.
- Prioriza utilidad para alguien que está aprendiendo programación profesionalmente.

Incluye ejemplos prácticos siempre que el concepto sea programable.
Los ejemplos deben:
- Ser realistas.
- Reflejar buenas prácticas.
- Tener contexto mínimo para entenderlos.
- Usar el lenguaje correspondiente a la clase.
Si no se puede inferir el lenguaje, usa pseudocódigo claro.
Si el concepto no aplica a código, no incluyas ejemplo.

Estructura obligatoria:

# Archivo: {title}{part_suffix}

## Resumen
- 4 a 6 bullets con las ideas centrales de la clase.
- Deben reflejar aprendizaje técnico real, no frases genéricas.

## Temas vistos
- Lista estructurada de los temas tratados.
- Cada tema debe tener una descripción breve pero técnica (1–2 líneas).

## Conceptos y notas detalladas
Para cada concepto relevante:

- Término:
  Definición técnica clara.
  Explicación práctica (¿para qué se usa? ¿por qué importa?).
  Posibles errores comunes si aplica.
  Ejemplo práctico:

```lenguaje
código aquí
```

## Puntos clave
- 6 a 10 bullets con los puntos más importantes.
- Deben servir como checklist de estudio.
- Evita frases motivacionales o genéricas.

"Transcripcion:\n"
f"{transcript}"
"""

def estimate_tokens(text):
    return max(1, len(text) // 4)


def extract_total_tokens(count_response):
    if hasattr(count_response, "total_tokens"):
        return count_response.total_tokens
    if isinstance(count_response, dict) and "total_tokens" in count_response:
        return count_response["total_tokens"]
    if isinstance(count_response, dict) and "totalTokens" in count_response:
        return count_response["totalTokens"]
    raise ValueError("Unable to read total_tokens from count_tokens response.")


def count_tokens_with_limiter(client, model_name, prompt, limiter):
    estimated = estimate_tokens(prompt)
    limiter.wait_for_quota(estimated)
    try:
        response = client.models.count_tokens(model=model_name, contents=prompt)
        return extract_total_tokens(response)
    finally:
        limiter.record_request(estimated)


def generate_with_retry(client, model_name, prompt, limiter, input_tokens):
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


def split_transcript_for_limit(client, model_name, title, transcript, limiter):
    full_prompt = build_prompt(title, transcript)
    input_tokens = count_tokens_with_limiter(client, model_name, full_prompt, limiter)
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
            part_tokens = count_tokens_with_limiter(client, model_name, part_prompt, limiter)
            if part_tokens + OUTPUT_TOKEN_BUDGET_PER_FILE > MAX_TOTAL_TOKENS_PER_REQUEST:
                too_large = True
                break

        if not too_large:
            return parts

        max_chars = int(max_chars * 0.8)
        if max_chars < 500:
            break

    return split_text_by_lines(transcript, max_chars)


def generate_markdown(client, model_name, title, transcript, limiter):
    parts = split_transcript_for_limit(client, model_name, title, transcript, limiter)
    total_parts = len(parts)
    outputs = []

    for i, part in enumerate(parts, start=1):
        if total_parts > 1:
            prompt = build_prompt(title, part, i, total_parts)
        else:
            prompt = build_prompt(title, part)

        input_tokens = count_tokens_with_limiter(client, model_name, prompt, limiter)
        if input_tokens + OUTPUT_TOKEN_BUDGET_PER_FILE > MAX_TOTAL_TOKENS_PER_REQUEST:
            raise SystemExit(
                "Input exceeds token budget even after splitting. "
                "Consider more aggressive local trimming."
            )

        output_text = generate_with_retry(client, model_name, prompt, limiter, input_tokens)
        outputs.append(output_text)

    return outputs
