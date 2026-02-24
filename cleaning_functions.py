"""Module for cleaning and normalizing transcript text.

Removes timestamps, user identifiers, greetings, and filler words from transcripts
to extract only the meaningful content for documentation generation.
"""
import re

# Regular expression to match HH:MM:SS.mmm timestamps that should be skipped
TIMESTAMP_REGEX = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\.\d{1,3}")

# Regular expression pattern to match user identifiers (UUID format with user ID)
# Used to skip lines containing user information that aren't part of the transcript content
USER_REGEX = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9]{1,5}-[0-9]")

# Regular expression pattern to match empty lines (only newline characters)
# Used to skip blank lines during transcript cleaning
LINE_BREAK = re.compile(r'^\n$')

# Set of phrases to be completely removed from the transcript
# Includes greetings, farewells, polite formalities, and WebVTT headers
# that don't contribute meaningful content to the cleaned transcript
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

# Set of filler words and interjections (like 'uh', 'um', 'well')
# These common utterances don't add semantic value and should be removed
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


def normalize_for_match(text):
    """Normalizes text for matching by converting case, removing punctuation, and normalizing whitespace.
    
    Processes text to make it suitable for reliable comparison against phrase sets regardless
    of original formatting, capitalization, or punctuation.
    
    Args:
        text (str): The input text to normalize
    
    Returns:
        str: Normalized text with lowercase conversion, punctuation removed, and whitespace normalized
    """
    text = text.strip().lower()
    # Remove all punctuation and special characters, keeping only word characters and spaces
    text = re.sub(r"[^\w\s]", "", text)
    # Replace multiple consecutive spaces with a single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_transcript(text):
    """Cleans a transcript by removing timestamps, metadata, greetings, and filler words.
    
    Processes raw transcript to extract only meaningful content by removing:
    - Timestamp lines (metadata)
    - User identifier lines (metadata)
    - Empty lines
    - Greeting and farewell phrases
    - Common filler words
    
    Args:
        text (str): The raw transcript text containing timestamps and metadata
    
    Returns:
        str: Cleaned transcript with only substantive content
    """
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Skip lines that contain timestamps, user identifiers, or are completely empty
        # These are metadata and formatting artifacts, not actual content
        if TIMESTAMP_REGEX.search(line) or USER_REGEX.search(line) or re.match(r'^\s*$', line):
            continue

        normalized = normalize_for_match(line)
        # Skip removal phrases (greetings, farewells, polite phrases)
        # Checks if any removal phrase is contained in the normalized line
        if any(phrase in normalized for phrase in REMOVAL_PHRASES):
            continue
        
        # if normalized in FILLER_PHRASES:
        #     continue

        lines.append(raw_line)

    return "\n".join(lines).strip()