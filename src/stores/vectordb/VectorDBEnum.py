from enum import Enum

class VectorDBEnum(Enum):
    QDRANT="QDRANT"

class DistanceMetricEnum(Enum):
    COSINE="cosine"
    DOT="dot"
    EUCLIDEAN="euclidean"