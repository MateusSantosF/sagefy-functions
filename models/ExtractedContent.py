from typing import List
from pydantic import BaseModel, Field
from utils.generate_unique_id import generate_unique_id


class ExtractedContentItem(BaseModel):
    id: str = Field(..., description="ID único gerado para o chunk do conteúdo.")
    content: str = Field(..., description="Texto do chunk extraído.")


class ExtractedContent(BaseModel):
    items: List[ExtractedContentItem] = Field(..., description="Lista de itens de conteúdo extraído.")

    @classmethod
    def from_raw_content(cls, content: List[dict]) -> "ExtractedContent":
        """
        Constrói uma instância de `ExtractedContent` a partir de uma lista de dicionários brutos.
        Gera o ID único para cada texto usando `generate_unique_id`.
        """
        items = [
            ExtractedContentItem(
                id=generate_unique_id(item["text"]),
                content=item["text"]
            )
            for item in content
        ]
        return cls(items=items)

    def to_dict(self) -> List[dict]:
        """Retorna o conteúdo extraído como uma lista de dicionários."""
        return [item.dict() for item in self.items]
