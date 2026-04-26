"""Replicate.com service — generate images from text prompts.

Uses black-forest-labs/flux-schnell for fast, high-quality images.
The `Prefer: wait` header requests synchronous polling (up to 60s).
"""
import httpx
import structlog

from maestro.config import Settings

log = structlog.get_logger()

_API_URL = "https://api.replicate.com/v1"
_MODEL = "black-forest-labs/flux-schnell"


class ReplicateError(RuntimeError):
    pass


class ReplicateClient:
    def __init__(self, settings: Settings, timeout_seconds: int = 90) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def generate_image(self, prompt: str, aspect_ratio: str = "1:1") -> str:
        """Generate an image from a text prompt. Returns the image URL or empty string if token is missing."""
        if not self.settings.replicate_api_token:
            log.warning("replicate_no_token", prompt=prompt[:60])
            return ""

        log.info("replicate_generate_start", prompt=prompt[:60], aspect_ratio=aspect_ratio)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{_API_URL}/models/{_MODEL}/predictions",
                json={
                    "input": {
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "output_format": "webp",
                    }
                },
                headers={
                    "Authorization": f"Token {self.settings.replicate_api_token}",
                    "Content-Type": "application/json",
                    "Prefer": "wait",
                },
            )

        if response.status_code >= 400:
            raise ReplicateError(
                f"Replicate API error {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        status = data.get("status")
        if status == "failed":
            raise ReplicateError(f"Replicate prediction failed: {data.get('error')}")

        output = data.get("output")
        if not output:
            raise ReplicateError(f"Replicate returned no output (status={status})")

        image_url: str = output[0] if isinstance(output, list) else str(output)
        log.info("replicate_generate_success", image_url=image_url[:80])
        return image_url
