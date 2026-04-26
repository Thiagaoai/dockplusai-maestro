"""Long-term semantic memory backed by Supabase pgvector.

Reads and writes `memory_chunks` table. Uses OpenAI text-embedding-3-small
(1536 dims) for embeddings and the `match_memory_chunks` RPC stored procedure
for cosine similarity search.

Usage:
    memory = SupabaseMemory(settings)
    await memory.save("roberts", "HOA Provincetown - respondeu cold email")
    results = await memory.search("roberts", "prospect interessado em paisagismo")
"""
from __future__ import annotations

from typing import Any

import structlog

from maestro.config import Settings

log = structlog.get_logger()

_EMBED_MODEL = "text-embedding-3-small"


class SupabaseMemory:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        if client is not None:
            self.client = client
        else:
            if not settings.supabase_url or not settings.supabase_service_key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
            from supabase import create_client

            self.client = create_client(settings.supabase_url, settings.supabase_service_key)

    def is_configured(self) -> bool:
        return bool(self.settings.openai_api_key and self.settings.supabase_url)

    async def _embed(self, text: str) -> list[float]:
        from openai import AsyncOpenAI

        oai = AsyncOpenAI(api_key=self.settings.openai_api_key)
        resp = await oai.embeddings.create(model=_EMBED_MODEL, input=text)
        return resp.data[0].embedding

    async def save(
        self,
        business: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        importance_score: float = 0.5,
    ) -> dict[str, Any]:
        """Embed and persist a memory chunk. Returns the created row."""
        embedding = await self._embed(content)
        row = {
            "business": business,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
            "importance_score": importance_score,
        }
        resp = self.client.table("memory_chunks").insert(row).execute()
        chunk = resp.data[0]
        log.info("memory_saved", business=business, chunk_id=chunk["id"])
        return chunk

    async def search(
        self,
        business: str,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return up to `limit` chunks similar to `query`, ordered by cosine similarity."""
        embedding = await self._embed(query)
        resp = self.client.rpc(
            "match_memory_chunks",
            {
                "query_embedding": embedding,
                "business_filter": business,
                "match_count": limit,
            },
        ).execute()
        results = resp.data or []
        log.info("memory_search", business=business, results=len(results))
        return results

    async def get_recent(
        self,
        business: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch most recently accessed chunks (useful for context injection)."""
        resp = (
            self.client.table("memory_chunks")
            .select("id,content,metadata,importance_score,last_accessed_at")
            .eq("business", business)
            .order("last_accessed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    async def update_access(self, chunk_id: str) -> None:
        """Refresh last_accessed_at and increment access_count via RPC."""
        self.client.rpc(
            "increment_memory_access",
            {"chunk_id": chunk_id},
        ).execute()
