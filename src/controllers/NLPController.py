from .BaseController import BaseController
from models import ResponseSignals
from models.db_schemes import Project
import os
from .ProjectController import ProjectController
import re
from typing import List, Dict, Any
from models.db_schemes import DataChunk
from stores.llm.LLMEnum import DocumentTypeEnum
class NLPController(BaseController):
    def __init__(self,vectordb_client=None,generation_client=None,embedding_client=None,template_parser=None):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser


    def create_collection_name(self, project_id: str):
        # Create a unique collection name based on the project ID
        cleaned_project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(project_id))  # Replace any non-alphanumeric characters with underscores
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
            return True, results
        else:
            return False, "VectorDB client is not initialized."
    
    def answer_rag_question(self, project: Project, query: str, limit: int = 5):
        # Step 1: Search in VectorDB
        search_success, retrived_documents = self.search_in_vectordb(project, query, limit)
        if not search_success:
            return False, f"Search failed: {retrived_documents}"

        # Step 2: Construct LLM Prompt

        system_prompt = self.template_parser.get("rag", "system_prompt")
        # document_prompt=[]  
        # for ind, doc in enumerate(retrived_documents):
        #     document_prompt.append(self.template_parser.get("rag", "document_prompt",
        #         {
        #             "doc_num": ind + 1,
        #             "chunk_text": doc['text'],
        #         }
        #     ))
    
        document_prompt = "\n".join([self.template_parser.get("rag", "document_prompt",
                {
                    "doc_num": ind + 1,
                    "chunk_text": self.generation_client.process_text(doc['text']),
                }
            ) for ind, doc in enumerate(retrived_documents)
        ])

        footer_prompt = self.template_parser.get(
            "rag",
            "footer_prompt",
            {"query": query}
        )
        chat_history = [
            self.generation_client.construct_prompt(system_prompt, role=self.generation_client.enums.SYSTEM.value),
        ]
        full_prompt = f"{document_prompt}\n{footer_prompt}\n\nUser Query: {query}"
        answer = self.generation_client.generate_text(full_prompt, chat_history=chat_history)
        if answer is None:
            return False, "Failed to generate answer from LLM." 
        return True, answer,full_prompt, chat_history


