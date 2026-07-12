from enum import Enum

class DatabaseEnum(str, Enum):
    PROJECTS_COLLECTION = "projects"
    DATA_CHUNKS_COLLECTION = "chunks"
    RESOURCES_COLLECTION = "resources"