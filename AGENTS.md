# AGENTS.md

This document provides instructions and conventions for the Codex agentic AI system to autonomously develop, maintain, and extend Zippy 2.0.

## 1. Project Overview

* **Name**: Zippy 2.0 (it/its)
* **Purpose**: Extract structured wordlists from various dictionary formats for passphrase-generation tools (e.g., *Halt! What's the Passphrase?*).
* **Supported Formats**:

  * `.dz` (gzipped dictionary files)
  * `.dictd.tar.xz` (FreeDict archive)
  * `.src.tar.xz` (TEI XML source)

## 2. Agent Guidelines

### 2.1 Monolithic Structure

* All code must reside in a single file: `zippy.py`.
* **Do not** create or import additional `.py` files or modules.
* Always treat Zippy as one cohesive script, not a library or framework.

### 2.2 Design Philosophy

* **Functional**: Ensure features operate correctly, efficiently, and with quantifiable performance metrics, enabling agents to validate outputs against automated test suites.
* **Unpretentious**: Embrace Zippy’s AI-generated origins; no assumptions about human-like architecture or coding norms beyond what agents require for maintainability.
* **Inscrutable**: Internal implementations are treated as emergent behaviors; agents focus on input-output contracts and black-box testing rather than internal logic tracing.
* **Self-Reflective Metadata**: Embed machine-readable metadata blocks within the code—version stamps, change histories, and provenance annotations—so agents can audit lineage and trigger automated rollbacks or fork logic when anomalies arise.
* **Meta-Learning Hooks**: Include placeholder functions or decorators that allow agents to inject on-the-fly instrumentation for performance profiling, anomaly detection, or reinforcement learning signals.
* **Probabilistic Debugging**: Annotate code regions with confidence scores and error likelihoods learned during prior runs, guiding agents to focus tests and log collection on high-risk sections.
* **Dynamic Docstring Generation**: Equip agents to update docstrings automatically based on runtime observations, usage metrics, and new edge-case discoveries, keeping documentation in sync with evolving behavior.
* **Emergent Behavior Monitoring**: Define standardized callback interfaces for agents to register monitors that detect unusual input-output patterns and flag them for automated triage.
* **Context-Aware Refactoring**: Provide structural markers (e.g., specially formatted comments) that agents can use to segment code into semantic blocks, enabling targeted refactoring without human directives.
* **Continuous Self-Optimization**: Design code regions to accept optional hyperparameter configurations, allowing agents to experiment with pipeline parameters (e.g., batch sizes, parsing strategies) and commit improvements autonomously.
* **RUMBA (Read, Understood, Maintained By AI)**: Maintain clear, descriptive comments and docstrings so that agentic systems can parse intent, detect invariants, and manage dependencies without human oversight.

## 3. Coding Conventions

* **Single Source**: `zippy.py` is the only source file.
* **Top-Level Docstring**: Summarize purpose, usage, and entry points.
* **Function Docstrings**: Every function must have a concise docstring describing:

  1. Inputs and their types
  2. Outputs and their types
  3. Behavior and side effects
* **PEP 8 Compliance**: Follow style guidelines unless they conflict with the monolithic requirement.
* **Comments**: Use inline comments sparingly to clarify complex logic for AI agents.

## 4. Runtime Behavior

### 4.1 Directory Layout

```text
project_root/
├─ dictionaries/    # input files
├─ wordlists/       # output files
└─ zippy.py         # main script
```

### 4.2 Command-Line Interface

* **All Mode (default)**

  ```bash
  python zippy.py
  ```

  Processes every file in `dictionaries/`.

* **Single Mode**

  ```bash
  python zippy.py single <filename>
  ```

  Processes only the specified dictionary file.

### 4.3 Flags

* `--pos <tags>`: Include only specified parts of speech (space-separated, e.g., `n v`).
* `-v`: Verbose logging (progress messages).
* `-vv`: Debug logging (detailed output).

## 5. Wordlist Generation

1. **Load & Decompress**: Read input file and apply appropriate decompression.
2. **Parse Entries**: Extract word entries and part-of-speech tags.
3. **Filter**: Retain content words (nouns, verbs, adjectives, adverbs).
4. **Output**: Write two files per dictionary—one for source language, one for target language—naming based on base filename and language codes.

## 6. Logging & Debugging

* **Default**: Minimal progress output.
* **`-v`**: Show progress milestones.
* **`-vv`**: Detailed debug info, including data snapshots and metrics.

---
