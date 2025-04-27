import uuid
import azure.functions as func
from sqlalchemy import select
from models.DatabaseModels import ClassModel, UserModel
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.token_utils import validate_user_access
from utils.db_session import db_session

turmas_bp = func.Blueprint()

@turmas_bp.function_name(name='register_students')
@turmas_bp.route(route='classes/students', methods=['POST'])
def register_students(req: func.HttpRequest) -> func.HttpResponse:
    """
    Registra múltiplos emails em uma turma (JSONB students).
    Só ADMIN e TEACHER podem acessar.
    """
    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    data = req.get_json()
    emails = data.get('emails', [])
    class_code = data.get('classCode')
    if not emails or not class_code:
        return ResponseModel({'error': 'emails e classCode obrigatórios.'}, status_code=400)

    cls = db_session.execute(
        select(ClassModel).where(ClassModel.class_code == class_code)
    ).scalar_one_or_none()
    if not cls:
        db_session.close()
        return ResponseModel({'error': 'Turma não encontrada.'}, status_code=404)

    # Permissão: só criador da turma (professor) ou ADMIN
    if user.get('role') == Role.TEACHER.value and cls.teacher_id != user.get('sub'):
        db_session.close()
        return ResponseModel({'error': 'Não autorizado.'}, status_code=403)

    # Atualiza lista de estudantes
    current = cls.students or []
    combined = list(set(current + emails))
    cls.students = combined
    cls.student_count = len(combined)
    db_session.commit()
    db_session.close()

    return ResponseModel({'message': 'Students registered successfully.', 'students': combined}, status_code=200)

@turmas_bp.function_name(name='remove_student')
@turmas_bp.route(route='classes/students/remove', methods=['POST'])
def remove_student(req: func.HttpRequest) -> func.HttpResponse:
    """
    Remove um estudante da lista JSONB de uma turma.
    """
    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    data = req.get_json()
    email = data.get('email')
    class_code = data.get('classCode')
    if not email or not class_code:
        return ResponseModel({'error': 'email e classCode obrigatórios.'}, status_code=400)

    cls = db_session.execute(
        select(ClassModel).where(ClassModel.class_code == class_code)
    ).scalar_one_or_none()
    if not cls:
        db_session.close()
        return ResponseModel({'error': 'Turma não encontrada.'}, status_code=404)

    if user.get('role') == Role.TEACHER.value and cls.teacher_id != user.get('sub'):
        db_session.close()
        return ResponseModel({'error': 'Não autorizado.'}, status_code=403)

    current = cls.students or []
    if email not in current:
        db_session.close()
        return ResponseModel({'error': 'Student not in class.'}, status_code=404)

    updated = [e for e in current if e != email]
    cls.students = updated
    cls.student_count = len(updated)
    db_session.commit()
    db_session.close()

    return ResponseModel({'message': 'Student removed.', 'students': updated}, status_code=200)

@turmas_bp.function_name(name='create_class')
@turmas_bp.route(route='classes', methods=['POST'])
def create_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Cria uma nova turma.
    Só ADMIN e TEACHER podem acessar.
    """
    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    data = req.get_json()
    class_code = data.get('classCode')
    access_code = data.get('accessCode')
    class_name = data.get('className')
    students = data.get('students', [])
    if not class_code or not access_code or not class_name:
        return ResponseModel({'error': 'classCode, accessCode e className obrigatórios.'}, status_code=400)

    exists = db_session.execute(
        select(ClassModel).where(ClassModel.class_code == class_code)
    ).scalar_one_or_none()
    if exists:
        db_session.close()
        return ResponseModel({'error': 'Turma já existe.'}, status_code=409)

    new_cls = ClassModel(
        id=str(uuid.uuid4()),
        class_code=class_code,
        access_code=access_code,
        class_name=class_name,
        teacher_id=user.get("sub"),
        students=list(set(students)),
        student_count=len(set(students))
    )
    db_session.add(new_cls)
    db_session.commit()
    db_session.close()

    return ResponseModel({'message': 'Class created.', 'classCode': class_code}, status_code=201)

@turmas_bp.function_name(name='update_class')
@turmas_bp.route(route='classes', methods=['PUT','PATCH'])
def update_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Atualiza nome ou access_code de uma turma.
    """
    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    data = req.get_json()
    class_code = data.get('classCode')
    new_name = data.get('className')
    new_access = data.get('accessCode')
    if not class_code:
        return ResponseModel({'error': 'classCode obrigatório.'}, status_code=400)

    cls = db_session.execute(
        select(ClassModel).where(ClassModel.class_code == class_code)
    ).scalar_one_or_none()
    if not cls:
        db_session.close()
        return ResponseModel({'error': 'Turma não encontrada.'}, status_code=404)
    if user.get('role') == Role.TEACHER.value and cls.teacher_id != user.get('sub'):
        db_session.close()
        return ResponseModel({'error': 'Não autorizado.'}, status_code=403)

    if new_name:
        cls.class_name = new_name
    if new_access:
        cls.access_code = new_access

    db_session.commit()
    db_session.close()
    return ResponseModel({'message': 'Class updated.', 'classCode': class_code}, status_code=200)

@turmas_bp.function_name(name='delete_class')
@turmas_bp.route(route='classes', methods=['DELETE'])
def delete_class(req: func.HttpRequest) -> func.HttpResponse:
    """
    Deleta uma turma.
    """
    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    code = req.params.get('classCode')
    if not code:
        return ResponseModel({'error': 'classCode obrigatório.'}, status_code=400)

    cls = db_session.execute(
        select(ClassModel).where(ClassModel.class_code == code)
    ).scalar_one_or_none()
    if not cls:
        db_session.close()
        return ResponseModel({'error': 'Turma não encontrada.'}, status_code=404)
    if user.get('role') == Role.TEACHER.value and cls.teacher_id != user.get('sub'):
        db_session.close()
        return ResponseModel({'error': 'Não autorizado.'}, status_code=403)

    db_session.delete(cls)
    db_session.commit()
    db_session.close()
    return ResponseModel({'message': 'Class deleted.'}, status_code=200)

@turmas_bp.function_name(name='list_classes')
@turmas_bp.route(route='classes', methods=['GET'])
def list_classes(req: func.HttpRequest) -> func.HttpResponse:
    """
    Lista turmas de um teacher ou todas (ADMIN).
    """
    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    if user.get('role') == Role.ADMIN.value:
        prof_email = req.params.get('professorEmail')
        if prof_email:
            users = db_session.execute(
                select(UserModel).where(UserModel.email == prof_email, UserModel.role == Role.TEACHER.value)
            ).scalar_one_or_none()
            if not users:
                db_session.close()
                return ResponseModel({'error': 'Professor não existe.'}, status_code=404)
            stmt = select(ClassModel).where(ClassModel.teacher_id == users.id)
        else:
            stmt = select(ClassModel)
    else:
        stmt = select(ClassModel).where(ClassModel.teacher_id == user.get('sub'))

    classes = db_session.execute(stmt).scalars().all()
    db_session.close()
    result = [
        {
            'classCode': c.class_code,
            'className': c.class_name,
            'accessCode': c.access_code,
            'studentCount': c.student_count
        } for c in classes
    ]
    return ResponseModel({'classes': result}, status_code=200)

@turmas_bp.function_name(name='get_class_by_code')
@turmas_bp.route(route='classes/read', methods=['GET'])
def get_class_by_code(req: func.HttpRequest) -> func.HttpResponse:
    """
    Retorna detalhes de uma turma.
    """
    code = req.params.get('classCode')
    if not code:
        return ResponseModel({'error': 'classCode obrigatório.'}, status_code=400)

    user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
    if isinstance(user, ResponseModel):
        return user

    cls = db_session.execute(
        select(ClassModel).where(ClassModel.class_code == code)
    ).scalar_one_or_none()
    db_session.close()
    if not cls:
        return ResponseModel({'error': 'Turma não encontrada.'}, status_code=404)
    if user.get('role') == Role.TEACHER.value and cls.teacher_id != user.get('sub'):
        return ResponseModel({'error': 'Não autorizado.'}, status_code=403)

    data = {
        'classCode': cls.class_code,
        'className': cls.class_name,
        'accessCode': cls.access_code,
        'students': cls.students or []
    }
    return ResponseModel({'data': data}, status_code=200)
