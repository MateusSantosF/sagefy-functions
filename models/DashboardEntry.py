from typing import TypedDict, Optional


class DashboardEntry(TypedDict):
    PartitionKey: str  # classCode
    RowKey: str        # Data do resumo, por exemplo, YYYY-MM-DD HH:MM
    class_code: Optional[str]
    total_conversations: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    top_categories: Optional[str]
    top_subcategories: Optional[str]
    timestamp: Optional[str]  # Formato ISO
    top_students: Optional[str] # JSON com os top 10 alunos