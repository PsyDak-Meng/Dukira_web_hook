# CLAUDE.md

Follow these rules at all times @/root/RULES.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RepoAgent** is an LLM-powered framework for repository-level code documentation generation. It automatically analyzes code repositories and generates comprehensive documentation in markdown format. The project consists of two main components:

- **Core documentation engine** (`repo_agent/`) - Handles code analysis, change detection, and document generation
- **Chat interface** (`repo_agent/chat_with_repo/`) - Provides interactive Q&A functionality for repository exploration

## Architecture

### Core Components

- **`main.py`** - CLI entry point with Click-based command interface
- **`runner.py`** - Main execution engine that orchestrates the documentation process
- **`change_detector.py`** - Git-based change detection for incremental documentation updates
- **`project_manager.py`** - Repository structure analysis and hierarchy management
- **`doc_meta_info.py`** - Metadata management for tracking documentation state
- **`settings.py`** - Pydantic-based configuration management with environment variable support
- **`multi_task_dispatch.py`** - Multi-threaded document generation coordination

### Chat System

- **`chat_with_repo/`** - Standalone module for repository Q&A functionality
- **`rag.py`** - RAG implementation for document retrieval
- **`vector_store_manager.py`** - Vector storage for semantic search
- **`gradio_interface.py`** - Web UI for chat functionality

## Development Commands

### Environment Setup
```bash
# Install PDM (package manager)
pip install pdm

# Install dependencies
pdm install

# Install with chat functionality
pdm install -G chat_with_repo

# Activate virtual environment
pdm venv activate
```

### Core Commands
```bash
# Generate/update documentation
repoagent run

# Preview changes without generating docs
repoagent diff

# Clean generated cache files
repoagent clean

# Start chat interface
repoagent chat-with-repo
```

### Testing
```bash
# Run all tests
pdm run pytest

# Run specific test file
pdm run pytest tests/test_change_detector.py

# Run with verbose output
pdm run pytest -v
```

### Code Quality
```bash
# Run linting (imports only per ruff config)
pdm run ruff check

# Auto-fix import issues
pdm run ruff check --fix

# Format code
pdm run ruff format
```

## Configuration

The project uses Pydantic settings with environment variable support. Key configuration:

- **OPENAI_API_KEY** - Required for LLM functionality
- **Target repository path** - Directory to analyze (default: current directory)
- **Model selection** - Default: `gpt-4o-mini`
- **Output paths** - `.project_doc_record` (hierarchy), `markdown_docs/` (output)

## Key Files to Understand

- **`repo_agent/settings.py:26-68`** - Configuration schema and validation
- **`repo_agent/main.py:140-182`** - CLI command definitions and parameter handling
- **`repo_agent/doc_meta_info.py`** - Core data structures for documentation metadata
- **`repo_agent/change_detector.py`** - Git integration for incremental updates

## Development Notes

- Uses **PDM** for dependency management instead of pip/poetry
- Supports **pre-commit hooks** for automatic documentation updates
- **Multi-threaded processing** for large repositories
- **Git-aware** change detection to avoid redundant documentation generation
- **Language-agnostic** output with configurable target languages