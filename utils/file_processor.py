from io import BytesIO
import re
import PyPDF2
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models.ExtractedContent import ExtractedContent
from docx import Document

def clean_text(text: str) -> str:
    """
    Remove pontos excessivos, deixando apenas um único ponto onde for necessário
    ou eliminando completamente.
    """
    # Substitui sequências de três ou mais pontos consecutivos por um único ponto
    cleaned_text = re.sub(r'\.{3,}', '.', text)
    # Remove os pontos restantes isolados em espaços
    cleaned_text = re.sub(r'\s*\.\s*', ' ', cleaned_text)
    # Remove múltiplos espaços e converte em espaço único
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

    # Remove espaços extras ao final
    return cleaned_text.strip()

def extract_content(blob_bytes: bytes, file_type: str) -> ExtractedContent:
    content = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=20,
        length_function=len,
        is_separator_regex=False,
    )

    if file_type == '.pdf':
        file_like_object = BytesIO(blob_bytes)
        reader = PyPDF2.PdfReader(file_like_object)
        text = ''
        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                text += page_text
        split_texts = text_splitter.split_text(text)
        for chunk_num, chunk in enumerate(split_texts, start=1):
            cleaned_chunk = clean_text(chunk)
            content.append({
                'page': chunk_num,
                'text': cleaned_chunk
            })

    elif file_type == '.docx':
        file_like_object = BytesIO(blob_bytes)
        document = Document(file_like_object)
        full_text = []
        for para in document.paragraphs:
            full_text.append(para.text)
        text = '\n'.join(full_text)
        split_texts = text_splitter.split_text(text)
        for chunk_num, chunk in enumerate(split_texts, start=1):
            cleaned_chunk = clean_text(chunk)
            content.append({
                'page': chunk_num,
                'text': cleaned_chunk
            })

    elif file_type == '.txt':
        text = blob_bytes.decode('utf-8')
        split_texts = text_splitter.split_text(text)
        for chunk_num, chunk in enumerate(split_texts, start=1):
            cleaned_chunk = clean_text(chunk)
            content.append({
                'page': chunk_num,
                'text': cleaned_chunk
            })

    elif file_type == '.md':
        text = blob_bytes.decode('utf-8')
        split_texts = text_splitter.split_text(text)
        for chunk_num, chunk in enumerate(split_texts, start=1):
            cleaned_chunk = clean_text(chunk)
            content.append({
                'page': chunk_num,
                'text': cleaned_chunk
            })
    else:
        raise ValueError(f"Tipo de arquivo {file_type} não suportado.")

    return ExtractedContent.from_raw_content(content)
