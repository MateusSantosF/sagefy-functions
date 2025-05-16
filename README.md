# Sagefy Functions

Este projeto é uma coleção de Azure Functions desenvolvidas para processar arquivos de treinamento de dados brutos, extraindo seu conteúdo e gerando arquivos JSON padronizados. O objetivo principal é evitar a duplicação de conteúdo com a identificação única baseada no texto extraído.

## 🛠 Tecnologias Utilizadas

- **Python 3.11**
- **Azure Functions**: Plataforma serverless para executar funções sob demanda.
- **Azure Blob Storage**: Armazenamento para arquivos brutos e processados.
- **LangChain**: Utilizado para extração de conteúdo de arquivos PDF, DOCX e TXT.
- **hashlib**: Para gerar IDs únicos baseados no conteúdo dos arquivos.
- **re**: Biblioteca padrão para manipulação e normalização de texto.
- **azure-storage-blob**: Cliente Python para interação com Azure Blob Storage.

## 📂 Arquitetura de Pastas

```
sagefy-functions/
├── blueprints/
│   └── process_training_data_func.py  # Função principal para processar arquivos.
├── utils/
│   ├── file_processor.py              # Funções para extração de conteúdo dos arquivos.
│   ├── generate_unique_id.py                # Funções para gerar IDs únicos baseados no conteúdo.
│   └── openai_client.py                  # Funções para interação com a API do OpenAI.
|   └── pinecone_client.py               # Funções para interação com a API do Pinecone.
├── models/
│   └── DocumentMetadata.py               # Classe para representar metadados de documentos.
│   └── ExtractedContent.py               # Classe para representar conteúdo extraído de documentos.
├── configs/
│   └── settings.py               # Configurações do projeto.
├── constants.py                       # Contém as constantes do projeto (nomes dos containers, etc.).
├── requirements.txt                   # Dependências do projeto.
└── host.json                          # Configuração do Azure Functions host.
```

## 📚 Dependências

As principais bibliotecas utilizadas no projeto estão listadas abaixo e são instaladas via `requirements.txt`:

- `azure-functions`: SDK para criar Azure Functions.
- `azure-storage-blob`: Interação com Azure Blob Storage.
- `azure-data-tables`: Cliente Python para interação com o Azure Data Tables.
- `pinecone-client`: Cliente Python para interação com a API do Pinecone.	
- `openai`: Cliente Python para interação com a API do OpenAI.
- `langchain`: Para extração de texto de documentos.
- `bcrypt`: Biblioteca padrão para hashing.
- `pyjwt`: Para geração de tokens JWT.

## 🚀 Funcionalidades

1. **Processamento de Arquivos**:
   - Suporte a arquivos PDF, DOCX e TXT.
   - Extração de conteúdo usando LangChain.

2. **Identificação Única de Conteúdo**:
   - Geração de IDs únicos baseados no conteúdo dos arquivos.
   - Ignora arquivos duplicados durante o processamento.

## 📈 Variáveis de Ambiente

### Principais Variáveis Utilizadas

- **`FUNCTIONS_WORKER_RUNTIME`**: Define o runtime (Python).
- **`AZURE_STORAGE_CONNECTION_STRING`**: String de conexão para o Azure Blob Storage.
- **`PINECONE_API_KEY`**: Chave de autenticação para o Pinecone.
- **`PINECONE_INDEX_NAME`**: Nome do índice do Pinecone.
- **`AZURE_OPENAI_API_KEY`**: Chave da API do Azure OpenAI.
- **`AZURE_OPENAI_ENDPOINT`**: Endpoint da API do Azure OpenAI.
- **`AZURE_OPENAI_MODEL`**: Modelo utilizado (por exemplo, `gpt-4o-mini`).
- **`OPENAI_API_VERSION`**: Versão da API OpenAI.
- **`OPENAI_EMBEDDING_MODEL`**: Modelo de embedding para extração de texto.


## 🔧 Como Executar

### Pré-requisitos

1. **Instalar Azure Functions Core Tools**:
   - [Guia de instalação](https://learn.microsoft.com/azure/azure-functions/functions-run-local).

2. **Configurar Ambiente Virtual**:
   ```bash
   python -m venv env
   source env/bin/activate  # Linux/Mac
   env\Scripts\activate     # Windows
   ```

3. **Instalar Dependências**:
   ```bash
   pip install -r requirements.txt
   ```

### Executando Localmente

1. Iniciar o runtime local do Azure Functions:
   ```bash
   func start
   ```

2. Subir um arquivo para o container de origem no Blob Storage e observar o processamento.

### Executando testes

```bash
 python -m tests.test_chat_quality
 ```

### Como fazer deploy deploy

1. Execute o seguinte comando, substituindo `<APP_NAME>` pelo nome da sua aplicação no Azure:
   ```bash
   func azure functionapp publish <APP_NAME> --build local
   ```


## 📈 Logs e Monitoramento

- **Logging**:
  - Os logs são configurados usando a biblioteca de `logging` do Python.
  - Todas as operações de processamento, upload e deleção de arquivos são registradas.

- **Monitoramento no Azure**:
  - As métricas das funções podem ser monitoradas diretamente no portal do Azure.

## 🛡️ Tratamento de Erros

- Os erros durante o processamento são registrados nos logs.
- Se o processamento falhar, o blob original não é excluído.
- Mensagens de erro detalhadas ajudam a identificar falhas relacionadas a arquivos incompatíveis ou problemas de conexão.
