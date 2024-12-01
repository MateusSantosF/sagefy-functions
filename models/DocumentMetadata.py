from typing import List, Optional
from pydantic import BaseModel

class DocumentMetadata(BaseModel):
    text: Optional[str] = None # Campo opcional
    tags: Optional[List[str]] = []  # Opcional com valor padrão
    category: Optional[str] = None  # Opcional com valor padrão None
    subcategory: Optional[str] = None  # Opcional com valor padrão None