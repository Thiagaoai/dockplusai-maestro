"""Tests for Replicate image generation service."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from maestro.services.replicate import ReplicateClient, ReplicateError


class _FakeSettings:
    replicate_api_token = "r8_fake_token"


class _NoTokenSettings:
    replicate_api_token = ""


def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = str(json_body)
    return resp


@pytest.mark.asyncio
async def test_generate_image_no_token_returns_empty():
    client = ReplicateClient(_NoTokenSettings())
    result = await client.generate_image("a green lawn in Cape Cod")
    assert result == ""


@pytest.mark.asyncio
async def test_generate_image_success():
    mock_resp = _mock_response(
        201,
        {
            "id": "pred_abc123",
            "status": "succeeded",
            "output": ["https://replicate.delivery/pbxt/abc123.webp"],
        },
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        client = ReplicateClient(_FakeSettings())
        url = await client.generate_image("spring lawn care tips, professional photo")

    assert url == "https://replicate.delivery/pbxt/abc123.webp"
    call_kwargs = mock_post.call_args
    assert "Prefer" in call_kwargs.kwargs.get("headers", {}) or any(
        "Prefer" in str(a) for a in call_kwargs.args
    )


@pytest.mark.asyncio
async def test_generate_image_api_error_raises():
    mock_resp = _mock_response(422, {"detail": "invalid input"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        client = ReplicateClient(_FakeSettings())
        with pytest.raises(ReplicateError, match="422"):
            await client.generate_image("bad prompt")


@pytest.mark.asyncio
async def test_generate_image_failed_status_raises():
    mock_resp = _mock_response(
        201, {"id": "pred_xyz", "status": "failed", "error": "CUDA OOM"}
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        client = ReplicateClient(_FakeSettings())
        with pytest.raises(ReplicateError, match="failed"):
            await client.generate_image("too large prompt")


@pytest.mark.asyncio
async def test_generate_image_no_output_raises():
    mock_resp = _mock_response(
        201, {"id": "pred_xyz", "status": "succeeded", "output": None}
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        client = ReplicateClient(_FakeSettings())
        with pytest.raises(ReplicateError, match="no output"):
            await client.generate_image("a prompt")


# ── content_creator helpers ──────────────────────────────────────────────────


def test_create_visual_prompts_returns_two_prompts():
    from maestro.subagents.marketing.content_creator import create_visual_prompts

    profile = MagicMock()
    profile.marketing.visual_style = "clean, professional, outdoor"

    prompts = create_visual_prompts("spring cleanup", profile)
    assert len(prompts) == 2
    assert "spring cleanup" in prompts[0]
    assert "spring cleanup" in prompts[1]


@pytest.mark.asyncio
async def test_generate_image_helper_no_token_returns_empty():
    from maestro.subagents.marketing.content_creator import generate_image

    settings = MagicMock()
    settings.replicate_api_token = ""
    result = await generate_image("a nice lawn", settings)
    assert result == ""


@pytest.mark.asyncio
async def test_generate_image_helper_delegates_to_client():
    from maestro.subagents.marketing.content_creator import generate_image

    settings = MagicMock()
    settings.replicate_api_token = "r8_token"

    mock_resp = _mock_response(
        201,
        {"id": "pred_1", "status": "succeeded", "output": ["https://img.example.com/1.webp"]},
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        url = await generate_image("beautiful garden, Cape Cod", settings)

    assert url == "https://img.example.com/1.webp"
