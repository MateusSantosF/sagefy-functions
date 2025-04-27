import io
import json
import logging
import azure.functions as func
from pathlib import Path
from models.DocumentMetadata import DocumentMetadata
from configs.settings import openai_client
from constants import BLOB_CONTAINER_NAME
from langchain_experimental.text_splitter import SemanticChunker
from configs.settings import embeddings, vector_store
from PyPDF2 import PdfReader
from docx import Document as DocxDocument

process_data_bp = func.Blueprint()

@process_data_bp.function_name(name="process-training-data")
@process_data_bp.blob_trigger(
    arg_name="blob",
    path=f"{BLOB_CONTAINER_NAME}/{{name}}",
    connection="AzureWebJobsStorage"
)
def process_raw_training_data(blob: func.InputStream):
    logging.info(f"Processando arquivo: {blob.name}")

    try:
        if not blob.name:
            logging.error("Blob name is None.")
            return

        blob_bytes = blob.read()
        ext = Path(blob.name).suffix.lower()

        if ext not in ['.pdf', '.docx', '.txt', '.md']:
            logging.error(f"Tipo de arquivo {ext} não suportado.")
            return

        full_content = get_blob_content(ext=ext, blob_bytes=blob_bytes)

        text_splitter = SemanticChunker(embeddings,
                                breakpoint_threshold_type="percentile",
                                breakpoint_threshold_amount=95.0,
                                min_chunk_size=200)
        

        docs = text_splitter.create_documents([full_content])
        class_code = Path(blob.name).parent.name
        file_name = Path(blob.name).name 

        enriched_docs = []
        for doc in docs:
            data = extract_metadata(doc.page_content)
            doc.metadata = {
                "file_id": file_name,
                "category": data.category,
                "subcategory": data.subcategory,
                "class_code": class_code
            }
            enriched_docs.append(doc)


        vector_store.add_documents(enriched_docs)
        logging.info(f"{len(docs)} chunks inseridos no vector store.")
    except Exception as e:
        logging.error(f"Erro ao processar o arquivo {blob.name}: {str(e)}")


def extract_metadata(text: str) -> DocumentMetadata:

    try:
        prompt = (
            "Analise o seguinte texto e identifique os seguintes metadados:\n"
            "- Tags relevantes\n"
            "- Categoria principal\n"
            "- Subcategoria\n"
            f"Texto: {text}\n"
            "Responda no formato JSON: {\"tags\": [\"...\"], \"category\": \"...\", \"subcategory\": \"...\"}"
        )
        response_text = openai_client.create_completion_json(
            prompt=prompt, max_tokens=300, temperature=0.6
        )
        if not response_text:
            return DocumentMetadata(text=text, category="Outros", subcategory="Outros", tags=[])

        data = json.loads(response_text)
        metadata = DocumentMetadata(**data)
        metadata.text = text
        return metadata

    except Exception as e:
        logging.error(f"Erro ao extrair metadados: {str(e)}")
        return DocumentMetadata(text=text, category="Outros", subcategory="Outros", tags=[])


def get_blob_content(ext:str, blob_bytes:bytes):

    full_text = ""

    if ext in ['.txt', '.md']:
        full_text = blob_bytes.decode('utf-8', errors='ignore')
    elif ext == '.pdf':
        reader = PdfReader(io.BytesIO(blob_bytes))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == '.docx':
        doc = DocxDocument(io.BytesIO(blob_bytes))
        full_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    else:
        logging.error(f"Tipo de arquivo {ext} não suportado.")
        raise 
    
    return full_text