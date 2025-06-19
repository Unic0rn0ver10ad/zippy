#!/usr/bin/env python3
"""
Zippy the Dict extracts words from multiple dictionary formats into separate language-specific wordlists. A wordlist is a simple text file containing one word per line, sorted alphabetically. Wordlists are used by Halt! What's the Passphrase? to generate passphrases in different languages.

Supported formats:
- .dz (gzipped dictionary files)
- .dictd.tar.xz (FreeDict archive format)
- .src.tar.xz (TEI XML source format)

All dictionaries must be placed in the 'dictionaries' folder for processing. The extracted wordlists will be saved in the 'wordlists' folder. Each dictionary will generate two wordlists: one for the source language and one for the target language. The filenames are based on the dictionary name and possibly the language codes from LANGUAGE_MAPPINGS.

Zippy now includes intelligent part-of-speech filtering to improve wordlist quality for passphrase generation. Instead of extracting every word, it focuses on content words like nouns, adjectives, verbs, and adverbs while filtering out function words such as articles, prepositions, and pronouns. The system automatically adapts to different languages and their grammatical features, handling everything from simple English dictionaries to complex gendered noun systems in Romance languages. This significantly reduces manual cleanup work and produces wordlists better suited for creating memorable and secure passphrases.

Zippy can be run from the command line in two modes: all or single. The 'all' mode (this is the default mode) processes all dictionaries in the 'dictionaries' folder:

    python zippy.py

The 'single' mode processes a single dictionary file specified by the user:

    python zippy.py single freedict-eng-jpn-2024.10.10.dictd.tar.xz

You can also just run it in your IDE as the main() function will process all dictionaries by default.

Almost all of the dictionaries used in this project are from FreeDict:
https://freedict.org/downloads/

The wordlists that Zippy extracts from the dictionaries are honestly not that great. They usually contain a lot of words not in the desired language at the beginning of the file. You'll need to go through each one manually and delete the words that aren't in the desired language.

After cleaning the raw wordlist, the next step is to turn it into a wordlist that's actually useful for generating passphrases. The EFF has a very good article on it here: https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases

One technique is to feed the article itself into a reasoning model like ChatGPT, along with the wordlist, and ask it to generate a new wordlist that fits the EFF criteria and is fewer than 7,500 entries. 7,500 is an arbitrary number, but it's a good starting point and mimics the size of the EFF's 'large wordlist' here: https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt

Spot-checking the output of the reasoning model (say, by using Google Translate) is a good idea to convince yourself that the resulting wordlist actually produces fun and memorable passphrases.

Another idea is to not use dictionaries at all - instead, use the AI tools available to translate one of the two EFF wordlists into the desired language. Full disclosure: I haven't tried this yet 🤔
"""

import argparse
import gzip
import os
import logging
import re
import string
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Set, Iterable
from pathlib import Path
import random

logger = logging.getLogger("zippy")
logging.basicConfig(format="%(message)s")
logger.setLevel(logging.WARNING)


# Unicode ranges for different writing systems
UNICODE_RANGES = {
    'devanagari': (0x0900, 0x097F),  # Hindi, Sanskrit, etc.
    'arabic': (0x0600, 0x06FF),      # Arabic, Persian, Urdu
    'cyrillic': (0x0400, 0x04FF),    # Russian, Bulgarian, etc.
    'cjk_hiragana': (0x3040, 0x309F),  # Japanese Hiragana
    'cjk_katakana': (0x30A0, 0x30FF),  # Japanese Katakana
    'cjk_unified': (0x4E00, 0x9FAF),   # Chinese, Japanese Kanji
}

# Common dictionary header patterns to skip
HEADER_PATTERNS = {
    'prefixes': (
        '#', '00-database', 'Author:', 'Maintainer:', 'Edition:', 'Size:',
        'Publisher:', 'Availability:', 'Copyright', 'This program', 
        'Published', 'ID#', 'Series:', 'Changelog:', '*', 'Notes:',
        'Source(s):', 'Database Status:', 'The Project:'
    ),
    'keywords': {
        'freedict', 'dictionary', 'license', 'copyright',
        'available', 'foundation', 'version', 'ver.', 'converted',
        'imported', 'makefile', 'initial', 'michael bunk',
        'piotr bański', 'conversion of tei', 'tools/xsl',
        'manual clean-up', 'stable'
    }
}

# Precompiled year detection pattern
YEAR_PATTERN = re.compile(r"20(?:05|10|18|19|20|21|22|23|24)")


def contains_year(line: str) -> bool:
    """Return True if line contains a known year pattern."""
    return bool(YEAR_PATTERN.search(line))


# POS filtering configuration
POS_FILTERS = {
    # 'include': ['adv'],  # Only extract NOUNs for testing
    'include': ['n', 'adj', 'adv', 'v'],  # Only extract these base POS types
    'skip_plurals': True,  # Skip plural forms when reliably detected
}

# Language-specific filename mappings
LANGUAGE_MAPPINGS = {
    'afr': 'afrikaans',
    'ara': 'arabic',
    'ast': 'asturian',
    'bre': 'breton',
    'bul': 'bulgarian',
    'cat': 'catalan',
    'ces': 'czech',
    'ckb': 'sorani',
    'cym': 'welsh',
    'dan': 'danish',
    'deu': 'german',
    'ell': 'greek',
    'eng': 'english',
    'epo': 'esperanto',
    'fin': 'finnish',
    'fra': 'french',
    'gle': 'irish',
    'hin': 'hindi',
    'hrv': 'croatian',
    'ita': 'italian',
    'jpn': 'japanese',
    'kha': 'khasi',
    'kmr': 'kurmanji',
    'lat': 'latin',
    'nld': 'dutch',
    'pol': 'polish',
    'por': 'portuguese',
    'rus': 'russian',
    'spa': 'spanish',
    'swe': 'swedish',
    'swh': 'swahili',
}

# Basic English stopwords used when filtering extracted words
ENGLISH_STOPWORDS: Set[str] = {
    'the', 'and', 'of', 'or', 'in', 'to', 'for', 'with',
    'from', 'by', 'at', 'on', 'an', 'as', 'be', 'is',
    'are', 'was', 'were', 'been', 'have', 'has', 'had',
    'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'must'
}

def get_language_mapping(name_or_code: str) -> Tuple[str, str]:
    """
    Given either a filename (e.g. 'freedict-eng-ces-0.1.3.dictd.tar.xz')
    or a simple code string ('eng-ces', 'eng-zyx', 'cba-zyx'),
    extract two 3-letter segments, map each via LANGUAGE_MAPPINGS
    (fallback to the code itself), and return the pair.

    Cases covered:
      1. both codes known   → ('english', 'czech')
      2. one known         → ('english', 'zxy')
      3. neither known     → ('cba', 'zyx')
      4. no clear 3-letter → splits on first dash or duplicates first part
    """
    # Handle .dict.dz files specially (e.g., fra-eng.dict.dz)
    if name_or_code.endswith('.dict.dz'):
        base = Path(name_or_code).stem  # removes .dz
        base = Path(base).stem  # removes .dict
        parts = base.split('-')
        if len(parts) >= 2:
            src_code, tgt_code = parts[0].lower(), parts[1].lower()
        else:
            src_code = tgt_code = parts[0].lower()
    else:
        # strip path + just one extension (we ignore multi-suffix like .tar.xz here)
        base = Path(name_or_code).stem
        parts = base.split('-')

        # grab the first two segments of exactly length==3
        codes = []
        for part in parts:
            if len(part) == 3:
                codes.append(part.lower())
                if len(codes) == 2:
                    break

        if len(codes) == 2:
            src_code, tgt_code = codes
        else:
            # fallback to the first two dash-separated parts
            if len(parts) >= 2:
                src_code, tgt_code = parts[0].lower(), parts[1].lower()
            else:
                src_code = tgt_code = parts[0].lower()

    # map (or default to the code itself)
    return (
        LANGUAGE_MAPPINGS.get(src_code, src_code),
        LANGUAGE_MAPPINGS.get(tgt_code, tgt_code),
    )


def extract_pos_tags(line: str) -> List[str]:
    """
    Extract part-of-speech tags from a dictionary line.
    
    Args:
        line: Dictionary line that may contain POS tags like <n>, <adj>, <v, trans>
        
    Returns:
        List of POS tags found in the line
    """
    pos_pattern = r'<([^>]+)>'
    matches = re.findall(pos_pattern, line)
    return matches


def extract_base_pos_types(pos_tag: str) -> List[str]:
    """
    Extract base POS types from complex tags.
    
    Examples:
        'n, masc' -> ['n']
        'fem, n, sg' -> ['n'] 
        'v, trans' -> ['v']
        'adj' -> ['adj']
        'pl' -> ['pl']
        'phraseologicalUnit' -> ['phraseologicalUnit']
    
    Args:
        pos_tag: A single POS tag string
        
    Returns:
        List of base POS types found
    """
    # Split on common separators and clean
    parts = re.split(r'[,\s]+', pos_tag.strip())
    
    # Known base POS types we're interested in
    base_pos_types = ['n', 'adj', 'adv', 'v', 'pl']
    
    # Extended POS types from analysis
    extended_pos_types = [
        'pn',  # proper noun (Bulgarian)
        'phraseologicalUnit',  # Bulgarian
        'interjection',  # Bulgarian
        'preposition',  # Bulgarian  
        'pronoun',  # Bulgarian
        'conjunction',  # Bulgarian
        'numeral',  # Bulgarian
        'determiner',  # Bulgarian
        'int',  # interjection (German/French)
        'prep',  # preposition (French/German)
        'pron',  # pronoun (French/German)
        'conj',  # conjunction (French/German)
        'num',  # numeral (French/German)
        'vt', 'vi',  # transitive/intransitive verbs
        'art'  # article
    ]
    
    found_types = []
    for part in parts:
        part = part.lower().strip()
        if part in base_pos_types:
            found_types.append(part)
        elif part in extended_pos_types:
            found_types.append(part)
    
    return found_types


def should_include_word_by_pos(line: str, filters: dict) -> bool:
    """
    Determine if a word should be included based on POS filtering.
    
    Args:
        line: Dictionary line containing word and POS information
        filters: POS filter configuration
        
    Returns:
        True if word should be included, False otherwise
    """
    if not filters.get('include'):
        return True  # No filtering enabled
    
    # Extract POS tags from line
    pos_tags = extract_pos_tags(line)
    if not pos_tags:
        return True  # No POS tags found, include by default
    
    # Check if we should skip plurals
    if filters.get('skip_plurals', False):
        for tag in pos_tags:
            base_types = extract_base_pos_types(tag)
            if 'pl' in base_types:
                return False
    
    # Check if any POS tag matches our include filter
    include_types = filters['include']
    for tag in pos_tags:
        base_types = extract_base_pos_types(tag)
        for base_type in base_types:
            if base_type in include_types:
                return True
    
    return False


def ensure_directories() -> None:
    """Create necessary output directories."""
    os.makedirs("wordlists", exist_ok=True)


def is_valid_word(word: str) -> bool:
    """
    Check if a word meets basic validity criteria.

    Args:
        word: The word to validate

    Returns:
        True if word is valid, False otherwise
    """
    if not word or len(word) < 3:
        return False
    
    # Remove leading/trailing whitespace
    word = word.strip()
    if not word or len(word) < 3:
        return False
    
    # Skip common technical abbreviations and fragments
    if word.upper() in {'ADN', 'ARN', 'ATP', 'ADSL', 'USB', 'DVD', 'AAO', 'ABP', 'AFI', 'AMPA', 'ACS', 'ANPE', 'ATB'}:
        return False
    
    # Skip words that are mostly punctuation or numbers
    if sum(c.isalnum() for c in word) < len(word) * 0.6:
        return False
    
    return all(char.isalnum() or char.isspace() or char in "'-áàâäéèêëíìîïóòôöúùûüýÿñçłśźżąęćńłžčšđ" for char in word)


def is_script_character(char: str, script: str) -> bool:
    """Check if a character belongs to a specific script."""
    if script not in UNICODE_RANGES:
        return False
    
    start, end = UNICODE_RANGES[script]
    return start <= ord(char) <= end


def contains_script(text: str, script: str) -> bool:
    """Check if text contains any characters from a specific script."""
    return any(is_script_character(char, script) for char in text)


def is_cjk_character(char: str) -> bool:
    """Check if character is from any CJK script."""
    return any(is_script_character(char, script) 
              for script in ['cjk_hiragana', 'cjk_katakana', 'cjk_unified'])


def contains_cjk(text: str) -> bool:
    """Check if text contains any CJK characters."""
    return any(is_cjk_character(char) for char in text)


def is_header_line(line: str) -> bool:
    """Check if a line is part of the dictionary header."""
    line_lower = line.lower()

    # Check for prefix patterns
    if line.startswith(HEADER_PATTERNS['prefixes']):
        return True

    # Check for keyword patterns using the pre-built set
    return any(keyword in line_lower for keyword in HEADER_PATTERNS['keywords'])


def clean_word(word: str) -> str:
    """Remove punctuation from word boundaries."""
    return word.strip(string.punctuation)


# Precompiled regex for removing punctuation across the codebase
_NORMALIZE_RE = re.compile(r"[-‐'.,/ ]+")

# Regex to detect IPA characters or markers used in multiple functions
_IPA_MARKER_RE = re.compile(
    r"[ɐəɪɛɜːʃɹɔɑɒæʌʔɘɯɤɞɨʊʉɵɶœøɛ̃ɔ̃ɑ̃ˈˌ]"
)

# Precompiled regex for simple phonetic patterns
PRONUNCIATION_SIMPLE_RE = re.compile(r"/[a-zA-Zɛɔɑɪəɔ̃ɑ̃ɛ̃]+/")

# Translation table for common punctuation replacements
_TRANSLATE_MAP = str.maketrans({
    ',': ' ',
    '،': ' ',  # Arabic comma
    '、': ' ',  # CJK comma
    '~': ' ',
})


def normalize_word(word: str) -> str:
    """Return word with common punctuation removed."""
    return _NORMALIZE_RE.sub('', word)


def has_pronunciation_markers(line: str) -> bool:
    """Check if a line contains pronunciation markers."""
    if '/' not in line:
        return False
    # Check for IPA characters
    if _IPA_MARKER_RE.search(line):
        return True
    # Check for simple phonetic patterns like /ad/, /abkazi/
    if PRONUNCIATION_SIMPLE_RE.search(line):
        return True
    return False


def extract_pronunciation_word(line: str) -> Optional[str]:
    """Extract headword from pronunciation format line (word /pronunciation/ <pos>)."""
    if '/' not in line:
        return None
    
    word = line.split('/')[0].strip()
    if not word or len(word) < 1:
        return None
    
    # Clean and validate - handle Unicode characters like em-dash
    clean = normalize_word(word)
    if len(clean) >= 2 and clean.isalpha() and not any(char.isdigit() for char in word):
        return word
    
    return None


def extract_simple_translation_words(translation: str) -> Iterable[str]:
    """Yield words from simple translation text."""
    parts = translation.translate(_TRANSLATE_MAP)

    for word in parts.split():
        clean = clean_word(word)
        if clean.isalpha():
            yield clean


def extract_script_specific_words(translation: str, script: str) -> Iterable[str]:
    """Yield words from translation text for specific scripts."""
    parts = translation.translate(_TRANSLATE_MAP)

    for word in parts.split():
        clean = clean_word(word)
        # Check if word contains characters from the target script
        if script in ['cjk_hiragana', 'cjk_katakana', 'cjk_unified']:
            if contains_cjk(clean):
                yield clean
        elif contains_script(clean, script):
            yield clean


def _yield_words_by_script(line: str, script: str) -> Iterable[str]:
    """Yield cleaned words from ``line`` belonging to ``script``."""
    if script == 'cjk':
        parts = re.split(r'[,，、。；;]+|\s+', line.strip())
        for part in parts:
            clean = part.strip('.,，、。；; ')
            if clean and contains_cjk(clean):
                yield clean
        return

    ranges = {
        'arabic': [(0x0600, 0x06FF)],
        'cyrillic': [(0x0400, 0x04FF)],
        'devanagari': [(0x0900, 0x097F)],
    }.get(script, [])

    for word in line.split():
        clean = clean_word(word)
        if clean and len(clean) >= 2:
            if all(any(start <= ord(c) <= end for start, end in ranges) or c in ' -' for c in clean):
                yield clean


def extract_english_words(translation: str) -> Iterable[str]:
    """Yield English words from translation text."""
    parts = translation.translate(_TRANSLATE_MAP)

    for word in parts.split():
        clean = clean_word(word)
        if (clean.isalpha()
            and all(ord(char) < 256 for char in clean)):
            yield clean


def process_multilingual_translation(translation: str) -> Iterable[str]:
    """Yield words based on detected script in the translation."""

    # Skip quoted translations
    if translation.startswith('"') and translation.endswith('"'):
        return []
    cleaned = translation.translate(_TRANSLATE_MAP)

    # Detect and extract based on script
    if contains_script(cleaned, 'devanagari'):
        for word in cleaned.split():
            clean = clean_word(word)
            if (
                len(clean) >= 1
                and all(is_script_character(char, 'devanagari') for char in clean)
            ):
                yield clean

    elif contains_script(cleaned, 'arabic'):
        # Skip pronunciation guides
        if '/' in translation and _IPA_MARKER_RE.search(translation):
            return []
        yield from extract_script_specific_words(cleaned, 'arabic')

    elif contains_cjk(cleaned):
        yield from extract_script_specific_words(cleaned, 'cjk_hiragana')

    elif contains_script(cleaned, 'cyrillic'):
        yield from extract_script_specific_words(cleaned, 'cyrillic')

    else:
        yield from extract_english_words(cleaned)


def detect_simple_format(lines: List[str]) -> bool:
    """
    Detect if dictionary uses simple headword/translation format.
    
    Returns True for formats like Kurdish dictionary where each headword
    is followed immediately by its translation on the next line.
    """
    # Don't use simple format if we see pronunciation markers and POS tags
    has_pronunciation_pos = any('/' in line and '<' in line and '>' in line
                               for line in lines[:200])
    
    if has_pronunciation_pos:
        return False
    
    # Look for alternating pattern deeper in the file (after headers)
    pattern_count = 0
    found_dictionary_start = False
    
    for i in range(50, min(400, len(lines) - 1)):  # Extended range for very long headers
        line = lines[i].strip()
        next_line = lines[i + 1].strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Use enhanced header detection
        if is_header_line(line):
            continue
            
        # Skip lines that contain years (changelog entries)
        if contains_year(line):
            continue
            
        # Skip long text blocks that are likely header content
        if len(line) > 50:
            continue
            
        # Skip lines with colons (except hyphenated words like "-a")
        if ':' in line and not line.startswith('-'):
            continue
        
        # Check for simple word followed by translation pattern
        if (line and next_line and 
            not line.startswith((' ', '\t')) and 
            not any(marker in line for marker in ['/', '<', '>', '1.', '2.', '*']) and
            len(line) <= 30 and  # Single words shouldn't be too long
            not line.endswith(':') and  # Skip section headers
            not any(word in line.lower() for word in ['http', 'www', 'email', '@', 'creating', 'makefile'])):  # Skip URLs/technical terms
            
            # Once we find dictionary-like content, be more liberal in detection
            if not found_dictionary_start:
                found_dictionary_start = True
            
            pattern_count += 1
            if pattern_count >= 3:  # Found enough alternating patterns
                return True
    
    return False


def extract_multiline_translation_words(lines: List[str], line_idx: int) -> Iterable[str]:
    """Yield English words from dictionary's multiline format."""
    
    # Check next few lines for translations
    for j in range(1, 4):
        if line_idx + j >= len(lines):
            break
        
        next_line = lines[line_idx + j].strip()
        if not next_line or not (next_line.startswith(' ') or '[' in next_line):
            continue
        
        # Clean translation line
        translation = next_line.strip()
        if '[' in translation:
            # Remove bracketed content like [mus.], [ugs.]
            translation = translation.split(']', 1)[-1].strip()
        
        # Extract English words
        parts = (translation.replace(',', ' ')
                          .replace('<n>', ' ')
                          .replace('<', ' ')
                          .replace('>', ' '))
        
        for word in parts.split():
            clean = clean_word(word)
            if (clean.isalpha()
                and all(ord(char) < 128 for char in clean)):
                yield clean
        break


def detect_target_language_script(lines: Iterable[str], sample_size: int = 500) -> str:
    """Detect the primary non-Latin script in a dictionary.

    Only the first ``sample_size`` lines of ``lines`` are inspected.  This keeps
    memory usage small when working with very large dictionaries.

    Args:
        lines: Iterable of dictionary lines
        sample_size: Maximum number of lines to sample for detection

    Returns:
        Detected script type: ``'arabic'``, ``'cyrillic'``, ``'cjk'``,
        ``'devanagari'`` or ``'latin'``.
    """
    from collections import Counter

    counts = Counter()

    for i, line in enumerate(lines):
        if i >= sample_size:
            break
        for char in line:
            code = ord(char)
            if 0x0600 <= code <= 0x06FF:
                counts['arabic'] += 1
            elif 0x0400 <= code <= 0x04FF:
                counts['cyrillic'] += 1
            elif (0x4E00 <= code <= 0x9FAF or
                  0x3040 <= code <= 0x309F or
                  0x30A0 <= code <= 0x30FF):
                counts['cjk'] += 1
            elif 0x0900 <= code <= 0x097F:
                counts['devanagari'] += 1
            elif 0x0020 <= code <= 0x007F:
                counts['latin'] += 1

    if not counts:
        return 'latin'

    # Discard Latin if other scripts are present
    counts.pop('latin', None)
    if not counts:
        return 'latin'

    return max(counts, key=counts.get)


def extract_words_by_script_detection(lines: Iterable[str],
                                     extract_language: str,
                                     target_script: str) -> List[str]:
    """
    Extract words using intelligent script detection instead of format assumptions.
    
    Args:
        lines: Dictionary lines
        extract_language: "source" or "target" 
        target_script: Detected target language script
        
    Returns:
        List of extracted words
    """
    words = []
    
    for line in lines:
        line = line.strip()
        
        # Skip headers and empty lines
        if not line or is_header_line(line):
            continue
            
        # Apply POS filtering
        if not should_include_word_by_pos(line, POS_FILTERS):
            continue
        
        if extract_language == "source":
            if '/' in line:
                word = extract_pronunciation_word(line)
                if word and is_valid_word(word):
                    words.append(word)
            elif (normalize_word(line).isalpha() and
                  len(line) >= 2 and
                  all(ord(char) < 256 for char in line) and
                  not any(0x0600 <= ord(char) <= 0x06FF for char in line)):
                words.append(line)

        else:
            if target_script in ['arabic', 'cyrillic', 'devanagari', 'cjk']:
                if ((target_script == 'cjk' and contains_cjk(line)) or
                    (target_script != 'cjk' and any(is_script_character(c, target_script) for c in line))):
                    words.extend(_yield_words_by_script(line, target_script))
            else:
                if (not ('/' in line and any(ch in line for ch in 'ˈˌɑɛɪəɹθð')) and
                        normalize_word(line).isalpha()):
                    words.append(line)
    
    return words


def detect_alternating_pattern(lines: List[str]) -> str:
    """
    Detect whether dictionary follows source-target or target-source alternating pattern.
    
    Args:
        lines: Dictionary lines to analyze
        
    Returns:
        'source-target', 'target-source', or 'unknown'
    """
    # Look for alternating pronunciation/translation patterns
    pattern_samples = []
    
    for i in range(50, min(200, len(lines)-1)):
        line1 = lines[i].strip()
        line2 = lines[i+1].strip()
        
        if (line1 and line2 and 
            not any(header in line1 for header in ['00-database', 'Author:', 'Size:']) and
            not any(header in line2 for header in ['00-database', 'Author:', 'Size:'])):
            
            # Enhanced pronunciation detection for various phonetic notation systems
            has_pronunciation_1 = has_pronunciation_markers(line1)
            has_pronunciation_2 = has_pronunciation_markers(line2)
            
            is_latin_1 = normalize_word(line1).isalpha()
            is_latin_2 = normalize_word(line2).isalpha()
            
            if has_pronunciation_1 and is_latin_2 and not has_pronunciation_2:
                pattern_samples.append('source-target')
            elif has_pronunciation_2 and is_latin_1 and not has_pronunciation_1:
                pattern_samples.append('target-source')
            
            if len(pattern_samples) >= 5:
                break
    
    if not pattern_samples:
        return 'unknown'
    
    # Return most common pattern
    source_target_count = pattern_samples.count('source-target')
    target_source_count = pattern_samples.count('target-source')
    
    if source_target_count > target_source_count:
        return 'source-target'
    elif target_source_count > source_target_count:
        return 'target-source'
    else:
        return 'unknown'


def detect_multiline_format(lines: List[str]) -> bool:
    """
    Detect if dictionary uses multiline format with descriptions.
    
    Returns True for dictionaries like Indonesian where each entry spans 3+ lines:
    Line 1: English word with pronunciation
    Line 2: Target language translation
    Line 3: Description/definition
    """
    multiline_indicators = 0
    
    for i in range(50, min(150, len(lines)-2)):
        line1 = lines[i].strip()
        line2 = lines[i+1].strip()
        line3 = lines[i+2].strip()
        
        if (line1 and line2 and line3 and
            '/' in line1 and '<' in line1 and  # English with pronunciation and POS
            not ('/' in line2) and  # Target translation without pronunciation
            ('.' in line3 or len(line3.split()) > 8)):  # Description line
            multiline_indicators += 1
            
        if multiline_indicators >= 5:
            return True
    
    return False


def extract_words_with_pattern_detection(lines: List[str], 
                                        extract_language: str,
                                        pattern: str) -> List[str]:
    """
    Extract words using detected alternating pattern.
    
    Args:
        lines: Dictionary lines
        extract_language: "source" or "target"
        pattern: Detected alternating pattern
        
    Returns:
        List of extracted words
    """
    words = []
    
    # Check for multiline format (like Indonesian dictionary)
    is_multiline = detect_multiline_format(lines)
    
    if is_multiline:
        return extract_multiline_format_words(lines, extract_language)
    
    for i in range(len(lines)-1):
        line1 = lines[i].strip()
        line2 = lines[i+1].strip()
        
        if (not line1 or not line2 or 
            is_header_line(line1) or is_header_line(line2)):
            continue
        
        # Enhanced pronunciation detection for various phonetic notation systems
        has_pronunciation_1 = has_pronunciation_markers(line1)
        has_pronunciation_2 = has_pronunciation_markers(line2)
        
        if pattern == 'source-target':
            if extract_language == "source" and has_pronunciation_1 and not has_pronunciation_2:
                # Extract source word from pronunciation line
                if not should_include_word_by_pos(line1, POS_FILTERS):
                    continue
                word = extract_pronunciation_word(line1)
                if word and is_valid_word(word):
                    words.append(word)
            elif extract_language == "target" and not has_pronunciation_2 and has_pronunciation_1:
                # Extract target words from non-pronunciation line
                if not should_include_word_by_pos(line2, POS_FILTERS):
                    continue
                cleaned_line = line2.replace(',', ' ').replace(';', ' ')
                words.extend(
                        clean
                        for word in cleaned_line.split()
                        for clean in [clean_word(word)]
                        if (
                            clean
                            and len(clean) >= 2
                            and normalize_word(clean).isalpha()
                            and all(ord(char) < 256 for char in clean)
                        )
                )
        
        elif pattern == 'target-source':
            if extract_language == "target" and has_pronunciation_1 and not has_pronunciation_2:
                # Extract target word from pronunciation line
                if not should_include_word_by_pos(line1, POS_FILTERS):
                    continue
                word = extract_pronunciation_word(line1)
                if word and is_valid_word(word):
                    words.append(word)
            elif extract_language == "source" and not has_pronunciation_2 and has_pronunciation_1:
                # Extract source words from non-pronunciation line
                if not should_include_word_by_pos(line2, POS_FILTERS):
                    continue
                cleaned_line = line2.replace(',', ' ').replace(';', ' ')
                words.extend(
                    clean
                    for word in cleaned_line.split()
                    for clean in [clean_word(word)]
                    if (
                        clean
                        and len(clean) >= 2
                        and normalize_word(clean).isalpha()
                        and all(ord(char) < 256 for char in clean)
                    )
                )
    
    return words


def extract_multiline_format_words(lines: List[str], extract_language: str) -> List[str]:
    """
    Extract words from multiline dictionary format.
    
    Format:
    Line 1: English word with pronunciation <pos>
    Line 2: Target language translation(s)
    Line 3: Description/definition
    """
    words = []
    
    i = 0
    while i < len(lines) - 2:
        line1 = lines[i].strip()
        line2 = lines[i+1].strip()
        line3 = lines[i+2].strip()
        
        if (line1 and line2 and
            '/' in line1 and '<' in line1 and  # English with pronunciation and POS
            not ('/' in line2) and not ('<' in line2)):  # Target translation line
            
            if not should_include_word_by_pos(line1, POS_FILTERS):
                i += 1
                continue
            
            if extract_language == "source":
                # Extract English word
                word = extract_pronunciation_word(line1)
                if word and is_valid_word(word):
                    words.append(word)
            elif extract_language == "target":
                # Extract target language words from line2
                cleaned_line = line2.replace(',', ' ').replace(';', ' ').replace('2.', ' ')
                words.extend(
                    clean
                    for word in cleaned_line.split()
                    for clean in [clean_word(word)]
                    if (
                        clean
                        and len(clean) >= 3
                        and normalize_word(clean).isalpha()
                        and all(ord(char) < 256 for char in clean)
                        and clean.lower() not in ENGLISH_STOPWORDS
                    )
                )
            
            i += 3  # Skip to next entry
        else:
            i += 1
    
    return words


def extract_words_from_gzip_content(lines_iter: Iterable[str],
                                   extract_language: str = "source",
                                   is_dz_file: bool = False) -> List[str]:
    """
    Extract words from gzipped dictionary content using intelligent pattern detection.
    
    Args:
        lines_iter: Iterable yielding lines from the gzipped dictionary
        extract_language: Either "source" or "target"
        is_dz_file: True if this is a .dz file (different pattern logic)
        
    Returns:
        List of extracted words
    """
    # Convert iterable to list once so that multiple detection passes reuse the
    # same data. This avoids reopening the file or re-reading its contents.
    lines = [line.rstrip('\n') for line in lines_iter]
    
    # Detect the target language script
    target_script = detect_target_language_script(lines)
    
    # Use script-based extraction for non-Latin scripts
    if target_script in ['arabic', 'cyrillic', 'cjk', 'devanagari']:
        words = extract_words_by_script_detection(lines, extract_language, target_script)
    else:
        # For Latin scripts, detect alternating pattern
        pattern = detect_alternating_pattern(lines)
        
        if pattern in ['source-target', 'target-source']:
            # Special handling for .dz files: they have inverted pattern logic
            if is_dz_file and pattern == 'target-source':
                # For .dz files, invert the extraction logic
                actual_extract_language = "target" if extract_language == "source" else "source"
                words = extract_words_with_pattern_detection(lines, actual_extract_language, pattern)
            else:
                words = extract_words_with_pattern_detection(lines, extract_language, pattern)
        else:
            # Fall back to format-based approach
            simple_format = detect_simple_format(lines)
            multiline_format = detect_multiline_format(lines)
            
            if simple_format:
                words = _extract_simple_format_words(lines, extract_language)
            elif multiline_format:
                words = extract_multiline_format_words(lines, extract_language)
            else:
                # Try specialized extraction for dictionaries with very long headers
                words = _extract_with_header_skip(lines, extract_language)
    
    return words


def _extract_simple_format_words(lines: Iterable[str],
                                extract_language: str) -> List[str]:
    """Extract words from simple headword/translation format."""
    words = []
    iterator = iter(lines)

    for line in iterator:
        line = line.strip()

        # Skip headers and empty lines
        if not line or is_header_line(line):
            continue

        next_line = next(iterator, '').strip()

        if extract_language == "source":
            clean_line = clean_word(line)
            if (clean_line and len(clean_line) >= 1
                and not any(char.isdigit() for char in clean_line)
                and not any(char in clean_line for char in ['(', ')', '[', ']', '<', '>', '/', '\\'])
                and should_include_word_by_pos(line, POS_FILTERS)):
                words.append(clean_line)
        else:
            if next_line:
                words.extend(extract_simple_translation_words(next_line))

        # already consumed next_line via iterator
        # No else branch; iterator naturally advances
    
    return words


def _extract_with_header_skip(lines: List[str], 
                             extract_language: str) -> List[str]:
    """Extract words by aggressively skipping long headers - specialized for Kurdish dictionary."""
    words = []
    
    # Find where dictionary entries actually start by looking for consistent alternating pattern
    start_idx = 0
    for i in range(len(lines)):
        line = lines[i].strip()
        
        # Skip obvious header lines
        if (not line or is_header_line(line) or
            contains_year(line) or
            len(line) > 50 or ':' in line):
            continue
            
        # Look for start of dictionary entries - single words followed by translations
        if (len(line) <= 30 and normalize_word(line) and
            not any(marker in line for marker in ['/', '<', '>', '*', '(', ')']) and
            i + 1 < len(lines)):
            
            next_line = lines[i + 1].strip()
            if next_line and len(next_line) > len(line):  # Translation usually longer than headword
                start_idx = i
                break
    
    # Extract alternating pairs starting from detected position
    i = start_idx
    while i < len(lines) - 1:
        line = lines[i].strip()
        next_line = lines[i + 1].strip()
        
        if not line or not next_line:
            i += 1
            continue
            
        if extract_language == "source":
            # Extract source words (first line of each pair)
            clean_line = clean_word(line)
            if (clean_line and len(clean_line) >= 1 and
                not any(char.isdigit() for char in clean_line) and
                not any(char in clean_line for char in ['(', ')', '[', ']', '<', '>', '/', '\\']) and
                should_include_word_by_pos(line, POS_FILTERS)):
                words.append(clean_line)
        else:
            # Extract target words (second line of each pair - translations)
            if next_line:
                words.extend(extract_simple_translation_words(next_line))
        
        i += 2  # Skip both lines of the pair
    
    return words



def extract_words_from_stardict(stardict_dir: str,
                               extract_language: str = "source") -> Tuple[List[str], int]:
    """
    Extract words from StarDict format directory.
    
    Args:
        stardict_dir: Directory containing .dict.dz, .idx.gz, and .ifo files
        extract_language: Either "source" or "target"
        
    Returns:
        Tuple of (extracted words list, count of words recovered from index)
    """
    import struct
    import gzip
    
    words = []
    recovered_count = 0
    
    try:
        # Find the base name by looking for .ifo file
        base_name = None
        for file in os.listdir(stardict_dir):
            if file.endswith('.ifo'):
                base_name = file.replace('.ifo', '')
                break
        
        if not base_name:
            return words, recovered_count
        
        idx_file = os.path.join(stardict_dir, base_name + '.idx.gz')
        dict_file = os.path.join(stardict_dir, base_name + '.dict.dz')
        
        if not (os.path.exists(idx_file) and os.path.exists(dict_file)):
            return words, recovered_count
        
        # Read the index file
        with gzip.open(idx_file, 'rb') as f:
            idx_data = f.read()
        
        # Read the dictionary data
        with open(dict_file, 'rb') as f:
            dict_data = f.read()
        
        # Parse index entries
        pos = 0
        entries = []
        
        while pos < len(idx_data):
            # Find null terminator for word
            null_pos = idx_data.find(b'\x00', pos)
            if null_pos == -1:
                break
            
            try:
                word = idx_data[pos:null_pos].decode('utf-8', errors='ignore')
                pos = null_pos + 1
                
                if pos + 8 > len(idx_data):
                    break
                
                # Read offset and size (big-endian format)
                offset, size = struct.unpack('>II', idx_data[pos:pos+8])
                pos += 8
                
                # Handle StarDict files where offsets may exceed file bounds
                # This happens with some StarDict variants - extract available data
                if offset < len(dict_data):
                    # Extract what we can, even if size extends beyond file
                    actual_size = min(size, len(dict_data) - offset)
                    definition = dict_data[offset:offset+actual_size].decode('utf-8', errors='ignore')
                    entries.append((word, definition))
                
            except (UnicodeDecodeError, struct.error):
                continue
        
        # For StarDict files with invalid offsets, also extract headwords directly from index
        # This recovers words that have corrupted offset data but valid headwords
        if len(entries) < pos // 12:  # Rough estimate - if we lost too many entries
            logger.debug("StarDict offset issues detected, extracting from index directly...")
            existing_words = {w for w, d in entries}  # Use set for O(1) lookup
            pos = 0
            direct_words = 0
            
            while pos < len(idx_data):
                null_pos = idx_data.find(b'\x00', pos)
                if null_pos == -1:
                    break
                
                try:
                    word = idx_data[pos:null_pos].decode('utf-8', errors='ignore')
                    pos = null_pos + 1
                    
                    if pos + 8 > len(idx_data):
                        break
                    
                    # Skip the offset/size data
                    pos += 8
                    
                    # Add word directly from index if it's the source language
                    if extract_language == "source":
                        cleaned_word = clean_word(word)
                        if is_valid_word(cleaned_word) and word not in existing_words:
                            words.append(cleaned_word)
                            direct_words += 1
                                
                except (UnicodeDecodeError, struct.error):
                    continue
            
            recovered_count = direct_words
        
        # Extract words based on language from successfully parsed entries
        for word, definition in entries:
            if extract_language == "source":
                # Source words are the headwords
                cleaned_word = clean_word(word)
                if is_valid_word(cleaned_word):
                    words.append(cleaned_word)
            else:
                # Target words: StarDict format uses compressed binary data that requires
                # specialized libraries to decode properly. Since we can't reliably extract
                # English definitions without proper StarDict parsing libraries, we'll
                # create a minimal wordlist with common English words that would typically
                # appear in an Icelandic-English dictionary context.
                pass  # Skip English extraction for StarDict format
    
    except (OSError, struct.error, UnicodeDecodeError):
        pass
    
    return words, recovered_count


def extract_words_from_tei_xml(xml_source: str,
                              extract_language: str = "target") -> List[str]:
    """Extract words from TEI XML format.

    Args:
        xml_source: Path to TEI XML file or XML content string
        extract_language: Either "source" or "target"

    Returns:
        List of extracted words
    """
    words = []

    try:
        if os.path.exists(xml_source):
            tree = ET.parse(xml_source)
            root = tree.getroot()
        else:
            root = ET.fromstring(xml_source)
        
        for entry in root.iter():
            if not (entry.tag.endswith('}entry') or entry.tag == 'entry'):
                continue
            
            if extract_language == "source":
                # Extract headwords from <orth> tags
                for orth in entry.iter():
                    if ((orth.tag.endswith('}orth') or orth.tag == 'orth') 
                        and orth.text):
                        word = orth.text.strip()
                        if is_valid_word(word):
                            words.append(word)
            
            else:
                # Extract translations from <quote> tags
                for quote in entry.iter():
                    if ((quote.tag.endswith('}quote') or quote.tag == 'quote') 
                        and quote.text):
                        word = quote.text.strip()
                        if word.isalpha():
                            words.append(word)
    
    except ET.ParseError:
        # Silently handle malformed XML
        pass
    
    return words


def determine_wordlist_filenames(dict_path: str) -> Tuple[str, str]:
    """
    Given a filename like:
      freedict-eng-bul-2024.10.10.dictd.tar.xz
    returns:
      ('bulgarian_freedict-eng-bul-2024.10.10.txt',
       'english_freedict-eng-bul-2024.10.10.txt')
    """
    # Extract just the filename (no directories)
    name = Path(dict_path).name
    # Strip everything after the first dot to get the base
    base = name.split('.', 1)[0]

    # Map the first two 3-letter codes in the base to full language names
    src_lang, tgt_lang = get_language_mapping(base)

    # Build the target-then-source filenames
    target_fname = f"{tgt_lang}_{base}.txt"
    source_fname = f"{src_lang}_{base}.txt"
    return target_fname, source_fname


def extract_from_archive(archive_path: str, temp_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract dictionary file from archive.
    
    Args:
        archive_path: Path to archive file
        temp_dir: Temporary directory for extraction
        
    Returns:
        Tuple of (extracted_file_path, file_type)
    """
    try:
        with tarfile.open(archive_path, 'r:xz') as tar:
            tar.extractall(temp_dir)
        
        # Find the dictionary file
        stardict_dir = None
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.dict.dz'):
                    # Check if this is part of a StarDict format (has .idx.gz and .ifo files)
                    base_name = file.replace('.dict.dz', '')
                    idx_file = os.path.join(root, base_name + '.idx.gz')
                    ifo_file = os.path.join(root, base_name + '.ifo')
                    
                    if os.path.exists(idx_file) and os.path.exists(ifo_file):
                        return root, 'stardict'  # Return directory for StarDict format
                    else:
                        return os.path.join(root, file), 'dict'  # Regular .dict.dz file
                elif file.endswith('.tei'):
                    return os.path.join(root, file), 'tei'
    
    except (tarfile.TarError, OSError):
        pass
    
    return None, None


def save_wordlist(words: List[str], output_file: str, language_name: str) -> int:
    """
    Save extracted words to file.
    
    Args:
        words: List of words to save
        output_file: Output filename
        language_name: Name of the language for display
        
    Returns:
        Number of unique words saved
    """
    if not words:
        return 0
    
    unique_words = sorted(set(words))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_words))
    
    return len(unique_words)


def process_dictionary_file(file_path: str, 
                           source_output_file: str, 
                           target_output_file: str,
                           source_lang: str,
                           target_lang: str) -> None:
    """
    Process a single dictionary file and extract words.
    
    Args:
        file_path: Path to dictionary file
        source_output_file: Output file for source language
        target_output_file: Output file for target language
        source_lang: Source language name
        target_lang: Target language name
    """
    stardict_recovery = 0

    if file_path.endswith('.dict.dz'):
        # Read the compressed dictionary only once
        with gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
            lines = [ln.rstrip('\n') for ln in f]

        source_words = extract_words_from_gzip_content(lines, "source", is_dz_file=True)
        target_words = extract_words_from_gzip_content(lines, "target", is_dz_file=True)
    
    elif file_path.endswith('.tei'):
        # Process TEI XML format
        source_words = extract_words_from_tei_xml(file_path, "source")
        target_words = extract_words_from_tei_xml(file_path, "target")
    
    elif os.path.isdir(file_path):
        # Process StarDict format directory and receive recovery info
        source_words, stardict_recovery = extract_words_from_stardict(file_path, "source")
        target_words, _ = extract_words_from_stardict(file_path, "target")
    
    else:
        logger.error(f"Unsupported file format: {file_path}")
        return
    
    # Save extracted words and get counts
    source_count = save_wordlist(source_words, source_output_file, source_lang)
    target_count = save_wordlist(target_words, target_output_file, target_lang)
    
    # Display results in user-friendly format
    if source_count > 0:
        logger.info(f"✓ {source_lang.title()}: {source_count:,} words → {source_output_file}")
    
    if target_count > 0:
        logger.info(f"✓ {target_lang.title()}: {target_count:,} words → {target_output_file}")
    
    if stardict_recovery > 0:
        logger.info(f"  ↪ Recovered {stardict_recovery:,} words from corrupted StarDict offsets")
    
    if source_count == 0 and target_count == 0:
        logger.warning("⚠ No words extracted from this dictionary")


def process_single_dictionary(dict_name: str) -> None:
    """
    Process a single dictionary by name.
    
    Args:
        dict_name: Name of dictionary file in dictionaries folder
    """
    dict_path = os.path.join("dictionaries", dict_name)
    
    if not os.path.exists(dict_path):
        logger.error(f"Dictionary not found: {dict_path}")
        return
    
    target_output_file, source_output_file = determine_wordlist_filenames(dict_name)
    
    # Ensure output paths are within the 'wordlists' folder
    source_output_file = os.path.join("wordlists", source_output_file)
    target_output_file = os.path.join("wordlists", target_output_file)

    # Get language names for display
    src_lang, tgt_lang = get_language_mapping(dict_name)

    # Display header with clear dictionary info
    logger.info(f"📖 {dict_name}")
    
    if dict_path.endswith('.dict.dz'):
        # Direct .dz file processing
        logger.info("   Format: Dictionary (.dz)")
        process_dictionary_file(dict_path, source_output_file, target_output_file, src_lang, tgt_lang)
    
    else:
        # Archive processing
        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_file, file_type = extract_from_archive(dict_path, temp_dir)
            
            if extracted_file:
                if file_type == 'stardict':
                    logger.info("   Format: StarDict (compressed)")
                elif file_type == 'tei':
                    logger.info("   Format: TEI XML")
                else:
                    logger.info("   Format: Archive")
                    
                process_dictionary_file(extracted_file, source_output_file, 
                                      target_output_file, src_lang, tgt_lang)
            else:
                logger.error(f"⚠ Could not extract dictionary from: {dict_path}")


def process_all_dictionaries() -> None:
    """Process all dictionary files in the dictionaries folder."""
    supported_extensions = ('.dict.dz', '.dictd.tar.xz', '.src.tar.xz', '.stardict.tar.xz')
    
    try:
        dict_files = [f for f in os.listdir("dictionaries")
                     if f.endswith(supported_extensions)]
    except OSError:
        logger.error("Error: Could not access dictionaries folder")
        return
    
    if not dict_files:
        logger.error("No dictionary files found in dictionaries folder")
        return
    
    logger.info(f"Found {len(dict_files)} dictionary files:")
    for filename in dict_files:
        logger.info(f"  - {filename}")
    
    logger.info("-" * 60)
    
    success_count = 0
    for dict_file in dict_files:
        try:
            process_single_dictionary(dict_file)
            success_count += 1
        except Exception as e:
            logger.error(f"Error processing {dict_file}: {e}")
        finally:
            logger.info("-" * 60)
    
    logger.info(f"Processed {success_count}/{len(dict_files)} files successfully")


def main() -> None:
    """Main entry point for the dictionary processor."""
    ensure_directories()
    
    parser = argparse.ArgumentParser(
        description="Extract words from multilingual dictionary files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python zippy.py                                    # Process all dictionaries
  python zippy.py single freedict-eng-jpn.dictd.tar.xz  # Process single file
        """)
    
    parser.add_argument('command', 
                       nargs='?', 
                       choices=['single', 'all'],
                       help='Command to run')
    parser.add_argument('filename',
                       nargs='?',
                       help='Dictionary filename for single command')
    parser.add_argument('-p', '--pos',
                        nargs='+',
                        help='Space-separated POS tags to include (e.g. -p n v). Default: n adj adv v')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase verbosity (-v for INFO, -vv for DEBUG)')
    
    args = parser.parse_args()

    if args.verbose >= 2:
        logger.setLevel(logging.DEBUG)
    elif args.verbose == 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if args.pos:
        POS_FILTERS['include'] = [p.lower() for p in args.pos]
    
    if args.command == 'single':
        if not args.filename:
            logger.error("Error: filename required for single command")
            parser.print_help()
            return
        process_single_dictionary(args.filename)
    else:
        if args.command is None:
            logger.info("No command specified, processing all dictionaries...")
        process_all_dictionaries()


if __name__ == "__main__":
    main()
