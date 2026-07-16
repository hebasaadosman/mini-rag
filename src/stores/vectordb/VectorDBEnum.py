from enum import Enum

class VectorDBEnum(Enum):
    QDRANT="qdrant"

class DistanceMetricEnum(Enum):
    COSINE="cosine"
    DOT="dot"
    EUCLIDEAN="euclidean"