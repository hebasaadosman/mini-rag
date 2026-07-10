from email.mime import message

from fastapi import FastAPI, APIRouter,Depends,UploadFile,status
from fastapi.responses import JSONResponse
import aiofiles
from helpers.config import get_settings, Settings
import os
from controllers import DataController, ProjectController
from models import ResponseSignals
import logging

logger = logging.getLogger("uvicorn.error")
data_controller = DataController()
data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1","data"],
)

@data_router.post("/upload/{project_id}")

async def upload_data(project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)):

    is_valid, signal = data_controller.validate_uploaded_file(file)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": signal})
    
    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_id, file_path = data_controller.generate_unique_filepath(original_filename=file.filename, project_id=project_id)
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error occurred while uploading file: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignals.FILE_UPLOAD_FAILED.value, "error": str(e)})

    return JSONResponse(status_code=status.HTTP_200_OK, content={"signal": ResponseSignals.FILE_UPLOAD_SUCCESS.value, "file_path": file_path, "file_id": file_id})
