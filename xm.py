#!/usr/bin/env python3
"""xm - Minimal AI agent shell (single file version)"""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Auto-install dependencies
def ensure_deps():
    deps = ["openai", "httpx"]
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "-q"])

ensure_deps()

import httpx
from openai import AsyncOpenAI

VERSION = "0.1.0"
CONFIG_DIR = Path.home() / ".xm"
DB_FILE = CONFIG_DIR / "sessions.db"

def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM ──────────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class Response:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""

class LLM(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> Response:
        pass

class OpenAILLM(LLM):
    def __init__(self, model: str = "deepseek-v4-flash"):
        self.model = model
        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "")
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
            if not api_key:
                api_key = "not-needed"
        kwargs["api_key"] = api_key or "not-needed"
        self.client = AsyncOpenAI(**kwargs)

    async def chat(self, messages, tools=None, model=None):
        kwargs = {"model": model or self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = await self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments)))
        return Response(content=msg.content, tool_calls=tool_calls, model=resp.model)

# ── Tools ────────────────────────────────────────────────────────────────

@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    handler: callable

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef):
        self._tools[tool.name] = tool

    def get_definitions(self):
        return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in self._tools.values()]

    async def execute(self, name, arguments):
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            import inspect
            result = tool.handler(**arguments)
            if inspect.isawaitable(result):
                result = await result
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def list_tools(self):
        return list(self._tools.keys())

async def run_shell(command: str, timeout: int = 30) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            err = stderr.decode("utf-8", errors="replace")
            if err:
                output += f"\n[stderr]\n{err}"
        return output or "(no output)"
    except asyncio.TimeoutError:
        return f"Error: timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"

def read_file(path: str, limit: int = 2000) -> str:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: not found: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        if len(lines) > limit:
            return "\n".join(lines[:limit]) + f"\n... ({len(lines)} total)"
        return content
    except Exception as e:
        return f"Error: {e}"

def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

async def fetch_url(url: str, max_length: int = 5000) -> str:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "xm/0.1"})
            resp.raise_for_status()
            text = resp.text[:max_length]
            if len(resp.text) > max_length:
                text += f"\n... (truncated)"
            return text
    except Exception as e:
        return f"Error: {e}"

def build_tools():
    reg = ToolRegistry()
    reg.register(ToolDef("run_shell", "Execute a shell command", {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer", "default": 30}}, "required": ["command"]}, run_shell))
    reg.register(ToolDef("read_file", "Read file contents", {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer", "default": 2000}}, "required": ["path"]}, read_file))
    reg.register(ToolDef("write_file", "Write to a file", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}, write_file))
    reg.register(ToolDef("fetch_url", "Fetch URL content", {"type": "object", "properties": {"url": {"type": "string"}, "max_length": {"type": "integer", "default": 5000}}, "required": ["url"]}, fetch_url))
    return reg

# ── Session ──────────────────────────────────────────────────────────────

class Session:
    def __init__(self):
        ensure_config_dir()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, tool_call_id TEXT, created_at TEXT);
        """)
        self.conn.commit()
        self.id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        self.conn.execute("INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)", (self.id, now, now))
        self.conn.commit()

    def add_message(self, role, content=None, tool_calls=None, tool_call_id=None):
        now = datetime.now().isoformat()
        self.conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (self.id, role, content, json.dumps(tool_calls) if tool_calls else None, tool_call_id, now))
        self.conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, self.id))
        self.conn.commit()

    def get_messages(self):
        rows = self.conn.execute("SELECT role, content, tool_calls, tool_call_id FROM messages WHERE session_id = ? ORDER BY id", (self.id,)).fetchall()
        msgs = []
        for r in rows:
            m = {"role": r["role"]}
            if r["content"]: m["content"] = r["content"]
            if r["tool_calls"]: m["tool_calls"] = json.loads(r["tool_calls"])
            if r["tool_call_id"]: m["tool_call_id"] = r["tool_call_id"]
            msgs.append(m)
        return msgs

    def close(self):
        self.conn.close()

# ── Agent ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = "You are xm, a minimal AI agent. You have tools: run_shell, read_file, write_file, fetch_url. Be concise."

async def agent_run(user_message: str, session: Session, llm: LLM, tools: ToolRegistry) -> str:
    session.add_message("user", user_message)
    messages = session.get_messages()
    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    tool_defs = tools.get_definitions()

    while True:
        response = await llm.chat(messages=messages, tools=tool_defs)
        tc_data = None
        if response.tool_calls:
            tc_data = [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}} for tc in response.tool_calls]
        session.add_message("assistant", content=response.content, tool_calls=tc_data)

        if not response.tool_calls:
            return response.content or ""

        for tc in response.tool_calls:
            result = await tools.execute(tc.name, tc.arguments)
            session.add_message("tool", content=result, tool_call_id=tc.id)

        messages = session.get_messages()
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

# ── CLI ──────────────────────────────────────────────────────────────────

def print_help():
    print(f"xm v{VERSION} - Minimal AI agent")
    print("Usage: python3 xm.py [ask \"question\"] | [tui]")
    print("  (no args)  - Interactive chat")
    print("  ask TEXT   - One-shot question")
    print("  tui        - TUI mode (requires: pip install textual)")
    print("  tools      - List tools")
    print("  sessions   - List sessions")

async def interactive():
    llm = OpenAILLM()
    tools = build_tools()
    session = Session()
    print(f"xm v{VERSION} | session: {session.id}\n")

    while True:
        try:
            msg = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not msg.strip():
            continue
        if msg.strip() == "/quit":
            break
        if msg.strip() == "/new":
            session.close()
            session = Session()
            print(f"New session: {session.id}\n")
            continue
        if msg.strip() == "/tools":
            print(", ".join(tools.list_tools()))
            continue
        if msg.strip() == "/help":
            print_help()
            continue

        result = await agent_run(msg, session, llm, tools)
        print(f"xm> {result}\n")

    session.close()

async def oneshot(message):
    llm = OpenAILLM()
    tools = build_tools()
    session = Session()
    result = await agent_run(message, session, llm, tools)
    print(result)
    session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "ask" and len(sys.argv) > 2:
            asyncio.run(oneshot(" ".join(sys.argv[2:])))
        elif cmd == "tools":
            print(", ".join(build_tools().list_tools()))
        elif cmd == "sessions":
            ensure_config_dir()
            conn = sqlite3.connect(str(DB_FILE))
            for r in conn.execute("SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 10"):
                print(f"  {r[0]}  {r[1] or '(untitled)'}  {r[2]}")
            conn.close()
        elif cmd == "tui":
            try:
                from textual.app import App, ComposeResult
                from textual.widgets import RichLog, Input, Static, Header
                from textual.containers import Horizontal
                from textual.binding import Binding
                from textual import on

                class XmTui(App):
                    CSS = """
                    Screen { layout: vertical; }
                    #chat { height: 1fr; padding: 0 1; }
                    #sep { height: 1; background: $surface; }
                    #bar { height: 3; padding: 0 1; }
                    #lbl { width: 5; content-align: left middle; }
                    #inp { width: 1fr; border: none; }
                    #inp:focus { border: none; }
                    """
                    BINDINGS = [Binding("ctrl+c", "quit", "Quit")]
                    TITLE = f"xm v{VERSION}"

                    def __init__(self):
                        super().__init__()
                        self.llm = OpenAILLM()
                        self.tools = build_tools()
                        self.session = Session()

                    def compose(self):
                        yield RichLog(id="chat", markup=True, wrap=True)
                        yield Static(id="sep")
                        with Horizontal(id="bar"):
                            yield Static("you>", id="lbl")
                            yield Input(placeholder="Type...", id="inp")

                    def on_mount(self):
                        self.query_one("#chat").write(f"[bold green]xm v{VERSION}[/] | {self.session.id}")
                        self.query_one("#inp").focus()

                    @on(Input.Submitted, "#inp")
                    async def on_input(self, event):
                        text = event.value.strip()
                        event.input.clear()
                        if not text:
                            return
                        log = self.query_one("#chat")
                        log.write(f"[cyan]you>[/] {text}")
                        self.run_worker(self._run(text))

                    async def _run(self, msg):
                        log = self.query_one("#chat")
                        try:
                            result = await agent_run(msg, self.session, self.llm, self.tools)
                            log.write(f"[green]xm>[/] {result}")
                        except Exception as e:
                            log.write(f"[red]Error:[/] {e}")

                XmTui().run()
            except ImportError:
                print("TUI requires textual: pip install textual")
        elif cmd == "--version" or cmd == "-v":
            print(f"xm v{VERSION}")
        else:
            print_help()
    else:
        asyncio.run(interactive())
