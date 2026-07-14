from fastapi import FastAPI
from routes import base,data
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings, Settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
app = FastAPI()

@app.on_event("startup")
async def startup_db_client():
    settings = get_settings()
    app.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URI)
    app.mongodb_client = app.mongodb_conn[settings.MONGODB_NAME]

    llm_provider_factory = LLMProviderFactory(config=settings.dict())
    app.generation_provider = llm_provider_factory.create_provider(settings.GENERATION_BACKEND)
    app.embedding_provider = llm_provider_factory.create_provider(settings.EMBEDDING_BACKEND)

    app.generation_provider.set_generation_model(settings.GENEERATION_MODEL_ID)
    app.embedding_provider.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, model_size=settings.EMBEDDING_MODEL_SIZE)
    
@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_conn.close()

app.include_router(base.base_router)
app.include_router(data.data_router)


