from typing import List, Dict
import uuid


class UserModule():
    def __init__(self):
        self.UserDB = {}

    def gen_session_id(self):
        session_id = str(uuid.uuid4())
        # session_id = 'tmp_session_id'
        self.UserDB['tmp_session_id'] = {
            'statistics': {
                'init': True,
                'btn1': False,
                'btn2': False,
                'upload': '',
                'download': '',
                'init_input': '',
                'save_response': ''
            },
            'analysis': {
                'init': True,
                'btn1': False,
                'btn2': False,
                'init_input': '',
                'save_response': ''
            }
        }
        self.UserDB[session_id] = {
            'statistics': {
                'init': True,
                'btn1': False,
                'btn2': False,
                'upload': '',
                'download': '',
                'init_input': '',
                'save_response': ''
            },
            'analysis': {
                'init': True,
                'btn1': False,
                'btn2': False,
                'init_input': '',
                'save_response': ''
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

    def set_save_response(self, session_id: str, category: str, value: str):
        self.UserDB[session_id][category]['save_response'] = value

    def set_init(self, session_id: str, value: bool, category: str) -> None:
        self.UserDB[session_id][category]['init'] = value

    def set_init_input(self, session_id: str, value: str, category: str):
        # if self.UserDB[session_id][category]['init']:
        #     self.UserDB[session_id][category]['init_input'] = value
        # test code
        self.UserDB[session_id][category]['init_input'] = value

    def add_init_input(self, session_id: str, value: str, category: str):
        self.UserDB[session_id][category]['init_input'] += f' {value}'

    def get_init_input(self, session_id: str, category: str) -> dict:
        return self.UserDB[session_id][category]['init_input']

    def set_download_fn(self, session_id: str, category: str, value: str):
        self.UserDB[session_id][category]['download'] = value

    def get_download_fn(self, session_id: str, category: str):
        return self.UserDB[session_id][category]['download']

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
        value_dict = {
            '회신양식 업로드': True,
            '회신양식 미업로드': False,
            '포트미스 데이터 사용': True,
            '포트미스 데이터 미사용': False
        }
        if category == 'statistics':
            value = value_dict.get(click_value, 'error')
        else:
            value = value_dict.get(click_value, 'error')
        if value != 'error':
            self.UserDB[session_id][category]['btn1'] = value
        return value

    def set_btn_two(self, session_id: str, click_value: str, category: str) -> bool:
        '''
        click_value
        '''
        value_dict = {
            '회신양식 컬럼 사용': True,
            '인공지능 생성 컬럼 사용': False,
            '웹 검색 정보 사용': True,
            '웹 검색 정보 미사용': False
        }
        if category == 'statistics':
            value = value_dict.get(click_value, 'error')
        else:
            value = value_dict.get(click_value, 'error')
        if value != 'error':
            self.UserDB[session_id][category]['btn2'] = value
        return value
