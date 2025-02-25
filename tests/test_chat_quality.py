import asyncio
import nest_asyncio
import pandas as pd  # Importa o pandas

from tests.setup_envs import load_local_settings
load_local_settings()
nest_asyncio.apply()

from configs.settings import openai_client,openai_client_4o, pinecone_client, pinecone_index_name
from models.DocumentMetadata import DocumentMetadata
from ragchecker import RAGResults, RAGChecker
from ragchecker.metrics import all_metrics

# Lista de 10 casos de teste
TEST_CASES = [
    {
        "query": "Quais são os objetivos gerais e específicos do curso Técnico em Multimeios Didáticos EaD?",
        "expected_answer": "O curso tem como objetivo geral formar profissionais aptos a integrar tecnologias digitais à prática educativa, promovendo autonomia, engajamento e inovação. Entre os objetivos específicos, destacam-se a estruturação de uma arquitetura serverless para reduzir custos, a identificação dos principais questionamentos dos alunos e a integração de práticas que articulem ensino, pesquisa e extensão."
    },
    {
        "query": "Quais competências e habilidades o curso pretende desenvolver nos alunos?",
        "expected_answer": "O curso visa desenvolver competências técnicas (uso de ferramentas multimídia, design instrucional e produção audiovisual) e habilidades interpessoais (pensamento crítico, trabalho em equipe, comunicação eficaz e resolução de problemas), preparando os alunos para atuar de forma integrada no ambiente de ensino presencial e a distância."
    },
    {
        "query": "Como a utilização de Inteligência Artificial e o chatbot proposto no TCC contribuem para o suporte educacional?",
        "expected_answer": "A implementação de um tutor virtual baseado em IA permite respostas rápidas e personalizadas às dúvidas dos alunos, otimizando o suporte, reduzindo a evasão e permitindo que os docentes se concentrem em questões mais complexas. A ferramenta utiliza técnicas de Retrieval-Augmented Generation para recuperar informações relevantes do conteúdo do curso."
    },
    {
        "query": "Como o curso integra teoria e prática na sua estrutura curricular?",
        "expected_answer": "A estrutura curricular combina conteúdos teóricos com atividades práticas – como projetos integradores, oficinas, simulações e laboratórios – promovendo a aplicação dos conhecimentos adquiridos em situações reais e interdisciplinares, conforme previsto no PPC."
    },
    {
        "query": "Qual a importância do Projeto Integrador no desenvolvimento do estudante?",
        "expected_answer": "O Projeto Integrador é essencial, pois reúne os conhecimentos de diferentes disciplinas, incentivando a pesquisa, o trabalho em equipe e a resolução de problemas reais. Ele permite ao aluno consolidar o aprendizado, desenvolver competências práticas e estabelecer conexões entre teoria e mercado de trabalho."
    },
    {
        "query": "Como posso acessar o ambiente Moodle da disciplina e onde encontrar o link de acesso?",
        "expected_answer": "O acesso ao Moodle é realizado por meio da plataforma institucional do IFSP, geralmente disponível no portal oficial do campus ou enviado via e-mail institucional. Em caso de dúvidas, recomenda-se consultar o manual do ambiente virtual ou a equipe de TI responsável."
    },
    {
        "query": "Quais são os passos para realizar o envio de trabalhos através do Moodle?",
        "expected_answer": "Normalmente, o envio de trabalhos no Moodle envolve: acesso à sala de aula virtual, localização da atividade específica, upload do arquivo no formato requisitado e confirmação do envio, com a geração de um comprovante digital."
    },
    {
        "query": "Como funciona o processo de avaliação e feedback dos trabalhos submetidos?",
        "expected_answer": "Após o envio, os trabalhos são avaliados pelos docentes de acordo com os critérios estabelecidos no plano de ensino. O feedback é fornecido por meio de notas, comentários individuais e, ocasionalmente, avaliações coletivas em fóruns do Moodle."
    },
    {
        "query": "Quais recursos do Moodle auxiliam na organização das atividades e no acompanhamento do desempenho dos alunos?",
        "expected_answer": "O Moodle oferece funcionalidades como fóruns de discussão, chats, agendas, ferramentas de avaliação (tarefas, questionários e lições) e envio de mensagens, facilitando o acompanhamento do progresso e a interação entre alunos e professores."
    },
    {
        "query": "Onde posso encontrar manuais ou orientações para esclarecer dúvidas sobre o uso do ambiente virtual?",
        "expected_answer": "As orientações geralmente estão disponíveis na seção de suporte do portal institucional do IFSP ou diretamente no ambiente Moodle, através de tutoriais, FAQs e vídeos explicativos. A equipe de TI ou o setor de apoio ao discente também pode prestar suporte personalizado."
    }
]

# Prompt padrão
DEFAULT_PROMPT = (
    "Você é um assistente virtual especializado em responder perguntas sobre a disciplina de Multimeios Didáticos. "
    "Você pode fornecer informações sobre atualizações, notas, provas, lembretes e informações configuradas pelo professor.\n\n"
    "### Instruções:\n"
    "- Responda APENAS com base no contexto fornecido.\n"
    "- Responda apenas perguntas em português.\n"
    "- Não conte piadas.\n"
    "- NÃO forneça informações sobre assuntos fora da disciplina.\n\n"
)


def my_llm_api_func(prompts: list[str]) -> list[str]:
    """
    Recebe uma lista de prompts e retorna as respostas do LLM.
    Usa o openai_client para chamar a função create_completion.
    """
    responses = []
    for prompt in prompts:
        print(f"Chamando OpenAI com o prompt: {prompt}")
        response, _ = openai_client.create_completion(
            prompt=prompt,
            max_tokens=5000,
            temperature=0,
        )
        responses.append(response)
    return responses

def chat_flow(prompt: str) -> dict:
    """
    Executa o fluxo de chat:
      1. Gera um documento hipotético a partir da pergunta do usuário.
      2. Cria embedding e realiza busca vetorial para recuperar o contexto.
      3. Constrói o prompt final do assistente e gera a resposta.
    Retorna um dicionário contendo o prompt final, a resposta e o contexto recuperado.
    """
    # Geração do documento hipotético
    hypothetical_document, _ = openai_client.create_completion(
        prompt=f"{DEFAULT_PROMPT} Pergunta do usuário: {prompt}",
        max_tokens=400,
        temperature=0.7,
    )
    if not hypothetical_document:
        raise Exception("Falha ao gerar o documento hipotético.")

    # Geração do embedding e busca no Pinecone
    hypothetical_document_embedding = openai_client.create_embedding(input_text=hypothetical_document)
    result = pinecone_client.vector_search(index_name=pinecone_index_name, vector=hypothetical_document_embedding)
    matches = result.get("matches", [])  # type: ignore
    matches_metadata = [DocumentMetadata(**match["metadata"]) for match in matches if "metadata" in match]
    matched_texts = [match.text for match in matches_metadata]

    # Construção do prompt final para o assistente
    assistant_prompt = (
        f"{DEFAULT_PROMPT}\nBaseado nas seguintes informações: {matched_texts}\n"
        f"Por favor, responda à seguinte pergunta: {prompt}"
    )
    assistant_response, _ = openai_client.create_completion(
        prompt=assistant_prompt,
        max_tokens=5000,
        temperature=0.3,
    )

    return {
        "prompt": assistant_prompt,
        "response": assistant_response,
        "context": matched_texts,
    }

async def main():
    rag_results_list = []
    print("=== Resultados dos Casos de Teste ===\n")
    # Processa cada caso de teste
    for i, case in enumerate(TEST_CASES):
        print(f"Teste {i+1}:")
        print(f"Pergunta: {case['query']}")
        result = chat_flow(case["query"])
        print("Resposta da IA:")
        print(result["response"])
        print("-" * 50)
        
        print(result["context"])
        item = {
            "query_id": f"test_{i}",
            "query": case["query"],
            "gt_answer": case["expected_answer"],
            "response": result["response"],
            # Converter o contexto recuperado para uma string única
           "retrieved_context": [
                {"text": text, "doc_id": f"context_{i}"} for text in result["context"]
            ],
            "answer2response": None  # Campo reservado para avaliação adicional
        }
        rag_results_list.append(item)
    
    rag_results = RAGResults.from_dict({"results": rag_results_list})  # type: ignore
    
    evaluator = RAGChecker(
        custom_llm_api_func=my_llm_api_func,
        batch_size_extractor=32,
        batch_size_checker=32
    )
    evaluator.evaluate(rag_results, all_metrics)
    
    # Exibe os resultados agregados das métricas
    print("\n=== Métricas de Avaliação ===")
    print(rag_results)
    overall_metrics = rag_results.metrics.get("overall_metrics", {})
    generator_metrics = rag_results.metrics.get("generator_metrics", {})
    retriever_metrics = rag_results.metrics.get("retriever_metrics", {})

    print("Overall Metrics:", overall_metrics)
    print("Generator Metrics:", generator_metrics)
    print("Retriever Metrics:", retriever_metrics)
    
    # Converter os resultados dos casos de teste em um DataFrame
    df_resultados = pd.DataFrame(rag_results_list)
    
    # Converter as métricas em DataFrames (cada um com uma única linha)
    df_overall = pd.DataFrame([overall_metrics])
    df_generator = pd.DataFrame([generator_metrics])
    df_retriever = pd.DataFrame([retriever_metrics])
    
    # Salvar tudo em um arquivo Excel com múltiplas planilhas
    with pd.ExcelWriter("resultados_execucao_with_hyde_and_context.xlsx", engine="openpyxl") as writer:
        df_resultados.to_excel(writer, sheet_name="Resultados", index=False)
        df_overall.to_excel(writer, sheet_name="Overall Metrics", index=False)
        df_generator.to_excel(writer, sheet_name="Generator Metrics", index=False)
        df_retriever.to_excel(writer, sheet_name="Retriever Metrics", index=False)
    
    print("Resultados e métricas salvos em 'resultados_execucao_with_hyde_and_context.xlsx'.")

if __name__ == '__main__':
    asyncio.run(main())
