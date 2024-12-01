import json
import logging
import azure.functions as func
from pathlib import Path
from models.DocumentMetadata import DocumentMetadata
from utils.file_processor import extract_content
from configs.settings import openai_client, pinecone_client

bp = func.Blueprint()

@bp.function_name(name="process-training-data")
@bp.blob_trigger(
    arg_name="blob",
    path="raw-training-data/{name}",
    connection="AzureWebJobsStorage"
)
def process_raw_training_data(blob: func.InputStream):
    logging.info(f"Processando arquivo: {blob.name}")

    try:
        if blob.name is None:
            logging.error("Blob name is None.")
            return
        # Ler o conteúdo do blob em bytes
        blob_bytes = blob.read()
        file_extension = Path(blob.name).suffix.lower()
        if file_extension not in ['.pdf', '.docx', '.txt', '.md']:
            logging.error(f"Tipo de arquivo {file_extension} não suportado.")
            return

        # Extrair conteúdo do arquivo usando LangChain
        content = extract_content(blob_bytes, file_extension)

        # Processar cada chunk com embeddings e Pinecone
        for chunk in content.items[0:2]:
            text = chunk.content

            # Gerar embeddings
            embedding = openai_client.create_embedding(input_text=text)
            # Extrair metadados relevantes
            metadata = extract_metadata(text)

            pinecone_client.upsert_vector(
                vector_id=chunk.id,
                values=embedding,
                metadata=metadata.model_dump()
            )

    except Exception as e:
        logging.error(f"Erro ao processar o arquivo {blob.name}: {str(e)}")


def extract_metadata(text: str) -> DocumentMetadata:
    """
    Utiliza a OpenAI para extrair metadados relevantes (tags, categoria e subcategoria).
    """
    try:
        prompt = (
            "Analise o seguinte texto e identifique os seguintes metadados:\n"
            "- Tags relevantes\n"
            "- Categoria principal\n"
            "- Subcategoria\n"

            f"Texto: {text}\n"
            'Responda no formato JSON: {"tags": ["..."], "category": "...", "subcategory": "..."}'
        )
        response_text  = openai_client.create_completion_json(prompt=prompt, max_tokens=300, temperature=0.6)
        if not response_text:
            return DocumentMetadata(text=text, category="Outros", subcategory="Outros", tags=[])
        
        response_json = json.loads(response_text)
        # Valide e crie o objeto DocumentMetadata
        metadata = DocumentMetadata(**response_json)
        metadata.text = text
        return metadata
    except Exception as e:
        logging.error(f"Erro ao extrair metadados: {str(e)}")
        return DocumentMetadata(text=text, category="Outros", subcategory="Outros", tags=[])