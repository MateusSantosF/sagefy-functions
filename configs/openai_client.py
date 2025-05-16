import logging
import os
from openai import AzureOpenAI

DEFAULT_TEMPERATURE = 0.4
DEFAULT_MAX_TOKENS = 400

class AzureOpenAIClient:
    EMBEDDING_MODEL = os.environ["OPENAI_EMBEDDING_MODEL"]
    COMPLETION_MODEL= os.environ["AZURE_OPENAI_MODEL"]
    CLIENT = AzureOpenAI()

    @staticmethod
    def create_completion(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE):
        try:
            response = AzureOpenAIClient.CLIENT.chat.completions.create(
                model=AzureOpenAIClient.COMPLETION_MODEL,
                messages=[{"content": prompt, "role": "system"}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return (response.choices[0].message.content, response)
        except Exception as e:
            logging.error(f"Erro ao criar completion: {str(e)}")
            raise

    @staticmethod
    def create_completion_json(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE):
        try:
            response = AzureOpenAIClient.CLIENT.chat.completions.create(
                model=AzureOpenAIClient.COMPLETION_MODEL,
                messages=[{"content": prompt, "role": "system"}],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Erro ao criar completion JSON: {str(e)}")
            raise

    @staticmethod
    def create_embedding(input_text: str):
        try:
            embedding = AzureOpenAIClient.CLIENT.embeddings.create(
                model=AzureOpenAIClient.EMBEDDING_MODEL,
                dimensions=1536,
                input=input_text
            )
            return embedding.data[0].embedding
        except Exception as e:
            logging.error(f"Erro ao criar embedding: {str(e)}")
            raise
