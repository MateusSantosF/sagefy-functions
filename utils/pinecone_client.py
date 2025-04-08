import logging
from typing import List
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

    def vector_search(self, index_name: str, vector: List[float], max_results = 6):
        try:
            matched_results = self.client.Index(index_name).query(
                top_k=max_results, 
                vector=vector,
                include_metadata=True,
                include_values=False,
            )
        
            return matched_results
        except Exception as e:
            logging.error(f"Erro ao realizar busca vetorial: {str(e)}")
            raise
    
    def delete_vectors_by_filter(self, filter: dict):
        """
        Exclui todos os vetores que satisfaçam o filtro.
        """
        try:
            self.index.delete(filter=filter)
        except Exception as e:
            logging.error(f"Erro ao deletar vetores com filtro {filter}: {str(e)}")
            raise