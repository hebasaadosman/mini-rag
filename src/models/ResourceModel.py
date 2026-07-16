from .BaseDataModel import BaseDataModel
from .db_schemes.resource import Resource
from .enums.DatabaseEnum import DatabaseEnum
from bson.objectid import ObjectId

class ResourceModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.RESOURCES_COLLECTION.value]

    @classmethod
    async def create_instance(cls, db_client:object):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        all_collections= await self.db_client.list_collection_names()
        if DatabaseEnum.RESOURCES_COLLECTION.value not in all_collections:
            self.collection = self.db_client[DatabaseEnum.RESOURCES_COLLECTION.value]
            indexes = Resource.get_indexes()
            for index in indexes:
                await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])

    async def create_resource(self, resource: Resource):
        resource_dict = resource.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(resource_dict)
        resource.id = result.inserted_id
        return resource

    async def get_all_projects_resources(self, resource_project_id: str,resource_type: str = None):
        query = {"resource_project_id": ObjectId(resource_project_id)}
        if resource_type:
            query["resource_type"] = resource_type
        resources_cursor = self.collection.find(query)
        resources = [Resource(**doc) async for doc in resources_cursor]
        return resources

    async def get_resource_record(self, resource_project_id: str, resource_name: str):
        resource_record = await self.collection.find_one({"resource_project_id": ObjectId(resource_project_id), "resource_name": resource_name})
        if resource_record:
            return Resource(**resource_record)
        return None