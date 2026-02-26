"""File handling utilities for transcript discovery, grouping, and merging."""
import os
import re

# Regular expression pattern to extract class name, class number, and part number
# Matches filenames like "Full_Stack_Python_1-1.txt" -> (Full_Stack_Python, 1, 1)
CLASS_PART_REGEX = re.compile(r"(.*)_([0-9]+)-([0-9]+)")

# Supported file extensions for transcript files
SUPPORTED_SUFFIXES = (".txt", ".md")

def delete_folder_content(dir):
    for _, _, files in os.walk(dir):
        if files:
            for file in files: 
                filepath = os.path.join(dir, file)
                os.remove(filepath)

def collect_transcript_files(folder):
    """Recursively collect transcript files; return sorted list for deterministic processing."""
    files = []
    for root, _, names in os.walk(folder):
        for name in names:
            if name.lower().endswith(SUPPORTED_SUFFIXES):
                files.append(os.path.join(root, name))
    files.sort()
    return files


def group_class_files(file_paths: list):
    """Group class files by base name and sort by part number for sequential merging."""
    grouped = {}
    for path in file_paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        
        match = CLASS_PART_REGEX.match(stem)
        if match:
            # Separate the previous match into groups
            base_name = match.group(1)
            class_number = int(match.group(2))
            part_number = int(match.group(3))
            class_key = f"{base_name}_{class_number}"
        else:
            class_key = stem
            part_number = 1

        # Validate if the key is present and then it's added into the group dict
        # to group the same classes
        if class_key not in grouped:
            grouped[class_key] = []
        grouped[class_key].append((part_number, path))
    
    # sort the dictionary to order asc
    for class_key, parts in grouped.items():
        parts.sort(key=lambda item: item[0])
        grouped[class_key] = parts
    
    return grouped

def merge_parts(part_entries):
    """Merge part files into single text; skip empty parts and handle encoding errors."""
    texts = []
    for _, path in part_entries:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
        if text:
            texts.append(text)

    return "\n".join(texts).strip()