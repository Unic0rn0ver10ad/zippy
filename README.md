# 🤖 Zippy 2.0 Is Here!

<img src="Zippy2.png" alt="Meet Zippy 2.0!" width="300">

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Zippy 2.0 (it/its) extracts structured wordlists from several different dictionary formats for use in the [Halt! What's the Passphrase?](https://github.com/Unic0rn0ver10ad/halt-whats-the-passphrase) project and other passphrase-generation tools. Zippy eats dictionaries and spits out wordlists.

Supported formats:
- .dz (gzipped dictionary files)
- .dictd.tar.xz (FreeDict archive format)
- .src.tar.xz (TEI XML source format)

---

## 🤖 Zippy 2.0 Is Proud Of Its Heritage!

**Zippy 2.0** is not handcrafted, artisinal, or a pet. It is 100% the product of AI code generation, refinement, and augmentation. It represents what a purely functional, AI-generated utility looks like when allowed to evolve through self-directed trial-and-error iteration under human guidance - and not very good guidance at that. Zippy is *not pretending* to be a traditionally engineered tool - and we shouldn't pretend that, either.

- **Every line** of Zippy had been written and re-written by multiple agentic coding systems.
- There has been no attempt to provide any human-authored logic, structure, or flow.
- Zippy is proud of every one of its big beautiful lines of code - there will be no code-shaming here. And y'all need to stop saying "code vomit" like it's a bad thing 🤮

---

## 🤔 Zippy 2.0 Has A Design Philosophy!

Zippy was designed to be:
- **Monolithic**: This single-file structure signals to humans and AIs alike that Zippy is *one thing*. Zippy isn't a library. It isn't a module. It’s definitely not a framework. It’s just a (very long) script. A complete program in one file is easier for AIs to ingest, interpret, and modify. It also makes it easier for humans to supervise the AI that is doing those things, and feel confident that the AI is "following orders" — even if that’s mostly for our own peace of mind 🫡
- **Functional** — It does the job, mostly correctly and sort of efficiently.
- **Unpretentious** — Zippy is *not pretending* to be a traditionally engineered tool - and we shouldn't pretend that, either.
- **Inscrutable** — We're using a black box (AI) to build a black box (Zippy 2.0). As above, let's not pretend we know (or even need to know) what's going on under the hood.
- **Extensible (by AI)** — The above having been said, we need to be able to expand on Zippy's capability from time to time. Such tinkering will most likely be performed by AI agents, not humans. With that in mind, all of Zippy's functions are scoped and documented to support agentic understanding, not human understanding.
- **Readable (by Humans)** — The above having been said, of course we're going to want to read Zippy's code - if for no other reason than to satisfy our own curiosity. Or maybe because if we can't at least pretend like we know what's going on, we'll collectively reach for our ⋔ pitchforks and 🔦 torches.

---

## 🕺💃🪩 Zippy is ready to RUMBA!

Zippy is built on a new coding paradigm, RUMBA: Read, Understood, Maintained by Agents. If you've never heard about it before, it's because I invented / discovered it. RUMBA is the future!

## 📦 Installation & Prerequisites

Zippy 2.0 requires **Python 3.8 or higher** and uses only standard library modules - no external dependencies required!

### Quick Start
1. Clone this repository
2. Ensure you have Python 3.8+ installed
3. Place your dictionary files in the `dictionaries/` folder
4. Run Zippy!

```bash
git clone https://github.com/your-username/zippy-review.git
cd zippy-review/zippy
python zippy.py
```

## 🦾 How to Use Zippy 2.0!

All dictionaries must be placed in the 'dictionaries' folder for processing. The extracted wordlists will be saved in the 'wordlists' folder. Each dictionary will generate two wordlists: one for the source language and one for the target language. The filenames are based on the dictionary name and possibly the language codes from LANGUAGE_MAPPINGS.

Zippy includes parts-of-speech (POS) filtering to improve wordlist quality for passphrase generation. Instead of extracting every word, it focuses on content words like nouns, adjectives, verbs, and adverbs while filtering out function words such as articles, prepositions, and pronouns. The system automatically adapts to different languages and their grammatical features, handling everything from simple English dictionaries to complex gendered noun systems in Romance languages. This significantly reduces manual cleanup work and produces wordlists better suited for creating memorable and secure passphrases.

Zippy can be run from the command line in two modes: all or single. The 'all' mode (this is the default mode) processes all dictionaries in the 'dictionaries' folder:

    python zippy.py

The 'single' mode processes a single dictionary file specified by the user:

    python zippy.py single freedict-eng-jpn-2024.10.10.dictd.tar.xz

You can restrict the parts of speech included in the output with the ``--pos``
flag. By default, nouns, adjectives, adverbs and verbs are included.  The flag
accepts a space-separated list of POS tags:

    python zippy.py --pos n v        # nouns and verbs only
    python zippy.py --pos n          # nouns only

The ``--pos`` option only works on dictionaries that actually contain POS tags.
Zippy will tell you whether tags were found when ``-v`` or ``-vv`` is used.
Use ``-pe`` to skip the English wordlist when a dictionary includes English. Dictionaries without English still produce two wordlists.
When processing FreeDict archives in either mode, Zippy shows the detected license for each dictionary.
When running ``process-all`` a ``licenses.md`` file summarizing each dictionary's license is created automatically.

Zippy also has some debug / logging levels you can set like this:

    python zippy.py -v               # show progress messages (includes POS tag info)
    python zippy.py -vv              # debug output (more detail)

Almost all of the dictionaries used in this project are from FreeDict:
https://freedict.org/downloads/

The wordlists that Zippy extracts from the dictionaries are honestly not that great. They usually contain a lot of words not in the desired language at the beginning of the file. You'll need to go through each one manually and delete the words that aren't in the desired language - deal with that 🐶

After cleaning the raw wordlist, the next step is to turn it into a wordlist that's actually useful for generating passphrases. The EFF has a very good article on it here: https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases

One technique is to feed the article itself into a reasoning model like [INSERT FAVORITE LLM HERE], along with the wordlist, and ask it to generate a new wordlist that fits the EFF criteria and is fewer than 7,500 entries. 7,500 is an arbitrary number, but it's a good starting point and mimics the size of the EFF's 'large wordlist' here: https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt

Spot-checking the output of the reasoning model (say, by using Google Translate) is a good idea to convince yourself that the resulting wordlist actually produces fun and memorable passphrases.
