import logging
from pinecone import Pinecone

class PineconeClient:
    def __init__(self, api_key: str, index_name: str):
        self.client = Pinecone(api_key=api_key)
        self.index = self.client.Index(index_name)

    def upsert_vector(self, vector_id: str, values: list, metadata: dict):
        try:
            self.index.upsert(vectors=[{"id": vector_id, "values": values, "metadata": metadata}])
        except Exception as e:
            logging.error(f"Erro ao upsertar vector {vector_id}: {str(e)}")
            raise
