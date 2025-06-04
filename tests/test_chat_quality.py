import asyncio
import os
import pandas as pd
from tests.setup_envs import load_local_settings
load_local_settings()
from blueprints.chat import core_agent_flow         
from azure.ai.evaluation import (
    AzureOpenAIModelConfiguration,
    IntentResolutionEvaluator,
    ResponseCompletenessEvaluator,
    TaskAdherenceEvaluator,
)
from tests.tests_case import TESTS_CASES

user = {
    "id": "teste_usuario_01",
    "name": "Usuário de Teste",
    "classCode": None   
}

model_config = AzureOpenAIModelConfiguration(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["OPENAI_API_VERSION"],
    azure_deployment=os.environ["AZURE_OPENAI_MODEL"]
)

async def execute_test_case(query: str):
    response, used_docs = core_agent_flow(user, query, log_usage=False)
    return response, used_docs

def save_with_excel_formatting(df: pd.DataFrame, file_name:str = "test_results.xlsx"):
    df = df.rename(columns={"query_id": "test_id"})  # Caso ainda esteja usando query_id
    ordered_cols = ["test_id", "intent_score", "completeness_score", "task_adherence_score", "query", "chatbot_response"]
    other_cols = [col for col in df.columns if col not in ordered_cols]
    df = df[ordered_cols + other_cols]

    with pd.ExcelWriter(file_name, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="results", index=False)
        workbook  = writer.book
        sheet     = writer.sheets["results"]

        # Formatação do cabeçalho
        header_fmt = workbook.add_format({ # type: ignore
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        for col_idx, col in enumerate(df.columns):
            sheet.write(0, col_idx, col, header_fmt)

        for col_idx, col in enumerate(df.columns):
            series = df[col].astype(str)
            if not series.empty:
                raw_max = series.map(len).max()
                try:
                    max_data_len = int(raw_max)
                except Exception:
                    max_data_len = int(raw_max.values[0]) if hasattr(raw_max, 'values') else 0 # type: ignore
            else:
                max_data_len = 0
            header_len = len(col)
            col_width = max(max_data_len, header_len) + 2
            sheet.set_column(col_idx, col_idx, col_width)

        max_row, max_col = df.shape
        last_col_letter = xl_col_to_name(max_col - 1) # type: ignore
        table_range = f"A1:{last_col_letter}{max_row+1}"
        sheet.add_table(table_range, {
            'columns': [{'header': hdr} for hdr in df.columns],
            'style': 'Table Style Medium 9'
        })
    print(f"✅ Avaliação salva em '{file_name}'")


async def main():
    print("🔎 Iniciando avaliação com Azure AI Evaluators...")
    results = []

    intent_evaluator = IntentResolutionEvaluator(model_config=model_config)
    completeness_evaluator = ResponseCompletenessEvaluator(model_config=model_config)
    adherence_evaluator = TaskAdherenceEvaluator(model_config=model_config)

    for idx, case in enumerate(TESTS_CASES, start=1):
        test_id = f"test_{idx}"
        query = case["query"]
        expected = case["expected_answer"]

        print(f"==========\nAvaliando {test_id}:\n  Pergunta: {query}")
        response, used_docs = await execute_test_case(query)
        intent_result = intent_evaluator(query=query, response=response)
        completeness_result = completeness_evaluator(response=response, ground_truth=expected)
        adherence_result = adherence_evaluator(query=query, response=response)

        # 4.2.3. Armazena no dicionário de resultados
        results.append({
            "test_id": test_id,
            "query": query,
            "expected_answer": expected,
            "chatbot_response": response,
            "used_documents": used_docs,
            "intent_score": intent_result.get("intent_resolution"),
            "intent_explanation": intent_result.get("intent_resolution_reason"),
            "completeness_score": completeness_result.get("response_completeness"),
            "completeness_explanation": completeness_result.get("response_completeness_reason"),
            "task_adherence_score": adherence_result.get("task_adherence"),
            "task_adherence_explanation": adherence_result.get("task_adherence_reason"),
        })

    df = pd.DataFrame(results)
    save_with_excel_formatting(df, "test_results_rag_hyde.xlsx")
    print("✅ Processo de avaliação concluído.")

if __name__ == "__main__":
    asyncio.run(main())
