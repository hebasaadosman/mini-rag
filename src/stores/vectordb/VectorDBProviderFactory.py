from .VectorDBEnum import DistanceMetricEnum
from controllers.BaseController import BaseController
from .VectorDBEnum import VectorDBEnum
from .providers.QdrantDBProvider import QdrantDBProvider

class VectorDBProviderFactory:

    def __init__(self,config: dict = None ):
        self.config = config or {}
        self.base_controller = BaseController()

    def create_provider(self, provider_name: str, db_path: str = None, distance_metric_method: str = "cosine"):
        if provider_name == VectorDBEnum.QDRANT.value:
            db_path = db_path or self.base_controller.get_database_path(self.config.get("VECTOR_DB_PATH", "qdrant_db"))
            distance_metric_method = distance_metric_method or self.config.get("VECTOR_DB_DISTANCE_METRIC_METHOD", DistanceMetricEnum.COSINE.value)
            return QdrantDBProvider(db_path=db_path, distance_metric_method=distance_metric_method)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

   