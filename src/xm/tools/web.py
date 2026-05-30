"""Web fetch/search tools"""

import httpx

from xm.tools import ToolDef


async def fetch_url(url: str, max_length: int = 5000) -> str:
    """Fetch content from a URL."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "xm-agent/0.1"},
            )
            resp.raise_for_status()
            text = resp.text[:max_length]
            if len(resp.text) > max_length:
                text += f"\n... (truncated, {len(resp.text)} total chars)"
            return text
    except Exception as e:
        return f"Error: {e}"


FETCH_URL_TOOL = ToolDef(
    name="fetch_url",
    description="Fetch content from a URL. Returns the response body.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "max_length": {
                "type": "integer",
                "description": "Max characters to return (default: 5000)",
                "default": 5000,
            },
        },
        "required": ["url"],
    },
    handler=fetch_url,
)
