from . import *


class OutputParser():
    def __init__(self):

        # 요청문
        self.check_query_parser = PydanticOutputParser(
            pydantic_object=self.InputValidityOutput)

        # 항구
        self.check_port_parser = PydanticOutputParser(
            pydantic_object=self.PortIncludeCheckOutput)
        self.extract_port_parser = PydanticOutputParser(
            pydantic_object=self.PortNameOutput)

        # 시설
        self.check_facil_parser = PydanticOutputParser(
            pydantic_object=self.FacilIncludeCheckOutput)
        self.extract_facil_parser = PydanticOutputParser(
            pydantic_object=self.FacilNameOutput)

        # 수출입
        self.check_io_parser = PydanticOutputParser(
            pydantic_object=self.TradeTypeIncludeCheckOutput)
        self.extract_io_parser = PydanticOutputParser(
            pydantic_object=self.TradeTypeCodeOutput)

        # 국가
        self.extract_country_parser = PydanticOutputParser(
            pydantic_object=self.CountryNameOutput)

        # 관련질문
        self.relevant_query_parser = PydanticOutputParser(
            pydantic_object=self.RelevanceUserQueryOutput)

    class InputValidityOutput(BaseModel):
        content: str = Field(description="YES or NO")

    class PortIncludeCheckOutput(BaseModel):
        content: str = Field(description="YES or NO")

    class PortNameOutput(BaseModel):
        content: list[str] = Field(
            description="항구명 목록을 생성합니다. 추가적인 정보는 생성하지 않습니다.")

    class FacilIncludeCheckOutput(BaseModel):
        content: str = Field(description="YES or NO")

    class FacilNameOutput(BaseModel):
        content: list[str] = Field(
            description="시설명 목록을 생성합니다. 추가적인 정보는 생성하지 않습니다.")

    class TradeTypeIncludeCheckOutput(BaseModel):
        content: str = Field(description="YES or NO")

    class TradeTypeCodeOutput(BaseModel):
        content: list[str] = Field(description="수출입유형 코드 변환 결과")

    class CountryNameOutput(BaseModel):
        content: list[str] = Field(description="국가명 추출 결과")

    class RelevanceUserQueryOutput(BaseModel):
        content: list[str] = Field(description="추천질문 리스트")


class SQLQueryOutputParser(BaseOutputParser):

    def get_cursor(self):
        try:
            conn = mariadb.connect(
                user="root",
                password="mariadb",
                host="192.168.1.20",
                port=4100,
                database="smartm2m"
            )
            cursor = conn.cursor()
            return cursor
        except mariadb.Error as e:
            print(f"Error connecting to MariaDB Platform: {e}")
            exit(1)

    def parse(self, text: str) -> Any:
        # SQL 쿼리 부분만 추출
        sql_query_pattern = re.compile(r'```sql\n(.*?)\n```', re.DOTALL)
        match = sql_query_pattern.search(text)
        if match:
            return match.group(1).strip()
        else:
            return ""
