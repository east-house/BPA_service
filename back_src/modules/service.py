from utils.text_to_sql import *
from modules.chain import *
from modules.node import SQLGenerator
from utils.sql_to_excel import ExcelTemplateApplier
from utils.history import ConversationHistory
from utils.util import check_yes, wrapped_string_generator, wrapped_event
from utils.search import get_search_contents
from loguru import logger


def check_chain(input_data: str, extract_info: ExtractInfo, userDB: dict, session_id: str, category):
    '''
    입력 텍스트에 항구정보, 시간 정보가 있는지 확인하는 chain

    message : 사용자 입력 문장 / 이전대화 있을 경우 Chain__rewrite_request 으로 변경해서 적용
    extract_info : 항만기본 정보 class
    '''
    logger.warning(f"input_data :{input_data}")
    userDB.add_init_input(session_id, input_data, category)
    input_prompt = userDB.get_init_input(session_id, category)
    logger.warning(f"input_prompt :{input_prompt}")
    state = {
        "MESSAGE": input_prompt,
        "PORT_DATA_LST": extract_info.PORT_NAME_LST,
        "FAC_NAME_LST": extract_info.FAC_NAME_LST,
        "COUNTRY_LIST": extract_info.COUNTRY_NAME_LST
    }
    # logger.warning(f"state : {state}")
    user_info = {"USE_PORT": check_yes(Chain__check_port.invoke(state).content),
                 "USE_TIME": check_yes(Chain__check_time.invoke(state).content)}
    # return info_check, response
    error_messages = {"USE_PORT": "⛔ 항구 정보가 없습니다. 값을 정확히 기입해주세요. 예:부산항",
                      "USE_TIME": "⛔ 시간 정보가 없습니다. 값을 정확히 기입해주세요. 예:최근 2년간, 2020~2022 동안"}
    for key, error_message in error_messages.items():
        if user_info.get(key) != "YES":
            # logger.warning(error_message)
            # userDB.add_init_input(session_id, input_data, category)
            return False, error_message, user_info
    return True, '', user_info


def sql_chain(
        userDB: dict, session_id: str, input_data: str, input_prompt: str, category: str,
        statistics_info: dict, extract_info: dict, conv_history, message_id: str,
        screen_type: str, file_name: str = ''):
    '''
    입력 텍스트에 대한 sql 생성 chain

    user_info : dummy_user의 정보
    message : 이전 대화 내용 + 사용자 입력 데이터 또는 사용자 입력 데이터
    category : 대화 종류
    input_data: 직전 사용자가 입력한 텍스트
    input_prompt: 사용자 입력 + 항구 + 시간정보
    '''
    # 일반 체인
    user_info = userDB.get_user_info(session_id, category)
    template_upload = user_info['btn1']
    use_template_cols = user_info['btn2']
    # 입력 데이터 prompt를 위한 class 모듈화
    excel_applier = ExcelTemplateApplier(copy.deepcopy(input_prompt))
    # 프롬프트 유형 선택 반영
    if template_upload:  # temp : True
        excel_path = user_info['upload']
        logger.warning(f"excel_path : {excel_path}")
        if use_template_cols:  # temp : True / use : False
            excel_applier.yes_template_common_parts(excel_path)
        else:  # temp: True / use : False
            excel_applier.yes_template_common_parts(excel_path)
            excel_applier.COLS = []
    else:  # temp: False
        pass
    # 체인 정의
    sql_obj = SQLGenerator(
        input_prompt,
        extract_info,
        excel_applier,
        category)
    # 데이터 베이스로부터 데이터 추출
    sql_obj.STATE = {
        "MESSAGE": input_prompt,
        "PORT_DATA_LST": extract_info.PORT_NAME_LST,
        "FAC_NAME_LST": extract_info.FAC_NAME_LST,
        "COUNTRY_LIST": extract_info.COUNTRY_NAME_LST
    }
    sql_obj.USE_INFO = statistics_info
    sql_obj.Node__extract_info()

    # SQL문 생성 chain 동작
    save_response = ''
    response_init = '\n### SQL문 생성\n'
    save_response += response_init
    logger.warning(f"file_name : {file_name}")
    if len(file_name) != 0:
        yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=file_name)
    yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=response_init, )
    for response in sql_obj.Node__generate_sql():
        save_response += response
        yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=response)

    while True:
        save_response += "\n\n### SQL문 실행 유효성 검증\n"
        yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data="\n\n### SQL문 실행 유효성 검증\n")

        sql_obj.Node__validate_query()
        if not sql_obj.ERROR:
            logger.info("### SQL문 피드백 생성")
            save_response += "\n\n### SQL문 피드백 생성\n"
            yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data="\n\n### SQL문 피드백 생성\n")
            sql_obj.Node__feedback()
            if sql_obj.RENERATE:
                logger.info("### 답변 재생성")
                save_response += "### 답변 재생성\n"
                yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data="### 답변 재생성\n")
                for response in sql_obj.Node__regenerate():
                    save_response += response
                    yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=response)
            else:
                save_response += "\n### 📢 답변이 양호합니다. 프로세스 종료합니다.\n"
                yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data="\n### 📢 답변이 양호합니다. 프로세스 종료합니다.\n")
                break
        else:
            logger.info("### SQL문 에러 처리\n")
            save_response += "\n### SQL문 에러 처리\n"
            yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data="\n### SQL문 에러 처리")
            for response in sql_obj.Node__handle_error():
                save_response += response
                yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=response)

    excel_df = sql_obj.Node__get_data_from_db()
    # 추출된 데이터가 없을 경우
    if len(excel_df) == 0:
        save_response += "\n ### 조건을 만족하는 데이터가 없습니다.\n"
        yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data="\n ### 조건을 만족하는 데이터가 없습니다.\n")
    else:
        save_response += f"{format_number(len(excel_df))}개의 데이터가 존재합니다.\n\n아래는 추출한 데이터 목록 일부입니다.\n"
        yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=f"{format_number(len(excel_df))}개의 데이터가 존재합니다.\n\n아래는 추출한 데이터 목록 일부입니다.\n")
        # 엑셀 적용
        excel_applier.apply_format(excel_df)
        excel_applier.set_data()
        excel_applier.set_time_and_path(datetime.now())
        excel_applier.extract_common_parts()

        # 회신 양식 업로드
        if template_upload == "continue":
            if use_template_cols == "continue":
                save_path = excel_applier.yes_template_with_template_cols()
            # 인공지능이 생성한 컬럼 사용
            elif use_template_cols == "cancel":
                save_path = excel_applier.yes_template_with_llm_cols()
        # 회신 양식 미업로드
        else:
            save_path = excel_applier.no_template()
        userDB.set_download_fn(session_id, category, save_path)

        check_number = len(excel_df.head(
            2).to_markdown(index=False).split(" "))
        for idx, part in enumerate(excel_df.head(2).to_markdown(index=False).split(" ")):
            if check_number == (idx+1):
                save_response += part
                yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=part, download=os.path.basename(save_path))
            else:
                save_response += part
                yield wrapped_event(message_id=message_id, session_id=session_id, type='4', data=part)
        # 첫 질문 사용자 정보 초기화
        userDB.set_init_input(session_id, '', category)
        conv_history.add_chat(
            {"user": {
                "message_id": f"{message_id}_user",
                "data": input_data,
                "source": [],
                "type": screen_type,
                "plot": "",
                "relevant_query": [],
                "download": ""
            },
                "assistant": {
                "message_id": f"{message_id}_ai",
                "data": save_response,
                "source": [],
                "type": screen_type,
                "plot": "",
                "relevant_query": [],
                "download": os.path.basename(save_path)
            }}
        )


def statistics_chain(
    input_data: str,
    session_id: str,
    userDB: dict,
    extract_info: dict,
    message_id: str,
    screen_type: str,
    file_name: str = ''
):
    category = 'statistics'
    # 대화 이력 들고오기
    conv_history = ConversationHistory(session_id)

    # 초기 입력 데이터
    input_prompt = userDB.get_init_input(session_id, category)
    # 항구정보, 시간 정보 점검 chain
    if input_prompt == input_data:
        input_data = ''
    # 항구정보, 시간 정보 점검 chain
    info_check, response, statistics_info = check_chain(
        input_data, extract_info, userDB, session_id, category)
    response_form = response
    if len(file_name) != 0:
        response_form = [file_name, response]
    # logger.warning(f"response_form :{response_form}")
    if info_check:
        # SQL 생성 chain
        input_prompt = userDB.get_init_input(session_id, category)
        logger.warning(f"input_prompt :{input_prompt}")
        response = sql_chain(
            userDB, session_id, input_data, input_prompt, category,
            statistics_info, extract_info, conv_history, message_id,
            screen_type, file_name
        )
        # user init 초기화
        userDB.set_init(session_id, True, category)
        return response
    else:  # 정보부족
        # 항구정보, 시간 정보 점검 결과 반환
        conv_history.add_chat(
            {"user": {
                "message_id": f"{message_id}_user",
                "data": input_data,
                "source": [],
                "type": screen_type,
                "plot": "",
                "relevant_query": [],
                "download": ""
            },
                "assistant": {
                "message_id": f"{message_id}_ai",
                    "data": response,
                    "source": [],
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": [],
                    "download": ""
            }}
        )
        return wrapped_string_generator(response_form, session_id, type=screen_type, message_id=message_id)


def general_answer_chain(
        prompt_state: dict, conv_history: ConversationHistory, session_id: str,
        message_id: str, screen_type: str, userDB: dict, send_data: str
):
    save_response = ''
    category = 'analysis'
    init_input_data = prompt_state["CURRENT"]["MESSAGE"]
    for token in send_data.split():
        yield wrapped_event(message_id=message_id, session_id=session_id, type=screen_type, data=token)
    for response in Chain__generate_general_answer.stream(prompt_state):
        save_response += response.content
        yield wrapped_event(message_id=message_id, session_id=session_id, type=screen_type, data=response.content)
    userDB.set_init_input(session_id, '', category)
    # ai 답변 등록
    conv_history.add_chat(
        {"user": {
            "message_id": f"{message_id}_user",
            "data": '',
            "source": [],
            "type": screen_type,
            "plot": "",
            "relevant_query": [],
            "download": ""
        },
            "assistant": {
            "message_id": f"{message_id}_ai",
            "data": save_response,
            "source": [],
            "type": screen_type,
            "plot": "",
            "relevant_query": [],
            "download": ""
        }}
    )


def web_search_and_answer_chain(
        prompt_state: dict, conv_history: ConversationHistory, session_id: str,
        message_id: str, screen_type: str, userDB: dict, send_data: str
):
    category = 'analysis'
    init_input_data = prompt_state["CURRENT"]["MESSAGE"]
    if conv_history.CHATS:
        previous_message = conv_history.CHATS[-2]['content']
        prompt_state['CURRENT']['PREVIOUS_MESSAGE'] = previous_message
    else:
        prompt_state['CURRENT']['PREVIOUS_MESSAGE'] = ""
    # 이전 선택 결과 보내기
    for token in send_data.split():
        yield wrapped_event(message_id=message_id, session_id=session_id, type=screen_type, data=token)
    # 검색 수행
    query = Chain__generate_search_text.invoke(prompt_state).content.strip('"')
    # logger.info(query)
    documents = get_search_contents(query)
    source = [{"title": i['title'], "href": i["href"]} for i in documents]
    yield wrapped_event(message_id=message_id, session_id=session_id, type='3', source=source)
    context = "# 참고내용\n" + \
        '\n'.join(
            [f"참고내용 ({idx+1}) 제목:{i['title']}\n참고내용 ({idx+1}) 본문:{i['body']}" for idx, i in enumerate(documents)])
    # logger.info(self.CONTEXT)  # TODO : 향후 참고 출처가 들어가는 부문
    # 사용자 질문 재수정 (검색한 내용과 검색어를 기반으로 답변하기 위함)
    prompt_state["CURRENT"]["MESSAGE"] = copy.deepcopy(query)
    # 컨텍스트 지정
    prompt_state["CURRENT"]["CONTEXT"] = context

    # 답변 생성
    save_response = ''
    for chunk in Chain__generate_answer_with_context.stream(prompt_state):
        # print("\033[38;5;12m" + chunk.content + "\033[0m", end="", flush=True)
        save_response += chunk.content
        yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=chunk.content)
    # 대화 저장
    userDB.set_init_input(session_id, '', category)
    conv_history.add_chat(
        {"user": {
            "message_id": f"{message_id}_user",
            "data": '',
            "source": [],
            "type": screen_type,
            "plot": "",
            "relevant_query": [],
            "download": ""
        },
            "assistant": {
            "message_id": f"{message_id}_ai",
            "data": save_response,
            "source": source,
            "type": screen_type,
            "plot": "",
            "relevant_query": [],
            "download": ""
        }}
    )


def analysis_chain(
        userDB: dict, input_data: str, prompt_state: str, category: str,
        extract_info: dict, statistics_info: dict, session_id: str,
        message_id: str, conv_history: dict, screen_type: str):
    user_info = userDB.get_user_info(session_id, category)
    excel_applier = ExcelTemplateApplier(
        copy.deepcopy(prompt_state["CURRENT"]["MESSAGE"]))

    sql_obj = SQLGenerator(
        prompt_state["CURRENT"]["MESSAGE"],
        extract_info,
        excel_applier,
        category)
    # 데이터 베이스로부터 데이터 추출
    sql_obj.STATE = {
        "MESSAGE": prompt_state["CURRENT"]["MESSAGE"],
        "PORT_DATA_LST": extract_info.PORT_NAME_LST,
        "FAC_NAME_LST": extract_info.FAC_NAME_LST,
        "COUNTRY_LIST": extract_info.COUNTRY_NAME_LST
    }
    sql_obj.USE_INFO = statistics_info
    sql_obj.Node__extract_info()

    # 최종 저장 객체
    save_response = ''
    relevant_response = ''

    # SQL문 생성 chain 동작
    response_init = '### SQL문 생성\n'
    save_response += response_init
    yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=response_init)
    for response in sql_obj.Node__generate_sql():
        save_response += response
        yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=response)

    while True:
        logger.info("### SQL문 실행 유효성 검증")
        yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="### SQL문 실행 유효성 검증")
        sql_obj.Node__validate_query()
        if not sql_obj.ERROR:
            logger.info("### SQL문 피드백 생성")
            yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="### SQL문 피드백 생성\n")
            sql_obj.Node__feedback()
            if sql_obj.RENERATE:
                logger.info("### 답변 재생성")
                yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="### 답변 재생성\n")
                for response in sql_obj.Node__regenerate():
                    save_response += response
                    yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=response)

            else:
                yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="### 📢 답변이 양호합니다. 프로세스 종료합니다.\n")
                break
        else:
            logger.info("### SQL문 에러 처리")
            yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="### SQL문 에러 처리")
            for response in sql_obj.Node__handle_error():
                save_response += response
                yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=response)

    '''
        Des:
            데이터 분석 수행
    '''
    analysis_df = sql_obj.Node__get_data_from_db()
    analysis_df_markdown = analysis_df.to_markdown(index=False)
    # 컨텍스트 지정 (1) 데이터프레임 정보 지정
    prompt_state["CURRENT"]["DATAFRAME"] = analysis_df_markdown
    # 컨텍스트 지정 (2) 통계정보 지정
    try:
        prompt_state["CURRENT"]["STATISTICS"] = analysis_df.groupby(analysis_df["년도"]).agg(
            ['mean', 'min', 'max', 'median', 'sum']).drop('월', axis=1).to_markdown()
    except:
        prompt_state["CURRENT"]["STATISTICS"] = ''

    # 분석 수행
    for chunk in Chain__generate_analysis.stream(prompt_state):
        save_response += chunk.content
        relevant_response += chunk.content
        yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=chunk.content)

    # 대화 저장
    # self.REVISED_ANSWER = f"실제 데이터 : {self.DF_MARKDOWN}\n답변 : {self.ANSWER}"
    # self.CONV_OBJ.add_chat({"user": self.SQLOBJ.MESSAGE,
    #                         "assistant": self.REVISED_ANSWER})

    '''
        Des:
            시각화 수행
    '''
    # 시각화
    if check_yes(Chain__check_plot.invoke(prompt_state).content) == "YES":
        logger.info("### 시각화 결과 생성")
        save_response += '\n### 시각화 결과 생성\n\n'
        yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="\n### 시각화 결과 생성\n\n")
        # plotly
        try:
            content = ''
            PLOTLY_ERROR_HANDLER = ''
            while True:
                prompt_state["CURRENT"]["PLOTLY_ERROR_HANDLER"] = PLOTLY_ERROR_HANDLER
                gen_code = ""
                for chunk in Chain__generate_plotly.stream(prompt_state):
                    # print("\033[38;5;12m" + chunk.content +
                    #       "\033[0m", end="", flush=True)
                    gen_code += chunk.content
                    save_response += chunk.content
                    yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data=chunk.content)

                extract_gen_code = extract_python_plotly_code(gen_code)
                try:
                    global_vars = {"DF": analysis_df}
                    local_vars = {}
                    exec(extract_gen_code, global_vars, local_vars)
                    break
                except Exception as error:
                    logger.warning("생성된 시각화 코드에 오류가 있습니다. 오류 내용을 참고해서 재생성합니다.")
                    PLOTLY_ERROR_HANDLER = f"\n이전 코드 실행시 오류가 발생했습니다.\n\n이전 코드 : {extract_gen_code}\n\n오류 내용 : {str(error)}\n\n오류 내용을 참고하세요."
                    save_response += "\n생성된 시각화 코드에 오류가 있습니다. 오류 내용을 참고해서 재생성합니다.\n"
                    yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="\n생성된 시각화 코드에 오류가 있습니다. 오류 내용을 참고해서 재생성합니다.\n")

            fig = local_vars.get('fig')
            from plotly import io as pio
            content = pio.to_json(fig, validate=True)
            yield wrapped_event(message_id=message_id, session_id=session_id, type='3', plot=content)

        except:
            logger.warning("### 시각화하기에 데이터가 불충분합니다. (동적) 시각화 제외합니다.")
            save_response += "\n### 시각화하기에 데이터가 불충분합니다. (동적) 시각화 제외합니다.\n"
            yield wrapped_event(message_id=message_id, session_id=session_id, type='3', data="\n### 시각화하기에 데이터가 불충분합니다. (동적) 시각화 제외합니다.\n")

    '''
        Des:
            관련/추천 질문 생성
    '''
    # 관련 질문 생성 (검색 기반 이전 대화 참고)
    if user_info['btn1'] == "cancel":
        try:
            relevant_queries = Chain__relevant_query_with_search.invoke({"MESSAGE": prompt_state["CURRENT"]["MESSAGE"],
                                                                        "ANSWER": relevant_response}).content
        except:
            relevant_queries = []
    # 관련 질문 생성 (데이터베이스 기반 이전 대화 참고)
    else:
        try:
            relevant_queries = Chain__relevant_query_with_database.invoke({"MESSAGE": prompt_state["CURRENT"]["MESSAGE"],
                                                                           "ANSWER": relevant_response}).content
        except:
            relevant_queries = []
    yield wrapped_event(message_id=message_id, session_id=session_id, type='3', plot=content, relevant_query=relevant_queries)
    userDB.set_init_input(session_id, '', category)
    conv_history.add_predict_chat(
        {"user": {
            "message_id": f"{message_id}_user",
            "data": input_data,
        },
            "assistant": {
            "message_id": f"{message_id}_ai",
            "data": relevant_response,
        }}
    )
    conv_history.add_chat(
        {"user": {
            "message_id": f"{message_id}_user",
            "data": input_data,
            "source": [],
            "type": screen_type,
            "plot": "",
            "relevant_query": [],
            "download": ""
        },
            "assistant": {
            "message_id": f"{message_id}_ai",
            "data": save_response,
            "source": [],
            "type": screen_type,
            "plot": content,
            "relevant_query": relevant_queries,
            "download": ""
        }}
    )
    # conv_history.add_chat(
    #     {"user": input_data,
    #      "assistant": save_response}
    # )


def harbor_chain(
    input_data: str,
    session_id: str,
    userDB: dict,
    extract_info: dict,
    message_id: str,
    screen_type: str,
    send_data: str = ''
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
    # 현시점 입력 텍스트 : input_data
    logger.warning(f"conv_history.HISTORY {conv_history.HISTORY}")
    prompt_state = {
        "CURRENT": {"MESSAGE": input_data},
        "HISTORY": conv_history.HISTORY
    }
    # done!!
    if not use_database:
        if not use_search:  # 일반 대화
            logger.warning(f"일반 대화")
            userDB.set_init(session_id, True, category)
            response = general_answer_chain(
                prompt_state, conv_history, session_id, message_id, screen_type, userDB, send_data)
            return response
        else:  # 웹정보 활용
            logger.warning(f"웹정보 활용")
            userDB.set_init(session_id, True, category)
            response = web_search_and_answer_chain(
                prompt_state, conv_history, session_id, message_id, screen_type, userDB, send_data)
            return response
    else:  # 내부 DB 사용
        logger.warning(f"내부 DB 사용")
        # 사용자 정보에 기록된 첫 질문 + 항구 + 시간 정보
        input_prompt = userDB.get_init_input(session_id, category)
        # 항구정보, 시간 정보 점검 chain
        if input_prompt == input_data:
            input_data = ''
        info_check, response, analysis_info = check_chain(
            input_data, extract_info, userDB, session_id, category)
        if info_check:
            # 첫 질문으로 프롬프트 수정
            prompt_state["CURRENT"]["MESSAGE"] = input_prompt
            # analysis 생성 chain
            logger.warning(f"analysis 생성 chain")
            userDB.set_init(session_id, True, category)
            response = analysis_chain(
                userDB, input_data, prompt_state, category, extract_info,
                analysis_info, session_id, message_id, conv_history, screen_type
            )
            return response
        else:  # 정보부족
            # 항구정보, 시간 정보 점검 결과 반환
            logger.warning(f"항구정보, 시간 정보 점검 결과 반환")
            conv_history.add_chat(
                {"user": {
                    "message_id": f"{message_id}_user",
                    "data": input_data,
                    "source": [],
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": [],
                    "download": ""
                },
                    "assistant": {
                    "message_id": f"{message_id}_ai",
                    "data": response,
                    "source": [],
                    "type": screen_type,
                    "plot": "",
                    "relevant_query": [],
                    "download": ""
                }}
            )
        return wrapped_string_generator(response, session_id, type=screen_type, message_id=message_id)
