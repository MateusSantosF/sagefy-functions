import azure.functions as func
from azure.functions import HttpRequest
from configs.settings import openai_client, pinecone_client, pinecone_index_name
from typing import TypedDict, List, Optional
from uuid import uuid4
import json

chat_bp = func.Blueprint()

class ResponseModel(TypedDict):
    request_id: str
    response: Optional[str]
    error: Optional[str]
    status: str

DEFAULT_PROMPT = (
    "Você é um assistente virtual especializado em responder perguntas sobre a disciplina de Multimeios Didáticos. "
    "Você pode fornecer informações sobre atualizações, notas, provas, lembretes e informações configuradas pelo professor.\n\n"
    "### Instruções:\n"
    "- Responda APENAS com base no contexto fornecido.\n"
    "- Responda apenas perguntas em português.\n"
    "- Não conte piadas.\n"
    "- NÃO forneça informações sobre assuntos fora da disciplina.\n\n"
)

@chat_bp.function_name(name="chat")
@chat_bp.route(route="chat", methods=["POST"])
def main(req: HttpRequest) -> func.HttpResponse:
    request_id = str(uuid4())  # Gera um ID único para cada requisição

    try:
        # Recebe o body da requisição
        body = req.get_json()
        user_prompt = body.get("prompt", "")

        if not user_prompt:
            response: ResponseModel = {
                "request_id": request_id,
                "response": None,
                "error": "Prompt is required in the request body.",
                "status": "error",
            }
            return func.HttpResponse(
                body=json.dumps(response),  # Converte para JSON
                status_code=400,
                mimetype="application/json"
            )

        # Gera um documento hipotético com base no prompt do usuário
        hypothetical_document = openai_client.create_completion(
            prompt=f"{DEFAULT_PROMPT} Pergunta do usuário: {user_prompt}",
            max_tokens=400,
            temperature=0.7,
        )

        if not hypothetical_document:
            response: ResponseModel = {
                "request_id": request_id,
                "response": None,
                "error": "Failed to generate hypothetical document.",
                "status": "error",
            }
            return func.HttpResponse(
                body=json.dumps(response),  # Converte para JSON
                status_code=500,
                mimetype="application/json"
            )

        # Gera o embedding do documento hipotético
        hypothetical_document_embedding = openai_client.create_embedding(input_text=hypothetical_document)

        # Realiza a busca no Pinecone
        result = pinecone_client.vector_search(index_name=pinecone_index_name, vector=hypothetical_document_embedding)
        matches = result.get("matches", [])  # type: ignore

        # Extrai apenas os textos dos metadados
        matched_texts = [match.get("metadata", {}).get("text", "") for match in matches if "metadata" in match]

        # Cria um novo prompt para a IA com os textos extraídos
        assistant_prompt = (
            f"{DEFAULT_PROMPT}\nBaseado nas seguintes informações: {matched_texts}\n"
            f"Por favor, responda à seguinte pergunta: {user_prompt}"
        )

        # Chama a IA com o novo prompt
        assistant_response = openai_client.create_completion(
            prompt=assistant_prompt,
            max_tokens=5000,
            temperature=0.3,
        )

        # Formata a resposta final
        response: ResponseModel = {
            "request_id": request_id,
            "response": assistant_response,
            "error": None,
            "status": "success",
        }
        return func.HttpResponse(
            body=json.dumps(response),  # Converte para JSON
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        # Resposta em caso de erro
        response: ResponseModel = {
            "request_id": request_id,
            "response": None,
            "error": str(e),
            "status": "error",
        }
        return func.HttpResponse(
            body=json.dumps(response),  # Converte para JSON
            status_code=500,
            mimetype="application/json"
        )
