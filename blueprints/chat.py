import azure.functions as func
from azure.functions import HttpRequest
from uuid import uuid4
import json

from blueprints.process_training_data_func import clean_utf8_text
from configs.openai_client import AzureOpenAIClient
from configs.system_prompt import (
    DEFAULT_PROMPT,
    SMALLTALK_DETECTION_AND_RESPONSE_PROMPT
)
from configs.settings import vector_store
from models.DocumentMetadata import DocumentMetadata
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.log_usage_metrics import log_usage_metrics
from utils.token_utils import validate_user_access

chat_bp = func.Blueprint()


def parse_request(req: HttpRequest, student_class_name= str | None):
    try:
        body = req.get_json()
    except ValueError:
        return None, None, ResponseModel({"error": "Formato JSON inválido."}, status_code=400)
    

    prompt = body.get("prompt", "").strip()
    prompt_enchanced = f"Sobre a disciplina {student_class_name}, responda: {prompt}" if student_class_name else prompt
    if not prompt:
        return None, None, ResponseModel({"error": "Campo 'prompt' é obrigatório."}, status_code=400)

    history = body.get("history", [])
    if not isinstance(history, list):
        return None, None, ResponseModel({"error": "Campo 'history' deve ser um array."}, status_code=400)

    history = history[-6:]
    return prompt, history, prompt_enchanced, None

def build_history_string(history: list) -> str:
    """
    Recebe uma lista de dicts com chaves 'sender' e 'content' e retorna
    uma string com cada mensagem em uma linha no formato "sender: content".
    """
    lines = [
        f"{msg['sender']}: {msg['content']}"
        for msg in history
        if 'sender' in msg and 'content' in msg
    ]
    return "\n".join(lines)

def detect_and_respond_smalltalk(user_prompt: str, history: list) -> str:
    history_str = build_history_string(history)
    combined = (
        f"Histórico de conversa:\n{history_str}\n\n" 
    ) + f"Mensagem do Usuário: {user_prompt}\n"

    prompt = (
        f"{SMALLTALK_DETECTION_AND_RESPONSE_PROMPT}\n"
        f"{combined}"
    )

    response_text = AzureOpenAIClient.create_completion_json(prompt=prompt)
    try:
        payload:dict = json.loads(response_text)
    except json.JSONDecodeError:
        return None

    if not payload.get("is_smalltalk", False):
        return None
    return payload.get("smalltalk_response", "").strip()


def generate_hypothetical_document(question: str) -> str:
    """
    Gera um documento hipotético a partir de uma pergunta, usando o modelo Azure OpenAI.
    Esse texto simula a resposta que o seu próprio chatbot daria, e será usado como chave para a busca vetorial.
    """
    # Montamos um prompt que indica ao modelo que crie uma resposta bem detalhada para servir de "contexto" na busca.
    hyde_prompt = (
        "Você é um sistema de geração de documentos hipotéticos.\n"
        "Dada a pergunta abaixo, gere uma resposta detalhada que cubra todos os pontos relevantes:\n\n"
        f"Pergunta: {question}\n"
        "Resposta detalhada (documento hipotético):"
    )
    # create_completion retorna (texto_gerado, resposta_raw). Usamos apenas o texto.
    hyde_doc, _ = AzureOpenAIClient.create_completion(prompt=hyde_prompt)
    return hyde_doc

def search_vector_store_hyde(document: str, user_class: str):
    """
    1) Gera o documento hipotético (hyde) a partir da pergunta (document).
    2) Cria embedding desse hyde document.
    3) Executa a busca vetorial usando esse embedding, aplicando filtros por class_code.
    4) Retorna lista de textos (context) e metadados.
    """
    
    # 1) Gera o documento hipotético
    hyde_doc = generate_hypothetical_document(document)
    embedding = AzureOpenAIClient.create_embedding(input_text=hyde_doc)

    filters = (
        {"$or": [
            {"class_code": user_class},
            {"class_code": "admin"},
            {"class_code": None}
        ]}
        if user_class else {}
    )

    results = vector_store.similarity_search_by_vector(
        embedding=embedding,
        k=10,
        filter=filters
    )

    context = [doc.page_content for doc in results]
    metadata = [DocumentMetadata(**doc.metadata) for doc in results]
    return context, metadata

def search_vector_store(document: str, user_class: str):
    embedding = AzureOpenAIClient.create_embedding(input_text=document)
    filters = ({"$or": [
        {"class_code": user_class}, {"class_code": "admin"}, {"class_code": None}
    ]} if user_class else {})
    results = vector_store.similarity_search_by_vector(
        embedding=embedding, k=10, filter=filters
    )
    context = [doc.page_content for doc in results]
    metadata = [DocumentMetadata(**doc.metadata) for doc in results]
    return context, metadata


def compose_assistant_prompt(context: list, user_prompt: str, user_history: list | None = []) -> str:
    context_str = "; ".join(context)
    history_str = build_history_string(user_history) 

    return (
        f"{DEFAULT_PROMPT}\n"
        f"Baseado nas seguintes informações: {context_str}\n"
        f"Pergunta do usuário: {user_prompt}\n"
        f"\nHistórico de conversa:\n{history_str}"
    )


def core_agent_flow(user, user_prompt: str, user_history: list, log_usage=True):
    context, metadata = search_vector_store(user_prompt, user.get("classCode"))
    assistant_prompt = compose_assistant_prompt(context, user_prompt, user_history)
    assistant_response, raw_resp = AzureOpenAIClient.create_completion(prompt=assistant_prompt)

    if log_usage:
        log_usage_metrics(
            user=user,
            prompt=user_prompt,
            response=raw_resp,
            metadata=metadata,
        )
    return assistant_response, context

@chat_bp.function_name(name="chat")
@chat_bp.route(route="chat", methods=["POST"],auth_level=func.AuthLevel.ANONYMOUS)
def main(req: HttpRequest) -> func.HttpResponse:
    request_id = str(uuid4())
    try:
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN, Role.STUDENT])
        if isinstance(user, ResponseModel):
            return user

        user_prompt, history, prompt_enchanced, err = parse_request(req, user.get("className", None))
        if err:
            return err

        smalltalk_reply = detect_and_respond_smalltalk(user_prompt, history)
        if smalltalk_reply is not None:
            payload = {
                "id": request_id,
                "response": smalltalk_reply,
                "history": history
            }
            return ResponseModel(payload, status_code=200)

        assistant_response, _ = core_agent_flow(user, prompt_enchanced, history)
        payload = {
            "id": request_id,
            "response": assistant_response,
            "history": history
        }
        return ResponseModel(payload, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)