from ml_collections import ConfigDict


UsedConfig = ConfigDict()
UsedConfig.MODEL = "CohereForAI/aya-23-35B"
UsedConfig.TOKENIZER = "CohereForAI/aya-23-35B"

IPConfig = ConfigDict()
IPConfig.H100_DGX = "http://192.168.1.20"
IPConfig.A100_DGX = "http://192.168.1.21"
IPConfig.H100_CLOUD_3 = "http://192.168.0.70"
IPConfig.REDIS = IPConfig.H100_DGX.replace("http://", "redis://")

PortConfig = ConfigDict()
PortConfig.MODEL_1 = "1330"
PortConfig.MODEL_2 = "1331"
PortConfig.MODEL_3 = "1315"
PortConfig.REDIS = "6379/0"
PortConfig.EMBEDDING = "11180"

ModelConfig = ConfigDict()
# ModelConfig.LLM_MODEL_NAME = "CohereForAI/aya-23-35B"
# ModelConfig.AYA_MODEL_NAME = "CohereForAI/aya-23-35B"
ModelConfig.QWEN_MODEL_NAME = "Qwen/Qwen2-72B-Instruct"
ModelConfig.EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"
# ModelConfig.RERANK_MODEL_NAME = "Dongjin-kr/ko-reranker"
ModelConfig.TOP_K = 1
ModelConfig.TOP_P = 0.001
ModelConfig.TEMPERATURE = 0.001
ModelConfig.MAX_NEW_TOKENS = 4096
ModelConfig.REPETATION_PENALTY = 1.03

HFConfig = ConfigDict()
HFConfig.HF_API_TOKEN = "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"

URLConfig = ConfigDict()
# URLConfig.LLM_ENDPOINT_URL = f"{IPConfig.H100_DGX}:{PortConfig.MODEL_1}"
# URLConfig.AYA_ENDPOINT_URL = f"{IPConfig.H100_DGX}:{PortConfig.MODEL_1}"
URLConfig.QWEN_ENDPOINT_URL = f"{IPConfig.H100_DGX}:{PortConfig.MODEL_1}"
URLConfig.REDIS_URL = f"{IPConfig.REDIS}:{PortConfig.REDIS}"

RetrieveConfig = ConfigDict()
RetrieveConfig.CHUNK_SIZE = 256
RetrieveConfig.SPACY_MODEL_NAME = "ko_core_news_sm"
RetrieveConfig.RELEVANT_STAGE_ONE_K = 20
RetrieveConfig.RELEVANT_CONVERSATION_K = 3
RetrieveConfig.RELEVANT_REFERENCE_THRESHOLD = 0.9
RetrieveConfig.RELEVANT_CONVERSATION_THRESHOLD = 0.7
