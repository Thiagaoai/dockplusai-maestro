import asyncio
import json
from pathlib import Path
from typing import Any


class ComposioError(RuntimeError):
    pass


class ComposioClient:
    def __init__(self, cli_path: str = "~/.composio/composio", timeout_seconds: int = 60) -> None:
        self.cli_path = str(Path(cli_path).expanduser())
        self.timeout_seconds = timeout_seconds

    async def execute(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            self.cli_path,
            "execute",
            slug,
            "-d",
            json.dumps(payload),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            raise ComposioError(f"Composio tool timed out: {slug}") from exc

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if process.returncode != 0:
            details = stderr_text or stdout_text
            raise ComposioError(f"Composio tool failed: {slug}: {details[-1000:]}")

        return self._parse_json(stdout_text)

    def _parse_json(self, output: str) -> dict[str, Any]:
        start = output.find("{")
        end = output.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {"raw": output}
        try:
            parsed = json.loads(output[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ComposioError(f"Could not parse Composio JSON output: {output[-1000:]}") from exc
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}
