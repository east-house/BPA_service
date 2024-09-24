from typing import List, Dict
import uuid


class UserModule():
    def __init__(self):
        self.UserDB = {}

    def gen_session_id(self):
        # session_id = str(uuid.uuid4())
        session_id = 'tmp_session_id'
        self.UserDB[session_id] = {
            'statistics': {
                'init': True,
                'btn1': False,
                'btn2': False,
                'upload': '',
                'download': '',
                'harbor_name': '',
                'datetime': '',
            },
            'harbor': {
                'init': True,
                'btn1': False,
                'btn2': False,
                'harbor_name': '',
                'datetime': '',
            }
        }
        return session_id

    def check_session_id(self, session_id: str) -> bool:
        if self.UserDB.get(session_id):
            return False
        else:
            return True

    def get_user_info(self, session_id: str, category: str) -> dict:
        return self.UserDB.get(session_id).get(category)

    # def pre_btn_message(self, session_id: str, category: str, step_number: int):
    #     return self.UserDB[session_id][category]['history'][-(step_number)]['ai']

    def set_init(self, session_id: str, value: bool, category: str) -> None:
        self.UserDB[session_id][category]['init'] = value

    def set_filename(self, session_id: str, file_name: str) -> str:
        '''
        file_name : 파일 이름 경로 제외
        '''
        try:
            self.UserDB[session_id]['statistics']['upload'] = file_name
            return True
        except:
            return False

    def get_filename(self, session_id: str):
        '''
        upload file name 전달
        '''
        return self.UserDB[session_id]['statistics']['upload']

    def set_btn_one(self, session_id: str, click_value: str, category: str) -> bool:
        '''
        click_value
        '''
        if category == 'statistics':
            value = True if click_value == '회신양식 업로드' else False
        else:
            value = True if click_value == '포트미스 데이터 사용' else False
        self.UserDB[session_id][category]['btn1'] = value
        return value

    def set_btn_two(self, session_id: str, click_value: str, category: str) -> bool:
        '''
        click_value
        '''
        if category == 'statistics':
            value = True if click_value == '회신양식 컬럼 사용' else False
        else:
            value = True if click_value == '웹 검색 정보 사용' else False
        self.UserDB[session_id][category]['btn2'] = value
        return value
