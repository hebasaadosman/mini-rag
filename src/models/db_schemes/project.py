from pydantic import BaseModel, Field,validator
from typing import Optional 
from datetime import datetime
from bson.objectid import ObjectId

class Project(BaseModel):
    _id: Optional[ObjectId] 
    project_id: str= Field(..., min_length=1, max_length=100)
    # name: str
    # description: Optional[str] = None
    # created_at: Optional[str] = None
    # updated_at: Optional[str] = None

    @validator('project_id')
    def validate_project_id(cls, value):
        if not value:
            raise ValueError('project_id must not be empty')
        if not value.isalnum():
            raise ValueError('project_id must be alphanumeric')
        if len(value) > 100:
            raise ValueError('project_id must not exceed 100 characters')
        return value

    class Config:
        arbitrary_types_allowed = True
    
        