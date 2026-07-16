from fastapi import APIRouter, Request,FastAPI,status
from fastapi.responses import JSONResponse
from models.ProjectModel import ProjectModel
from controllers import NLPController
import logging
from .schemes.npl import PushRequest, SearchRequest
from models import ResponseSignals
from models.ChunkModel import ChunkModel
from bson import ObjectId

logger = logging.getLogger("uvicorn.error")
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v","nlp"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: str,push_request: PushRequest):
   
   project_model= await ProjectModel.create_instance(
           db_client=request.app.mongodb_client
   )
   chunk_model= await ChunkModel.create_instance(
            db_client=request.app.mongodb_client
   )
   project = await project_model.get_project_or_create_one(project_id)
   if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignals.PROJECT_NOT_FOUND.value.format(project_id=project_id)},
        )
   nlp_controller = NLPController(
       vectordb_client=request.app.vector_db_client,
         generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client
   )
   has_records=True
   page_number = 1
   page_size = 50
   inserted_count = 0

   while has_records:

       page_chunks = await chunk_model.get_chunks_by_project_id(project.id, page_number=page_number, page_size=page_size)

       if len(page_chunks):
           page_number += 1
       if not page_chunks or len(page_chunks) == 0:
           has_records = False
           break

    
       success, message = nlp_controller.index_into_vectordb(project, page_chunks, do_reset=push_request.do_reset)
       if not success:
           return JSONResponse(
               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
               content={"signal": ResponseSignals.INSERT_INTO_VECTORDB_FAILED.value, "message": message},
           )
       inserted_count += len(page_chunks)

   return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"signal": ResponseSignals.INSERT_INTO_VECTORDB_SUCCESS.value, "inserted_count": inserted_count},
    )

@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: str):
    project_model= await ProjectModel.create_instance(
           db_client=request.app.mongodb_client
   )
    project = await project_model.get_project_or_create_one(project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignals.PROJECT_NOT_FOUND.value.format(project_id=project_id)},
        )
    nlp_controller = NLPController(
       vectordb_client=request.app.vector_db_client,
         generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client
   )
    success, collection_info = nlp_controller.get_vectordb_collection_info(project)
    if not success:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignals.GET_VECTORDB_COLLECTION_INFO_FAILED.value, "message": collection_info},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"signal": ResponseSignals.GET_VECTORDB_COLLECTION_INFO_SUCCESS.value, "collection_info": collection_info},
    )
@nlp_router.post("/index/search/{project_id}")
async def search_project_index(request: Request, project_id: str, search_request: SearchRequest):
    project_model= await ProjectModel.create_instance(
           db_client=request.app.mongodb_client
   )
    project = await project_model.get_project_or_create_one(project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignals.PROJECT_NOT_FOUND.value.format(project_id=project_id)},
        )
    nlp_controller = NLPController(
       vectordb_client=request.app.vector_db_client,
         generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client
   )
    success, search_results = nlp_controller.search_in_vectordb(
        project=project,
        query=search_request.query,
        limit=search_request.limit
    )
    if not success:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignals.SEARCH_VECTORDB_FAILED.value, "message": search_results},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"signal": ResponseSignals.SEARCH_VECTORDB_SUCCESS.value, "results": search_results},
    )