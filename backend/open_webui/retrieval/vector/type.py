try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class VectorType(StrEnum):
    MILVUS = "milvus"
    QDRANT = "qdrant"
    CHROMA = "chroma"
    PINECONE = "pinecone"
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"
    PGVECTOR = "pgvector"
