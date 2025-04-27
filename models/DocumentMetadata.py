from typing import Optional
from pydantic import BaseModel

class DocumentMetadata(BaseModel):
    text: Optional[str] = None 
    category: Optional[str] = None 
    subcategory: Optional[str] = None