from datetime import datetime
import uuid
import azure.functions as func
import base64

from models.Roles import Role
from models.User import User
from utils.blob_utils import list_files, upload_file, delete_blob
from utils.token_utils import validate_user_access
from models.ResponseModel import ResponseModel

files_bp = func.Blueprint()

def get_folder(class_code: str | None, user: User | None) -> str:
    if not user:
        raise Exception("Usuário não encontrado.")
    
    role = user.get("role")
    if not class_code:
        if role == "ADMIN":
            return "administrator"
        else:
            raise Exception("class_code é obrigatório.")
    return class_code

def transform_metadata(metadata: dict) -> dict:

    if not metadata:
        return {}
    return {
        "professor": metadata.get("professor"),
        "classCode": metadata.get("class_code"),
        "fileId": metadata.get("file_id"),
        "originalFileName": metadata.get("original_file_name")
    }

@files_bp.function_name(name="get_files")
@files_bp.route(route="files", methods=["GET"])
def get_files(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Recupera o parâmetro class_code da URL
        class_code = req.params.get("class_code")
        
        # Valida o acesso do usuário (aceitando ADMIN e TEACHER)
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        try:
            folder = get_folder(class_code, user)
        except Exception as e:
            return ResponseModel({"error": str(e)}, status_code=400)

        # Lista os blobs a partir do prefixo (pasta)
        blobs = list_files(prefix=folder + "/")
        files = []
        for blob in blobs:
            files.append({
                "name": blob.name,
                "size": blob.size,	
                "uploadedAt": blob.creation_time.isoformat() if blob.creation_time else None,
                "metadata": transform_metadata(blob.metadata)
            })

        return ResponseModel({"files": files}, status_code=200)
    except Exception as e:
        print(f"Erro ao listar arquivos: {str(e)}")
        return ResponseModel({"error": str(e)}, status_code=500)

@files_bp.function_name(name="upload_file")
@files_bp.route(route="files", methods=["POST"])
def upload_file_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Valida o acesso do usuário (permitindo ADMIN e TEACHER)
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user
        
        data = req.get_json()
        file_name = data.get("fileName")
        file_content_base64 = data.get("fileContent")
        class_code = data.get("class_code")

        if not file_name or not file_content_base64:
            return ResponseModel({"error": "fileName e fileContent são obrigatórios."}, status_code=400)

        # Decodifica o conteúdo do arquivo
        file_bytes = base64.b64decode(file_content_base64)

        try:
            folder = get_folder(class_code, user)
        except Exception as e:
            return ResponseModel({"error": str(e)}, status_code=400)

        file_id = str(uuid.uuid4())

        metadata = {
            "professor": user.get("email"),
            "class_code": folder,
            "file_id": file_id,
            "original_file_name": file_name
        }
        uploaded_blob_name = upload_file(folder, file_name, file_bytes, metadata)

        return ResponseModel({
            "message": "Arquivo enviado com sucesso.",
            "data": {
                "name": uploaded_blob_name,
                "size": len(file_bytes),
                "uploadedAt": datetime.now().isoformat(),
                "metadata": metadata,
            }
        }, status_code=201)
    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)

@files_bp.function_name(name="delete_file")
@files_bp.route(route="files", methods=["DELETE"])
def delete_file_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Valida o acesso do usuário (permitindo ADMIN e TEACHER)
        user = validate_user_access(req, allowed_roles=[Role.TEACHER, Role.ADMIN])
        if isinstance(user, ResponseModel):
            return user

        file_name = req.params.get("file_name")
        if not file_name:
            return ResponseModel({"error": "Nome do arquivo não especificado."}, status_code=400)

        file_id = req.params.get("file_id")
        if not file_id:
            return ResponseModel({"error": "Identificador do arquivo não encontrado nos metadados."}, status_code=400)

        delete_blob(file_name)

        from configs.settings import pinecone_client
        pinecone_client.delete_vectors_by_filter({"file_id": file_id})

        return ResponseModel({"message": "Arquivo e registros do Pinecone deletados com sucesso."}, status_code=200)
    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)
