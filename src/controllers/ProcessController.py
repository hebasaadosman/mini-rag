from .BaseController import BaseController
from models import ProcessingEnum
import os
from .ProjectController import ProjectController
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ProcessController(BaseController):
    def __init__(self,project_id: str):
        super().__init__()
        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        file_extension = os.path.splitext(file_id)[-1]
        return file_extension
    
    def get_file_loader(self, file_id: str):
        file_extension = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(self.project_path, file_id)
        if file_extension == ProcessingEnum.PDF.value:
            loader = PyMuPDFLoader(file_path)
        elif file_extension == ProcessingEnum.TXT.value:
            loader = TextLoader(file_path, encoding="utf8")
        else:
            raise ValueError(f"Unsupported file extension: {file_extension}")
        return loader
    
    def get_file_content(self, file_id: str):
        loader = self.get_file_loader(file_id=file_id)
        documents = loader.load()
        return documents
    async def process_file_content(self, file_id: str, chunk_size: int = 100, overlap_size: int = 20, do_reset: int = 0):
        file_content = self.get_file_content(file_id=file_id)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap_size,length_function=len, separators=["\n\n", "\n", " ", ""])
        file_content_texts= [
            
            doc.page_content 
            for doc in file_content
            
            
            ]
        file_content_metadata = [
            doc.metadata
            for doc in file_content
        ]
       
        chunks = text_splitter.create_documents(file_content_texts, metadatas=file_content_metadata)
        # serializable_chunks = [
        #     {
        #         "page_content": chunk.page_content,
        #         "metadata": chunk.metadata,
        #     }
        #     for chunk in chunks
        # ]

        # return serializable_chunks
        return chunks