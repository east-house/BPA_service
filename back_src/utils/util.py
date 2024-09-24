from fastapi import HTTPException, File, status
from loguru import logger
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
