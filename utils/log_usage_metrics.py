import uuid
from typing import List
from datetime import datetime
from models.DatabaseModels import MetricsModel
from models.DocumentMetadata import DocumentMetadata
from openai.types.chat import ChatCompletion
from models.Roles import Role
from utils.db_session import db_session


def log_usage_metrics(
    user: dict,
    prompt: str,
    response: ChatCompletion,
    metadata: List[DocumentMetadata]
) -> None:
    """
    Registra métricas de uso no Postgres na tabela metrics.
    """
    # Tokens
    completion_tokens = response.usage.completion_tokens  # type: ignore
    prompt_tokens = response.usage.prompt_tokens  # type: ignore
    total_tokens = response.usage.total_tokens  # type: ignore

    # Unique row key
    row_key = str(uuid.uuid4())

    # User info
    user_email = user.get("email")
    user_role = user.get("role")
    class_code = user.get("classCode") if user_role == Role.STUDENT.value else None

    request_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()

    categories = ", ".join([doc.category for doc in metadata if doc.category])
    subcategories = ", ".join([doc.subcategory for doc in metadata if doc.subcategory])
    assistant_response = response.choices[0].message.content  # type: ignore

    # Persist MetricsModel
    try:
        metric = MetricsModel(
            id=row_key,
            request_id=request_id,
            user_email=user_email,
            user_role=user_role,
            class_code=class_code,
            categories=categories,
            subcategories=subcategories,
            prompt=prompt,
            response=assistant_response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            timestamp=timestamp
        )
        db_session.add(metric)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
