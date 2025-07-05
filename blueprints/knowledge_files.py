from pathlib import Path
import re
import uuid
import base64
from datetime import datetime
import azure.functions as func
from sqlalchemy import select, text
from models.DatabaseModels import FileMeta
from models.Roles import Role
from models.ResponseModel import ResponseModel
from utils.token_utils import validate_user_access
from utils.blob_utils import upload_file, delete_blob
from utils.db_session import SessionLocal

files_bp = func.Blueprint()

def get_folder(class_code: str | None, user: dict) -> str:
    if not user:
        raise Exception("Usuário não encontrado.")
    role = user.get("role")
    if not class_code:
        if role == Role.ADMIN.value:
            return "administrator"
        else:
            raise Exception("class_code é obrigatório.")
    return class_code

@files_bp.function_name(name="get_files")
@files_bp.route(route="files", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_files(req: func.HttpRequest) -> func.HttpResponse:
    try:
        class_code = req.params.get("class_code")
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user
        
        if user.get("role") == Role.ADMIN.value:
            class_code = "admin"

        folder = get_folder(class_code, user)
        # Consulta FileMeta no Postgres
        stmt = select(FileMeta).where(
            FileMeta.class_code == folder
        )
        db_session = SessionLocal()
        files = db_session.execute(stmt).scalars().all()

        result = []
        for f in files:
            item = {
                'id': f.file_id,
                'name': f.blob_name,
                'uploadedAt': f.uploaded_at.isoformat(),
                'metadata': f.blob_metadata
            }
            result.append(item)

        return ResponseModel({'files': result}, status_code=200)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)

@files_bp.function_name(name="upload_file")
@files_bp.route(route="files", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upload_file_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    try:
        db_session = SessionLocal()
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        data = req.get_json()
        file_name = data.get('fileName')
        ext = Path(file_name).suffix.lower()

        content_b64 = data.get('fileContent')
        class_code = data.get('class_code')
        if not file_name or not content_b64:
            return ResponseModel({'error': 'fileName e fileContent são obrigatórios.'}, status_code=400)
        
        if user.get("role") == Role.ADMIN.value:
            class_code = "admin"

        file_bytes = base64.b64decode(content_b64)
        folder = get_folder(class_code, user)
        blob_id = f"{str(uuid.uuid4())}{ext}"

        def clean_metadata_value(value: str) -> str:
            # Remove caracteres que não são letras, números, hífen ou underline
            return re.sub(r"[^a-zA-Z0-9_.-]", "_", value)

        metadata = {
            'file_id': clean_metadata_value(blob_id),
            'original_name': clean_metadata_value(file_name),
            'uploaded_by': clean_metadata_value(user.get('email')),
            'class_code': clean_metadata_value(folder)
        }

        blob_name = upload_file(folder, blob_id, file_bytes, metadata)

        # Salva metadata no Postgres em FileMeta
        file_record = FileMeta(
            file_id=blob_id,
            class_code= class_code,
            blob_name=blob_name,
            blob_metadata=metadata,
            uploaded_at=datetime.utcnow()
        )
        db_session.add(file_record)
        db_session.commit()
        db_session.close()

        return ResponseModel({
            'message': 'Arquivo enviado com sucesso.',
            'data': metadata
        }, status_code=201)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)

@files_bp.function_name(name="delete_file")
@files_bp.route(route="files", methods=["DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
def delete_file_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    try:
        db_session = SessionLocal()
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        file_id = req.params.get('file_id')
        if not file_id:
            return ResponseModel({'error': 'file_id é obrigatório.'}, status_code=400)

        stmt = select(FileMeta).where(FileMeta.file_id == file_id)
        file_rec = db_session.execute(stmt).scalar_one_or_none()
        if not file_rec:
            db_session.close()
            return ResponseModel({'error': 'Arquivo não encontrado.'}, status_code=404)

        # Deleta blob
        delete_blob(file_rec.blob_name)
        # Remove do vector store
        db_session.execute(
            text("DELETE FROM langchain_pg_embedding WHERE cmetadata->>'file_id' = :file_id"),
            {"file_id": file_id}
        )
        # Remove metadata do Postgres
        db_session.delete(file_rec)
        db_session.commit()
        db_session.close()

        return ResponseModel({'message': 'Arquivo removido com sucesso.'}, status_code=200)
    except Exception as e:
        return ResponseModel({'error': str(e)}, status_code=500)
