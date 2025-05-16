import os
from langchain_postgres import PGVector
from langchain_openai import AzureOpenAIEmbeddings

USERS_TABLE = "users"
CLASSES_TABLE = "classes"
METRICS_TABLE = "metrics"
DASHBOARD_TABLE = "dashboard"

embeddings = AzureOpenAIEmbeddings(
    model=os.environ.get("OPENAI_EMBEDDING_MODEL"),
    dimensions=os.environ.get("OPENAI_EMBEDDING_MODEL_DIMENSIONS")
)
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="knowledge",
    connection=os.environ.get("PGSQL_CONNECTION"),
    use_jsonb=True,
)