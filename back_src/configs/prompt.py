import copy
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from . import *
from loguru import logger

PARSER_OBJ = OutputParser()
SYSTEM_PROMPT = Text2SQLConfig.qwen_system

# 추천 질문


def prompt_relevant_query_with_database_prompt(STATE):
    # .encode('utf-8').decode('unicode_escape')
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.relevant_query_parser.get_format_instructions()
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.relevant_query_with_database_prompt.format_map(
                STATE)
        ),
    ]
    logger.warning("추천질문 생성 프롬프트 (1) DB 조회시")
    logger.info(prompt)
    return prompt


def prompt_relevant_query_with_search_prompt(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.relevant_query_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.relevant_query_with_search_prompt.format_map(
                STATE)
        ),
    ]
    logger.warning("추천질문 생성 프롬프트 (2) 웹 검색시")
    logger.info(prompt)
    return prompt


# 통계요청 사용자 요청 요약
def prompt_query_summary(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=SQL2ExcelConfig.summary.format_map(STATE)
        ),
    ]
    return prompt

# 민원대응


def prompt_customer_service(STATE):
    return STATE['HISTORY']+[HumanMessage(content=CustomerServiceConfig.generate.format_map(STATE['CURRENT']))]


# 정보추출, 라우팅
# 사용자 요청 분류
def prompt_classify_request(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.check_query_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.classify_request.format_map(STATE)
        ),
    ]
    return prompt

# 항구


def prompt_check_port(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.check_port_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.check_port.format_map(STATE)
        ),
    ]
    return prompt


def prompt_extract_port(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.extract_port_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.extract_port.format_map(STATE)
        ),
    ]
    return prompt

# 시간


def prompt_check_time(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.check_time.format_map(STATE)
        ),
    ]
    return prompt


def prompt_extract_time(STATE):
    now = datetime.now()
    STATE["TIME"] = now.strftime("%Y-%m-%d")
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.extract_time.format_map(STATE)
        ),
    ]
    return prompt

# 시설


def prompt_check_facil(STATE):
    from loguru import logger
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.check_facil_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    STATE_COPY = copy.deepcopy(STATE)
    STATE_COPY["MESSAGE"] = re.sub(r'_+', ' ', STATE_COPY["MESSAGE"])
    STATE_COPY["MESSAGE"] = re.sub(r'\b\w{1,3}별\b', '', STATE_COPY["MESSAGE"])
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.check_facil.format_map(STATE_COPY)
        ),
    ]
    return prompt


def prompt_extract_facil(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.extract_facil_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    STATE_COPY = copy.deepcopy(STATE)
    STATE_COPY["MESSAGE"] = re.sub(r'_+', ' ', STATE_COPY["MESSAGE"])
    STATE_COPY["MESSAGE"] = re.sub(r'\b\w{1,3}별\b', '', STATE_COPY["MESSAGE"])
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.extract_facil.format_map(STATE_COPY)
        ),
    ]
    return prompt

# 수출입 유형


def prompt_check_iotype(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.check_io_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.check_iotype.format_map(STATE)
        ),
    ]
    return prompt


def prompt_extract_iotype(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.extract_io_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.extract_iotype.format_map(STATE)
        ),
    ]
    return prompt

# 국가


def prompt_check_country(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.check_country.format_map(STATE)
        ),
    ]
    return prompt


def prompt_extract_country(STATE):
    STATE['FORMAT_INSTRUCTIONS'] = PARSER_OBJ.extract_country_parser.get_format_instructions(
    ).encode('utf-8').decode('unicode_escape')
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.extract_country.format_map(STATE)
        ),
    ]
    return prompt


# 생성
# 단순 답변
def prompt_generate_general_answer(STATE):
    prompt = STATE['HISTORY']+[HumanMessage(
        content=Text2SQLConfig.generate_general_answer.format_map(STATE['CURRENT']))]
    logger.warning("DB검색 미사용, 웹검색 미사용시 답변생성")
    logger.info(prompt)
    return prompt


def prompt_generate_answer_with_context(STATE):
    now = datetime.now()
    STATE['CURRENT']["TIME"] = now.strftime("%Y-%m-%d")
    prompt = STATE['HISTORY']+[HumanMessage(
        content=Text2SQLConfig.generate_answer_with_context.format_map(STATE['CURRENT']))]
    logger.warning("DB검색 미사용, 웹검색 결과 기반 답변생성")
    logger.info(prompt)
    return prompt

# 단순 SQL 쿼리 생성


def prompt_generate_sql(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.generate_sql.format_map(STATE)
        ),
    ]
    logger.warning("SQL 생성")
    logger.info(prompt)
    return prompt

# 분석 결과 생성


def prompt_generate_analysis(STATE):
    prompt = STATE['HISTORY']+[HumanMessage(
        content=Text2SQLConfig.generate_analysis.format_map(STATE['CURRENT']))]
    logger.warning("DB검색 사용결과 기반 답변생성")
    logger.info(prompt)
    return prompt


# 수정 및 에러처리
# 사용자 요청 재작성
def prompt_rewrite_request(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.rewrite_sql_request.format_map(STATE)
        ),
    ]
    return prompt

# 에러제거


def prompt_handle_error(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.handle_error.format_map(STATE)
        ),
    ]
    return prompt

# 피드백


def prompt_feedback(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.feedback.format_map(STATE)
        ),
    ]
    return prompt

# 재생성


def prompt_regenerate(STATE):
    now = datetime.now()
    STATE["TIME"] = now.strftime("%Y-%m-%d")
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.regenerate.format_map(STATE)
        ),
    ]
    return prompt


# 시각화
def prompt_check_plot(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.check_plot.format_map(STATE['CURRENT'])
        ),
    ]
    logger.warning("시각화 필요여부 판단")
    logger.info(prompt)
    return prompt


def prompt_generate_pyplot(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.generate_pyplot.format_map(STATE['CURRENT'])
        ),
    ]
    logger.warning("pyplot 시각화")
    logger.info(prompt)
    return prompt


def prompt_generate_plotly(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.generate_plotly.format_map(STATE['CURRENT'])
        ),
    ]
    logger.warning("plotly 시각화")
    # logger.info(prompt)
    return prompt


# 검색
def prompt_generate_search_text(STATE):
    now = datetime.now()
    STATE['CURRENT']["TIME"] = now.strftime("%Y-%m-%d")
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.generate_search_text.format_map(
                STATE['CURRENT'])
        ),
    ]
    logger.warning("검색어 생성")
    logger.info(prompt)
    return prompt


def prompt_select_good_search(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.select_good_search.format_map(STATE)
        ),
    ]
    logger.warning("검색결과 양호여부 1차 판단")
    logger.info(prompt)
    return prompt


def prompt_select_good_search_with_body(STATE):
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=Text2SQLConfig.select_good_search_with_body.format_map(
                STATE)
        ),
    ]
    logger.warning("검색결과 양호여부 2차 판단")
    logger.info(prompt)
    return prompt
