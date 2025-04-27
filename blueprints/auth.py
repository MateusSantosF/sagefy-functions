import uuid
import azure.functions as func
from sqlalchemy import  select, update
from constants import ADMIN_EMAIL, ADMIN_PASSWORD_HASH, JWT_EXP_DELTA_SECONDS, REFRESH_TOKEN_EXP_DELTA_SECONDS
from models.DatabaseModels import ClassModel, UserModel
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.token_utils import create_jwt, validate_user_access, verify_jwt
from utils.check_password_hash import check_password_hash
from utils.generate_password_hash import generate_password_hash
from utils.db_session import db_session

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

        # Admin
        if email == ADMIN_EMAIL:
            if not check_password_hash(ADMIN_PASSWORD_HASH, password):
                return ResponseModel({'error': 'Senha incorreta.'}, status_code=401)
            role = Role.ADMIN.value
            name = 'Admin'
        else:
            stmt = select(UserModel).where(
                UserModel.email == email,
                UserModel.role == Role.TEACHER.value
            )
            user = db_session.execute(stmt).scalar_one_or_none()
            db_session.close()
            if not user or not check_password_hash(user.password or '', password):
                return ResponseModel({'error': 'Credenciais inválidas.'}, status_code=401)
            role = Role.TEACHER.value
            name = user.name

        payload = {'email': email, 'role': role, 'name': name, "sub": user.id}
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

@auth_bp.function_name(name='create_teacher')
@auth_bp.route(route='teachers', methods=['POST'])
def create_teacher(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_ctx = validate_user_access(req, allowed_roles=[Role.ADMIN])
        if isinstance(user_ctx, ResponseModel):
            return user_ctx
        
        data = req.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')

        if not email or not password:
            return ResponseModel({'error': 'Email e senha são obrigatórios.'}, status_code=400)

        exists = db_session.execute(select(UserModel).where(UserModel.email == email)).scalar_one_or_none()
        if exists:
            db_session.close()
            return ResponseModel({'error': 'Professor já registrado.'}, status_code=409)

        user = UserModel(
            id=str(uuid.uuid4()),
            role=Role.TEACHER.value,
            name=name,
            email=email,
            password=generate_password_hash(password)
        )
        db_session.add(user)
        db_session.commit()
        db_session.close()
        return ResponseModel({'message': 'Professor registrado com sucesso.'}, status_code=201)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)

@auth_bp.function_name(name='refresh_token')
@auth_bp.route(route='refresh-token', methods=['POST'])
def refresh_token(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        token = data.get('refreshToken')
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
        return ResponseModel({'error': str(e)}, status_code=500)
