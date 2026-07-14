from abc import ABC, abstractmethod

class LLMInterface(ABC):
    @abstractmethod
    def set_generation_model(self, model_id: str):
        pass

    @abstractmethod
    def set_embedding_model(self, model_id: str,model_size: int = None):
        pass

    @abstractmethod
    def generate_text(self, prompt: str, chat_history: list = [], max_tokens: int = 100, temperature: float = None, **kwargs) -> str:
        pass

    @abstractmethod
    def generate_embedding(self, text: str, document_type: str=None, **kwargs) -> list:
        pass


    @abstractmethod
    def construct_prompt(self, prompt: str, role: str, **kwargs) -> dict:
        pass