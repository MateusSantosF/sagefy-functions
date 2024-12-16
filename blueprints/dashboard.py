import datetime
import logging
from typing import List, Dict

import azure.functions as func
from azure.functions import HttpRequest

from configs.settings import metrics_client, dashboard_client
from models.MetricsEntry import MetricsEntry
from models.DashboardEntry import DashboardEntry
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.token_utils import validate_user_access

dashboard_bp = func.Blueprint()

def extract_insights(metrics: List[MetricsEntry]) -> Dict:
    """
    Extrai insights das métricas fornecidas.
    """
    total_conversations = len(metrics)
    total_prompt_tokens = sum(metric.get("prompt_tokens", 0) or 0 for metric in metrics)
    total_completion_tokens = sum(metric.get("completion_tokens", 0) or 0 for metric in metrics)
    total_tokens = sum(metric.get("total_tokens", 0) or 0 for metric in metrics)

    # Contagem de categorias e subcategorias
    category_counts = {}
    subcategory_counts = {}
    for metric in metrics:
        categories = metric.get("categories", "")
        subcategories = metric.get("subcategories", "")
        if categories:
            for cat in categories.split(", "):
                category_counts[cat] = category_counts.get(cat, 0) + 1
        if subcategories:
            for subcat in subcategories.split(", "):
                subcategory_counts[subcat] = subcategory_counts.get(subcat, 0) + 1

    # Obter as top 5 categorias e subcategorias
    top_categories = ", ".join([k for k, v in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)[:5]])
    top_subcategories = ", ".join([k for k, v in sorted(subcategory_counts.items(), key=lambda item: item[1], reverse=True)[:5]])

    return {
        "total_conversations": total_conversations,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "top_categories": top_categories,
        "top_subcategories": top_subcategories
    }

def group_metrics_by_class(metrics: List[MetricsEntry]) -> Dict[str, List[MetricsEntry]]:
    """
    Agrupa as métricas por classCode.
    """
    grouped = {}
    for metric in metrics:
        class_code = metric.get("class_code", 'unknown')
        if class_code not in grouped:
            grouped[class_code] = []
        grouped[class_code].append(metric)
    return grouped

def create_dashboard_entry(class_code: str, insights: Dict) -> DashboardEntry:
    """
    Cria uma entrada para a tabela de dashboard.
    """
    timestamp = datetime.datetime.utcnow().isoformat()
    row_key = timestamp  # Pode ajustar para incluir data e hora de forma mais legível

    dashboard_entry: DashboardEntry = {
        "PartitionKey": class_code,
        "RowKey": row_key,
        "class_code": class_code,
        "total_conversations": insights["total_conversations"],
        "total_prompt_tokens": insights["total_prompt_tokens"],
        "total_completion_tokens": insights["total_completion_tokens"],
        "total_tokens": insights["total_tokens"],
        "top_categories": insights["top_categories"],
        "top_subcategories": insights["top_subcategories"],
        "timestamp": timestamp
    }

    return dashboard_entry

def delete_processed_metrics(metrics: List[MetricsEntry]) -> None:
    """
    Deleta as métricas processadas da tabela de métricas.
    """
    for metric in metrics:
        try:
            metrics_client.delete_entity(
                partition_key=metric["PartitionKey"],
                row_key=metric["RowKey"]
            )
        except Exception as e:
            logging.error(f"Erro ao deletar métrica {metric['RowKey']}: {str(e)}")

def fetch_all_metrics() -> List[MetricsEntry]:
    """
    Recupera todas as métricas da tabela de métricas.
    """
    metrics = []
    try:
        entities = metrics_client.list_entities()
        for entity in entities:
            metrics.append(entity)
    except Exception as e:
        logging.error(f"Erro ao recuperar métricas: {str(e)}")
    return metrics

@dashboard_bp.function_name(name="process_metrics")
@dashboard_bp.timer_trigger(schedule="*/30 * * * *", run_on_startup=True, arg_name="mytimer")	
def main(mytimer: func.TimerRequest) -> None:
    """
    Função principal que é disparada a cada 30 minutos.
    """
    utc_timestamp = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.warning('A execução da função está atrasada!')

    logging.info(f'Função Timer Trigger iniciada em {utc_timestamp}')

    try:
        # 1. Recuperar todas as métricas
        metrics = fetch_all_metrics()
        if not metrics:
            logging.info("Nenhuma métrica para processar.")
            return

        # 2. Agrupar métricas por classCode
        grouped_metrics = group_metrics_by_class(metrics)

        # 3. Processar cada grupo e salvar no dashboard
        for class_code, metrics_list in grouped_metrics.items():
            insights = extract_insights(metrics_list)
            dashboard_entry = create_dashboard_entry(class_code, insights)

            try:
                dashboard_client.create_entity(entity=dashboard_entry)
                logging.info(f"Resumo consolidado salvo para a classe {class_code}.")

                # 4. Deletar as métricas processadas
                delete_processed_metrics(metrics_list)
                logging.info(f"Métricas processadas deletadas para a classe {class_code}.")
            except Exception as e:
                logging.error(f"Erro ao salvar resumo para a classe {class_code}: {str(e)}")

        logging.info("Processamento de métricas concluído com sucesso.")

    except Exception as e:
        logging.error(f"Erro na função Timer Trigger: {str(e)}")


@dashboard_bp.function_name(name="classes_dashboard")
@dashboard_bp.route(route="dashboard", methods=["GET"])
def get_dashboard_metrics(req: HttpRequest) -> func.HttpResponse:
    """
    Endpoint para listar métricas do dashboard de uma classe específica ou de todas as classes
    caso o usuário seja um administrador e o classCode esteja vazio.
    """
    try:
        # Autenticar o usuário e obter suas informações
        user = validate_user_access(req, allowed_roles=[Role.ADMIN, Role.TEACHER])
        if isinstance(user, ResponseModel):
            return user  # Retorna a resposta de erro se a autenticação falhar

        # Verifica o papel do usuário e o classCode associado
        user_role = user.get("role")
        class_code = user.get("classCode", None)

        # Administrador sem classCode, retorna todas as métricas
        if user_role == Role.ADMIN.value and not class_code:
            try:
                metrics = []
                entities = dashboard_client.list_entities()
                for entity in entities:
                    metrics.append(entity)
                return ResponseModel({"metrics": metrics}, status_code=200)
            except Exception as e:
                return ResponseModel({"error": f"Erro ao listar métricas consolidadas: {str(e)}"}, status_code=500)

        # Se for um professor ou admin com classCode, busca métricas da classe
        if not class_code:
            return ResponseModel({"error": "classCode é obrigatório para professores."}, status_code=400)

        try:
            # Filtrar métricas pela classCode
            filter_query = f"PartitionKey eq '{class_code}'"
            metrics = []
            entities = dashboard_client.query_entities(query_filter=filter_query)
            for entity in entities:
                metrics.append(entity)
        except Exception as e:
            return ResponseModel({"error": f"Erro ao recuperar métricas consolidadas: {str(e)}"}, status_code=500)

        # Retorna as métricas da classe
        return ResponseModel({"metrics": metrics}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)