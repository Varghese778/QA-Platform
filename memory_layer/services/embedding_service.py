"""EmbeddingService - Generates dense vector embeddings (mocked for MVP)."""

import hashlib
import json
import logging
from typing import List, Optional

import redis.asyncio as redis

from memory_layer.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """
    Generates and caches dense vector embeddings.

    For MVP, returns mock embeddings (deterministic based on text).
    In production, would call the actual embedding model API.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Checks cache first, then generates if needed.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding (1536 dimensions).
        """
        if not text:
            # Empty text -> zero vector
            return [0.0] * settings.embedding_dimension

        # Check cache
        text_hash = self._hash_text(text)
        cached = await self._get_cached_embedding(text_hash)
        if cached is not None:
            logger.debug(f"Cache hit for embedding {text_hash[:8]}")
            return cached

        # Generate embedding (mock)
        embedding = self._generate_mock_embedding(text)

        # Cache result
        await self._cache_embedding(text_hash, embedding)

        return embedding

    def _hash_text(self, text: str) -> str:
        """Hash text for caching."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def _get_cached_embedding(self, text_hash: str) -> Optional[List[float]]:
        """Get embedding from Redis cache."""
        if not settings.embedding_cache_enabled:
            return None

        try:
            redis_client = await self.get_redis()
            cache_key = f"embedding:{text_hash}"
            cached_json = await redis_client.get(cache_key)
            if cached_json:
                return json.loads(cached_json)
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")

        return None

    async def _cache_embedding(
        self,
        text_hash: str,
        embedding: List[float],
    ) -> None:
        """Cache embedding in Redis."""
        if not settings.embedding_cache_enabled:
            return

        try:
            redis_client = await self.get_redis()
            cache_key = f"embedding:{text_hash}"
            await redis_client.setex(
                cache_key,
                settings.embedding_cache_ttl_seconds,
                json.dumps(embedding),
            )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def _generate_mock_embedding(self, text: str) -> List[float]:
        """
        Generate deterministic mock embedding based on text.

        For MVP: Use hash of text to seed a pseudo-random vector.
        """
        import hashlib

        # Create deterministic seed from text
        text_hash = hashlib.md5(text.encode()).digest()

        # Create 1536-dimensional vector using the hash
        embedding = []
        for i in range(settings.embedding_dimension):
            # Use hash bytes to generate values in [-1, 1]
            byte_index = i % len(text_hash)
            byte_val = text_hash[byte_index]
            # Normalize to [-1, 1]
            value = (byte_val / 255.0) * 2.0 - 1.0
            embedding.append(value)

        # Normalize to unit vector
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Returns:
        Score between 0.0 and 1.0.
    """
    if not vec1 or not vec2:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    # Cosine similarity is in [-1, 1], scale to [0, 1]
    similarity = dot_product / (magnitude1 * magnitude2)
    return max(0.0, min(1.0, (similarity + 1.0) / 2.0))
