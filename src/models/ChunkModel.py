from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk
from .enums.DatabaseEnum import DatabaseEnum
from bson.objectid import ObjectId
from pymongo import InsertOne



class ChunkModel(BaseDataModel):

    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.DATA_CHUNKS_COLLECTION.value]

    @classmethod
    async def create_instance(cls, db_client:object):
        instance = cls(db_client)
        await instance.init_collection()
        return instance
    
    async def init_collection(self):
        all_collections= await self.db_client.list_collection_names()
        if DatabaseEnum.DATA_CHUNKS_COLLECTION.value not in all_collections:
            self.collection = self.db_client[DatabaseEnum.DATA_CHUNKS_COLLECTION.value]
            indexes = DataChunk.get_indexes()
            for index in indexes:
                await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])

    async def create_chunk(self, chunk: DataChunk):
        chunk_dict = chunk.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(chunk_dict)
        chunk._id = result.inserted_id
        return chunk
    
    async def insert_many_chunks(self, chunks: list,batch_size: int = 100):

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            operations = [InsertOne(chunk.dict(by_alias=True, exclude_unset=True)) for chunk in batch]
            await self.collection.bulk_write(operations)
            return  len(chunks)
    
    async def get_chunk_by_id(self, chunk_id: str):
        chunk = await self.collection.find_one({"_id": ObjectId(chunk_id)})
        if chunk:
            return DataChunk(**chunk)
        return None

    async def update_chunk(self, chunk_id: str, updated_data: dict):
        result = await self.collection.update_one(
            {"_id": ObjectId(chunk_id)}, {"$set": updated_data}
        )
        return result.modified_count

    async def delete_chunk(self, chunk_id: str):
        result = await self.collection.delete_one({"_id": ObjectId(chunk_id)})
        return result.deleted_count
    
    async def delete_chunks_by_project_id(self, project_id: str):
        result = await self.collection.delete_many({"chunk_project_id": ObjectId(project_id)})
        return result.deleted_count