
from fastapi import FastAPI,Request, APIRouter,Depends,UploadFile,status,Request
from fastapi.responses import JSONResponse
import aiofiles
from helpers.config import get_settings, Settings
import os
from controllers import DataController, ProjectController, ProcessController
from models import ResponseSignals
import logging

from models.db_schemes.data_chunk import DataChunk
from .schemes.data import ProcessRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
logger = logging.getLogger("uvicorn.error")
data_controller = DataController()
data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1","data"],
)

@data_router.post("/upload/{project_id}")

async def upload_data(request: Request, project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)):

    project_model = ProjectModel(request.app.mongodb_client) 
    project = await project_model.get_project_or_create_one(project_id=project_id)
    is_valid, signal = data_controller.validate_uploaded_file(file)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": signal})
    
    file_id, file_path = data_controller.generate_unique_filepath(original_filename=file.filename, project_id=project_id)
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error occurred while uploading file: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_UPLOAD_FAILED.value, "error": str(e)})

    return JSONResponse(status_code=status.HTTP_200_OK, content={"signal": ResponseSignals.FILE_UPLOAD_SUCCESS.value, "file_id": file_id})



@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest, app_settings: Settings = Depends(get_settings)):
    file_id = process_request.file_id
    process_controller = ProcessController(project_id=project_id)
    try:
        project_model = ProjectModel(db_client=request.app.mongodb_client) 
        project = await project_model.get_project_or_create_one(project_id=project_id)
        chunk_model = ChunkModel(request.app.mongodb_client)
      
        chunks = await process_controller.process_file_content(file_id=file_id, chunk_size=process_request.chunk_size, overlap_size=process_request.overlap_size,do_reset=process_request.do_reset)
        if chunks is None or len(chunks) == 0:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_PROCESS_FAILED.value, "error": "No chunks generated from the file."})
        # Save chunks to the database
        
        if process_request.do_reset ==1:
                    deleted_count = await chunk_model.delete_chunks_by_project_id(project_id=project.id)
                    logger.info(f"Deleted {deleted_count} chunks for project {project_id} due to reset request.")
                    
        await chunk_model.insert_many_chunks([
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.id 
            )
            for i, chunk in enumerate(chunks)
        ])
        return JSONResponse(status_code=status.HTTP_200_OK, content={"signal": ResponseSignals.FILE_PROCESS_SUCCESS.value, "no_chunks": [len(chunks)]})
    except Exception as e:
        logger.error(f"Error occurred while processing file: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_PROCESS_FAILED.value, "error": str(e)})
    