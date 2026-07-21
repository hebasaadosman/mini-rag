from urllib import response

from ..LLMEnum import CohereRoleEnum,DocumentTypeEnum
import cohere
import logging
class CohereProvider():
    def __init__(self, api_key: str, default_input_max_characters: int = 2000,
                 default_generation_max_output_tokens: int = 100, default_generation_temperature: float = 0.1):
        self.api_key = api_key
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = "command-xlarge-nightly"

        self.embedding_model_id = "embed-english-v2.0"
        self.embedding_size = 1024
        self.client = cohere.Client(self.api_key)
        self.enums=CohereRoleEnum
        self.logger = logging.getLogger(__name__)


    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, model_size: int = None):
        self.embedding_model_id = model_id
        if model_size is not None:
            self.embedding_size = model_size


    def generate_text(self, prompt: str, chat_history: list = [], max_tokens: int = 100, temperature: float = None, **kwargs) -> str:   
            
        if not self.client:
            self.logger.error("Cohere client is not initialized. Please check your API key.")
            return None
        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set. Please set it using set_generation_model method.")
            return None

        if temperature is None:
            temperature = self.default_generation_temperature

        if max_tokens is None:
            max_tokens = self.default_generation_max_output_tokens

        chat_history.append(
            self.construct_prompt("You are a helpful assistant.", role=CohereRoleEnum.SYSTEM.value)
        )
        chat_history.append(
            self.construct_prompt(prompt, role=CohereRoleEnum.USER.value)
        )

        response = self.client.generate(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        if not response or not hasattr(response, 'generations') or len(response.generations) == 0:
            self.logger.error("Failed to generate text. Response is empty or invalid.")
            return None
        
        return response.generations[0].text.strip()

    def generate_embedding(self, text: str, document_type: str=None, **kwargs) -> list:
        if not self.client:
            self.logger.error("Cohere client is not initialized. Please check your API key.")
            return None
        if not self.embedding_model_id:
            self.logger.error("Embedding model ID is not set. Please set it using set_embedding_model method.")
            return None
        document_type = CohereRoleEnum.DOCUMENT.value 
        if document_type == DocumentTypeEnum.QUERY .value:
            document_type = CohereRoleEnum.QUERY.value
        

        response = self.client.embed(
            model=self.embedding_model_id,
            texts=[(text)],
            input_type=document_type,
            embedding_types=["float"],

        )
        if (
            not response
            or not hasattr(response, "embeddings")
            or not response.embeddings.float
            ):
                self.logger.error(
                    "Failed to generate embedding. Response is empty or invalid."
                )
                return None

    
        return response.embeddings.float[0]


    def construct_prompt(self, prompt: str, role: str = CohereRoleEnum.USER.value, **kwargs):
        return {
                "role": role,
                "text": prompt
            }
        
    

    def process_text(self, text: str) -> str:
        if len(text) > self.default_input_max_characters:
            self.logger.warning(f"Input text exceeds the maximum allowed characters ({self.default_input_max_characters}). Truncating.")
            return text[:self.default_input_max_characters]
        return text