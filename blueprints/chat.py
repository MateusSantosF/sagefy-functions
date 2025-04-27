import azure.functions as func
from azure.functions import HttpRequest
from configs.settings import openai_client, vector_store
from uuid import uuid4
from models.DocumentMetadata import DocumentMetadata
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.log_usage_metrics import log_usage_metrics
from utils.token_utils import validate_user_access
chat_bp = func.Blueprint()


DEFAULT_PROMPT = (
    "Você é um assistente virtual especializado em responder perguntas sobre a disciplina de Multimeios Didáticos. "
    "Você pode fornecer informações sobre atualizações, notas, provas, lembretes e informações configuradas pelo professor.\n\n"
    "### Instruções:\n"
    "- Responda APENAS com base no contexto fornecido.\n"
    "- Responda sobre 'dedê' minha namorada, se perguntado. Seja sempre educado com ela.\n"
    "- Responda apenas perguntas em português.\n"
    "- Não conte piadas.\n"
    "- NÃO forneça informações sobre assuntos fora da disciplina.\n\n"
)

@chat_bp.function_name(name="chat")
@chat_bp.route(route="chat", methods=["POST"])
def main(req: HttpRequest) -> func.HttpResponse:
    request_id = str(uuid4())  # Gera um ID único para cada requisição

    try:
        # Autenticação do usuário
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN, Role.STUDENT])
        if isinstance(user, ResponseModel):  # Se retornou um erro, repassa a resposta
            return user
        
        # Recebe o body da requisição
        body = req.get_json()
        user_prompt = body.get("prompt", "")

        if not user_prompt:
            return ResponseModel({"error": "Prompt is required in the request body."}, status_code=400)

        # Gera um documento hipotético com base no prompt do usuário
        hypothetical_document, raw_response = openai_client.create_completion(
            prompt=f"{DEFAULT_PROMPT} Pergunta do usuário: {user_prompt}",
            max_tokens=400,
            temperature=0.7,
        )

        if not hypothetical_document:
            return ResponseModel({"error": "Failed to generate hypothetical document."}, status_code=500)

        hypothetical_document_embedding = openai_client.create_embedding(input_text=hypothetical_document)

        class_code = user.get("classCode")
        filters = {}
        if class_code is not None:
            filters = {"class_code": class_code}
        
        result = vector_store.similarity_search_by_vector(
            embedding=hypothetical_document_embedding, k=10, filter=filters
        )
        
        matches_metadata = []
        context = []
        for document in result:
            context.append(document.page_content)
            matches_metadata.append(DocumentMetadata(**document.metadata))

        print("Contexto:", context)

        # Cria um novo prompt para a IA com os textos extraídos
        assistant_prompt = (
            f"{DEFAULT_PROMPT}\nBaseado nas seguintes informações: {context}\n"
            f"Por favor, responda à seguinte pergunta: {user_prompt}"
        )

        # Chama a IA com o novo prompt
        assistant_response, raw_response = openai_client.create_completion(
            prompt=assistant_prompt,
            max_tokens=5000,
            temperature=0.3,
        )


        log_usage_metrics(
            user=user,
            prompt=user_prompt,
            response=raw_response,
            metadata=matches_metadata,
        )

        # Formata a resposta final
        response = {
            "id": request_id,
            "response": assistant_response,
            "history": [],
        }
        return ResponseModel(response, status_code=200)
    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)
