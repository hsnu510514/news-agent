from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src.core.config import settings

COLLECTION_NAME = "news_embeddings"
VECTOR_SIZE = 768

client = QdrantClient(url=settings.QDRANT_URL)


def ensure_collection() -> None:
    collections = client.get_collections().collections
    names = [c.name for c in collections]
    if COLLECTION_NAME not in names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def upsert_embedding(point_id: str, vector: list[float], payload: dict) -> None:
    from qdrant_client.models import PointStruct

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )


def search_embeddings(query_vector: list[float], limit: int = 10) -> list[dict]:
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit,
    )
    return [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]


def search_embeddings_with_filter(query_vector: list[float], type_filter: str, limit: int = 10) -> list[dict]:
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(key="type", match=MatchValue(value=type_filter))
            ]
        ),
        limit=limit,
    )
    return [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]