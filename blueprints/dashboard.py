import datetime
import json
import logging
from typing import List, Dict, Tuple, Any

import azure.functions as func
from azure.functions import HttpRequest

from configs.settings import metrics_client, dashboard_client, classes_client
from models.MetricsEntry import MetricsEntry
from models.DashboardEntry import DashboardEntry
from models.ResponseModel import ResponseModel
from models.Roles import Role
from utils.token_utils import validate_user_access

dashboard_bp = func.Blueprint()

def extract_insights(metrics: List[MetricsEntry]) -> Dict:
    """
    Extrai insights das métricas fornecidas (total de conversas, tokens, etc.).
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
    top_categories = ", ".join(
        [k for k, v in sorted(category_counts.items(), key=lambda item: item[1], reverse=True)[:15]]
    )
    top_subcategories = ", ".join(
        [k for k, v in sorted(subcategory_counts.items(), key=lambda item: item[1], reverse=True)[:15]]
    )

    return {
        "total_conversations": total_conversations,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "top_categories": top_categories,
        "top_subcategories": top_subcategories
    }

def get_top_students(metrics: List[MetricsEntry]) -> List[Dict[str, Any]]:
    """
    Retorna os 10 alunos com maior uso do chatbot.
    Aqui, cada métrica (linha) conta como 1 interação.
    """
    usage_counter = {}
    for metric in metrics:
        email = metric.get("user_email")
        if email:
            usage_counter[email] = usage_counter.get(email, 0) + 1

    # Ordenar do maior para o menor e pegar top 10
    sorted_usage = sorted(usage_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    top_students = []
    for email, count in sorted_usage:
        top_students.append({"email": email, "count": count})

    return top_students

def group_metrics_by_class_and_month(metrics: List[MetricsEntry]) -> Dict[Tuple[str, int, int], List[MetricsEntry]]:
    """
    Agrupa as métricas por (classCode, ano, mês).
    """
    grouped = {}
    for metric in metrics:
        class_code = metric.get("class_code", "unknown")

        # Tenta parsear a data/hora do timestamp da métrica
        # Ex.: "2024-07-28T12:34:56.123456"
        timestamp_str = metric.get("timestamp")
        if timestamp_str:
            try:
                dt = datetime.datetime.fromisoformat(timestamp_str)
            except ValueError:
                # Se falhar o parse, pode assumir data atual ou ignorar
                dt = datetime.datetime.utcnow()
        else:
            dt = datetime.datetime.utcnow()

        year = dt.year
        month = dt.month

        key = (class_code, year, month)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(metric)

    return grouped

def create_dashboard_entry(
    class_code: str,
    year: int,
    month: int,
    insights: Dict,
    top_students: List[Dict[str, Any]]
) -> DashboardEntry:
    """
    Cria uma entrada para a tabela de dashboard com dados mensais.
    A RowKey será YYYY-MM para facilitar a consulta por mês.
    """
    # YYYY-MM como RowKey
    row_key = f"{year:04d}-{month:02d}"

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
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "top_students": json.dumps(top_students)
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
    Agora, consolida as métricas mensalmente.
    """
    utc_timestamp = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.warning("A execução da função está atrasada!")

    logging.info(f"Função Timer Trigger iniciada em {utc_timestamp}")

    try:
        # 1. Recuperar todas as métricas
        metrics = fetch_all_metrics()
        if not metrics:
            logging.info("Nenhuma métrica para processar.")
            return

        # 2. Agrupar métricas por (classCode, ano, mês)
        grouped_metrics = group_metrics_by_class_and_month(metrics)

        # 3. Processar cada grupo e salvar no dashboard
        for (class_code, year, month), metrics_list in grouped_metrics.items():
            insights = extract_insights(metrics_list)
            top_students = get_top_students(metrics_list)
            dashboard_entry = create_dashboard_entry(class_code, year, month, insights, top_students)

            try:
                dashboard_client.create_entity(entity=dashboard_entry)
                logging.info(f"Resumo consolidado salvo para a classe {class_code} no período {year}-{month}.")

                # 4. Deletar as métricas processadas
                delete_processed_metrics(metrics_list)
                logging.info(f"Métricas processadas deletadas para a classe {class_code}, mês {month}/{year}.")
            except Exception as e:
                logging.error(f"Erro ao salvar resumo para a classe {class_code}, {year}-{month}: {str(e)}")

        logging.info("Processamento de métricas concluído com sucesso.")

    except Exception as e:
        logging.error(f"Erro na função Timer Trigger: {str(e)}")


@dashboard_bp.function_name(name="classes_dashboard")
@dashboard_bp.route(route="dashboard", methods=["GET"])
def get_dashboard_metrics(req: HttpRequest) -> func.HttpResponse:
    """
    Endpoint para listar métricas do dashboard. Tanto o professor quanto o admin
    devem conseguir retornar todas as turmas, porém com as restrições:
      - ADMIN: vê todas as turmas
      - PROFESSOR: vê apenas as turmas associadas a ele
    """
    try:
        # 1. Autenticar o usuário
        user = validate_user_access(req, allowed_roles=[Role.ADMIN, Role.TEACHER])
        if isinstance(user, ResponseModel):
            return user  # Se falhar, retorna a resposta de erro

        user_role = user.get("role")
        user_email = user.get("email")

        # 2. Obter todas as turmas que o usuário pode visualizar
        class_codes = []
        try:
            if user_role == Role.ADMIN.value:
                # ADMIN => todas as turmas
                classes_entities = classes_client.list_entities()
            else:
                # PROFESSOR => apenas as turmas onde professorID = professor_email
                filter_query = f"professorID eq '{user_email}'"
                classes_entities = classes_client.query_entities(query_filter=filter_query)

            for entity in classes_entities:
                # Ajuste conforme o nome do campo que guarda o classCode
                # Se for "PartitionKey" ou "RowKey", ou "classCode"
                code = entity.get("classCode")
                # ou code = entity["classCode"] caso tenha certeza do campo
                if code: 
                    class_codes.append(code)
        except Exception as e:
            return ResponseModel({"error": f"Erro ao consultar turmas: {str(e)}"}, status_code=500)

        # Se não achar nenhuma turma associada, retorna lista vazia
        if not class_codes:
            return ResponseModel({"metrics": []}, status_code=200)

        # 3. Buscar métricas de dashboard para cada turma encontrada
        #    Ex.: cada item no dashboard tem PartitionKey = classCode, RowKey = YYYY-MM, etc.
        all_metrics = {}
        for code in class_codes:
            try:
                # Filtra pela partição = classCode
                filter_query = f"PartitionKey eq '{code}'"
                dashboard_entities = dashboard_client.query_entities(query_filter=filter_query)
                
                # Convertemos para lista e armazenamos
                # se quiser, pode converter cada entity num dicionário limpinho
                metrics_list = []
                for entity in dashboard_entities:
                    metrics_list.append(entity)
                
                # Montar dict class_code => [todas as métricas encontradas]
                all_metrics[code] = metrics_list

            except Exception as e:
                logging.error(f"Erro ao recuperar métricas para a turma {code}: {str(e)}")
                # Pode optar por pular ou retornar erro. Aqui, vamos apenas pular.
                all_metrics[code] = []

        # 4. Retorna a resposta
        return ResponseModel({"metrics": all_metrics}, status_code=200)

    except Exception as e:
        return ResponseModel({"error": str(e)}, status_code=500)