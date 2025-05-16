import logging
from datetime import datetime, date
from typing import Dict, List, Any, Tuple
import uuid
import azure.functions as func
from sqlalchemy import select
from models.DatabaseModels import ClassModel, MetricsModel, DailyDashboardModel
from models.Roles import Role
from models.ResponseModel import ResponseModel
from utils.token_utils import validate_user_access
from utils.db_session import SessionLocal

# Blueprint
dashboard_bp = func.Blueprint()

def extract_insights(metrics: List[MetricsModel]) -> Dict[str, Any]:
    total_conversations = len(metrics)
    total_prompt_tokens = sum(m.prompt_tokens for m in metrics)
    total_completion_tokens = sum(m.completion_tokens for m in metrics)
    total_tokens = sum(m.total_tokens for m in metrics)

    category_counts: Dict[str, int] = {}
    subcategory_counts: Dict[str, int] = {}
    for m in metrics:
        if m.categories:
            for cat in m.categories.split(", "):
                category_counts[cat] = category_counts.get(cat, 0) + 1
        if m.subcategories:
            for sub in m.subcategories.split(", "):
                subcategory_counts[sub] = subcategory_counts.get(sub, 0) + 1

    top_categories = [k for k, _ in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    top_subcategories = [k for k, _ in sorted(subcategory_counts.items(), key=lambda x: x[1], reverse=True)[:10]]

    return {
        "total_conversations": total_conversations,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "top_categories": top_categories,
        "top_subcategories": top_subcategories,
    }


def get_top_students(metrics: List[MetricsModel]) -> List[Dict[str, Any]]:
    counter: Dict[str, int] = {}
    for m in metrics:
        email = m.user_email
        if email:
            counter[email] = counter.get(email, 0) + 1
    top = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:10]
    return [{"email": e, "count": c} for e, c in top]


@dashboard_bp.function_name(name="process_daily_dashboard")
@dashboard_bp.timer_trigger(schedule="0 */3 * * *", run_on_startup=True, arg_name="timer")
def process_daily_dashboard(timer: func.TimerRequest) -> None:
    logging.info("Iniciando consolidação diária de métricas...")
    try:
        db_session = SessionLocal()

        # Buscar todas as métricas ainda não consolidadas
        metrics = db_session.execute(select(MetricsModel)).scalars().all()
        if not metrics:
            logging.info("Nenhuma métrica para consolidar.")
            return

        # Agrupamento por (class_code, date)
        grouped: Dict[Tuple[str, date], List[MetricsModel]] = {}
        for m in metrics:
            cls = m.class_code or "unknown"
            d = m.timestamp.date()
            key = (cls, d)
            grouped.setdefault(key, []).append(m)

        # Para cada grupo, recalcular e salvar
        for (cls, d), mets in grouped.items():
            insights = extract_insights(mets)
            top_students = get_top_students(mets)
            # Remover entradas anteriores para esta classe e dia
            db_session.query(DailyDashboardModel).filter(
                DailyDashboardModel.class_code == cls,
                DailyDashboardModel.date == d
            ).delete()
            # Criar nova entrada
            entry = DailyDashboardModel(
                id=str(uuid.uuid4()),
                class_code=cls,
                date=d,
                total_conversations=insights["total_conversations"],
                total_prompt_tokens=insights["total_prompt_tokens"],
                total_completion_tokens=insights["total_completion_tokens"],
                total_tokens=insights["total_tokens"],
                top_categories=insights["top_categories"],
                top_subcategories=insights["top_subcategories"],
                top_students=top_students,
                updated_at=datetime.utcnow()
            )
            db_session.add(entry)
        db_session.commit()
        logging.info("Consolidação diária concluída com sucesso.")
    except Exception as e:
        db_session.rollback()
        logging.error(f"Erro na consolidação diária: {str(e)}")
    finally:
        db_session.close()


@dashboard_bp.function_name(name="get_dashboard")
@dashboard_bp.route(route="dashboard", methods=["GET"])
def get_dashboard(req: func.HttpRequest) -> func.HttpResponse:
    user = validate_user_access(req, allowed_roles=[Role.ADMIN, Role.TEACHER])
    if isinstance(user, ResponseModel):
        return user

    try:
        db_session = SessionLocal()

        # Lista de classes
        if user.get("role") == Role.ADMIN.value:
            classes = db_session.execute(select(ClassModel)).scalars().all()
        else:
            classes = db_session.execute(
                select(ClassModel).where(
                    ClassModel.teacher.has(email=user.get("email"))
                )
            ).scalars().all()
        class_codes = [c.class_code for c in classes]
        if not class_codes:
            return ResponseModel({"dashboard": {}}, status_code=200)

        # Recupera registros consolidados
        records = db_session.execute(
            select(DailyDashboardModel).where(
                DailyDashboardModel.class_code.in_(class_codes)
            )
        ).scalars().all()

        # Agrupa por classe
        dashboard: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            item: Dict[str, Any] = {
                "timestamp": r.date.isoformat(),
                "class_code": r.class_code,
                "total_conversations": r.total_conversations,
                "total_prompt_tokens": r.total_prompt_tokens,
                "total_completion_tokens": r.total_completion_tokens,
                "total_tokens": r.total_tokens,
                "top_categories": r.top_categories,
                "top_subcategories": r.top_subcategories,
                "top_students": r.top_students,
                "updated_at": r.updated_at.isoformat()
            }
            dashboard.setdefault(r.class_code, []).append(item)

        return ResponseModel({"metrics": dashboard}, status_code=200)
    except Exception as e:
        logging.error(f"Erro ao recuperar dashboard: {str(e)}")
        return ResponseModel({"error": str(e)}, status_code=500)
    finally:
        db_session.close()
