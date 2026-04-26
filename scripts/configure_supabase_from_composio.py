"""Configure local .env from the Composio-connected Supabase project.

This script intentionally does not print API keys. It writes them to .env,
which is ignored by git, and prints only key prefixes for verification.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_REF = "nithporoqakujydqfpsa"
PROJECT_URL = f"https://{PROJECT_REF}.supabase.co"
COMPOSIO_BIN = Path.home() / ".composio" / "composio"


def _extract_json(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("Composio did not return JSON")
    return json.loads(output[start : end + 1])


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    ordered_keys = [
        "APP_ENV",
        "LOG_LEVEL",
        "DRY_RUN",
        "STORAGE_BACKEND",
        "WEBHOOK_BASE_URL",
        "PROMPT_VERSION",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_ANON_KEY",
    ]
    lines: list[str] = []
    seen: set[str] = set()
    for key in ordered_keys:
        if key in values:
            lines.append(f"{key}={values[key]}")
            seen.add(key)
    for key in sorted(k for k in values if k not in seen):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    result = subprocess.run(
        [
            str(COMPOSIO_BIN),
            "execute",
            "SUPABASE_GET_PROJECT_API_KEYS",
            "-d",
            json.dumps({"ref": PROJECT_REF, "reveal": False}),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = _extract_json(result.stdout + result.stderr)
    if not payload.get("successful"):
        raise RuntimeError(payload.get("error") or "Composio key fetch failed")

    details = payload["data"]["details"]
    anon = next(item["api_key"] for item in details if item.get("name") == "anon")
    service = next(item["api_key"] for item in details if item.get("name") == "service_role")

    env_path = Path(".env")
    values = _load_env(env_path)
    values.setdefault("APP_ENV", "dev")
    values.setdefault("LOG_LEVEL", "INFO")
    values.setdefault("DRY_RUN", "true")
    values.setdefault("WEBHOOK_BASE_URL", "http://localhost:8000")
    values.setdefault("PROMPT_VERSION", "v1")
    values["STORAGE_BACKEND"] = "supabase"
    values["SUPABASE_URL"] = PROJECT_URL
    values["SUPABASE_ANON_KEY"] = anon
    values["SUPABASE_SERVICE_KEY"] = service
    _write_env(env_path, values)

    print("Configured .env for Supabase project maestro")
    print(f"SUPABASE_URL={PROJECT_URL}")
    print(f"SUPABASE_ANON_KEY prefix={anon[-5:]}")
    print(f"SUPABASE_SERVICE_KEY prefix={service[-5:]}")


if __name__ == "__main__":
    main()
