import datetime
from uuid import uuid4
from models.MetricsEntry import MetricsEntry
from configs.settings import metrics_client
from models.User import User
from openai.types.chat import ChatCompletion

def log_usage_metrics(
    user: User,
    prompt: str,
    response: ChatCompletion,
) -> None:
    """
    Registra métricas de uso na tabela de métricas do Azure.

    Args:
        metrics_client (TableClient): Cliente da tabela de métricas.
        user (dict): Informações sobre o usuário que fez a requisição.
        prompt (str): O prompt enviado pelo usuário.
        response (str): A resposta gerada pelo assistente.
        tokens_used (int): Número de tokens utilizados na requisição.
    """
    # Gerar um RowKey único usando UUID
    row_key = str(uuid4())

    completion_tokens = response.usage.completion_tokens  # type: ignore
    prompt_tokens = response.usage.prompt_tokens # type: ignore
    total_tokens =response.usage.total_tokens # type: ignore

    # Determinar o PartitionKey. Pode ser o email do usuário ou uma data, dependendo da sua preferência.
    # Aqui, usamos a data atual para facilitar a consulta por data.
    partition_key = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    # Extrair informações do usuário
    user_email = user.get("email")
    user_role = user.get("role")
    class_code = user.get("classCode") if user_role == "STUDENT" else None

    # Gerar um request_id único
    request_id = str(uuid4())

    # Capturar o timestamp atual em formato ISO
    timestamp = datetime.datetime.utcnow().isoformat()

    # Criar a entrada de métricas
    metrics_entry: MetricsEntry = {
        "PartitionKey": partition_key,
        "RowKey": row_key,
        "request_id": request_id,
        "user_email": user_email,
        "user_role": user_role,
        "class_code": class_code,
        "prompt": prompt,
        "response": response.choices[0].message.content,
        "completion_tokens": completion_tokens,
        "prompt_tokens": prompt_tokens,
        "total_tokens": total_tokens,
        "timestamp": timestamp
    }
    
    # Inserir a entidade na tabela de métricas
    metrics_client.create_entity(entity=metrics_entry)
