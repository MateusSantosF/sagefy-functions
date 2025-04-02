from typing import List, TypedDict

class Class(TypedDict):
    PartitionKey: str  # accessCode
    RowKey: str  # accessCode
    className: str
    classCode: str
    accessCode: str
    professorID: str  # Email do professor
    students: str
    studentCount: int