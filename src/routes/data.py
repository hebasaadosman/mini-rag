
from fastapi import FastAPI,Request, APIRouter,Depends,UploadFile,status,Request
from fastapi.responses import JSONResponse
import aiofiles
from helpers.config import get_settings, Settings
import os
from controllers import DataController, ProjectController, ProcessController
from models import ResponseSignals
import logging
from bson.objectid import ObjectId
from models.db_schemes.data_chunk import DataChunk
from .schemes.data import ProcessRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.ResourceModel import ResourceModel
from models.db_schemes.resource import Resource
from models.db_schemes.data_chunk import DataChunk
from models.enums.ResourceTypeEnum import ResourceTypeEnum

logger = logging.getLogger("uvicorn.error")
data_controller = DataController()
data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1","data"],
)

@data_router.post("/upload/{project_id}")

async def upload_data(request: Request, project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)):

    project_model = await ProjectModel.create_instance(request.app.mongodb_client) 
    project = await project_model.get_project_or_create_one(project_id=project_id)
    is_valid, signal = await data_controller.validate_uploaded_file(file)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": signal})
    
    file_id, file_path = data_controller.generate_unique_filepath(original_filename=file.filename, project_id=project_id)
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
        resource_model = await ResourceModel.create_instance(request.app.mongodb_client)
        resource = Resource(
            resource_name=file_id,
            resource_size=os.path.getsize(file_path),
            resource_project_id=project.id,
            resource_type=ResourceTypeEnum.FILE.value,
        )
        resource_record = await resource_model.create_resource(resource)
        
    except Exception as e:
        logger.error(f"Error occurred while uploading file: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_UPLOAD_FAILED.value, "error": str(e)})


    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"signal": ResponseSignals.FILE_UPLOAD_SUCCESS.value, "file_id": str(resource_record.id), "file_path": file_path, "file_size": resource_record.resource_size})



@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest, app_settings: Settings = Depends(get_settings)):
    process_controller = ProcessController(project_id=project_id)
    try:
        project_model = await ProjectModel.create_instance(request.app.mongodb_client)
        project = await project_model.get_project_or_create_one(project_id=project_id)
        chunk_model = await ChunkModel.create_instance(request.app.mongodb_client)
        project_file_ids = {}
        resource_model=ResourceModel(request.app.mongodb_client)
        processed_files=0
        no_records=0
        if process_request.file_id:
             resource_record=await resource_model.get_resource_record(resource_project_id=project.id, resource_name=process_request.file_id)
             if not resource_record:
                    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.NO_FILES_FOUND.value})
             project_file_ids = {str(resource_record.id): resource_record.resource_name}
        else:
             resource_model = await resource_model.create_instance(request.app.mongodb_client)
             project_files =await resource_model.get_all_projects_resources(resource_project_id=project.id, resource_type=ResourceTypeEnum.FILE.value)


             project_file_ids = {
                        str(resource.id): resource.resource_name
                        for resource in project_files
                        }
             
        if len(project_file_ids) == 0:
             return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_PROCESS_FAILED.value, "error": f"{ResponseSignals.NO_FILES_FOUND.value}"})
        
       
        for _id, file_id in project_file_ids.items():
            chunks = await process_controller.process_file_content(file_id=file_id, chunk_size=process_request.chunk_size, overlap_size=process_request.overlap_size,do_reset=process_request.do_reset)
            
            if chunks is None or len(chunks) == 0:
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_PROCESS_FAILED.value, "error": "No chunks generated from the file."})
            # Save chunks to the database
            if process_request.do_reset == 1:
                deleted_count = await chunk_model.delete_chunks_by_project_id(project_id=project.id)
                logger.info(f"Deleted {deleted_count} chunks for project {project_id} due to reset request.")

            no_records += await chunk_model.insert_many_chunks([
                DataChunk(
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=i+1,
                    chunk_project_id=project.id,
                    chunk_resource_id=ObjectId(_id)  # Using the actual resource ID
                )
                for i, chunk in enumerate(chunks)
            ])
            processed_files += 1
        return JSONResponse(status_code=status.HTTP_200_OK, content={"signal": ResponseSignals.FILE_PROCESS_SUCCESS.value, "no_chunks": no_records, "no_files": processed_files})
    except Exception as e:
        logger.error(f"Error occurred while processing file: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_PROCESS_FAILED.value, "error": str(e)})
    