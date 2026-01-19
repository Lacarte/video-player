"""
Ordering engine for sorting files and folders.

Rules (applied per folder level):
1. Extract number at START of name
2. If not found, extract number at END
3. If no number, push to bottom (order = 999999)
4. Same number = alphabetical sort
"""

import re
from typing import Tuple


def extract_sort_key(name: str) -> Tuple[int, str]:
    """
    Extract sorting key from a filename or folder name.

    Returns:
        Tuple of (numeric_order, alphabetic_key)

    Examples:
        "1_intro.mp4"     -> (1, "intro.mp4")
        "01 - Setup.mp4"  -> (1, "Setup.mp4")
        "[1] Welcome"     -> (1, "Welcome")
        "intro_1.mp4"     -> (1, "intro.mp4")
        "lesson.mp4"      -> (999999, "lesson.mp4")
        "1a.mp4"          -> (1, "a.mp4")
        "a1.mp4"          -> (1, "a.mp4")
    """
    # Remove extension for analysis (but keep for sorting)
    base_name = name

    # Names starting with "-" go to the bottom (order 999998, before items with no number)
    if base_name.startswith('-'):
        return (999998, base_name.lower())

    # Pattern 1: Number at START
    # Matches: "1_", "01 ", "1.", "1-", "[1]", "(1)", "1a" etc.
    start_patterns = [
        r'^(\d+)[\s_\-\.\)\]]+(.*)$',  # "1_intro", "01 - intro", "1.intro"
        r'^\[(\d+)\][\s_\-\.]*(.*)$',   # "[1] intro", "[01]intro"
        r'^\((\d+)\)[\s_\-\.]*(.*)$',   # "(1) intro"
        r'^(\d+)([a-zA-Z].*)$',          # "1a", "01intro"
    ]

    for pattern in start_patterns:
        match = re.match(pattern, base_name)
        if match:
            num = int(match.group(1))
            rest = match.group(2).strip() or base_name
            return (num, rest.lower())

    # Pattern 2: "Word Number" format (Módulo 1, Chapter 10, etc.)
    # Must have a word followed by space and number
    word_number_pattern = r'^(.+?)\s+(\d+)(.*)$'
    match = re.match(word_number_pattern, base_name)
    if match:
        prefix = match.group(1).strip()
        num = int(match.group(2))
        suffix = match.group(3).strip()
        # Return with prefix for secondary sorting (so "Módulo 1" and "Chapter 1" sort separately)
        return (num, prefix.lower() + ' ' + suffix.lower())

    # Pattern 3: Number at END with separator (requires: "_1", "-1", ".1")
    # Does NOT match: "lesson.mp4" (4 is part of extension)
    end_pattern = r'^(.+?)[\s_\-](\d+)(\.[^.]+)?$'  # "intro_1.mp4", "intro - 01.mp4"

    match = re.match(end_pattern, base_name)
    if match:
        rest = match.group(1).strip()
        num = int(match.group(2))
        ext = match.group(3) or ''
        return (num, (rest + ext).lower())

    # Pattern 3: No number found
    return (999999, base_name.lower())


def sort_items(items: list, key_func=None, ctime_func=None) -> list:
    """
    Sort a list of items using the ordering rules.

    Args:
        items: List of items to sort
        key_func: Optional function to extract the name from each item.
                  If None, assumes items are strings.
        ctime_func: Optional function to extract creation time from each item.
                    Used for items starting with "-" which sort by creation date.

    Returns:
        Sorted list
    """
    if key_func is None:
        key_func = lambda x: x

    def sort_key(item):
        name = key_func(item)
        num, alpha = extract_sort_key(name)

        # For items starting with "-", use creation time as secondary sort
        if name.startswith('-') and ctime_func is not None:
            try:
                ctime = ctime_func(item)
                return (num, ctime, alpha)
            except:
                pass

        return (num, 0, alpha)

    return sorted(items, key=sort_key)


def get_clean_title(filename: str) -> str:
    """
    Extract a clean, readable title from a filename.

    Removes:
    - Leading numbers and separators
    - File extension
    - Common prefixes like "lesson", "video", etc.

    Examples:
        "01_introduction.mp4" -> "Introduction"
        "1 - Getting Started.mkv" -> "Getting Started"
        "[1] Welcome to the course.mp4" -> "Welcome to the course"
    """
    # Remove extension
    name = re.sub(r'\.[^.]+$', '', filename)

    # Remove leading number patterns
    patterns = [
        r'^(\d+)[\s_\-\.\)\]]+',  # "1_", "01 - ", "1."
        r'^\[(\d+)\][\s_\-\.]*',   # "[1] ", "[01]"
        r'^\((\d+)\)[\s_\-\.]*',   # "(1) "
    ]

    for pattern in patterns:
        name = re.sub(pattern, '', name)

    # Clean up any remaining artifacts
    name = name.strip(' _-.')

    # Capitalize first letter if all lowercase
    if name and name[0].islower():
        name = name[0].upper() + name[1:]

    return name or filename


# Test cases (run with: python -m scanner.ordering)
if __name__ == "__main__":
    test_cases = [
        "1_intro.mp4",
        "01 - Setup.mp4",
        "[1] Welcome.mp4",
        "intro_1.mp4",
        "lesson.mp4",
        "1a.mp4",
        "a1.mp4",
        "Chapter 1",
        "2. Variables",
        "10_conclusion.mp4",
        "2_basics.mp4",
        "no_number_here.txt",
        "finale_99.mp4",
    ]

    print("Sort Key Extraction:")
    print("-" * 50)
    for name in test_cases:
        key = extract_sort_key(name)
        title = get_clean_title(name)
        print(f"  {name:30} -> {str(key):20} | {title}")

    print("\nSorted Order:")
    print("-" * 50)
    sorted_items = sort_items(test_cases)
    for i, name in enumerate(sorted_items, 1):
        print(f"  {i:2}. {name}")
