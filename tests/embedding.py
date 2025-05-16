# %% [code]
import io
import sys
sys.path.append("..")
import os
import json
from PyPDF2 import PdfReader
from langchain_experimental.text_splitter import SemanticChunker
from langchain.text_splitter import RecursiveCharacterTextSplitter
def load_local_settings():
    """Carrega variáveis de ambiente do local.settings.json para testes"""
    settings_path = os.path.join(os.path.dirname(__file__), "../local.settings.json")

    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Arquivo local.settings.json não encontrado: {settings_path}")

    with open(settings_path, "r") as f:
        settings = json.load(f)

    for key, value in settings.get("Values", {}).items():
        os.environ[key] = value  # Define as variáveis de ambiente

# Carrega as variáveis antes de tudo
load_local_settings()
# importe seu objeto de embeddings (e, se quiser, VectorStore)
from configs.settings import embeddings


# %% [code]
def read_pdf(path: str, max_page: int = None) -> str:
    """
    Lê todas as páginas de um PDF e retorna uma string com o texto concatenado.
    """
    reader = PdfReader(path)
    texts = []
  
    for i, page in enumerate(reader.pages):
        if max_page is not None and i >= max_page:
            break
        txt = page.extract_text()
        if txt:
            texts.append(txt)
    return "\n".join(texts)

# %% [code]
def token_count(input_string) -> int:
    """
    Count the number of tokens in the input string using the 'o200k_base' encoding.

    Args:
        input_string (str): The input string to count tokens for.

    Returns:
        int: The number of tokens in the input string.
    """
    import tiktoken

    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(input_string)
    token_count = len(tokens)
    return token_count
# %% [code]
def split_document(text: str):
    """
    1) Chunks semânticos com SemanticChunker
    2) Para cada chunk semântico, faz split recursivo em pedaços menores
    Retorna a lista de LangChain Documents semânticos e a lista de sub-chunks (strings).
    """
    # --- Chunking semântico ---

    chunk_size = 512  # tamanho alvo
    sem_chunker = SemanticChunker(
        embeddings=embeddings,
        breakpoint_threshold_type="gradient",
        breakpoint_threshold_amount=80.0,
        min_chunk_size=128
    )
    # --- Split recursivo de cada bloco semântico ---
    char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=int(chunk_size * 0.13),
            length_function=token_count,
            separators=[
                "\n\n",
                "\n",
                " ",
                ".",
                ",",
                "\u200b",  # Zero-width space
                "\uff0c",  # Fullwidth comma
                "\u3001",  # Ideographic comma
                "\uff0e",  # Fullwidth full stop
                "\u3002",  # Ideographic full stop
                "",
            ],
    )
    sem_docs = sem_chunker.create_documents([text])
    print(f"Chunks semânticos gerados: {len(sem_docs)}")
    print("\n=== Exemplos de chunks ===")
    for i, chunk in enumerate(sem_docs, start=1):
        print(f"\n--- chunk {i} ---")
        print(chunk)
        print("------------------------")
    
    all_subchunks = []
    for idx, doc in enumerate(sem_docs, start=1):
        subchunks = char_splitter.split_text(doc.page_content)
        print(f"  • Chunk semântico {idx} dividido em {len(subchunks)} sub-chunks")
        all_subchunks.extend(subchunks)

    print(f"Total de sub-chunks: {len(all_subchunks)}")
    return sem_docs, all_subchunks
# %% [code]
pdf_path = "C:\\Users\\mateu\\Documents\\Trabalho de Conclusao de Curso\\sagefy-functions\\training_data\Bloco 1 (1).pdf"

# 2) Leia o texto
raw_text = read_pdf(
    path=pdf_path,
    max_page=10,  # Defina o número máximo de páginas a serem lidas
)

# 3) Execute as etapas de chunking
sem_docs, subchunks = split_document(raw_text)

# %% 
# 4) Mostre alguns sub-chunks para inspeção
print("\n=== Exemplos de sub-chunks ===")
for i, chunk in enumerate(subchunks, start=1):
    print(f"\n--- Sub-chunk {i} ---")
    print(chunk)
    print("------------------------")

# %%
