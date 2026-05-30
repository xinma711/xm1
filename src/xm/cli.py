"""CLI entry point"""

import asyncio

import click

from xm import __version__

DEFAULT_SYSTEM_PROMPT = """You are xm, a minimal AI agent. You have access to tools to execute shell commands, read/write files, and fetch web content. Use tools when needed to help the user. Be concise and direct."""


def _build_tools():
    from xm.tools import ToolRegistry
    from xm.tools.shell import SHELL_TOOL
    from xm.tools.file import READ_FILE_TOOL, WRITE_FILE_TOOL
    from xm.tools.web import FETCH_URL_TOOL

    registry = ToolRegistry()
    registry.register(SHELL_TOOL)
    registry.register(READ_FILE_TOOL)
    registry.register(WRITE_FILE_TOOL)
    registry.register(FETCH_URL_TOOL)
    return registry


def _build_llm(provider: str = "openai", model: str | None = None):
    if provider == "openai":
        from xm.llm.openai import OpenAILLM

        return OpenAILLM(model=model or "gpt-4o")
    else:
        raise click.ClickException(f"Unknown provider: {provider}")


async def _interactive(provider: str, model: str | None, system_prompt: str, verbose: bool):
    from xm.agent import run
    from xm.session import Session

    llm = _build_llm(provider, model)
    tools = _build_tools()
    session = Session()

    click.echo(f"xm v{__version__} | session: {session.id}")
    click.echo("Type your message. Commands: /quit /help /new\n")

    while True:
        try:
            user_input = click.prompt("you", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye.")
            break

        if not user_input.strip():
            continue

        # Handle commands
        if user_input.strip() == "/quit":
            click.echo("Bye.")
            break
        elif user_input.strip() == "/new":
            session.close()
            session = Session()
            click.echo(f"\nNew session: {session.id}\n")
            continue
        elif user_input.strip() == "/help":
            click.echo("Commands:")
            click.echo("  /quit   - Exit")
            click.echo("  /new    - Start new session")
            click.echo("  /tools  - List available tools")
            click.echo("  /help   - Show this help")
            continue
        elif user_input.strip() == "/tools":
            click.echo("Available tools: " + ", ".join(tools.list_tools()))
            continue

        try:
            result = await run(
                user_message=user_input,
                session=session,
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                verbose=verbose,
            )
            click.echo(f"\nxm> {result}\n")
        except Exception as e:
            click.echo(f"\nError: {e}\n")

    session.close()


async def _oneshot(
    message: str, provider: str, model: str | None, system_prompt: str, verbose: bool
):
    from xm.agent import run
    from xm.session import Session

    llm = _build_llm(provider, model)
    tools = _build_tools()
    session = Session()

    result = await run(
        user_message=message,
        session=session,
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        verbose=verbose,
    )
    click.echo(result)
    session.close()


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.option("--provider", "-p", default="openai", help="LLM provider")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--system-prompt", "-s", default=DEFAULT_SYSTEM_PROMPT, help="System prompt")
@click.option("--verbose", is_flag=True, help="Show tool calls")
@click.pass_context
def main(ctx, version, provider, model, system_prompt, verbose):
    """xm - Minimal AI agent shell"""
    if version:
        click.echo(f"xm v{__version__}")
        return

    ctx.ensure_object(dict)
    ctx.obj["provider"] = provider
    ctx.obj["model"] = model
    ctx.obj["system_prompt"] = system_prompt
    ctx.obj["verbose"] = verbose

    if ctx.invoked_subcommand is None:
        asyncio.run(_interactive(provider, model, system_prompt, verbose))


@main.command()
@click.argument("message")
@click.pass_context
def ask(ctx, message):
    """Ask a one-shot question"""
    asyncio.run(
        _oneshot(
            message,
            ctx.obj["provider"],
            ctx.obj["model"],
            ctx.obj["system_prompt"],
            ctx.obj["verbose"],
        )
    )


@main.command()
def tools():
    """List available tools"""
    registry = _build_tools()
    for name in registry.list_tools():
        click.echo(f"  {name}")


@main.command()
def sessions():
    """List recent sessions"""
    from xm.session import list_sessions

    for s in list_sessions():
        title = s["title"] or "(untitled)"
        click.echo(f"  {s['id']}  {title}  {s['updated_at']}")


@main.command()
@click.option("--provider", "-p", default="openai", help="LLM provider")
@click.option("--model", "-m", default=None, help="Model name")
def tui(provider, model):
    """Launch the TUI interface"""
    from xm.tui import ChatApp

    app = ChatApp(provider=provider, model=model)
    app.run()


if __name__ == "__main__":
    main()
