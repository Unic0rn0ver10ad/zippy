# Zippy the Dict 2.0!
<img src="Zippy2.png" alt="Meet Zippy the Dict 2.0!" width="300">

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