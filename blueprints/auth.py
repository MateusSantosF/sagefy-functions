import json
import azure.functions as func
import datetime
import os
from models.Class import Class
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.token_utils import create_jwt, validate_user_access, verify_jwt
from utils.check_password_hash import check_password_hash
from utils.generate_password_hash import generate_password_hash
from azure.data.tables import UpdateMode

from configs.settings import classes_client, users_client
from models.User import User 


auth_bp = func.Blueprint()

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]
JWT_EXP_DELTA_SECONDS = 3600 # 1 horas
REFRESH_TOKEN_EXP_DELTA_SECONDS = 3600 * 24 * 30  # 30 dias

@auth_bp.function_name(name="authenticate_student")
@auth_bp.route(route="authenticate/students", methods=["POST"])
def authenticate_student(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para autenticar um aluno e retornar um token JWT.
    """
    try:
        data = req.get_json()
        email = data.get("email")
        access_code = data.get("accessCode")

        if not email or not access_code:
            return ResponseModel({"error": "Email e accessCode são obrigatórios."}, status_code=400)

        # Recupera todas as turmas correspondentes ao código de acesso
        try:
            filter_query = f"accessCode eq '{access_code}'"
            target_classes = list(classes_client.query_entities(query_filter=filter_query))
            
            if not target_classes:
                return ResponseModel({"error": "Nenhuma turma encontrada com este código de acesso."}, status_code=404)
        except Exception as e:
            return ResponseModel({"error": f"Erro ao buscar turmas: {str(e)}"}, status_code=500)

        # Itera pelas turmas para verificar o email do estudante
        matched_turma = None
        for turma_data in target_classes:
            turma = Class(**turma_data)
            parsed_students_list = json.loads(turma.get("students", "[]"))
            if email in parsed_students_list:
                matched_turma = turma
                break

        if not matched_turma:
            return ResponseModel({"error": "Email não autorizado para nenhuma turma com este código de acesso."}, status_code=403)

        # Gera o token JWT
        payload = {
            "email": email,
            "classCode": matched_turma.get("classCode"),
            "role": "STUDENT",
        }

        token = create_jwt(payload, expires_delta_seconds=JWT_EXP_DELTA_SECONDS, type="access")
        refresh_token = create_jwt(payload, REFRESH_TOKEN_EXP_DELTA_SECONDS, type="refresh")

        return ResponseModel({"accessToken": token, "refreshToken": refresh_token}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)


@auth_bp.function_name(name="authenticate_managers")
@auth_bp.route(route="authenticate/managers", methods=["POST"])
def authenticate_admin_professor(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para autenticar ADMIN e PROFESSOR e retornar um token JWT.
    """
    try:
        data = req.get_json()
        email = data.get("email")
        password = data.get("password")  # Senha enviada no corpo da requisição

        if not email or not password:
            return ResponseModel({"error": "Email e senha são obrigatórios."}, status_code=400)

        # Verifica se o email corresponde ao admin
        if email == ADMIN_EMAIL:
            # Verifica a senha do admin
            if not check_password_hash(ADMIN_PASSWORD_HASH, password):
                return ResponseModel({"error": "Senha incorreta."}, status_code=401)
            
            role = Role.ADMIN.value
            payload = {
                "email": email,
                "role": role,
            }
            token = create_jwt(payload)
            refresh_token = create_jwt(payload, REFRESH_TOKEN_EXP_DELTA_SECONDS, "refresh")

            return ResponseModel({"accessToken": token, "refreshToken": refresh_token}, status_code=200)

        else:
            # Tenta obter como PROFESSOR
            try:
                user_entity = users_client.get_entity(partition_key=Role.TEACHER.value, row_key=email)
                user = User(**user_entity)
                role = Role.TEACHER.value
            except:
                return ResponseModel({"error": "Usuário não encontrado."}, status_code=404)

            # Verifica a senha do professor
            if not check_password_hash(user.get("password"), password):
                return ResponseModel({"error": "Senha incorreta."}, status_code=401)

            # Gera o token JWT
            payload = {
                "email": email,
                "role": role,
            }
            token = create_jwt(payload)
            refresh_token = create_jwt(payload, REFRESH_TOKEN_EXP_DELTA_SECONDS, "refresh")

            return ResponseModel({"accessToken": token, "refreshToken":refresh_token }, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)


@auth_bp.function_name(name="change_password")
@auth_bp.route(route="change_password", methods=["POST"])
def change_password(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para professores autenticados alterarem sua senha.
    Requer autenticação via token JWT.
    Recebe a senha atual e a nova senha.
    """
    try:
        # Autentica o usuário e obtém suas informações
        user = validate_user_access(req, allowed_roles=[Role.TEACHER])
        if isinstance(user, ResponseModel):
            return user

        data = req.get_json()
        current_password = data.get("currentPassword")
        new_password = data.get("newPassword")

        if not current_password or not new_password:
            return ResponseModel({"error": "Senha atual e nova senha são obrigatórias."}, status_code=400)

        email = user.get("email")

        # Recupera o usuário da tabela
        try:
            user_entity = users_client.get_entity(partition_key=Role.TEACHER.value, row_key=email)
            professor = User(**user_entity)
        except:
            return ResponseModel({"error": "Professor não encontrado."}, status_code=404)

        # Verifica a senha atual
        if not check_password_hash(professor.get("password"), current_password):
            return ResponseModel({"error": "Senha atual incorreta."}, status_code=401)

        # Gera o hash da nova senha
        new_password_hash = generate_password_hash(new_password)

        # Atualiza a senha no objeto professor
        professor["password"] = new_password_hash

        # Atualiza a entidade na tabela
        try:
            users_client.update_entity(entity=professor, mode=UpdateMode.REPLACE)
        except Exception as update_error:
            return ResponseModel({"error": "Erro ao atualizar a senha."}, status_code=500)

        return ResponseModel({"message": "Senha alterada com sucesso."}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)

@auth_bp.function_name(name="create_teacher")
@auth_bp.route(route="teachers", methods=["POST"])
def register_professor(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para registrar um novo professor.
    Somente ADMIN autenticado pode acessar.
    Recebe email e password do professor.
    """
    try:
        # Autentica o usuário e garante que é ADMIN
        user = validate_user_access(req, allowed_roles=[Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        data = req.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return ResponseModel({"error": "Email e senha são obrigatórios."}, status_code=400)

        # Verifica se o professor já está registrado
        try:
            existing_professor = users_client.get_entity(partition_key=Role.TEACHER.value, row_key=email)
            return ResponseModel({"error": "Professor já está registrado."}, status_code=409)
        except:
            pass  # Professor não existe, prossegue

        # Gera o hash da senha
        password_hash = generate_password_hash(password)

        # Cria o objeto de usuário
        professor = {
            "PartitionKey":Role.TEACHER.value,
            "RowKey":email,
            "email":email,
            "password": password_hash,
        }

        # Salva o professor na tabela de usuários
        try:
            users_client.create_entity(entity=professor)
        except Exception as e:
            return ResponseModel({"error": f"Erro ao registrar o professor: {str(e)}"}, status_code=500)

        return ResponseModel({"message": "Professor registrado com sucesso."}, status_code=201)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)
    
@auth_bp.function_name(name="refresh_token")
@auth_bp.route(route="refresh-token", methods=["POST"])
def refresh_access_token(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para atualizar o access token usando um refresh token válido.
    """
    try:
        data = req.get_json()
        refresh_token = data.get("refreshToken")

        if not refresh_token:
            return ResponseModel({"error": "Refresh token é obrigatório."}, status_code=400)

        # Decodifica e valida o refresh token
        decoded_refresh = verify_jwt(refresh_token, expected_type="refresh")
        if not decoded_refresh:
            return ResponseModel({"error": "Refresh token inválido ou expirado."}, status_code=401)

        email = decoded_refresh.get("email")
        role = decoded_refresh.get("role")

        if not email or not role:
            return ResponseModel({"error": "Token inválido."}, status_code=401)

        # Gera um novo access token
        payload = {
            "email": email,
            "role": role
        }
        new_access_token = create_jwt(payload, JWT_EXP_DELTA_SECONDS, "access")
        new_refresh_token = create_jwt(payload, REFRESH_TOKEN_EXP_DELTA_SECONDS, "refresh")

        return ResponseModel({
            "accessToken": new_access_token,
            "refreshToken": new_refresh_token
        }, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)