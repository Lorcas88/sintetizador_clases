"""Module for merging multi-part class transcripts into complete documents.

Handles grouping class files by their base name and part numbers, then merging
all parts of a class back into a single coherent transcript.
"""
import os
import re

# Regular expression pattern to extract class name, class number, and part number
# Matches filenames like "Full_Stack_Python_1-1.txt" -> (Full_Stack_Python, 1, 1)
CLASS_PART_REGEX = re.compile(r"(.*)_([0-9]+)-([0-9]+)")

# Supported file extensions for transcript files
SUPPORTED_SUFFIXES = (".txt", ".md")

def collect_transcript_files(folder):
    """Recursively collect transcript files under `folder`.
    
    Returns a sorted list of paths for deterministic processing.
    """
    files = []
    for root, _, names in os.walk(folder):
        for name in names:
            if name.lower().endswith(SUPPORTED_SUFFIXES):
                files.append(os.path.join(root, name))
    files.sort()
    return files


def group_class_files(file_paths):
    """Group class files by their base name and order by part number.
    
    Parses filenames to extract class name, class number, and part number.
    Groups files that belong to the same class together, sorted by part number
    for proper sequential merging.
    
    Filename format expected: "ClassName_ClassNumber-PartNumber.extension"
    Example: "Full_Stack_Python_1-01.txt" groups under "Full_Stack_Python_1"
    
    Args:
        file_paths (list[str]): List of file paths to group and organize
    
    Returns:
        dict: Dictionary mapping class keys to list of (part_number, path) tuples,
              sorted by part number in ascending order
    """
    grouped = {}
    for path in file_paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        match = CLASS_PART_REGEX.match(stem)
        if match:
            base_name = match.group(1)
            class_number = match.group(2)
            part_number = int(match.group(3))
            class_key = f"{base_name}_{class_number}"
        else:
            class_key = stem
            part_number = 1

        grouped.setdefault(class_key, []).append((part_number, path))

    for class_key, parts in grouped.items():
        parts.sort(key=lambda item: item[0])
        grouped[class_key] = parts

    return grouped


def merge_parts(part_entries):
    """Merge multiple part files into a single concatenated text.
    
    Reads all part files in order (already sorted by part_entries),
    extracts the text content, and concatenates them with newline separators.
    Skips empty parts and filters out encoding errors.
    
    Args:
        part_entries (list[tuple]): List of (part_number, file_path) tuples,
                                    must be pre-sorted by part number
    
    Returns:
        str: Concatenated text from all parts, with empty lines trimmed
    """
    texts = []
    for _, path in part_entries:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
        if text:
            texts.append(text)

    return "\n".join(texts).strip()