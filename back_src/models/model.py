from configs.config import HFConfig, URLConfig, ModelConfig
from langchain.llms.huggingface_endpoint import HuggingFaceEndpoint
from langchain_community.chat_models.huggingface import ChatHuggingFace

# TODO : 민원대응 전용
# from langchain_huggingface.embeddings import HuggingFaceEmbeddings

# TODO : 민원대응 전용
# embedding_model = HuggingFaceEmbeddings(model_name=ModelConfig.EMBEDDING_MODEL_NAME)

# aya_llm_endpoint = HuggingFaceEndpoint(
#     endpoint_url=URLConfig.AYA_ENDPOINT_URL,
#     huggingfacehub_api_token=HFConfig.HF_API_TOKEN,
#     max_new_tokens=ModelConfig.MAX_NEW_TOKENS,
#     top_k=ModelConfig.TOP_K,
#     top_p=ModelConfig.TOP_P,
#     temperature=ModelConfig.TEMPERATURE,
#     repetition_penalty=ModelConfig.REPETATION_PENALTY,
#     model_kwargs={},
#     stop_sequences=["<|START_OF_TURN_TOKEN|>","<|CHATBOT_TOKEN|>","<|END_OF_TURN_TOKEN|>"]
# )
# aya_llm = ChatHuggingFace(
#     llm=aya_llm_endpoint,
#     model_id=ModelConfig.AYA_MODEL_NAME
# )

qwen_llm_endpoint = HuggingFaceEndpoint(
    endpoint_url=URLConfig.QWEN_ENDPOINT_URL,
    huggingfacehub_api_token=HFConfig.HF_API_TOKEN,
    max_new_tokens=ModelConfig.MAX_NEW_TOKENS,
    top_k=ModelConfig.TOP_K,
    top_p=ModelConfig.TOP_P,
    temperature=ModelConfig.TEMPERATURE,
    repetition_penalty=ModelConfig.REPETATION_PENALTY,
    model_kwargs={},
    stop_sequences=["<|im_end|>"]
)
qwen_llm = ChatHuggingFace(
    llm=qwen_llm_endpoint,
    model_id=ModelConfig.QWEN_MODEL_NAME
)
