import os
from utils.openai_client import AzureOpenAIClient
from langchain_postgres import PGVector
from langchain_openai import AzureOpenAIEmbeddings

USERS_TABLE = "users"
CLASSES_TABLE = "classes"
METRICS_TABLE = "metrics"
DASHBOARD_TABLE = "dashboard"

embeddings = AzureOpenAIEmbeddings(
    model=os.environ["OPENAI_EMBEDDING_MODEL"],
    dimensions=os.environ["OPENAI_EMBEDDING_MODEL_DIMENSIONS"]
)
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="knowledge",
    connection=os.environ["PGSQL_CONNECTION"],
    use_jsonb=True,
)

openai_client = AzureOpenAIClient(model=os.environ["AZURE_OPENAI_MODEL"], embedding_model=os.environ["OPENAI_EMBEDDING_MODEL"])