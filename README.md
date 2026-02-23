# Resumenes NotebookLM (Gemini)

Convierte transcripciones de clases en un markdown compatible con NotebookLM usando la API de Gemini.

## Requisitos

- Python 3.10+
- API key de Gemini

## Instalacion

```bash
pip install -r requirements.txt
```

## Configuracion

1. Copia `.env.example` a `.env` y coloca tu API key.
2. Exporta la variable de entorno antes de ejecutar:

```bash
set GEMINI_API_KEY=tu_api_key
```

## Uso

1. Coloca tus transcripciones en `transcripts/` (archivos `.txt` o `.md`).
2. Ejecuta:

```bash
python main.py
```

Los resultados se guardan en `notebooklm_output/` con extension `.notebooklm.md`.
Los textos recortados se guardan en `notebooklm_output/_clean/`.
Si un archivo no cabe en un request, se divide en partes con sufijo `.parte_XX`.

## Modelo

El modelo por defecto es `gemini-2.5-flash` y puede editarse en `main.py`.
