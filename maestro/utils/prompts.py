"""Jinja2 prompt loader for versioned prompt templates in maestro/prompts/."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_ROOT = Path(__file__).parent.parent / "prompts"


def _make_env(version: str) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_PROMPTS_ROOT / version)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["tojson"] = lambda value, indent=None: json.dumps(value, indent=indent, default=str)
    return env


def load_prompt(name: str, context: dict, version: str = "v1") -> str:
    """Render a Jinja2 prompt template and return the string.

    name: filename without .md extension (e.g. 'cfo_weekly_briefing')
    context: variables injected into the template
    """
    env = _make_env(version)
    template = env.get_template(f"{name}.md")
    return template.render(**context)
