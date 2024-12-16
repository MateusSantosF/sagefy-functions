import json
import azure.functions as func
from configs.settings import classes_client, users_client
from models.Class import Class
from models.ResponseModel import ResponseModel
from typing import List
from azure.data.tables import UpdateMode

from models.Roles import Role
from utils.token_utils import validate_user_access

turmas_bp = func.Blueprint()

@turmas_bp.function_name(name="register_students")
@turmas_bp.route(route="classes/students", methods=["POST"])
def register_emails(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para registrar uma lista de emails em uma turma específica.
    Somente PROFESSORES e ADMIN podem acessar.
    """
    try:
        # Autenticação do usuário
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):  # Se retornou um erro, repassa a resposta
            return user

        data = req.get_json()
        emails: List[str] = data.get("emails", [])
        classCode: str = data.get("classCode", "")

        if not emails or not classCode:
            return ResponseModel({"error": "Emails e classCode são obrigatórios."}, status_code=400)

        # Recupera a entidade da turma usando PartitionKey e RowKey
        try:
            turma = classes_client.get_entity(partition_key=classCode, row_key=classCode)
            turma = Class(**turma)
        except:
            return ResponseModel({"error": "Turma não encontrada."}, status_code=404)

        # Verifica se o usuário é o professor da turma ou um ADMIN
        if user.get("role") == "PROFESSOR" and turma.get("professorID") != user.get("email"):
            return ResponseModel({"error": "Você não é o professor desta turma."}, status_code=403)

        # Atualiza a lista de alunos
        existing_students =  turma.get("students", "[]")
        parsed_students: List[str] = json.loads(existing_students)
        updated_students = list(set(parsed_students + emails))
        distinct_students = list(set(updated_students))
        turma["students"] = json.dumps(distinct_students)
        turma["studentCount"] = len(distinct_students)
        classes_client.update_entity(entity=turma, mode=UpdateMode.MERGE)

        return ResponseModel({"message": "Emails registrados com sucesso."}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)

@turmas_bp.function_name(name="remove_student")
@turmas_bp.route(route="classes/students/remove", methods=["POST"])
def remove_student(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para remover um estudante de uma turma específica.
    Somente PROFESSORES e ADMIN podem acessar.
    """
    try:
        # Autenticação do usuário
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):  # Se retornou um erro, repassa a resposta
            return user

        # Obter dados da requisição
        data = req.get_json()
        email_to_remove = data.get("email")
        class_code = data.get("classCode")

        if not email_to_remove or not class_code:
            return ResponseModel({"error": "Email e classCode são obrigatórios."}, status_code=400)

        # Recupera a entidade da turma usando PartitionKey e RowKey
        try:
            turma_entity = classes_client.get_entity(partition_key=class_code, row_key=class_code)
            turma = Class(**turma_entity)
        except:
            return ResponseModel({"error": "Turma não encontrada."}, status_code=404)

        # Verifica se o usuário é o professor da turma ou um ADMIN
        if user.get("role") == Role.TEACHER.value and turma.get("professorID") != user.get("email"):
            return ResponseModel({"error": "Você não é o professor desta turma."}, status_code=403)

        # Atualiza a lista de alunos
        try:
            existing_students = json.loads(turma.get("students", "[]"))
            if email_to_remove not in existing_students:
                return ResponseModel({"error": "O email fornecido não está na lista de estudantes desta turma."}, status_code=404)

            updated_students = [email for email in existing_students if email != email_to_remove]
            turma["students"] = json.dumps(updated_students)
            turma["studentCount"] = len(updated_students)

            # Atualiza a turma na tabela
            classes_client.update_entity(entity=turma, mode=UpdateMode.MERGE)

            return ResponseModel({"message": "Estudante removido com sucesso.", "remaining_students": updated_students}, status_code=200)
        except Exception as e:
            return ResponseModel({"error": f"Erro ao processar a lista de estudantes: {str(e)}"}, status_code=500)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)
    
@turmas_bp.function_name(name="create_class")
@turmas_bp.route(route="classes", methods=["POST"])
def create_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para criar uma nova turma.
    Somente PROFESSORES e ADMIN podem acessar.
    """
    try:
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        data = req.get_json()
        class_code = data.get("classCode")
        access_code = data.get("accessCode")
        students = data.get("students", [])
        professor_email = user.get("email")

        if not class_code or not access_code:
            return ResponseModel({"error": "classCode e accessCode são obrigatórios."}, status_code=400)

        # Verifica se a turma já existe
        try:
            classes_client.get_entity(partition_key=class_code, row_key=class_code)
            return ResponseModel({"error": "Turma já existe."}, status_code=409)
        except:
            pass  # Turma não existe, prossegue

        # Cria nova turma
        turma = {
            "PartitionKey": class_code,
            "RowKey": class_code,
            "classCode": class_code,
            "accessCode": access_code,
            "professorID": professor_email,
            "students": json.dumps(students),
            "studentCount": len(students)
        }
        classes_client.create_entity(entity=turma)

        return ResponseModel({"message": "Turma criada com sucesso."}, status_code=201)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)

@turmas_bp.function_name(name="update_class")
@turmas_bp.route(route="classes", methods=["PUT", "PATCH"])
def update_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para atualizar uma turma existente.
    Somente PROFESSORES e ADMIN podem acessar.
    """
    try:
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        data = req.get_json()
        class_code = data.get("classCode")
        new_access_code = data.get("acessCode")  # Opcional

        if not class_code:
            return ResponseModel({"error": "classCode é obrigatório."}, status_code=400)

        # Recupera a turma
        try:
            turma = classes_client.get_entity(partition_key=class_code, row_key=class_code)
            turma = Class(**turma)
        except:
            return ResponseModel({"error": "Turma não encontrada."}, status_code=404)

        # Verifica se o usuário é o professor da turma ou um ADMIN
        if user.get("role") == "PROFESSOR" and turma.get("professorID") != user.get("email"):
            return ResponseModel({"error": "Você não é o professor desta turma."}, status_code=403)

        # Atualiza o accessCode se fornecido
        if new_access_code:
            turma["accessCode"] = new_access_code

        classes_client.update_entity(entity=turma, mode=UpdateMode.MERGE)

        return ResponseModel({"message": "Turma atualizada com sucesso."}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)

@turmas_bp.function_name(name="delete_class")
@turmas_bp.route(route="classes", methods=["DELETE"])
def delete_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para remover uma turma.
    Somente PROFESSORES e ADMIN podem acessar.
    """
    try:
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        class_code = req.params.get("classCode")

        if not class_code:
            return ResponseModel({"error": "classCode é obrigatório."}, status_code=400)

        # Recupera a turma para verificar permissões
        try:
            turma = classes_client.get_entity(partition_key=class_code, row_key=class_code)
            turma = Class(**turma)
        except:
            return ResponseModel({"error": "Turma não encontrada."}, status_code=404)

        # Verifica se o usuário é o professor da turma ou um ADMIN
        if user.get("role") == "PROFESSOR" and turma.get("professorID") != user.get("email"):
            return ResponseModel({"error": "Você não é o professor desta turma."}, status_code=403)

        # Deleta a turma
        classes_client.delete_entity(partition_key=class_code, row_key=class_code)
        return ResponseModel({"message": "Turma removida com sucesso."}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)
    
    
@turmas_bp.function_name(name="list_classes")
@turmas_bp.route(route="classes", methods=["GET"])
def list_classes(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para listar todas as turmas de um professor específico ou todas as turmas (para ADMIN).
    - ADMIN pode listar turmas de qualquer professor fornecendo o email como parâmetro de consulta.
    - PROFESSOR pode listar apenas suas próprias turmas.
    """
    try:
        # Autentica o usuário e obtém suas informações
        user = validate_user_access(req, allowed_roles=[Role.ADMIN, Role.TEACHER])
        if isinstance(user, ResponseModel):
            return user  # Retorna a resposta de erro se a autenticação falhar

        # Inicializa o email do professor
        professor_email = None

        # Verifica o papel do usuário
        if user.get("role") == Role.ADMIN.value:
            # Administrador pode especificar o email do professor via parâmetro de consulta
            professor_email = req.params.get("professorEmail")
            if not professor_email:
                # Tenta obter do corpo da requisição se não estiver nos parâmetros
                try:
                    data = req.get_json()
                    professor_email = data.get("professorEmail")
                except:
                    pass

            if not professor_email:
                # Se não fornecer professorEmail, retorna todas as turmas
                filter_query = None
            else:
                # Filtra pelas turmas do professor especificado
                filter_query = f"professorID eq '{professor_email}'"

                # Opcional: Verificar se o professor existe na tabela de usuários
                try:
                    users_client.get_entity(partition_key=Role.TEACHER.value, row_key=professor_email)
                except:
                    return ResponseModel({"error": "Professor não encontrado."}, status_code=404)
        elif user.get("role") == Role.TEACHER.value:
            # Professor só pode listar suas próprias turmas
            professor_email = user.get("email")
            filter_query = f"professorID eq '{professor_email}'"
        else:
            # Papel não autorizado
            return ResponseModel({"error": "Permissão negada."}, status_code=403)

        # Realiza a consulta na tabela de classes
        classes = []
        try:
            if filter_query:
                entities = classes_client.query_entities(query_filter=filter_query, select=["RowKey", "PartitionKey", "accessCode", "classCode", "studentCount"])
            else:
                # ADMIN solicitando todas as turmas
                entities = classes_client.list_entities()

            for entity in entities:
                turma = Class(**entity)
                classes.append(turma)
        except Exception as query_error:
            return ResponseModel({"error": f"Erro ao consultar as turmas: {str(query_error)}"}, status_code=500)

        return ResponseModel({"classes": classes}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)

@turmas_bp.function_name(name="get_class_by_code")
@turmas_bp.route(route="classes/read", methods=["GET"])
def get_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint para ler uma turma específica.
    - ADMIN pode ler qualquer turma.
    - PROFESSOR pode ler apenas suas próprias turmas.
    """
    classCode = req.params.get("classCode")

    if not classCode:
        return ResponseModel({"error": "classCode é obrigatório."}, status_code=400)

    try:
        # Autentica o usuário e obtém suas informações
        user = validate_user_access(req, allowed_roles=[Role.ADMIN, Role.TEACHER])
        if isinstance(user, ResponseModel):
            return user  # Retorna a resposta de erro se a autenticação falhar

        # Recupera a turma especificada
        try:
            turma_entity = classes_client.get_entity(partition_key=classCode, row_key=classCode)
            turma = Class(**turma_entity)
        except:
            return ResponseModel({"error": "Turma não encontrada."}, status_code=404)

        # Verifica permissões
        if user.get("role") == Role.TEACHER.value and turma.get("professorID") != user.get("email"):
            return ResponseModel({"error": "Você não tem permissão para acessar esta turma."}, status_code=403)

        deserializedStudents = json.loads(turma.get("students", "[]"))
        turma["students"] = deserializedStudents
        # Retorna os detalhes da turma
        return ResponseModel({"data": turma}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)