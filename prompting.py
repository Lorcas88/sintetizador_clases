"""Prompt building utilities for Markdown generation via Gemini API."""

def build_prompt_instructions():
    """Return the shared instruction block for Spanish Markdown generation."""
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
    """Build the full prompt for a batch of class transcripts."""
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