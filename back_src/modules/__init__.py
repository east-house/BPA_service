# from configs.profile import GetProfile
# import chainlit as cl
from configs.prompt import *
from utils.text_to_sql import *
from utils.util import *
from models.model import qwen_llm  # aya_llm
LLM = qwen_llm

# chat_profiles = GetProfile()
