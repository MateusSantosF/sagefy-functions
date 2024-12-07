
from enum import Enum
from typing import List, TypedDict, Optional
from models.Roles import Role

class User(TypedDict):
    PartitionKey: Role # Role do usuário
    RowKey: str  # Email do usuário
    name: str
    email: str
    password: Optional[str]
    classes: Optional[List[str]]