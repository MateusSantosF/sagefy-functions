import os
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from constants import BLOB_CONTAINER_NAME

AZURE_STORAGE_CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

def list_files(prefix: str):

    blobs = container_client.list_blobs(name_starts_with=prefix, include=["metadata"])
    return [blob for blob in blobs]

def upload_file(folder: str, file_name: str, data: bytes, metadata: dict = {}):

    blob_name = f"{folder}/{file_name}"
    blob_client = container_client.get_blob_client(blob_name)
    
    blob_client.upload_blob(data, overwrite=True, metadata=metadata)
    return blob_name

def delete_blob(blob_name: str):
    print(f"Excluindo blob: {blob_name}")
    blob_client = container_client.get_blob_client(blob_name)
    try:
        blob_client.delete_blob()
    except ResourceNotFoundError:
        raise Exception("Arquivo não encontrado no storage.")