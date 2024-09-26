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


@app.post("/testchain")
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
        input_data, session_id, userDB, extract_info, message_id)
    return StreamingResponse(response)


@app.post("/test_chain_analysis")
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
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)
    # 유저 정보 들고옴
    user_info = userDB.get_user_info(session_id, category)
    screen_type = '3'
    # 통계용 LLM chain
    response = harbor_chain(input_data, session_id,
                            userDB, extract_info, message_id)
    return StreamingResponse(response)

    ########################


# def general_answer_chain(prompt_state: dict, conv_history: ConversationHistory):
#     save_response = ''
#     for response in Chain__generate_general_answer.stream(prompt_state):
#         print("\033[38;5;12m" + response.content +
#               "\033[0m", end="", flush=True)
#         save_response += response.content
#         yield response.content
#     # ai 답변 등록
#     conv_history.add_chat(
#         {"user": prompt_state['CURRENT']['MESSAGE'],
#          "assistant": save_response}
#     )


# def web_search_and_answer_chain(prompt_state: dict, conv_history: ConversationHistory):
#     if conv_history.CHATS:
#         previous_message = conv_history.CHATS[-2]['content']
#         prompt_state['CURRENT']['PREVIOUS_MESSAGE'] = previous_message
#     else:
#         prompt_state['CURRENT']['PREVIOUS_MESSAGE'] = ""
#     # 검색 수행
#     query = Chain__generate_search_text.invoke(prompt_state).content.strip('"')
#     # logger.info(query)
#     documents = get_search_contents(query)
#     source = [{"title": i['title'], "href": i["href"]} for i in documents]
#     context = "# 참고내용\n" + \
#         '\n'.join(
#             [f"참고내용 ({idx+1}) 제목:{i['title']}\n참고내용 ({idx+1}) 본문:{i['body']}" for idx, i in enumerate(documents)])
#     # logger.info(self.CONTEXT)  # TODO : 향후 참고 출처가 들어가는 부문
#     # 사용자 질문 재수정 (검색한 내용과 검색어를 기반으로 답변하기 위함)
#     prompt_state["CURRENT"]["MESSAGE"] = copy.deepcopy(query)

#     # 컨텍스트 지정
#     prompt_state["CURRENT"]["CONTEXT"] = context

#     # 답변 생성
#     save_response = ''
#     for chunk in Chain__generate_answer_with_context.stream(prompt_state):
#         print("\033[38;5;12m" + chunk.content + "\033[0m", end="", flush=True)
#         save_response += chunk.content
#         yield chunk.content
#     # 대화 저장
#     conv_history.add_chat({"user": query,
#                            "assistant": save_response})


# def _analysis_chain(user_info: str, prompt_state: str, category: str, statistics_info: dict, conv_history: ConversationHistory):
#     excel_applier = ExcelTemplateApplier(
#         copy.deepcopy(prompt_state["CURRENT"]["MESSAGE"]))

#     sql_obj = SQLGenerator(
#         prompt_state["CURRENT"]["MESSAGE"],
#         extract_info,
#         excel_applier,
#         category)
#     # 데이터 베이스로부터 데이터 추출
#     sql_obj.STATE = {
#         "MESSAGE": prompt_state["CURRENT"]["MESSAGE"],
#         "PORT_DATA_LST": extract_info.PORT_NAME_LST,
#         "FAC_NAME_LST": extract_info.FAC_NAME_LST,
#         "COUNTRY_LIST": extract_info.COUNTRY_NAME_LST
#     }
#     sql_obj.USE_INFO = statistics_info
#     sql_obj.Node__extract_info()

#     # 최종 저장 객체
#     save_response = ''
#     relevant_response = ''
#     # SQL문 생성 chain 동작
#     response_init = '### SQL문 생성\n'
#     yield response_init
#     for response in sql_obj.Node__generate_sql():
#         save_response += response
#         yield response

#     while True:
#         logger.info("### SQL문 실행 유효성 검증")
#         yield "### SQL문 실행 유효성 검증\n"
#         sql_obj.Node__validate_query()
#         if not sql_obj.ERROR:
#             logger.info("### SQL문 피드백 생성")
#             yield "### SQL문 피드백 생성\n"
#             sql_obj.Node__feedback()
#             if sql_obj.RENERATE:
#                 logger.info("### 답변 재생성")
#                 yield "### 답변 재생성\n"
#                 for response in sql_obj.Node__regenerate():
#                     save_response += response
#                     yield response
#             else:
#                 yield "### 📢 답변이 양호합니다. 프로세스 종료합니다.\n"
#                 break
#         else:
#             logger.info("### SQL문 에러 처리")
#             yield "### SQL문 에러 처리"
#             for response in sql_obj.Node__handle_error():
#                 save_response += response
#                 yield response

#     '''
#         Des:
#             데이터 분석 수행
#     '''
#     analysis_df = sql_obj.Node__get_data_from_db()

#     analysis_df_markdown = analysis_df.to_markdown(index=False)

#     # 컨텍스트 지정 (1) 데이터프레임 정보 지정
#     prompt_state["CURRENT"]["DATAFRAME"] = analysis_df_markdown

#     # 컨텍스트 지정 (2) 통계정보 지정
#     try:
#         prompt_state["CURRENT"]["STATISTICS"] = analysis_df.groupby(analysis_df["년도"]).agg(
#             ['mean', 'min', 'max', 'median', 'sum']).drop('월', axis=1).to_markdown()
#     except:
#         prompt_state["CURRENT"]["STATISTICS"] = ''

#     # 분석 수행

#     for chunk in Chain__generate_analysis.stream(prompt_state):
#         save_response += chunk.content
#         relevant_response += chunk.content
#         yield chunk.content

#     # 대화 저장
#     # self.REVISED_ANSWER = f"실제 데이터 : {self.DF_MARKDOWN}\n답변 : {self.ANSWER}"
#     # self.CONV_OBJ.add_chat({"user": self.SQLOBJ.MESSAGE,
#     #                         "assistant": self.REVISED_ANSWER})

#     '''
#         Des:
#             시각화 수행
#     '''
#     # 시각화
#     if check_yes(Chain__check_plot.invoke(prompt_state).content) == "YES":
#         logger.info("### 시각화 결과 생성")
#         yield "### 시각화 결과 생성\n\n"
#         # plotly
#         try:
#             PLOTLY_ERROR_HANDLER = ''
#             while True:
#                 prompt_state["CURRENT"]["PLOTLY_ERROR_HANDLER"] = PLOTLY_ERROR_HANDLER
#                 gen_code = ""
#                 for chunk in Chain__generate_plotly.stream(prompt_state):
#                     # print("\033[38;5;12m" + chunk.content +
#                     #       "\033[0m", end="", flush=True)
#                     gen_code += chunk.content
#                     yield chunk.content
#                 extract_gen_code = extract_python_plotly_code(gen_code)
#                 try:
#                     global_vars = {"DF": analysis_df}
#                     local_vars = {}
#                     exec(extract_gen_code, global_vars, local_vars)
#                     break
#                 except Exception as error:
#                     logger.warning("생성된 시각화 코드에 오류가 있습니다. 오류 내용을 참고해서 재생성합니다.")
#                     PLOTLY_ERROR_HANDLER = f"\n이전 코드 실행시 오류가 발생했습니다.\n\n이전 코드 : {extract_gen_code}\n\n오류 내용 : {str(error)}\n\n오류 내용을 참고하세요."
#                     yield f"\n생성된 시각화 코드에 오류가 있습니다. 오류 내용을 참고해서 재생성합니다.\n"

#             fig = local_vars.get('fig')
#             from plotly import io as pio
#             content = pio.to_json(fig, validate=True)
#             yield content

#         except:
#             logger.warning("### 시각화하기에 데이터가 불충분합니다. (동적) 시각화 제외합니다.")

#     '''
#         Des:
#             관련/추천 질문 생성
#     '''
#     # 관련 질문 생성 (검색 기반 이전 대화 참고)
#     if user_info['btn1'] == "cancel":
#         relevant_queries = Chain__relevant_query_with_search.invoke({"MESSAGE": prompt_state["CURRENT"]["MESSAGE"],
#                                                                      "ANSWER": relevant_response}).content

#     # 관련 질문 생성 (데이터베이스 기반 이전 대화 참고)
#     else:
#         relevant_queries = Chain__relevant_query_with_database.invoke({"MESSAGE": prompt_state["CURRENT"]["MESSAGE"],
#                                                                        "ANSWER": relevant_response}).content
#     yield relevant_queries


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
    chat_list = []
    for pre_chat in previous_chats:
        if not (pre_chat['user'].startswith("Selected") or pre_chat['user'].startswith("File")):
            if pre_chat['user'] != '':
                chat_list.append({
                    'id': 'user',
                    'data': pre_chat['user'],
                    'session_id': session_id
                })
            if pre_chat['assistant'] != '':
                chat_list.append({
                    'id': 'ai',
                    'data': pre_chat['assistant'],
                    'session_id': session_id
                })
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
    # 회신양식 업로드
    pre_text = f'Selected : {click_value}'

    message_id = str(uuid.uuid4())[:6]
    # debug part
    user_info = userDB.get_user_info(session_id, category)
    logger.warning(f"user_info : {user_info}")
    if response:
        conv_history.add_chat(
            {"user": '',
             "assistant": pre_text}
        )
        screen_type = '2'
        data = f"{pre_text}\n 양식에 기재된 컬럼명들을 동일하게 사용하시겠습니까?"
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id))
    else:
        screen_type = '4'
        # 통계용 LLM chain
        input_data = userDB.get_init_input(session_id, category)
        response = statistics_chain(
            input_data, session_id, userDB, extract_info, message_id)
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
    pre_data = chat_history[-1]['assistant']
    if response:
        screen_type = '3'
        data = f'Selected : {click_value}'
        send_data = f"{pre_data}\n\n{data}"
        conv_history.add_chat(
            {"user": '',
             "assistant": data}
        )
        # user_info = userDB.get_user_info(session_id, category)
        # logger.warning(f"user_info : {user_info}")
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
    send_name = os.path.basename(xlsx_path)
    conv_history.add_chat(
        {"user": '',
         "assistant": f'File: {send_name}'}
    )
    response = userDB.set_filename(session_id, xlsx_path)
    if response:
        screen_type = '4'
        # 통계용 LLM chain
        input_data = userDB.get_init_input(session_id, category)
        response = statistics_chain(
            input_data, session_id, userDB, extract_info, message_id, file_name=send_name)
        return StreamingResponse(response)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to save file information to user information..")


@app.post("/download_file")
async def download_file(
    request: Request,
    session_id: str = Body('tmp_session_id')
) -> dict:
    '''
    # 파일 다운로드
    '''
    category = 'statistics'

    try:
        file_path = "exports/BPA_tmp_v1.xlsx"
        # fn = dummy_user['save_filename']
        # file_path = f"exports/{fn}"
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": f'/{file_path}',
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
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)
    # 유저 정보 들고옴
    user_info = userDB.get_user_info(session_id, category)
    if user_info['init']:  # 초기 대화 시작
        screen_type = '1'
        data = "회신 양식 업로드를 하시겠습니까?"
        conv_history.add_chat(
            {"user": input_data,
             "assistant": ''}
        )
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id))
    else:  # 통계용 LLM을 이용한 대화
        screen_type = '4'
        # 통계용 LLM chain
        response = statistics_chain(
            input_data, session_id, userDB, extract_info, message_id)
        return StreamingResponse(response)


@app.post("/harbor_btn_one")
async def harbor_btn_one(
    request: Request,
    click_value: str = Body(''),
    session_id: str = Body('')
) -> dict:
    '''
    항만데이터분석 방법 선택 버튼1
    '''
    category = 'analysis'
    response = userDB.set_btn_one(session_id, click_value, category)
    pre_text = f'Selected : {click_value}'
    if response:
        screen_type = '3'
        data = f"{pre_text}\n더미데이터 텍스트..."
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": {
                    "session_id": session_id,
                    "type": screen_type,
                    "source": [],
                    "data": data,
                    "plot": "",
                    "relevant_query": "",
                },
                "message": "success"
            }
        )
    else:
        screen_type = '2'
        data = f"{pre_text}\n 웹검색 정보를 사용할까요?"
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": {
                    "session_id": session_id,
                    "type": screen_type,
                    "source": [],
                    "data": data,
                    "plot": "",
                    "relevant_query": "",
                },
                "message": "success"
            }
        )


@app.post("/harbor_btn_two")
async def harbor_btn_two(
    request: Request,
    click_value: str = Body(''),
    session_id: str = Body('')
) -> dict:
    '''
    항만데이터분석 방법 선택 버튼2
    '''
    category = 'analysis'
    response = userDB.set_btn_one(session_id, click_value, category)

    screen_type = '3'
    data = f'Selected : {click_value}'
    userDB.set_history(session_id, data, category, role='ai')
    return JSONResponse(
        content={
            "state": status.HTTP_200_OK,
            "result": {
                "session_id": session_id,
                "type": screen_type,
                "source": [],
                "data": data,
                "plot": "",
                "relevant_query": "",
            },
            "message": "success"
        }
    )


@app.post("/analytest")
async def _analysis_llm(
    request: Request,
    input_data: str = Body(''),
    session_id: str = Body('tmp_session_id')
):
    '''
    항만데이터분석용 LLM 추론 함수
    args:
        input_data : 사용자 입력데이터
        session_id : 대화창 아이디
    '''
    category = 'analysis'
    # 사용자 정보 가져오기
    user_info = userDB.get_user_info(session_id, category)
    use_database = user_info['btn1']
    use_search = user_info['btn2']
    # 이전 대화들고오기
    conv_history = ConversationHistory(session_id)
    conv_history.get_history_chats()
    conv_history.get_histotry_format_prompt()
    prompt_state = {
        "CURRENT": {"MESSAGE": input_data},
        "HISTORY": conv_history.HISTORY
    }
    if not use_database:
        if not use_search:  # 일반 대화
            logger.warning(f"일반 대화")
            response = general_answer_chain(prompt_state, conv_history)
            return StreamingResponse(wrapped_event_generator(response, session_id))
        else:  # 웹정보 활용
            logger.warning(f"웹정보 활용")
            response = web_search_and_answer_chain(prompt_state, conv_history)
            return StreamingResponse(wrapped_event_generator(response, session_id))
    else:  # 내부 DB 사용
        logger.warning(f"내부 DB 사용")
        previous_chats = conv_history.get_chats()
        if previous_chats:
            message = Chain__rewrite_request.invoke({
                "PREV_MESSAGE": previous_chats[-1]["user"],
                "PREV_SQL": previous_chats[-1].get("SQL"),
                "MESSAGE": input_data
            }).content
        else:
            message = input_data
        info_check, response, analysis_info = check_chain(
            message, extract_info)

        if info_check:
            # analysis 생성 chain
            logger.warning(f"analysis 생성 chain")
            response = _analysis_chain(
                user_info, prompt_state, category, analysis_info, conv_history
            )
            conv_history.add_chat(
                {"user": input_data,
                 "assistant": 'response'}
            )
            return StreamingResponse(wrapped_event_generator(response, session_id))

            # response = 'analysis 생성 chain result'
            # return StreamingResponse(wrapped_string_generator(response, session_id))
        else:  # 정보부족
            # 항구정보, 시간 정보 점검 결과 반환
            logger.warning(f"항구정보, 시간 정보 점검 결과 반환")
            conv_history.add_chat(
                {"user": input_data,
                 "assistant": response}
            )
            return StreamingResponse(wrapped_string_generator(response, session_id))


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
    # 초기 질문 사용자 정보에 저장
    userDB.set_init_input(session_id, input_data, category)
    # 유저 정보 들고옴
    user_info = userDB.get_user_info(session_id, category)
    if user_info['init']:  # 초기 대화 시작
        screen_type = '1'
        data = "포트미스 데이터를 사용하시겠습니까?"
        conv_history.add_chat(
            {"user": input_data,
             "assistant": ''}
        )
        return StreamingResponse(wrapped_string_generator(data, session_id, screen_type, message_id))
    else:  # 통계용 LLM을 이용한 대화
        screen_type = '3'
        # 통계용 LLM chain
        response = harbor_chain(input_data, session_id,
                                userDB, extract_info, message_id)
        return StreamingResponse(response)

if __name__ == "__main__":
    uvicorn.run("main:app", host=args.host,
                port=args.port, workers=1)
