from fastapi import HTTPException, File, status
from loguru import logger
import json
import re


def check_save_xlsx(target_file: File) -> str:
    contents = check_xlsx(target_file)
    save_path = save_xlsx(target_file, contents)
    return save_path


def check_xlsx(check_file: File) -> None:
    if not check_file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="The file extension is invalid.")
    contents = check_file.file.read()
    # if not contents.startswith(b'%PK'):
    #     raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    #                         detail="The uploaded file is not a xlsx type PK.")
    logger.warning(f"check xlsx done!!")
    return contents


def save_xlsx(save_file: File, contents: str) -> str:
    save_file_path = f"imports/{save_file.filename}"
    # contents = save_file.file.read()
    logger.warning(f"save_file_path : {save_file_path}")
    with open(save_file_path, "wb") as buffer:
        buffer.write(contents)
    return save_file_path


def check_yes(text):
    if re.search(r'yes', text, re.IGNORECASE):
        return "YES"
    else:
        return "NO"


def extract_python_code(text):
    python_code_pattern = re.compile(r'```python\n(.*?)\n```', re.DOTALL)
    match = python_code_pattern.search(text)
    if match:
        return match.group(1).strip()
    else:
        return ""


def extract_python_pyplot_code(text):
    python_code_pattern = re.compile(
        r'```python\n(.*?)\nplt.show()', re.DOTALL)
    match = python_code_pattern.search(text)
    if match:
        return match.group(1).strip()
    else:
        return ""


def extract_python_plotly_code(text):
    python_code_pattern = re.compile(
        r'```python\n(.*?)\nfig.show()', re.DOTALL)
    match = python_code_pattern.search(text)
    if match:
        return match.group(1).strip()
    else:
        return ""


def format_number(x):
    '''
        Des:
            숫자형 데이터 comma로 구분
    '''
    if isinstance(x, (int, float)):  # 숫자형 데이터인지 확인
        return "{:,}".format(x)
    else:
        return x


def wrapped_event(message_id='', session_id='', type='', source=[], data='', plot='',  relevant_query=[], download=''):
    return json.dumps({
        "state": status.HTTP_200_OK,
        "result": {
            "message_id": message_id,
            "session_id": session_id,
            "type": type,
            "source": [{
                "href": "http://www.shippingnewsnet.com/news/articleView.html?idxno=45703",
                "title": "Bpa, '22년 부산항 컨테이너 물동량 2,350만teu 목표 < 항만 < 뉴스 < 기사본문 - 쉬핑뉴스넷"
            },
                {
                "href": "https://www.data.go.kr/data/15055477/fileData.do",
                "title": "부산항만공사_부산항 연도별 물동량 추이_20231231 | 공공데이터포털"
            },
                {
                "href": "https://www.data.go.kr/data/15055478/fileData.do",
                "title": "부산항만공사_부산항 컨테이너 수송통계_20221231 | 공공데이터포털"
            },
                {
                "href": "https://www.yna.co.kr/view/AKR20221025051900051",
                "title": "심상찮은 부산항 물동량 감소세…9월에만 14% ↓ | 연합뉴스"
            }],
            "data": data,
            "plot": plot,
            "relevant_query": relevant_query,
            "download": download
        },
        "message": "success"
    }, ensure_ascii=False)


def wrapped_string_generator(string_response, session_id, type, message_id: str = 1):
    if isinstance(string_response, list):
        string_response_form = string_response
    else:
        string_response_form = [string_response]
    for string in string_response_form:
        yield json.dumps({
            "state": status.HTTP_200_OK,
            "result": {
                "message_id": message_id,
                "session_id": session_id,
                "type": type,
                "source": [],
                "data": string,
                "plot": "",
                "relevant_query": [],
                "download": ""
            },
            "message": "success"
        }, ensure_ascii=False)
