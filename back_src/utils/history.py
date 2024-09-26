import redis
import json
from configs.config import URLConfig
from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from . import SYSTEM_PROMPT

from loguru import logger


class ConversationHistory():
    def __init__(self, SESSION_ID):
        self.REDIS_CLIENT = redis.StrictRedis.from_url(URLConfig.REDIS_URL)
        self.SESSION_ID = SESSION_ID

    # 사용자 세션 번호에 따라 대화 저장
    def add_chat(self, message_dict):
        key = f"session:{self.SESSION_ID}:chats"
        message_json = json.dumps(message_dict, ensure_ascii=False)
        list_length = self.REDIS_CLIENT.llen(key)
        self.REDIS_CLIENT.rpush(key, message_json)
        # if list_length < 3:
        #     self.REDIS_CLIENT.rpush(key, message_json)
        # else:
        #     self.REDIS_CLIENT.lpop(key)  # 리스트의 왼쪽 첫 번째 요소를 제거
        #     self.REDIS_CLIENT.rpush(key, message_json)  # 새로운 요소를 오른쪽 끝에 추가

    def get_chats(self) -> List[Dict]:
        '''
            Des: 
                특정 세션의 대화 2개만 조회
                - 통계 추출 태스크에서 사용
                - 이전 대화 기반 요청문 수정
            Returns:
                chat : 이전 STATE(Dict 타입) 저장된 리스트 (대화, 쿼리 등)
        '''
        key = f"session:{self.SESSION_ID}:chats"
        chats = self.REDIS_CLIENT.lrange(key, 0, -1)  # 모든 대화 로드
        chats = [json.loads(chat.decode('utf-8'))
                 for chat in chats][-2:]  # 디코딩
        return chats

    def get_all_chats(self) -> List[Dict]:
        '''
            Des: 
                특정 세션의 대화 전체 조회
                - 통계 추출 태스크에서 사용
                - 이전 대화 기반 요청문 수정
            Returns:
                chat : 이전 STATE(Dict 타입) 저장된 리스트 (대화, 쿼리 등)
        '''
        key = f"session:{self.SESSION_ID}:chats"
        chats = self.REDIS_CLIENT.lrange(key, 0, -1)  # 모든 대화 로드
        chats = [json.loads(chat.decode('utf-8'))
                 for chat in chats]  # 디코딩
        return chats

    # 특정 세션의 대화 전체 삭제
    def delete_chats(self):
        key = f"session:{self.SESSION_ID}:chats"
        self.REDIS_CLIENT.delete(key)

    def get_history_chats(self) -> Optional[List[Dict[str, str]]]:
        '''
            Des: 
                특정 세션의 대화 조회후 멀티턴 포맷으로 변경 (user, assistant)
        '''
        PREVIOUS_CHATS = self.get_chats()
        if PREVIOUS_CHATS:
            self.CHATS = []
            for chat in PREVIOUS_CHATS[-2:]:
                # logger.warning(chat)
                if not (chat['user']['data'].startswith("Selected") or chat['user']['data'].startswith("File")):
                    self.CHATS.extend([{"role": "user", "content": chat['user']['data']},
                                       {"role": "assistant", "content": chat['assistant']['data']}])
        else:
            self.CHATS = []

    def get_histotry_format_prompt(self):
        '''
            Des: 
                특정 세션의 멀티턴 대화를 langchain_core.messages (SystemMessage,HumanMessage,AIMessage)로 변환
            Returns:
                chat : langchain_core.messages 포맷으로 변경된 리스트
        '''
        self.HISTORY = [SystemMessage(content=SYSTEM_PROMPT)]
        if self.CHATS:
            for chat in self.CHATS:
                if chat['role'] == "user":
                    self.HISTORY.append(HumanMessage(content=chat['content']))
                else:
                    self.HISTORY.append(AIMessage(content=chat['content']))
