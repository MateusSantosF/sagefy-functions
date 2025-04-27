
from typing import TypedDict

class Token(TypedDict):
    sub: str
    name: str
    email: str
    role: str
