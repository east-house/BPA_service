import pandas as pd
from . import *
from .chain import *
from models.model import *
from utils.parser import SQLQueryOutputParser
from typing import List, Dict, Tuple


class SQLGenerator():
    def __init__(self,
                 MESSAGE,
                 EXTRACT_INFO_OBJ,
                 EXCEL_APPLIER_OBJ,
                 MODE):

        # 사용자 입력
        self.MESSAGE = MESSAGE

        # 관리되는 정보
        self.STATE = None
        self.ERROR = None
        self.SQL = None
        self.POST_SQL = None  # SQL 쿼리 부분
        self.PARSER = SQLQueryOutputParser()
        self.CURSOR = self.PARSER.get_cursor()
        self.RENERATE = None

        # 정보추출 클래스 객체
        self.EXTRACT_INFO_OBJ = EXTRACT_INFO_OBJ

        # 엑셀변환 클래스 객체
        self.EXCEL_APPLIER_OBJ = EXCEL_APPLIER_OBJ

        # 대화 모드 (모드에 따라 SQL 생성 프롬프트 상이)
        self.MODE = MODE

    def get_post_sql(self):
        '''
            Des:
                파이썬 코드에서 SQL 쿼리 부분만 추출
        '''
        return self.PARSER.parse(self.SQL)

    def Node__classify_request(self):
        self.STATE = {"MESSAGE": self.MESSAGE}
        return check_yes(Chain__classify_request.invoke(self.STATE).content)

    def Node__check_essential_info(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        '''
            Des:
                필수정보 확인
            Returns:
                사용자 정보, 에러 메시지
        '''
        self.STATE = {"MESSAGE": self.MESSAGE,
                      "PORT_DATA_LST": self.EXTRACT_INFO_OBJ.PORT_NAME_LST,
                      "FAC_NAME_LST": self.EXTRACT_INFO_OBJ.FAC_NAME_LST,
                      "COUNTRY_LIST": self.EXTRACT_INFO_OBJ.COUNTRY_NAME_LST}

        self.USE_INFO = {"USE_PORT": check_yes(Chain__check_port.invoke(self.STATE).content),
                         "USE_TIME": check_yes(Chain__check_time.invoke(self.STATE).content)}

        error_messages = {"USE_PORT": "⛔ 항구 정보가 없습니다. 값을 정확히 기입해주세요. 예:부산항",
                          "USE_TIME": "⛔ 시간 정보가 없습니다. 값을 정확히 기입해주세요. 예:최근 2년간, 2020~2022 동안"}

        return self.USE_INFO, error_messages

    def Node__extract_info(self):
        '''
            Des:
                사용자 요청에서 정보 추출
        '''
        self.USE_INFO["USE_FACIL"] = check_yes(
            Chain__check_facil.invoke(self.STATE).content)
        self.USE_INFO["USE_IO"] = check_yes(
            Chain__check_io.invoke(self.STATE).content)
        self.USE_INFO["USE_COUNTRY"] = check_yes(
            Chain__check_country.invoke(self.STATE).content)

        for key in self.USE_INFO.keys():
            if key == "USE_PORT" and self.USE_INFO.get(key) == "YES":
                try:
                    PORT_NAME = Chain__extract_port.invoke(self.STATE).content
                    self.EXTRACT_INFO_OBJ.change_str_to_lst(PORT_NAME)
                    self.EXTRACT_INFO_OBJ.extract_port_from_excel()  # self.PORT_INFO 생성
                except:
                    logger.warning("항구명 추출 파싱오류가 발생했습니다. 기본값인 부산항을 사용합니다.")
                    self.EXTRACT_INFO_OBJ.PORT_INFO = "항구명 : 부산항, 항구 코드(DB 조회시 사용) : 020"
            if key == "USE_TIME" and self.USE_INFO.get(key) == "YES":
                TIME = Chain__extract_time.invoke(self.STATE).content
                self.EXTRACT_INFO_OBJ.set_time_info(TIME)
            if key == "USE_FACIL" and self.USE_INFO.get(key) == "YES":
                try:
                    FACIL_NAME = Chain__extract_facil.invoke(
                        self.STATE).content
                    self.EXTRACT_INFO_OBJ.change_str_to_lst(FACIL_NAME)
                    self.EXTRACT_INFO_OBJ.extract_facil_from_excel()  # self.FAC_INFO 생성
                except:
                    logger.warning("시설명 추출 파싱오류가 발생했습니다. 시설명을 미사용 합니다.")
                    self.EXTRACT_INFO_OBJ.FAC_INFO = ""
            if key == "USE_IO" and self.USE_INFO.get(key) == "YES":
                try:
                    IO = Chain__extract_io.invoke(self.STATE).content
                    self.EXTRACT_INFO_OBJ.set_IO_info(IO)
                except:
                    logger.warning("수출입유형 추출 파싱오류가 발생했습니다. 수출입환적을 모두 사용 합니다.")
                    self.EXTRACT_INFO_OBJ.IO_INFO = "수출입 정보 : II, OO, IT, OT"
            if key == "USE_COUNTRY" and self.USE_INFO.get(key) == "YES":
                try:
                    COUNTRY = Chain__extract_country.invoke(self.STATE).content
                    self.EXTRACT_INFO_OBJ.set_COUNTRY_info(COUNTRY)
                except:
                    logger.waring("국가명 추출 파싱오류가 발생했습니다. 국가명을 미사용합니다.")
                    self.EXTRACT_INFO_OBJ.COUNTRY_INFO = ""
        self.EXTRACT_INFO_OBJ.get_total_info()

    def Node__generate_sql(self):
        '''
            Des:
                SQL 쿼리 생성
        '''

        # 통계추출 일 경우
        if self.MODE == "statistic":
            AGGREGATE = ""

        # 데이터분석 일 경우
        else:
            AGGREGATE = "\n무조건 집계함수(월별 집계)를 사용하세요."

        # 양식 컬럼 사용할 경우
        if self.EXCEL_APPLIER_OBJ.COLS:
            COLUMNS = f"\n출력할 컬럼 정보:\n{copy.deepcopy(self.EXCEL_APPLIER_OBJ.COLS)}"

        # LLM이 생성한 컬럼 사용할 경우
        else:
            COLUMNS = "\nColumns 명은 Alias를 사용하여 적합한 한국어로 변경하세요. 하지만 시간 정보중에 연도 정보는 무조건 '년도', 월 정보는 무조건 '월' 로 Column명을 설정하세요."

        self.STATE = {"MESSAGE": self.MESSAGE,
                      "INFOS_STR": self.EXTRACT_INFO_OBJ.INFOS_STR,
                      "SCHEMA": Text2SQLConfig.table_column_info,
                      "DEFAULT": Text2SQLConfig.default_info,
                      "COLUMNS": COLUMNS,
                      "AGGREGATE": AGGREGATE}

        # SQL 쿼리 생성
        self.SQL = ''
        for chunk in Chain__generate_sql.stream(self.STATE):
            self.SQL += chunk.content
            yield chunk.content

    def Node__validate_query(self):
        '''
            Des:
                SQL 쿼리 실행
        '''
        self.POST_SQL = self.get_post_sql()
        try:
            self.CURSOR.execute(self.POST_SQL)
            self.ERROR = None
        except Exception as error:
            self.ERROR = str(error)

    def Node__handle_error(self):
        '''
            Des:
                SQL 쿼리 유효성 검사 수행
        '''
        self.STATE = {"MESSAGE": self.MESSAGE,
                      "INFOS_STR": self.EXTRACT_INFO_OBJ.INFOS_STR,
                      "SCHEMA": Text2SQLConfig.table_column_info,
                      "ERROR": self.ERROR,
                      "SQL": self.POST_SQL,
                      "DEFAULT": Text2SQLConfig.default_info}

        # 에러 수정
        self.SQL = ''
        for chunk in Chain__handle_error.stream(self.STATE):
            self.SQL += chunk.content
            yield chunk.content

    def Node__feedback(self):
        '''
            Des:
                생성한 SQL 쿼리 품질 검사
        '''
        self.STATE = {"MESSAGE": self.MESSAGE,
                      "INFOS_STR": self.EXTRACT_INFO_OBJ.INFOS_STR,
                      "SCHEMA": Text2SQLConfig.table_column_info,
                      "SQL": self.POST_SQL,
                      "DEFAULT": Text2SQLConfig.default_info}

        # self.FEEDBACK = ''
        # for chunk in Chain__get_feedback.stream(self.STATE):
        #     self.FEEDBACK += chunk.content
        #     yield chunk.content

        # self.FEEDBACK = Chain__get_feedback.invoke(self.STATE).content

        self.FEEDBACK = "YES"  # TODO 임시

        if check_yes(self.FEEDBACK) == "YES":
            self.RENERATE = False
        else:
            self.RENERATE = True

    def Node__regenerate(self):
        '''
            Des:
                피드백 기반 SQL 쿼리 재생성
        '''
        self.STATE = {"MESSAGE": self.MESSAGE,
                      "INFOS_STR": self.EXTRACT_INFO_OBJ.INFOS_STR,
                      "SCHEMA": Text2SQLConfig.table_column_info,
                      "FEEDBACK": self.FEEDBACK,
                      "SQL": self.POST_SQL,
                      "DEFAULT": Text2SQLConfig.default_info}

        # 재생성
        self.SQL = ''
        for chunk in Chain__regenerate.stream(self.STATE):
            self.SQL += chunk.content
            yield chunk.content

    def Node__get_data_from_db(self) -> pd.DataFrame:
        '''
            Des:
                데이터 추출
            Returns:
                추출한 데이터프레임
        '''
        self.CURSOR.execute(self.POST_SQL)
        column_names = [i[0] for i in self.CURSOR.description]
        rows = self.CURSOR.fetchall()
        DF = pd.DataFrame(rows, columns=column_names)
        return DF
