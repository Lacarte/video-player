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


def extract_sort_key(name: str) -> Tuple[str, int, str]:
    """
    Extract sorting key from a filename or folder name.

    Returns:
        Tuple of (prefix, numeric_order, alphabetic_key)
        - prefix: groups items together (e.g., "A roadmap_mes" items stay together)
        - numeric_order: sorts within the group
        - alphabetic_key: tiebreaker

    Examples:
        "1_intro.mp4"     -> ("", 1, "intro.mp4")
        "01 - Setup.mp4"  -> ("", 1, "setup.mp4")
        "[1] Welcome"     -> ("", 1, "welcome")
        "intro_1.mp4"     -> ("intro", 1, "")
        "lesson.mp4"      -> ("~~~", 999999, "lesson.mp4")
        "Módulo 1"        -> ("módulo", 1, "")
    """
    # Remove extension for analysis (but keep for sorting)
    base_name = name

    # Names starting with "-" go to the bottom (order 999998, before items with no number)
    if base_name.startswith('-'):
        return ('~~', 999998, base_name.lower())

    # Pattern 1: Number at START
    # Matches: "1_", "01 ", "1.", "1-", "[1]", "(1)", "1a", or just "1" etc.
    start_patterns = [
        r'^(\d+)[\s_\-\.\)\]]+(.*)$',  # "1_intro", "01 - intro", "1.intro"
        r'^\[(\d+)\][\s_\-\.]*(.*)$',   # "[1] intro", "[01]intro"
        r'^\((\d+)\)[\s_\-\.]*(.*)$',   # "(1) intro"
        r'^(\d+)([a-zA-Z].*)$',          # "1a", "01intro"
        r'^(\d+)()$',                     # Just "1", "01", "123" (bare number)
    ]

    for pattern in start_patterns:
        match = re.match(pattern, base_name)
        if match:
            num = int(match.group(1))
            rest = match.group(2).strip() or base_name
            # Use prefix that sorts after end-pattern items (like "a roadmap") but before
            # word-number items starting with later letters (like "módulo")
            # 'l' chosen because: a < l < m
            return ('l__numbered', num, rest.lower())

    # Pattern 2: "Word Number" format (Módulo 1, Chapter 10, etc.)
    # Must have a word followed by space and number
    word_number_pattern = r'^(.+?)\s+(\d+)(.*)$'
    match = re.match(word_number_pattern, base_name)
    if match:
        prefix = match.group(1).strip()
        num = int(match.group(2))
        suffix = match.group(3).strip()
        # Prefix groups items together, then sort by number within prefix
        return (prefix.lower(), num, suffix.lower())

    # Pattern 3: Number at END with separator (requires: "_1", "-1", ".1")
    # Does NOT match: "lesson.mp4" (4 is part of extension)
    end_pattern = r'^(.+?)[\s_\-](\d+)(\.[^.]+)?$'  # "intro_1.mp4", "intro - 01.mp4"

    match = re.match(end_pattern, base_name)
    if match:
        rest = match.group(1).strip()
        num = int(match.group(2))
        ext = match.group(3) or ''
        # Prefix groups items together, then sort by number within prefix
        return (rest.lower(), num, ext.lower())

    # No number found - push to bottom
    return ('~~~', 999999, base_name.lower())


def sort_items(items: list, key_func=None, ctime_func=None) -> list:
    """
    Sort a list of items using the ordering rules.

    Args:
        items: List of items to sort
        key_func: Optional function to extract the name from each item.
                  If None, assumes items are strings.
        ctime_func: Optional function to extract creation time from each item.
                    (Currently unused - kept for API compatibility)

    Returns:
        Sorted list
    """
    if key_func is None:
        key_func = lambda x: x

    def sort_key(item):
        name = key_func(item)
        prefix, num, alpha = extract_sort_key(name)
        # Sort by: prefix (groups items), then number, then alphabetically
        return (prefix, num, alpha)

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
        # Test case for roadmap ordering
        "A roadmap_mes_1",
        "1 Empieza aquí",
        "Módulo 1 - Fundamentos",
        "A roadmap_mes_2",
        "A roadmap_mes_3",
        "Módulo 3 - Instalación",
        "Módulo 4 - Nodos",
    ]

    print("Sort Key Extraction:")
    print("-" * 50)
    for name in test_cases:
        key = extract_sort_key(name)
        title = get_clean_title(name)
        print(f"  {name:30} -> {str(key):30} | {title}")

    print("\nSorted Order:")
    print("-" * 50)
    sorted_items = sort_items(test_cases)
    for i, name in enumerate(sorted_items, 1):
        print(f"  {i:2}. {name}")
