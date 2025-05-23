import datetime
import os
from typing import List, Optional
import jwt
import azure.functions as func

from models.Token import Token
from models.ResponseModel import ResponseModel
from models.Roles import Role

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

def verify_jwt(token: str, expected_type:str) -> Optional[Token]:
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if expected_type and decoded.get("type") != expected_type:
            return None
        return decoded
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def create_jwt(payload: dict,expires_delta_seconds=3600, type="access") -> str:
    payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_delta_seconds)
    payload["type"] = type
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def validate_user_access(req:func.HttpRequest, allowed_roles: List[Role]):
    """
    Valida se o usuário possui uma role permitida para acessar o endpoint.

    Args:
        req (HttpRequest): O objeto de requisição HTTP.
        allowed_roles (list): Lista de roles permitidos.

    Returns:
        dict: Usuário decodificado do token JWT se válido.
        ResponseModel: Resposta de erro se a validação falhar.
    """
    # Verifica se o cabeçalho de autorização está presente
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return ResponseModel({"error": "Autenticação requerida."}, status_code=401)

    # Decodifica o token JWT
    token = auth_header.split(" ")[1]
    user = verify_jwt(token, "access")
    if not user:
        return ResponseModel({"error": "Token inválido ou expirado."}, status_code=401)

    allowed_role_values = [role.value for role in allowed_roles]

    # Verifica se o role do usuário está na lista de roles permitidos
    if allowed_role_values and user.get("role") not in allowed_role_values:
        return ResponseModel({"error": "Permissão negada."}, status_code=403)

    # Retorna o usuário se válido
    return user