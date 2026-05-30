# xm

Minimal AI agent shell. Chat with LLMs, execute tools, manage sessions.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Interactive mode
xm

# One-shot
xm ask "what time is it?"

# TUI mode
xm tui

# List tools
xm tools

# List sessions
xm sessions
```

## Configuration

Set your API endpoint:

```bash
# OpenAI or compatible
export OPENAI_BASE_URL=http://your-endpoint/v1
export OPENAI_API_KEY=your-key  # or leave empty for local
```

## Features

- Tool execution (shell, file read/write, web fetch)
- Session persistence (SQLite)
- Multiple LLM providers
- TUI interface (Textual)

## Phase 1 Complete

- [x] LLM provider abstraction
- [x] Tool registry + shell/file/web tools
- [x] Agent dispatcher (tool call loop)
- [x] Basic CLI
- [x] Session storage (SQLite)
- [x] TUI interface
