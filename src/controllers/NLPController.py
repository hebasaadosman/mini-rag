from .BaseController import BaseController
from models import ResponseSignals
from models.db_schemes.project import Project
import os
from .ProjectController import ProjectController
import re
from typing import List, Dict, Any
from models.db_schemes.data_chunk import DataChunk
from stores.llm.LLMEnum import DocumentTypeEnum
class NLPController(BaseController):
    def __init__(self,vectordb_client=None,generation_client=None,embedding_client=None):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client


    def create_collection_name(self, project_id: str):
        # Create a unique collection name based on the project ID
        cleaned_project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', project_id)
        collection_name = f"collection_project_{cleaned_project_id}"
        return collection_name


    def reset_vectordb_collection(self, project: Project):
        collection_name = self.create_collection_name(project.project_id)
        if self.vectordb_client:
            self.vectordb_client.delete_collection(collection_name)
            return True, f"Collection '{collection_name}' has been reset."
        else:
            return False, "VectorDB client is not initialized."

    def get_vectordb_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project.project_id)
        if self.vectordb_client:
            collection_info = self.vectordb_client.get_collection_info(collection_name)
            return True, collection_info
        else:
            return False, "VectorDB client is not initialized."

    def index_into_vectordb(self, project: Project, chunks: List[DataChunk], do_reset: bool = False):
        collection_name = self.create_collection_name(project.project_id)

        if self.vectordb_client:
            if do_reset:
                self.vectordb_client.delete_collection(collection_name)
            # Assuming chunks is a list of DataChunk objects
            texts = [chunk.chunk_text for chunk in chunks]
            metadatas = [chunk.chunk_metadata for chunk in chunks]
            vectors=[
                self.embedding_client.generate_embedding(text, document_type=DocumentTypeEnum.DOCUMENT.value) for text in texts
            ]
            vector_size = len(vectors[0])
            _= self.vectordb_client.create_collection(collection_name, vector_size=vector_size, do_reset=do_reset)
            records = []
            for text, vector, metadata in zip(texts, vectors, metadatas):
                records.append({
                    "text": text,
                    "vector": vector,
                    "metadata": metadata
                })
            inserted_count = self.vectordb_client.insert_many_vectors(
                collection_name=collection_name,
                vectors=records
            )

            return True, f"Indexed {inserted_count} chunks into collection '{collection_name}'."
        else:
            return False, "VectorDB client is not initialized."
    def search_in_vectordb(self, project: Project, query: str, limit: int = 5):
        collection_name = self.create_collection_name(project.project_id)
        if self.vectordb_client:
            query_vector = self.embedding_client.generate_embedding(query, document_type=DocumentTypeEnum.QUERY.value)
            if query_vector is None:
                return False, "Failed to generate embedding for the query."
            
            search_results = self.vectordb_client.search_by_vector(collection_name, query_vector, limit)
            if search_results is None:
                return False, "Search operation failed."
            results = [
            point.model_dump(mode="json")
            for point in search_results
          ]
            return True,{
                "query": query,
                "results": results
            }
        else:
            return False, "VectorDB client is not initialized."