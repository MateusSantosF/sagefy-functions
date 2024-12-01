import os
from utils.openai_client import AzureOpenAIClient
from utils.pinecone_client import PineconeClient

# Inicializar clientes
pinecone_client = PineconeClient(api_key=os.environ["PINECONE_API_KEY"], index_name=os.environ["PINECONE_INDEX_NAME"])
openai_client = AzureOpenAIClient(model=os.environ["AZURE_OPENAI_MODEL"], embedding_model=os.environ["OPENAI_EMBEDDING_MODEL"])
