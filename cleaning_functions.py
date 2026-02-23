import re # Regular expressions library

# Regular expression pattern to match timestamps in format HH:MM:SS.mmm
TIMESTAMP_REGEX = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\.\d{1,3}")
USER_REGEX = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9]{1,5}-[0-9]")
LINE_BREAK = re.compile(r'^\n$')

# Set of phrases to be completely removed from the transcript
REMOVAL_PHRASES = {
    "webvtt",
    "hola",
    "hola a todos",
    "hola a todas",
    "buen día",
    "buenos días",
    "buenas tardes",
    "buenas noches",
    "bienvenidos",
    "bienvenidas",
    "bienvenidos a la clase",
    "bienvenidas a la clase",
    "que tal",
    "qu tal",
    "como estan",
    "cómo estan",
    "como estan",
    "gracias por estar",
    "muchas gracias",
    "gracias",
    "nos vemos",
    "hasta luego",
    "hasta la proxima",
    "adios",
    "chao",
    "que tengan buen día",
    "que tengan buena noche",
    "nos vemos en la proxima",
    "gracias por su tiempo",
    "gracias por la asistencia",
    "estén todos bien",
    "sesión del día"
}

# Set of filler words (like 'uh', 'um', 'well') that should be removed from the transcript
FILLER_PHRASES = {
    "eh",
    "em",
    "mmm",
    "ok",
    "vale",
    "bueno",
    "entonces",
    "este",
}

# Normalizes text for matching: converts to lowercase, removes punctuation, and normalizes whitespace
# This allows for reliable comparison against phrase sets regardless of formatting
def normalize_for_match(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", "", text) # Remove all punctuation and special characters, keeping only word characters and spaces
    text = re.sub(r"\s+", " ", text) # Replace multiple consecutive spaces with a single space
    return text.strip()

# Cleans a transcript by removing timestamps, greeting phrases, and filler words
# Returns a cleaned version with only the meaningful content
def clean_transcript(text):
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Skip lines that contain a timestamp, user identifier or lines that have no content
        if TIMESTAMP_REGEX.search(line) or USER_REGEX.search(line) or re.match(r'^\s*$', line):
            continue

        # if re.match(r'^\s*$', line):
        #     print("salto linea")
        #     continue

        normalized = normalize_for_match(line)
        # Skip removal phrases (greetings, farewells, polite phrases)
        # if normalized in REMOVAL_PHRASES:
        #     continue
        if any(phrase in normalized for phrase in REMOVAL_PHRASES):
            continue
        # # Skip filler phrases (utterances like 'uh', 'um', 'well')
        # if normalized in FILLER_PHRASES:
        #     continue

        lines.append(raw_line)

    return "\n".join(lines).strip()
