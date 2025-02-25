import os
from utils.openai_client import AzureOpenAIClient
from utils.pinecone_client import PineconeClient
from azure.data.tables import TableServiceClient

USERS_TABLE = "users"
CLASSES_TABLE = "classes"
METRICS_TABLE = "metrics"
DASHBOARD_TABLE = "dashboard"
pinecone_index_name = "sagefy"

# Inicializar clientes
pinecone_client = PineconeClient(api_key=os.environ["PINECONE_API_KEY"], index_name=os.environ["PINECONE_INDEX_NAME"])
openai_client = AzureOpenAIClient(model=os.environ["AZURE_OPENAI_MODEL"], embedding_model=os.environ["OPENAI_EMBEDDING_MODEL"])
openai_client_4o = AzureOpenAIClient(model="gpt-4o", embedding_model=os.environ["OPENAI_EMBEDDING_MODEL"])

azure_tables_client = TableServiceClient.from_connection_string(conn_str=os.environ["AZURE_TABLES_CONNECTION_STRING"])
users_client = azure_tables_client.get_table_client(USERS_TABLE)
classes_client = azure_tables_client.get_table_client(CLASSES_TABLE)
metrics_client = azure_tables_client.get_table_client(METRICS_TABLE)
dashboard_client = azure_tables_client.get_table_client(DASHBOARD_TABLE)