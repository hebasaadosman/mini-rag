from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from .enums.DatabaseEnum import DatabaseEnum

class ProjectModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.PROJECTS_COLLECTION]

    async def create_project(self, project: Project):
        project_dict = project.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(project_dict)
        project._id = result.inserted_id
        return project

    async def get_project_or_create_one(self, project_id: str):
        project = await self.collection.find_one({"project_id": project_id})
        if project:
            return Project(**project)
        new_project = Project(project_id=project_id)
        await self.create_project(new_project)
        return new_project

    async def update_project(self, project_id: str, updated_data: dict):
        result = await self.collection.update_one(
            {"project_id": project_id}, {"$set": updated_data}
        )
        return result.modified_count

    async def delete_project(self, project_id: str):
        result = await self.collection.delete_one({"project_id": project_id})
        return result.deleted_count

    async def get_all_projects(self,page: int = 1, page_size: int = 10):
        skip = (page - 1) * page_size
        projects_cursor = self.collection.find().skip(skip).limit(page_size)    
        projects = []
        async for project in projects_cursor:
            projects.append(Project(**project))
        total_count = await self.collection.count_documents({})
        return projects, total_count