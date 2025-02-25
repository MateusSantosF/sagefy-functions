# utils/openai_client.py
import logging
from openai import AzureOpenAI

class AzureOpenAIClient:
    def __init__(self, model: str, embedding_model: str):
        self.completion_model = model
        self.embedding_model = embedding_model
        self.client = AzureOpenAI()

    def create_completion(self, prompt: str, max_tokens: int = 100, temperature: float = 0.0):
        try:
            response = self.client.chat.completions.create(
                model=self.completion_model,
                messages=[{"content": prompt, "role": "system"}],
                max_tokens=max_tokens,
                temperature=temperature,
         
            )
            return (response.choices[0].message.content, response)
        except Exception as e:
            logging.error(f"Erro ao criar completion: {str(e)}")
            raise

    def create_completion_json(self, prompt: str, max_tokens: int = 100, temperature: float = 0.0):
        try:
            response = self.client.chat.completions.create(
                model=self.completion_model,
                messages=[{"content": prompt, "role": "system"}],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
                
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Erro ao criar completion: {str(e)}")
            raise

    def create_embedding(self, input_text: str):
        try:
            embedding = self.client.embeddings.create(
                model=self.embedding_model,
                dimensions=1536,            
                input=input_text
            )
            return embedding.data[0].embedding
        except Exception as e:
            logging.error(f"Erro ao criar embedding: {str(e)}")
            raise
