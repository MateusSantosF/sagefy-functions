from http.client import HTTPException
import uuid
import azure.functions as func
from sqlalchemy import  select, update
from constants import JWT_EXP_DELTA_SECONDS, REFRESH_TOKEN_EXP_DELTA_SECONDS
from models.DatabaseModels import ClassModel, UserModel
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.token_utils import create_jwt, validate_user_access, verify_jwt
from utils.check_password_hash import check_password_hash
from utils.generate_password_hash import generate_password_hash
from utils.db_session import SessionLocal

auth_bp = func.Blueprint()


@auth_bp.function_name(name='authenticate_student')
@auth_bp.route(route='authenticate/students', methods=['POST'])
def authenticate_student(req: func.HttpRequest) -> func.HttpResponse:
    try:

        body = req.get_json()
        email = body.get('email')
        access_code = body.get('accessCode')
        if not email or not access_code:
            return ResponseModel({'error': 'Email e accessCode são obrigatórios.'}, status_code=400)

        stmt = select(ClassModel).where(
            ClassModel.access_code == access_code,
            ClassModel.students.contains([email])
        )
        db_session = SessionLocal()
        classes = db_session.execute(stmt).scalars().all()
        db_session.close()
        if not classes:
            return ResponseModel({'error': 'Credenciais de aluno inválidas.'}, status_code=403)

        cls = classes[0]
        payload = {'email': email, 'classCode': cls.class_code, 'role': 'STUDENT'}
        at = create_jwt(payload, expires_delta_seconds=JWT_EXP_DELTA_SECONDS, type='access')
        rt = create_jwt(payload, expires_delta_seconds=REFRESH_TOKEN_EXP_DELTA_SECONDS, type='refresh')
        return ResponseModel({'accessToken': at, 'refreshToken': rt}, status_code=200)
    except Exception as e:
        print(e)
        return ResponseModel({'error': str(e)}, status_code=500)

@auth_bp.function_name(name='authenticate_managers')
@auth_bp.route(route='authenticate/managers', methods=['POST'])
def authenticate_managers(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        email = body.get('email')
        password = body.get('password')
        if not email or not password:
            return ResponseModel({'error': 'Email e senha são obrigatórios.'}, status_code=400)
        
        db_session = SessionLocal()
        stmt = select(UserModel).where(
            UserModel.email == email
        )
        user = db_session.execute(stmt).scalar_one_or_none()

        db_session.close()
        if not user or not check_password_hash(user.password or '', password):
            return ResponseModel({'error': 'Credenciais inválidas.'}, status_code=401)
        name = user.name
        user_id = user.id

        payload = {'email': email, 'role': user.role, 'name': name, "sub":user_id}
        at = create_jwt(payload)
        rt = create_jwt(payload, REFRESH_TOKEN_EXP_DELTA_SECONDS, 'refresh')
        return ResponseModel({'accessToken': at, 'refreshToken': rt}, status_code=200)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)

@auth_bp.function_name(name='change_password')
@auth_bp.route(route='change_password', methods=['POST'])
def change_password(req: func.HttpRequest) -> func.HttpResponse:
    try:

        user_ctx = validate_user_access(req, allowed_roles=[Role.TEACHER])
        if isinstance(user_ctx, ResponseModel):
            return user_ctx
        
        db_session = SessionLocal()
        data = req.get_json()
        current = data.get('currentPassword')
        new_pw = data.get('newPassword')
        if not current or not new_pw:
            return ResponseModel({'error': 'Senha atual e nova senha são obrigatórias.'}, status_code=400)

        stmt = select(UserModel).where(UserModel.email == user_ctx.get('email'))
        user = db_session.execute(stmt).scalar_one_or_none()
        if not user or not check_password_hash(user.password or '', current):
            db_session.close()
            return ResponseModel({'error': 'Credenciais inválidas.'}, status_code=401)

        pw_hash = generate_password_hash(new_pw)
        db_session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(password=pw_hash)
        )
        db_session.commit()
        db_session.close()
        return ResponseModel({'message': 'Senha alterada com sucesso.'}, status_code=200)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)

@auth_bp.function_name(name='change_teacher_password')
@auth_bp.route(route='teachers/password', methods=['PUT'])
def change_teacher_password(req: func.HttpRequest) -> func.HttpResponse:
    user_ctx = validate_user_access(req, allowed_roles=[Role.ADMIN])
    if isinstance(user_ctx, ResponseModel):
        return user_ctx

    data = req.get_json()
    new_pw = data.get('newPassword')
    teacher_id = data.get('teacherId')
    if not new_pw:
        return ResponseModel({'error': 'Nova senha é obrigatória.'}, status_code=400)

    session = SessionLocal()
    try:
        stmt = select(UserModel).where(
            UserModel.id == teacher_id,
            UserModel.role == Role.TEACHER.value,
            UserModel.is_active == True
        )
        teacher = session.execute(stmt).scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Professor não encontrado.")

        # 4) atualizar a senha
        hashed = generate_password_hash(new_pw)
        session.execute(
            update(UserModel)
            .where(UserModel.id == teacher.id)
            .values(password=hashed)
        )
        session.commit()

        return ResponseModel({'message': 'Senha do professor alterada com sucesso.'}, status_code=200)

    except HTTPException as he:
        session.rollback()
        return ResponseModel({'error': he.detail}, status_code=he.status_code)

    except Exception as e:
        session.rollback()
        return ResponseModel({'error': str(e)}, status_code=500)

    finally:
        session.close()
        
@auth_bp.function_name(name='create_teacher')
@auth_bp.route(route='teachers', methods=['POST'])
def create_teacher(req: func.HttpRequest) -> func.HttpResponse:
    # 1) validação de acesso
    user_ctx = validate_user_access(req, allowed_roles=[Role.ADMIN])
    if isinstance(user_ctx, ResponseModel):
        return user_ctx

    data = req.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')

    if not email or not password:
        return ResponseModel(
            {'error': 'Email e senha são obrigatórios.'},
            status_code=400
        )

    session = SessionLocal()
    try:
        stmt = select(UserModel).where(UserModel.email == email)
        existing = session.execute(stmt).scalar_one_or_none()

        if existing:
            if not existing.is_active:
                session.execute(
                    update(UserModel)
                    .where(UserModel.id == existing.id)
                    .values(is_active=True)
                )
                session.commit()
                return ResponseModel(
                    {'message': 'Professor reativado com sucesso.'},
                    status_code=200
                )
            else:
                return ResponseModel(
                    {'error': 'Professor já registrado.'},
                    status_code=409
                )

        new_user = UserModel(
            id=str(uuid.uuid4()),
            role=Role.TEACHER.value,
            name=name,
            email=email,
            password=generate_password_hash(password),
            is_active=True
        )
        session.add(new_user)
        session.commit()
        return ResponseModel(
            {'message': 'Professor registrado com sucesso.'},
            status_code=201
        )

    except Exception as e:
        session.rollback()
        return ResponseModel({'error': str(e)}, status_code=500)

    finally:
        session.close()


@auth_bp.function_name(name='list_teachers')
@auth_bp.route(route='teachers', methods=['GET'])
def list_teachers(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Somente ADMIN pode listar
        user_ctx = validate_user_access(req, allowed_roles=[Role.ADMIN])
        if isinstance(user_ctx, ResponseModel):
            return user_ctx

        db_session = SessionLocal()
        # Buscar todos que tenham role=TEACHER e is_active=True
        stmt = select(UserModel).where(
            UserModel.role == Role.TEACHER.value,
            UserModel.is_active == True
        )
        result = db_session.execute(stmt).scalars().all()
        db_session.close()

        # Serializar lista
        teachers = [
            {
                'id': t.id,
                'name': t.name,
                'email': t.email
            }
            for t in result
        ]

        return ResponseModel({'teachers': teachers}, status_code=200)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)


# 2) Inativar professor
@auth_bp.function_name(name='deactivate_teacher')
@auth_bp.route(route='teachers', methods=['DELETE'])
def deactivate_teacher(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Apenas ADMIN pode inativar
        user_ctx = validate_user_access(req, allowed_roles=[Role.ADMIN])
        if isinstance(user_ctx, ResponseModel):
            return user_ctx

        # Receber e-mail como query param
        email = req.params.get('email')
        if not email:
            return ResponseModel({'error': 'Parâmetro email é obrigatório.'}, status_code=400)

        # Verificar existência
        stmt = select(UserModel).where(
            UserModel.email == email,
            UserModel.role == Role.TEACHER.value
        )
        db_session = SessionLocal()
        teacher = db_session.execute(stmt).scalar_one_or_none()
        if not teacher:
            db_session.close()
            return ResponseModel({'error': 'Professor não encontrado.'}, status_code=404)

        # Marcar como inativo
        teacher.is_active = False
        db_session.commit()
        db_session.close()

        return ResponseModel({'message': 'Professor inativado com sucesso.'}, status_code=200)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)
    
@auth_bp.function_name(name='refresh_token')
@auth_bp.route(route='refresh-token', methods=['POST'])
def refresh_token(req: func.HttpRequest) -> func.HttpResponse:

    try:
        body = req.get_json()  
        token = body.get("refreshToken")
        if not token:
            return ResponseModel({'error': 'Refresh token é obrigatório.'}, status_code=400)
        decoded = verify_jwt(token, expected_type='refresh')
        if not decoded:
            return ResponseModel({'error': 'Refresh token inválido ou expirado.'}, status_code=401)
        payload = {'email': decoded.get('email'), 'role': decoded.get('role'), 'name': decoded.get('name'), "sub": decoded.get("sub")}
        new_at = create_jwt(payload, JWT_EXP_DELTA_SECONDS, 'access')
        new_rt = create_jwt(payload, REFRESH_TOKEN_EXP_DELTA_SECONDS, 'refresh')
        return ResponseModel({'accessToken': new_at, 'refreshToken': new_rt}, status_code=200)
    except Exception as e:
        print("Raw error:", str(e))
        return ResponseModel({'error': str(e)}, status_code=500)
