from utils.text_to_sql import *
from modules.chain import *
from modules.service import statistics_chain, harbor_chain
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import FastAPI, HTTPException, Request, status, Body, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from concurrent.futures import ThreadPoolExecutor
from starlette.responses import FileResponse
from utils.util import *
from utils.history import ConversationHistory
from loguru import logger
from typing import List
from jose import jwt

import argparse
import asyncio
import uvicorn
import uuid
import os

from utils.dummy_user import UserModule

from utils.sql_to_excel import ExcelTemplateApplier
from modules.node import SQLGenerator

userDB = UserModule()
extract_info = ExtractInfo()
extract_info.load_name_lst()

session_id = userDB.gen_session_id()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    return args


args = parse_args()
executor = ThreadPoolExecutor()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용. 필요에 따라 변경 가능
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)
app.mount("/exports", StaticFiles(directory="exports"), name="exports")
app.mount("/imports", StaticFiles(directory="imports"), name="imports")
# app.mount("/data", StaticFiles(directory="data"), name="data")


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc):
    return JSONResponse(
        content={
            "state": exc.status_code,
            "result": "",
            "message": exc.detail
        }
    )


@app.middleware("http")
async def add_executor_middleware(request: Request, call_next):
    '''
    reqeust를 받아서  프로세스를 비동기 처리함수로 전달
    '''
    user_token = request.headers.get('user-token')
    if user_token != None:  # 비로그인 사용자
        try:
            token_type, token = user_token.split()
            if token_type != "Bearer":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="The authentication method is incorrect.")
            user_data = jwt.decode(token, "default", algorithms=["HS256"])
        except Exception as e:
            logger.warning(f"error message : {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
        request.state.user_data = user_data
    request.state.executor = executor
    response = await call_next(request)
    return response


async def run_task_block(func, *args, **kwargs):
    '''
    미들웨어를 통화해 실행 요청이된 함수를 thread로 분산하여 비동기 처리
    함수 작성 예시
    @app.get("/task1/{seconds}")
    async def task1(seconds: int):
        result = await run_blocking_task([처리할 함수], [함수에 사용되는 변수1], [함수에 사용되는 변수2])
        return {"result": result}
    '''
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, func, *args, **kwargs)
    return result


@app.post("/test_chain_analysis")
async def _statistics_chain(
    # request: Request,
    input_data: str = Body(''),
    session_id: str = Body('tmp_session_id')
):
    category = 'statistics'
    message_id = str(uuid.uuid4())[:6]
    conv_history = ConversationHistory(session_id)
    # 사용자 문자 있는지 여부 확인
    if len(session_id.strip()) == 0:
        session_id = userDB.gen_session_id()
    # DB에 사용자 session_id 있는지 확인
    elif userDB.check_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is not exist..")
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)

    screen_type = '4'
    # 통계용 LLM chain
    response = statistics_chain(
        input_data, session_id, userDB, extract_info, message_id, screen_type)
    return StreamingResponse(response)


@app.post("/testchain")
async def _harbor_llm(
    request: Request,
    input_data: str = Body(''),
    session_id: str = Body('tmp_session_id')
) -> dict:
    '''
    항만데이터 분석 llm 추론
    '''
    category = 'analysis'
    message_id = str(uuid.uuid4())[:6]
    conv_history = ConversationHistory(session_id)
    response = userDB.set_btn_one(session_id, '포트미스 데이터 사용', category)
    # 사용자 문자 있는지 여부 확인
    if len(session_id.strip()) == 0:
        session_id = userDB.gen_session_id()
    # DB에 사용자 session_id 있는지 확인
    elif userDB.check_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is not exist..")
    # 유저 정보 들고옴
    user_info = userDB.get_user_info(session_id, category)
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)
    # 통계용 LLM을 이용한 대화
    screen_type = '3'
    # 통계용 LLM chain
    response = harbor_chain(input_data, session_id,
                            userDB, extract_info, message_id, screen_type)
    return StreamingResponse(response)
    ########################


@ app.post('/load_chat')
async def load_chat(
    request: Request,
    session_id: str = Body('tmp_session_id'),
) -> dict:
    '''
    새로고침 및 뒤로가기 사용시 현재 대화 불러오기\n
    session_id : 대화를 나타내는 객체 key 값
    '''
    category = "statistics"
    conv_history = ConversationHistory(session_id)
    previous_chats = conv_history.get_all_chats()
    logger.warning(f"previous_chats : {previous_chats}")
    chat_list = []
    for pre_chat in previous_chats:
        if pre_chat['user']['data'] != '':
            user_load_chat = pre_chat['user']
            user_load_chat['id'] = 'user'
            user_load_chat['session_id'] = session_id
            chat_list.append(user_load_chat)
        if pre_chat['assistant']['data'] != '':
            user_load_chat = pre_chat['assistant']
            user_load_chat['id'] = 'ai'
            user_load_chat['session_id'] = session_id
            chat_list.append(user_load_chat)
    return JSONResponse(
        content={
            "state": status.HTTP_200_OK,
            "result": chat_list,
            "message": "success"
        }
    )


@app.post("/statistics_btn_one")
async def statistics_btn_one(
    request: Request,
    session_id: str = Body('tmp_session_id'),
    click_value: str = Body('')
) -> dict:
    '''
    1) 회신양식 업로드 2) 회신양식 미업로드 중에서 선택
    통계 부분에서 사용되는 첫번째 버튼
    '''
    category = 'statistics'
    conv_history = ConversationHistory(session_id)
    response = userDB.set_btn_one(session_id, click_value, category)
    userDB.set_init(session_id, False, category)
    message_id = str(uuid.uuid4())[:6]
    # 회신양식 업로드
    pre_text = f'Selected : {click_value}'
    # debug part
    # user_info = userDB.get_user_info(session_id, category)
    # logger.warning(f"user_info : {user_info}")
    if response:
        screen_type = '2'
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": pre_text,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        data = f"{pre_text}\n 양식에 기재된 컬럼명들을 동일하게 사용하시겠습니까?"
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id,))
    else:
        screen_type = '4'
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": pre_text,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        # 통계용 LLM chain
        input_data = userDB.get_init_input(session_id, category)
        response = statistics_chain(
            input_data, session_id, userDB, extract_info, message_id, screen_type)
        return StreamingResponse(response)


@app.post("/statistics_btn_two")
async def statistics_btn_two(
    request: Request,
    session_id: str = Body('tmp_session_id'),
    click_value: str = Body('')
) -> dict:
    '''
    1) 회신양식 컬럼 사용 2) 인공지능 생성 컬럼 사용
    통계 부분에서 사용되는 두번째 버튼
    '''
    category = 'statistics'
    response = userDB.set_btn_two(session_id, click_value, category)
    message_id = str(uuid.uuid4())[:6]
    conv_history = ConversationHistory(session_id)
    chat_history = conv_history.get_all_chats()
    pre_data = chat_history[-1]['assistant']['data']
    if response:
        screen_type = '3'
        current_data = f'Selected : {click_value}'
        send_data = f"{pre_data}\n\n{current_data}"
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": current_data,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        return StreamingResponse(wrapped_string_generator(send_data, session_id, screen_type, message_id))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to save btn data to user information..")


@app.post("/upload_file")
async def upload_file(
    request: Request,
    files: List[UploadFile] = File(default=[]),
    session_id: str = Body('tmp_session_id')
) -> dict:
    '''
    # 파일 업로드
    단순 파일 업로드 xlsx 확장자만 가능하고 파일 갯수는 1개
    '''
    category = 'statistics'
    message_id = str(uuid.uuid4())[:6]
    conv_history = ConversationHistory(session_id)
    # 파일 갯수 체크
    if len(files) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Over file number..")
    # 파일 확장자 점검
    for fi in files:
        xlsx_path = check_save_xlsx(fi)
    file_name = os.path.basename(xlsx_path)

    chat_history = conv_history.get_all_chats()
    pre_data = f"{chat_history[-2]['assistant']['data']}\n\n{chat_history[-1]['assistant']['data']}"
    current_data = f'File: {file_name}'
    send_data = f'{pre_data}\n\n\{current_data}'
    response = userDB.set_filename(session_id, xlsx_path)
    if response:
        screen_type = '4'
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": current_data,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        # 통계용 LLM chain
        input_data = userDB.get_init_input(session_id, category)
        response = statistics_chain(
            input_data, session_id, userDB, extract_info, message_id, screen_type, file_name=send_data)
        return StreamingResponse(response)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to save file information to user information..")


@ app.post("/download_file")
async def download_file(
    request: Request,
    session_id: str = Body('tmp_session_id'),
    file_name: str = Body('')
) -> dict:
    '''
    # 파일 다운로드
    '''
    category = 'statistics'
    try:
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": f'/exports/SQL2Excel/{file_name}',
                "message": "success"
            }
        )
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="xlsx file is not exist..")


@app.post("/statistics_llm")
async def statistics_llm(
    request: Request,
    input_data: str = Body(''),
    session_id: str = Body('tmp_session_id'),
) -> dict:
    category = 'statistics'
    message_id = str(uuid.uuid4())[:6]
    conv_history = ConversationHistory(session_id)
    # 사용자 문자 있는지 여부 확인
    if len(session_id.strip()) == 0:
        session_id = userDB.gen_session_id()
    # DB에 사용자 session_id 있는지 확인
    elif userDB.check_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is not exist..")
    # 유저 정보 들고옴
    user_info = userDB.get_user_info(session_id, category)
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)
    if user_info['init']:  # 초기 대화 시작
        screen_type = '1'
        data = "회신 양식 업로드를 하시겠습니까?"
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": input_data,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id))
    else:  # 통계용 LLM을 이용한 대화
        screen_type = '4'
        # 통계용 LLM chain
        response = statistics_chain(
            input_data, session_id, userDB, extract_info, message_id, screen_type)
        return StreamingResponse(response)


@app.post("/harbor_btn_one")
async def harbor_btn_one(
    request: Request,
    click_value: str = Body(''),
    session_id: str = Body('tmp_session_id')
) -> dict:
    '''
    항만데이터분석 방법 선택 버튼1
    '''
    category = 'analysis'
    response = userDB.set_btn_one(session_id, click_value, category)
    userDB.set_init(session_id, False, category)
    conv_history = ConversationHistory(session_id)
    message_id = str(uuid.uuid4())[:6]
    pre_text = f'Selected : {click_value}'

    if response:
        screen_type = '3'
        # 초기 입력 데이터
        input_data = userDB.get_init_input(session_id, category)
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": pre_text,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        logger.warning(f"harbor_btn_one input_data : {input_data}")
        # 통계용 LLM chain
        response = harbor_chain(input_data, session_id,
                                userDB, extract_info, message_id, screen_type)
        return StreamingResponse(response)
    else:
        screen_type = '2'
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": pre_text,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        data = f"{pre_text}\n 웹검색 정보를 사용할까요?"
        logger.warning(f"harbor_btn_one data : {data}")
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id))


@app.post("/harbor_btn_two")
async def harbor_btn_two(
    request: Request,
    click_value: str = Body(''),
    session_id: str = Body('tmp_session_id')
) -> dict:
    '''
    항만데이터분석 방법 선택 버튼2
    '''
    category = 'analysis'
    response = userDB.set_btn_two(session_id, click_value, category)
    message_id = str(uuid.uuid4())[:6]
    screen_type = '3'
    conv_history = ConversationHistory(session_id)
    chat_history = conv_history.get_all_chats()
    logger.warning(f"chat_history : {chat_history}")
    pre_text = chat_history[-1]['assistant']['data']
    current_text = f'Selected : {click_value}'
    send_data = f"{pre_text}\n\n{current_text}"
    conv_history.add_chat(
        {
            "user": {
                "message_id": f"{message_id}_user",
                "data": "",
                "source": "",
                "type": screen_type,
                "plot": "",
                "relevant_query": "",
                "download": ""
            },
            "assistant": {
                "message_id": f"{message_id}_ai",
                "data": current_text,
                "source": "",
                "type": screen_type,
                "plot": "",
                "relevant_query": "",
                "download": ""
            }}
    )

    # 초기 입력 데이터
    input_data = userDB.get_init_input(session_id, category)
    # 통계용 LLM chain
    response = harbor_chain(input_data, session_id,
                            userDB, extract_info, message_id, screen_type, send_data)
    return StreamingResponse(response)


@app.post("/harbor_llm")
async def harbor_llm(
    request: Request,
    input_data: str = Body(''),
    session_id: str = Body('tmp_session_id')
) -> dict:
    '''
    항만데이터 분석 llm 추론 
    '''
    category = 'analysis'
    message_id = str(uuid.uuid4())[:6]
    conv_history = ConversationHistory(session_id)
    # 사용자 문자 있는지 여부 확인
    if len(session_id.strip()) == 0:
        session_id = userDB.gen_session_id()
    # DB에 사용자 session_id 있는지 확인
    elif userDB.check_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is not exist..")
    # 유저 정보 들고옴
    user_info = userDB.get_user_info(session_id, category)
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)
    if user_info['init']:  # 초기 대화 시작
        screen_type = '1'
        data = "포트미스 데이터를 사용하시겠습니까?"
        conv_history.add_chat(
            {
                "user": {
                    "message_id": f"{message_id}_user",
                    "data": input_data,
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                },
                "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": "",
                    "source": "",
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": "",
                    "download": ""
                }}
        )
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id))
    else:  # 통계용 LLM을 이용한 대화
        screen_type = '3'
        # 통계용 LLM chain
        response = harbor_chain(input_data, session_id,
                                userDB, extract_info, message_id, screen_type)
        return StreamingResponse(response)

if __name__ == "__main__":
    uvicorn.run("main:app", host=args.host,
                port=args.port, workers=1)
