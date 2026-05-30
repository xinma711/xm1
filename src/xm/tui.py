"""Textual TUI interface"""

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import RichLog, Static
from textual.widgets import Input

from xm import __version__

SYSTEM_PROMPT = """You are xm, a minimal AI agent. You have access to tools to execute shell commands, read/write files, and fetch web content. Use tools when needed to help the user. Be concise and direct."""


class ChatApp(App):
    """xm TUI"""

    CSS = """
    Screen { layout: vertical; }
    #chat-log { height: 1fr; padding: 0 1; }
    #separator { height: 1; background: $surface; }
    #input-bar { height: 3; padding: 0 1; }
    #prompt { width: 5; content-align: left middle; }
    #user-input { width: 1fr; border: none; }
    #user-input:focus { border: none; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "new_session", "New"),
        Binding("ctrl+l", "clear_log", "Clear"),
    ]

    TITLE = f"xm v{__version__}"

    def __init__(self, provider: str = "openai", model: str | None = None):
        super().__init__()
        self.provider = provider
        self.model_name = model
        self.llm = None
        self.tools = None
        self.session = None

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
        yield Static(id="separator")
        with Horizontal(id="input-bar"):
            yield Static("you>", id="prompt")
            yield Input(placeholder="Type a message...", id="user-input")

    def on_mount(self):
        self._init_agent()
        self.query_one("#user-input").focus()

    def _init_agent(self):
        from xm.session import Session

        def _build_tools():
            from xm.tools import ToolRegistry
            from xm.tools.shell import SHELL_TOOL
            from xm.tools.file import READ_FILE_TOOL, WRITE_FILE_TOOL
            from xm.tools.web import FETCH_URL_TOOL

            reg = ToolRegistry()
            reg.register(SHELL_TOOL)
            reg.register(READ_FILE_TOOL)
            reg.register(WRITE_FILE_TOOL)
            reg.register(FETCH_URL_TOOL)
            return reg

        def _build_llm():
            if self.provider == "openai":
                from xm.llm.openai import OpenAILLM
                return OpenAILLM(model=self.model_name or "deepseek-v4-flash")
            raise ValueError(f"Unknown provider: {self.provider}")

        self.llm = _build_llm()
        self.tools = _build_tools()
        self.session = Session()

        log = self.query_one("#chat-log")
        log.write(f"[bold green]xm v{__version__}[/] | session: {self.session.id}")
        log.write("[dim]Commands: /help /new /tools /list /quit[/]")
        log.write("")

    def _handle_command(self, cmd: str):
        log = self.query_one("#chat-log")
        parts = cmd.strip().split()
        c = parts[0].lower()

        if c == "/quit":
            self.exit()
        elif c == "/new":
            if self.session:
                self.session.close()
            from xm.session import Session
            self.session = Session()
            log.write(f"[dim]New session: {self.session.id}[/]")
        elif c == "/help":
            log.write("[bold cyan]Commands:[/]")
            log.write("  /quit   - Exit")
            log.write("  /new    - New session")
            log.write("  /tools  - List tools")
            log.write("  /list   - List sessions")
            log.write("  /clear  - Clear screen")
        elif c == "/tools":
            log.write(f"[dim]{', '.join(self.tools.list_tools())}[/]")
        elif c == "/list":
            from xm.session import list_sessions
            for s in list_sessions():
                t = s["title"] or "(untitled)"
                log.write(f"  {s['id']}  {t}  {s['updated_at']}")
        elif c == "/clear":
            self.query_one("#chat-log").clear()
        else:
            log.write(f"[dim]Unknown: {c}[/]")

    @on(Input.Submitted, "#user-input")
    async def on_input(self, event: Input.Submitted):
        text = event.value.strip()
        event.input.clear()
        if not text:
            return

        if text.startswith("/"):
            self._handle_command(text)
            return

        log = self.query_one("#chat-log")
        log.write(f"[bold cyan]you>[/] {text}")
        self.session.add_message("user", text)

        self.run_worker(self._run_agent(text))

    async def _run_agent(self, user_message: str):
        from xm.agent import run

        log = self.query_one("#chat-log")
        try:
            result = await run(
                user_message=user_message,
                session=self.session,
                llm=self.llm,
                tools=self.tools,
                system_prompt=SYSTEM_PROMPT,
                verbose=False,
            )
            log.write(f"[bold green]xm>[/] {result}")
        except Exception as e:
            log.write(f"[bold red]Error:[/] {e}")

    def action_new_session(self):
        self._handle_command("/new")

    def action_clear_log(self):
        self.query_one("#chat-log").clear()
