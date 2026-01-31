# AGENTS.md

This file provides guidance for AI coding agents working on the Hachimi voice assistant project.

## Build, Test, and Lint Commands

### Run the Voice Assistant
```bash
python run.py
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Test Commands
The project has a single test file using Python's `unittest` framework:

```bash
# Run all tests in test_context_summary.py
python tests/test_context_summary.py

# Run specific test function (modify if __name__ == "__main__" block to select)
python tests/test_context_summary.py  # Currently runs all 7 tests by default
```

**Available Test Functions:**
- `test_config.py` - Configuration management tests
- `test_logger.py` - Logging system tests
- `test_context_summary.py` tests:
  - `test_summarization_enabled()` - Test context summarization feature
- `test_summarization_disabled()` - Test default behavior without summarization
- `test_time_expiration()` - Test time-based context expiration
- `test_summary_role()` - Test custom summary role configuration
- `test_llm_summarization()` - Test LLM-based summarization (requires mock)
- `test_summary_length_config()` - Test summary length configuration
- `test_summary_prompt_template()` - Test custom summary prompt templates

**Note**: Tests use `unittest.mock` and direct module imports. No pytest or other test frameworks configured.

### Lint and Type Check
```bash
# No lint commands available (no linting tools configured)
# No type checking configured (no mypy or pyright)
```

## Code Style Guidelines

### Imports
- **Ordering**: Mixed - some files group imports logically (stdlib → third-party → local), others are mixed

### Type Hints
- **Usage**: Consistent type hints on function signatures and class methods

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `Config`, `MCPVoiceAgent`, `ContextManager`)
- **Functions/Methods**: `snake_case` (e.g., `process_tts`, `get_all_tools`, `_load_config`)
- **Variables**: `snake_case` (e.g., `audio_queue`, `tts_text`, `server_name`)
- **Private members**: `_prefix` (e.g., `_config`, `_load_config`, `_resolve_env_vars`)

### Error Handling
- **Style**: Try-except blocks with specific exception handling where appropriate
- **Logging**: Use the global `logger` from `logger.py` for error reporting

### Docstrings
- **Style**: Google-style docstrings or simple comments for function/method documentation
- **Language**: Mixed - some modules use Chinese docstrings, some use English

### Logging
- **Usage**: Import `logger` from `logger.py` (global instance)
- **Levels**: `logger.info()`, `logger.debug()`, `logger.warning()`, `logger.error()`, `logger.exception()`
- **Style**: Include process/module prefix in messages (e.g., `[STT]`, `[LLM]`, `[TTS]`)

### String Formatting
- **Style**: Prefer f-strings for interpolation
- **Encoding**: Use explicit `encoding='utf-8'` for file operations

## Architecture Notes

### Multiprocessing
- Uses `multiprocessing` with `spawn` method (cross-platform compatibility)
- Four main processes: KWS, STT, LLM, TTS
- Communication via `multiprocessing.Queue` and `multiprocessing.Event`

### Async/Await
- LLM/MCP module uses `asyncio` for async operations
- Use `async with` context managers for resource management

### Configuration
- Loaded from `config.yaml` via `config.py`
- Supports environment variable substitution: `${VAR_NAME:default_value}`
- Environment variables documented in `.env.example`

### MCP Integration
- Supports both SSE and Stdio MCP servers
- Multiple servers configurable in `config.yaml`
- Vector-based tool selection using BGE-M3-1288 embeddings

### Context Management
- `ContextManager` supports time-based and turn-based context expiration
- Optional LLM-based summarization when context exceeds limits
- Configurable summary prompts and token limits

## Development Practices

- **Mixed Language**: Codebase contains Chinese and English comments/docstrings
- **Emoji Logging**: Emojis used in log messages (🚀, ✅, ❌, etc.)
- **No Type Checking**: No mypy or type stubs configured
- **No Linting**: No pylint, flake8, or ruff configured
- **Minimal Tests**: Single test file for context manager only

## Key Files

- `main.py`: Entry point, multiprocessing setup
- `config.py`: Configuration management with env var substitution
- `config.yaml`: Central configuration file
- `logger.py`: Unified logging system
- `voice_listener.py`: Wake word detection and VAD
- `stt.py`: Speech-to-Text processing
- `tts.py`: Text-to-Speech playback
- `llm_mcp_host/`: MCP host module (agent.py, mcp_manager.py, context_manager.py, etc.)
- `test_context_summary.py`: Unit tests for context manager
- `.env.example`: Environment variable template
