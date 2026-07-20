from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):


    APP_NAME: str
    APP_VERSION: str
    OPENAI_API_KEY: str
    FILE_ALLOWED_TYPES: list[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int
    MONGODB_URI: str
    MONGODB_NAME: str 
    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str
    OPENAI_KEY: str=None
    OPENAI_API_URL: str=None
    COHERE_API_KEY: str=None
    GENEERATION_MODEL_ID: str=None
    EMBEDDING_MODEL_ID: str=None
    EMBEDDING_MODEL_TEMPERATURE: float=None
    INPUT_DEFAULT_MAX_CHARACTERS: int=None
    GENERATION_DEFAULT_MAX_TOKENS: int=None
    EMBEDDING_MODEL_SIZE: int
    VECTOR_DB_BACKEND: str
    VECTOR_DB_PATH: str
    VECTOR_DB_DISTANCE_METRIC_METHOD: str
    DEFAULT_LANGUAGE: str
    PRIMARY_LANGUAGE: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()