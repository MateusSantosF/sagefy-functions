from tests.setup_envs import load_local_settings
from tests.tests_case import TESTS_CASES
load_local_settings()

from configs.openai_client import AzureOpenAIClient
import os
import pandas as pd
import asyncio

from configs.system_prompt import DEFAULT_PROMPT
from configs.settings import vector_store
from azure.ai.evaluation import (
    AzureOpenAIModelConfiguration,
    IntentResolutionEvaluator,
    ResponseCompletenessEvaluator,
    TaskAdherenceEvaluator,
)

model_config = AzureOpenAIModelConfiguration(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["OPENAI_API_VERSION"],
    azure_deployment=os.environ["AZURE_OPENAI_MODEL"]
)

def save_with_excel_formatting(df):
    df = df.rename(columns={"query_id": "test_id"})  # Caso ainda esteja usando query_id
    ordered_cols = ["test_id", "intent_score", "completeness_score", "task_adherence_score", "query", "chatbot_response"]
    other_cols = [col for col in df.columns if col not in ordered_cols]
    df = df[ordered_cols + other_cols]

    # Gera Excel com formatação e tabela
    output_file = "test_results_azure_case_04_hybrid_approach_no_hyde.xlsx"
    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
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
    print(f"✅ Avaliação salva em '{output_file}'")

async def execute_test_case(query: str):
    embedding = AzureOpenAIClient.create_embedding(input_text=query)
    filters = {}  # ou setar class_code
    docs = vector_store.similarity_search_with_score_by_vector(embedding, k=8, filter=filters)
    used_documents = ",".join([f"{doc.metadata['file_id']}[{score:.4f}]" for doc, score in docs])

    # 3) Monta contexto e metadata
    context = [doc.page_content for doc, score in docs]

    # 4) Cria prompt final e chama chatbot
    assistant_prompt = (
        f"{DEFAULT_PROMPT}\nBaseado nas seguintes informações: {context}\n"
        f"Responda à seguinte pergunta: {query}"
    )
    assistant_response, raw = AzureOpenAIClient.create_completion(prompt=assistant_prompt)

    return assistant_response, used_documents

async def evaluate_with_azure():
    print("Iniciando avaliação com Azure...")
    intent_evaluator      = IntentResolutionEvaluator(model_config=model_config)
    completeness_evaluator = ResponseCompletenessEvaluator(model_config=model_config)
    adherence_evaluator    = TaskAdherenceEvaluator(model_config=model_config)

    results = []

    for idx, case in enumerate(TESTS_CASES, start=1):
        query_id = f"test_{idx}"
        query = case["query"]
        expected = case["expected_answer"]
        print(f"Avaliando teste: {query_id}")
        print(f"  Pergunta: {query}")

        # 1) executa chat
        response, used_docs = await execute_test_case(query)
        # 2) avalia via Azure
        intent  = intent_evaluator(query=query, response=response)
        completeness = completeness_evaluator(response=response, ground_truth=expected)
        adherence   = adherence_evaluator(query=query, response=response)

        # 3) coleta resultados
        results.append({
            "test_id": query_id,
            "query": query,
            "chatbot_response": response,
            "expected_answer": expected,
            "used_documents": used_docs,
            "intent_score": intent.get("intent_resolution"),
            "completeness_score": completeness.get("response_completeness"),
            "task_adherence_score": adherence.get("task_adherence"),
            "intent_explanation": intent.get("intent_resolution_reason"),
            "completeness_explanation": completeness.get("response_completeness_reason"),
            "task_adherence_explanation": adherence.get("task_adherence_reason"),
        })

    df = pd.DataFrame(results)
    save_with_excel_formatting(df)

if __name__ == "__main__":
    asyncio.run(evaluate_with_azure())
