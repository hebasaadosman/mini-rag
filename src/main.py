from fastapi import FastAPI
from routes import base,data,nlp
from helpers.config import get_settings, Settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession
from sqlalchemy.orm import sessionmaker

app = FastAPI()

@app.on_event("startup")
async def startup_db_client():
    settings = get_settings()

    # app.db_mongo_conn = AsyncIOMotorClient(settings.MONGODB_URI)
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    app.pg_engine = create_async_engine(postgres_conn, echo=True)

    app.db_client = sessionmaker(app.pg_engine, class_=AsyncSession, expire_on_commit=False)

    llm_provider_factory = LLMProviderFactory(config=settings.dict())
    vector_db_provider_factory = VectorDBProviderFactory(config=settings.dict())
    app.generation_client = llm_provider_factory.create_provider(settings.GENERATION_BACKEND)
    app.embedding_client = llm_provider_factory.create_provider(settings.EMBEDDING_BACKEND)

    app.generation_client.set_generation_model(settings.GENEERATION_MODEL_ID)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, model_size=settings.EMBEDDING_MODEL_SIZE)

    app.vector_db_client = vector_db_provider_factory.create_provider(settings.VECTOR_DB_BACKEND, db_path=settings.VECTOR_DB_PATH, distance_metric_method=settings.VECTOR_DB_DISTANCE_METRIC_METHOD)
    app.vector_db_client.connect()
    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANGUAGE,
        default_language=settings.DEFAULT_LANGUAGE,
    )
    
@app.on_event("shutdown")
async def shutdown_db_client():
    app.db_client.close_all_sessions()
    app.vector_db_client.disconnect()
    app.pg_engine.dispose()

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)


