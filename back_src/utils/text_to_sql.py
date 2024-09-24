import pandas as pd
import json
import ast
import re
import os


from typing import List


class ExtractInfo():
    def __init__(self):
        self.DATA_PATH = "data/Text2SQL"
        self.EXCEL_FILE_PATH = os.path.join(self.DATA_PATH, "harbor_info.xlsx")
        self.PORT_DF = pd.read_excel(
            self.EXCEL_FILE_PATH, sheet_name="(공통)항만정보")
        self.FACIL_DF = pd.read_excel(
            self.EXCEL_FILE_PATH, sheet_name="시설코드(부산항만)")
        self.COUNTRY_DF = pd.read_excel(
            self.EXCEL_FILE_PATH, sheet_name="(공통)국가코드")
        self.PORT_DATA_PATH = os.path.join(self.DATA_PATH, "code_cw.json")
        self.FAC_DATA_PATH = os.path.join(self.DATA_PATH, "facil_cw.json")
        self.PORT_NAME_LST = ''  # 사용할 수 있는 항구명 목록
        self.FAC_NAME_LST = ''  # 사용할 수 있는 시설명 목록
        self.PORT_INFO = ''  # 생성 chain에 들어갈 항구 정보
        self.FAC_INFO = ''  # 생성 chain에 들어갈 시설 정보
        self.TIME_INFO = ''  # 생성 chain에 들어갈 시간 정보
        self.IO_INFO = ''  # 생성 chain에 들어갈 수출입 정보
        self.COUNTRY_INFO = ''  # 생성 chain에 들어갈 국가 정보
        self.STR_TO_LST_PATTERN = r'\{.*?\}'  # 출력 문자열을 리스트형태로 변환할때 사용하는 패턴
        self.LIST = []  # 출력 문자열을 리스트 형태로 변환시 저장
        self.STRING = ''  # 생성 chain 출력 결과물
        self.INFOS_STR = ''  # 최종 취합정보

    def load_name_lst(self):
        '''
            Des: 
                필요 메타정보 추출
                - PORT_NAME_LST : 항구정보
                - FAC_NAME_LST : 시설정보
                - COUNTRY_NAME_LST : 국가정보
        '''
        data = json.load(open(self.PORT_DATA_PATH))
        self.PORT_NAME_LST = [i['port']['PRT_AT_NAME'] for i in data['data']]

        data = json.load(open(self.FAC_DATA_PATH))
        self.FAC_NAME_LST = []
        for temp in data['data']:
            lst = temp['facil']['FAC_NAME']
            self.FAC_NAME_LST.append(lst)

        self.COUNTRY_NAME_LST = self.COUNTRY_DF["한글명"].tolist()

    def change_str_to_lst(self, STRING: str) -> List:
        '''
            Des:
                출력 문자열을 리스트로 변환하는 함수
            Args:
                변경할 문자열
        '''
        match = re.search(self.STR_TO_LST_PATTERN, STRING, re.DOTALL)
        self.LIST = ast.literal_eval(match.group(0))['content']

    def extract_port_from_excel(self):
        '''
            Des:
                사용자 요청에 해당되는 항구명과 청코드 추출
        '''
        self.PORT_INFO = ''
        for _, row in self.PORT_DF[self.PORT_DF['항구명'].isin(self.LIST)].iterrows():
            self.PORT_INFO += f"항구명 : {row['항구명']}, 항구 코드(DB 조회시 사용) : {row['청코드']}\n"

    def extract_facil_from_excel(self):
        '''
            Des:
                사용자 요청에 해당되는 시설명과 시설코드 추출
        '''
        self.FAC_INFO = ''
        for _, row in self.FACIL_DF[self.FACIL_DF['시설명'].isin(self.LIST)].iterrows():
            self.FAC_INFO += f"시설명 : {row['시설명']}, "

            if not pd.isna(row['선석 구분']):
                self.FAC_INFO += f"시설 선석 구분 : {row['선석 구분']}, "
            self.FAC_INFO += f"시설 코드(DB 조회시 사용) : {row['코드']}\n"

    def set_time_info(self, TIME_INFO: str):
        '''
            Des:
                시간 정보 설정
            Args:
                시간 문자열
        '''
        self.TIME_INFO = TIME_INFO

    def set_IO_info(self, IO_INFO: str):
        '''
            Des:
                수출입 정보 설정
            Args:
                수출입 정보 문자열                
        '''
        self.IO_INFO = '수출입 정보 : '+', '.join(IO_INFO)

    def set_COUNTRY_info(self, COUNTRIES: str):
        '''
            Des:
                국가 정보 설정
            Args:
                국가 정보 문자열
        '''
        self.COUNTRY_INFO = "국가 정보 : "
        for country in COUNTRIES:
            if country in ["대한민국", "북한(조선민주주의인민공화국)"]:
                continue
            code = self.COUNTRY_DF[self.COUNTRY_DF['한글명']
                                   == country]['2자리코드'].values[0]
            self.COUNTRY_INFO += f"{country}({code}), "
        self.COUNTRY_INFO = self.COUNTRY_INFO.strip().rstrip(",")

    def get_total_info(self):
        '''
            Des:
                정보 종합
        '''
        self.INFOS_STR = self.PORT_INFO+"\n"+self.TIME_INFO+"\n" + \
            self.IO_INFO+"\n"+self.FAC_INFO+"\n"+self.COUNTRY_INFO
        self.INFOS_STR = re.sub(r'\n+', '\n', self.INFOS_STR)
