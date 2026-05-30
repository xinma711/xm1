"""File read/write tools"""

from pathlib import Path

from xm.tools import ToolDef


def read_file(path: str, limit: int = 2000) -> str:
    """Read a file's contents."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        if len(lines) > limit:
            return "\n".join(lines[:limit]) + f"\n... ({len(lines)} total lines)"
        return content
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


READ_FILE_TOOL = ToolDef(
    name="read_file",
    description="Read the contents of a file. Returns the text content.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            },
            "limit": {
                "type": "integer",
                "description": "Max lines to read (default: 2000)",
                "default": 2000,
            },
        },
        "required": ["path"],
    },
    handler=read_file,
)

WRITE_FILE_TOOL = ToolDef(
    name="write_file",
    description="Write content to a file. Creates parent directories if needed.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
    handler=write_file,
)
