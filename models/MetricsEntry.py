from typing import TypedDict, Optional, List

class MetricsEntry(TypedDict):
    PartitionKey: str  # Obrigatório
    RowKey: str        # Obrigatório
    request_id: Optional[str]
    user_email: Optional[str]
    user_role: Optional[str]
    class_code: Optional[str]
    prompt: Optional[str]
    response: Optional[str]
    completion_tokens: Optional[int]
    prompt_tokens: Optional[int]
    total_tokens: Optional[int]
    categories: Optional[str]
    subcategories: Optional[str]
    timestamp: Optional[str]  # Formato ISO