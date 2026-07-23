from fastapi import APIRouter, Request,FastAPI,status
from fastapi.responses import JSONResponse
from models.ProjectModel import ProjectModel
from controllers import NLPController
import logging
from .schemes.nlp import PushRequest, SearchRequest
from models import ResponseSignals
from models.ChunkModel import ChunkModel
import asyncio
from cohere.errors.too_many_requests_error import TooManyRequestsError
import random
from typing import Any

logger = logging.getLogger("uvicorn.error")
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1","nlp"],
)

INDEX_PAGE_SIZE = 10
INDEX_MAX_RETRIES = 5
INDEX_BATCH_TIMEOUT_SECONDS = 90
INDEX_MAX_BACKOFF_SECONDS = 60
INDEX_DELAY_BETWEEN_BATCHES_SECONDS = 2

def is_rate_limit_error(error: Any) -> bool:
   
    error_text = str(error).lower()

    rate_limit_markers = (
        "429",
        "rate limit",
        "too many requests",
        "token rate limit exceeded",
    )

    return any(marker in error_text for marker in rate_limit_markers)
def calculate_retry_delay(attempt: int) -> float:
    
    base_delay = min(
        INDEX_MAX_BACKOFF_SECONDS,
        10 * (2 ** (attempt - 1)),
    )

    jitter = random.uniform(0, 3)

    return base_delay + jitter

@nlp_router.post("/index/push/{project_id}")
async def index_project(
    request: Request,
    project_id: int,
    push_request: PushRequest,
):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    chunk_model = await ChunkModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id
    )

    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "signal": (
                    ResponseSignals.PROJECT_NOT_FOUND.value.format(
                        project_id=project_id
                    )
                )
            },
        )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    collection_name = await nlp_controller.create_collection_name(
        project.project_id
    )

    page_number = 1
    inserted_count = 0

    try:
        logger.info(
            "Starting indexing: project_id=%s reset=%s",
            project.project_id,
            push_request.do_reset,
        )

        # مهم:
        # يجب أن يتعامل create_collection داخليًا مع do_reset.
        # لا يجب حذف الجدول في كل retry أو كل batch.
        await request.app.vectordb_client.create_collection(
            collection_name=collection_name,
            vector_size=(
                request.app.vectordb_client.default_vector_size
            ),
            # أضيفي هذا لو الـ method تدعمه:
            # do_reset=push_request.do_reset,
        )

        total_chunks_count = (
            await chunk_model.get_total_chunks_count_by_project_id(
                project.project_id
            )
        )

        logger.info(
            "Indexing project %s: total_chunks=%s",
            project.project_id,
            total_chunks_count,
        )

        while True:
            # توقف لو المستخدم أغلق الاتصال
            if await request.is_disconnected():
                logger.warning(
                    "Client disconnected while indexing project %s. "
                    "Inserted chunks: %s",
                    project.project_id,
                    inserted_count,
                )

                return JSONResponse(
                    status_code=499,
                    content={
                        "signal": "CLIENT_DISCONNECTED",
                        "inserted_count": inserted_count,
                        "next_page": page_number,
                    },
                )

            page_chunks, _, _ = (
                await chunk_model.get_chunks_by_project_id(
                    project.project_id,
                    page_number=page_number,
                    page_size=INDEX_PAGE_SIZE,
                )
            )

            if not page_chunks:
                break

            success = False
            last_error = ""

            for attempt in range(
                1,
                INDEX_MAX_RETRIES + 1,
            ):
                try:
                    success, message = await asyncio.wait_for(
                        nlp_controller.index_into_vectordb(
                            project,
                            page_chunks,
                        ),
                        timeout=INDEX_BATCH_TIMEOUT_SECONDS,
                    )

                    if success:
                        last_error = ""
                        break

                    last_error = str(message)

                    # لا نكرر الأخطاء غير المؤقتة
                    if not is_rate_limit_error(last_error):
                        logger.error(
                            "Non-retryable indexing failure. "
                            "project_id=%s page=%s error=%s",
                            project.project_id,
                            page_number,
                            last_error,
                        )
                        break

                except asyncio.TimeoutError:
                    last_error = (
                        "Embedding/indexing batch timed out after "
                        f"{INDEX_BATCH_TIMEOUT_SECONDS} seconds"
                    )

                    logger.warning(
                        "Indexing batch timeout. "
                        "project_id=%s page=%s attempt=%s/%s",
                        project.project_id,
                        page_number,
                        attempt,
                        INDEX_MAX_RETRIES,
                    )

                except Exception as exc:
                    last_error = str(exc)

                    if not is_rate_limit_error(exc):
                        logger.exception(
                            "Unexpected indexing error. "
                            "project_id=%s page=%s",
                            project.project_id,
                            page_number,
                        )
                        raise

                if attempt < INDEX_MAX_RETRIES:
                    wait_seconds = calculate_retry_delay(
                        attempt
                    )

                    logger.warning(
                        "Temporary indexing failure. "
                        "project_id=%s page=%s "
                        "attempt=%s/%s retry_after=%.1fs "
                        "error=%s",
                        project.project_id,
                        page_number,
                        attempt,
                        INDEX_MAX_RETRIES,
                        wait_seconds,
                        last_error,
                    )

                    await asyncio.sleep(wait_seconds)

            if not success:
                logger.error(
                    "Indexing failed after retries. "
                    "project_id=%s page=%s inserted=%s error=%s",
                    project.project_id,
                    page_number,
                    inserted_count,
                    last_error,
                )

                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    headers={
                        "Retry-After": "60",
                    },
                    content={
                        "signal": (
                            ResponseSignals
                            .INSERT_INTO_VECTORDB_FAILED
                            .value
                        ),
                        "message": last_error,
                        "inserted_count": inserted_count,
                        "failed_page": page_number,
                        "retryable": is_rate_limit_error(
                            last_error
                        ),
                    },
                )

            batch_size = len(page_chunks)

            inserted_count += batch_size
            page_number += 1

            logger.info(
                "Indexed batch successfully. "
                "project_id=%s inserted=%s/%s next_page=%s",
                project.project_id,
                inserted_count,
                total_chunks_count,
                page_number,
            )

            # تهدئة إرسال الطلبات إلى مزود الـ embedding
            await asyncio.sleep(
                INDEX_DELAY_BETWEEN_BATCHES_SECONDS
            )

        logger.info(
            "Indexing completed successfully. "
            "project_id=%s inserted=%s",
            project.project_id,
            inserted_count,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "signal": (
                    ResponseSignals
                    .INSERT_INTO_VECTORDB_SUCCESS
                    .value
                ),
                "inserted_count": inserted_count,
                "total_chunks": total_chunks_count,
            },
        )

    except Exception as exc:
        logger.exception(
            "Indexing endpoint failed unexpectedly. "
            "project_id=%s inserted=%s",
            project.project_id,
            inserted_count,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "signal": (
                    ResponseSignals
                    .INSERT_INTO_VECTORDB_FAILED
                    .value
                ),
                "message": str(exc),
                "inserted_count": inserted_count,
                "failed_page": page_number,
            },
        )


@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):
    project_model= await ProjectModel.create_instance(
           db_client=request.app.db_client
   )
    project = await project_model.get_project_or_create_one(project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignals.PROJECT_NOT_FOUND.value.format(project_id=project_id)},
        )
    nlp_controller = NLPController(
       vectordb_client=request.app.vectordb_client,
         generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser
   )
    success, collection_info = await nlp_controller.get_vectordb_collection_info(project)
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
async def search_project_index(request: Request, project_id: int, search_request: SearchRequest):
    project_model= await ProjectModel.create_instance(
           db_client=request.app.db_client
   )
    project = await project_model.get_project_or_create_one(project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignals.PROJECT_NOT_FOUND.value.format(project_id=project_id)},
        )
    nlp_controller = NLPController(
       vectordb_client=request.app.vectordb_client,
         generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser
   )
    success, search_results = await nlp_controller.search_in_vectordb(
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

@nlp_router.post("/index/answer/{project_id}")
async def answer_rag_question(request: Request, project_id: int, search_request: SearchRequest):
    project_model= await ProjectModel.create_instance(
           db_client=request.app.db_client
   )
    project = await project_model.get_project_or_create_one(project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignals.PROJECT_NOT_FOUND.value.format(project_id=project_id)},
        )
    nlp_controller = NLPController(
       vectordb_client=request.app.vectordb_client,
         generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser
   )
    success, answer,full_prompt, chat_history = await nlp_controller.answer_rag_question(
        project=project,
        query=search_request.query,
        limit=search_request.limit
    )
    if not success:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignals.ANSWER_RAG_FAILED.value, "message": answer},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"signal": ResponseSignals.ANSWER_RAG_SUCCESS.value, "answer": answer,"full_prompt":full_prompt,"chat_history":chat_history},
    )
