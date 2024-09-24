from utils.text_to_sql import *
from modules.chain import *
from modules.node import SQLGenerator
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import FastAPI, HTTPException, Request, status, Body, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from concurrent.futures import ThreadPoolExecutor
from starlette.responses import FileResponse
from utils.util import check_save_xlsx, check_yes
from utils.history import ConversationHistory
from utils.sql_to_excel import ExcelTemplateApplier
from loguru import logger
from typing import List
from jose import jwt

import argparse
import asyncio
import json
import time
import os
import uvicorn

from utils.dummy_data import dummy_data
from utils.dummy_user import UserModule

userDB = UserModule()
extract_info = ExtractInfo()
extract_info.load_name_lst()

session_id = userDB.gen_session_id()
# userDB.set_history(session_id, '안녕하세요', 'statistics', role='user')
# userDB.set_history(session_id, '반갑', 'statistics', role='ai')


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


def dummy_statistics():
    dummy_data = {
        "source": [],
        "data": "```sql\nSELECT \n    '부산항' AS 항구명,\n    data.YYYY AS 년,\n    data.MM AS 월,\n    SUM(CASE WHEN data.IO_TP = 'II' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수입,\n    SUM(CASE WHEN data.IO_TP = 'OO' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수출,\n    SUM(CASE WHEN data.IO_TP = 'IT' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수입환적,\n    SUM(CASE WHEN data.IO_TP = 'OT' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수출환적\nFROM \n    data\nWHERE \n    data.PRT_AT_CODE IN (020, 021, 022) AND \n    data.YYYY = 2022\nGROUP BY \n    년, 월;\n```\n이 SQL 쿼리는 부산항(코드 020, 021, 022)에서 2022년에 발생한 수입, 수출, 수입환적, 수출환적의 적컨 TEU 수량을 월별로 집계합니다. 이때, 아국선과 외국선의 적컨 TEU 수량을 합산하여 결과를 제공합니다. | 항구명   |   년 |   월 |   수입 |   수출 |   수입환적 |   수출환적 |\n|:---------|-----:|-----:|-------:|-------:|-----------:|-----------:|\n| 부산항   | 2022 |    1 | 283138 | 362682 |     528216 |     507601 |\n| 부산항   | 2022 |    2 | 223267 | 346902 |     422894 |     473787 | ### 해석\n\n#### 총 적컨 TEU (Twenty-foot Equivalent Unit)\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 1.519M | 1.387M | 1.672M | 1.485M | 18.23M |\n| 2021 | 1.629M | 1.441M | 1.712M | 1.631M | 19.54M |\n| 2022 | 1.559M | 1.324M | 1.736M | 1.571M | 18.71M |\n\n2020년에서 2021년으로 넘어가면서 총 적컨 TEU의 평균이 약 7% 증가하였고, 이는 2021년에 더 많은 컨테이너가 처리되었음을 의미합니다. 그러나 2021년에서 2022년으로 넘어가면서 총 적컨 TEU의 평균은 약 4% 감소하였습니다.\n\n#### 총 공컨 TEU\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 299.6K | 243.1K | 355.9K | 286.3K | 3.595M |\n| 2021 | 263.4K | 220.4K | 308.5K | 266.8K | 3.161M |\n| 2022 | 280.9K | 236.3K | 302.5K | 285.9K | 3.371M |\n\n총 공컨 TEU의 경우, 2020년에서 2021년으로 넘어가면서 평균이 약 12% 감소하였으나, 2021년에서 2022년으로 넘어가면서 다시 약 6% 증가하였습니다.\n\n#### 총 톤수\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 112.8M | 103.0M | 126.5M | 110.8M | 1.354B |\n| 2021 | 102.2M | 95.4M | 113.3M | 101.4M | 1.226B |\n| 2022 | 103.8M | 93.3M | 117.4M | 103.0M | 1.246B |\n\n총 톤수의 경우, 2020년에서 2021년으로 넘어가면서 평균이 약 9% 감소하였으나, 2021년에서 2022년으로 넘어가면서 약 2% 증가하였습니다.\n\n결론적으로, 부산항의 물동량은 2020년에서 2021년으로 넘어가면서 감소하였으나, 2021년에서 2022년으로 넘어가면서 다시 증가하였습니다. 이는 전 세계적인 공급망 혼란과 관련이 있을 수 있습니다. ```python\nimport plotly.graph_objects as go\nfrom plotly.subplots import make_subplots\n\n# Create figure with secondary y-axis\nfig = make_subplots(specs=[[{\"secondary_y\": True}]])\n\n# Add traces\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_적컨_TEU']/1000,\n               name=\"적컨 TEU (천)\",\n               line=dict(color='#ff6f91'),\n               fill='tozeroy'),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_공컨_TEU']/1000,\n               name=\"공컨 TEU (천)\",\n               line=dict(color='#ff9671'),\n               fill='tozeroy'),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_톤수']/1000000,\n               name=\"톤수 (백만)\",\n               line=dict(color='#2c73d2'),\n               fill='tozeroy'),\n    secondary_y=True,\n)\n\n# Add trendlines\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_적컨_TEU'].rolling(window=3).mean()/1000,\n               name=\"적컨 TEU Trend\",\n               line=dict(color='#ff6f91', dash='dash')),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_공컨_TEU'].rolling(window=3).mean()/1000,\n               name=\"공컨 TEU Trend\",\n               line=dict(color='#ff9671', dash='dash')),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_톤수'].rolling(window=3).mean()/1000000,\n               name=\"톤수 Trend\",\n               line=dict(color='#2c73d2', dash='dash')),\n    secondary_y=True,\n)\n\n# Update layout\nfig.update_layout(\n    legend=dict(\n        orientation=\"h\",\n        yanchor=\"bottom\",\n        y=1.02,\n        xanchor=\"center\",\n        x=0.5\n    ),\n    plot_bgcolor='white',\n    xaxis=dict(\n        title=\"년-월\",\n        showgrid=True,\n        gridcolor='lightgray',\n        tickangle=-45,\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    yaxis=dict(\n        title=\"적컨/공컨 TEU (천)\",\n        showgrid=True,\n        gridcolor='lightgray',\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    yaxis2=dict(\n        title=\"톤수 (백만)\",\n        showgrid=False,\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    margin=dict(l=50, r=50, t=50, b=100),\n    hovermode='x unified'\n)\n\nfig.show()\n```\n``` ```python\nimport matplotlib.pyplot as plt\nimport pandas as pd\n\nplt.rcParams[\"font.family\"] = 'NanumGothic'\n\nDF['년도'] = DF['년도'].astype(str)\nDF['년월'] = DF['년도'].str[-2:] + '.' + DF['월'].astype(str)\n\nfig = plt.figure(figsize=(20,20))\n\n# subplot 1: 총_적컨_TEU\nplt.subplot(3,1,1)\nplt.plot(DF['년월'], DF['총_적컨_TEU']/1000, marker='o', label='적컨 TEU')\nplt.title('부산항 총 적컨 TEU 추이')\nplt.xlabel('년-월')\nplt.ylabel('적컨 TEU (천)')\nplt.grid(True)\nplt.legend()\n\n# subplot 2: 총_공컨_TEU\nplt.subplot(3,1,2)\nplt.plot(DF['년월'], DF['총_공컨_TEU']/1000, marker='^', label='공컨 TEU')\nplt.title('부산항 총 공컨 TEU 추이')\nplt.xlabel('년-월')\nplt.ylabel('공컨 TEU (천)')\nplt.grid(True)\nplt.legend()\n\n# subplot 3: 총_톤수\nplt.subplot(3,1,3)\nplt.bar(DF['년월'], DF['총_톤수']/1000000, color='green', label='총 톤수')\nplt.title('부산항 총 톤수 추이')\nplt.xlabel('년-월')\nplt.ylabel('톤수 (백만)')\nplt.grid(True)\nplt.legend()\n\nplt.show()\n```\n```",
        "plot": "",
        "relevant_query": []
    }
    return dummy_data


def dummy_harbor1():
    dummy_data = {
        "source": [],
        "data": "```sql\nSELECT \n    '부산항' AS 항구명,\n    data.YYYY AS 년,\n    data.MM AS 월,\n    SUM(CASE WHEN data.IO_TP = 'II' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수입,\n    SUM(CASE WHEN data.IO_TP = 'OO' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수출,\n    SUM(CASE WHEN data.IO_TP = 'IT' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수입환적,\n    SUM(CASE WHEN data.IO_TP = 'OT' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수출환적\nFROM \n    data\nWHERE \n    data.PRT_AT_CODE IN (020, 021, 022) AND \n    data.YYYY = 2022\nGROUP BY \n    년, 월;\n```\n이 SQL 쿼리는 부산항(코드 020, 021, 022)에서 2022년에 발생한 수입, 수출, 수입환적, 수출환적의 적컨 TEU 수량을 월별로 집계합니다. 이때, 아국선과 외국선의 적컨 TEU 수량을 합산하여 결과를 제공합니다. | 항구명   |   년 |   월 |   수입 |   수출 |   수입환적 |   수출환적 |\n|:---------|-----:|-----:|-------:|-------:|-----------:|-----------:|\n| 부산항   | 2022 |    1 | 283138 | 362682 |     528216 |     507601 |\n| 부산항   | 2022 |    2 | 223267 | 346902 |     422894 |     473787 | ### 해석\n\n#### 총 적컨 TEU (Twenty-foot Equivalent Unit)\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 1.519M | 1.387M | 1.672M | 1.485M | 18.23M |\n| 2021 | 1.629M | 1.441M | 1.712M | 1.631M | 19.54M |\n| 2022 | 1.559M | 1.324M | 1.736M | 1.571M | 18.71M |\n\n2020년에서 2021년으로 넘어가면서 총 적컨 TEU의 평균이 약 7% 증가하였고, 이는 2021년에 더 많은 컨테이너가 처리되었음을 의미합니다. 그러나 2021년에서 2022년으로 넘어가면서 총 적컨 TEU의 평균은 약 4% 감소하였습니다.\n\n#### 총 공컨 TEU\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 299.6K | 243.1K | 355.9K | 286.3K | 3.595M |\n| 2021 | 263.4K | 220.4K | 308.5K | 266.8K | 3.161M |\n| 2022 | 280.9K | 236.3K | 302.5K | 285.9K | 3.371M |\n\n총 공컨 TEU의 경우, 2020년에서 2021년으로 넘어가면서 평균이 약 12% 감소하였으나, 2021년에서 2022년으로 넘어가면서 다시 약 6% 증가하였습니다.\n\n#### 총 톤수\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 112.8M | 103.0M | 126.5M | 110.8M | 1.354B |\n| 2021 | 102.2M | 95.4M | 113.3M | 101.4M | 1.226B |\n| 2022 | 103.8M | 93.3M | 117.4M | 103.0M | 1.246B |\n\n총 톤수의 경우, 2020년에서 2021년으로 넘어가면서 평균이 약 9% 감소하였으나, 2021년에서 2022년으로 넘어가면서 약 2% 증가하였습니다.\n\n결론적으로, 부산항의 물동량은 2020년에서 2021년으로 넘어가면서 감소하였으나, 2021년에서 2022년으로 넘어가면서 다시 증가하였습니다. 이는 전 세계적인 공급망 혼란과 관련이 있을 수 있습니다. ```python\nimport plotly.graph_objects as go\nfrom plotly.subplots import make_subplots\n\n# Create figure with secondary y-axis\nfig = make_subplots(specs=[[{\"secondary_y\": True}]])\n\n# Add traces\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_적컨_TEU']/1000,\n               name=\"적컨 TEU (천)\",\n               line=dict(color='#ff6f91'),\n               fill='tozeroy'),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_공컨_TEU']/1000,\n               name=\"공컨 TEU (천)\",\n               line=dict(color='#ff9671'),\n               fill='tozeroy'),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_톤수']/1000000,\n               name=\"톤수 (백만)\",\n               line=dict(color='#2c73d2'),\n               fill='tozeroy'),\n    secondary_y=True,\n)\n\n# Add trendlines\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_적컨_TEU'].rolling(window=3).mean()/1000,\n               name=\"적컨 TEU Trend\",\n               line=dict(color='#ff6f91', dash='dash')),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_공컨_TEU'].rolling(window=3).mean()/1000,\n               name=\"공컨 TEU Trend\",\n               line=dict(color='#ff9671', dash='dash')),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_톤수'].rolling(window=3).mean()/1000000,\n               name=\"톤수 Trend\",\n               line=dict(color='#2c73d2', dash='dash')),\n    secondary_y=True,\n)\n\n# Update layout\nfig.update_layout(\n    legend=dict(\n        orientation=\"h\",\n        yanchor=\"bottom\",\n        y=1.02,\n        xanchor=\"center\",\n        x=0.5\n    ),\n    plot_bgcolor='white',\n    xaxis=dict(\n        title=\"년-월\",\n        showgrid=True,\n        gridcolor='lightgray',\n        tickangle=-45,\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    yaxis=dict(\n        title=\"적컨/공컨 TEU (천)\",\n        showgrid=True,\n        gridcolor='lightgray',\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    yaxis2=dict(\n        title=\"톤수 (백만)\",\n        showgrid=False,\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    margin=dict(l=50, r=50, t=50, b=100),\n    hovermode='x unified'\n)\n\nfig.show()\n```\n``` ```python\nimport matplotlib.pyplot as plt\nimport pandas as pd\n\nplt.rcParams[\"font.family\"] = 'NanumGothic'\n\nDF['년도'] = DF['년도'].astype(str)\nDF['년월'] = DF['년도'].str[-2:] + '.' + DF['월'].astype(str)\n\nfig = plt.figure(figsize=(20,20))\n\n# subplot 1: 총_적컨_TEU\nplt.subplot(3,1,1)\nplt.plot(DF['년월'], DF['총_적컨_TEU']/1000, marker='o', label='적컨 TEU')\nplt.title('부산항 총 적컨 TEU 추이')\nplt.xlabel('년-월')\nplt.ylabel('적컨 TEU (천)')\nplt.grid(True)\nplt.legend()\n\n# subplot 2: 총_공컨_TEU\nplt.subplot(3,1,2)\nplt.plot(DF['년월'], DF['총_공컨_TEU']/1000, marker='^', label='공컨 TEU')\nplt.title('부산항 총 공컨 TEU 추이')\nplt.xlabel('년-월')\nplt.ylabel('공컨 TEU (천)')\nplt.grid(True)\nplt.legend()\n\n# subplot 3: 총_톤수\nplt.subplot(3,1,3)\nplt.bar(DF['년월'], DF['총_톤수']/1000000, color='green', label='총 톤수')\nplt.title('부산항 총 톤수 추이')\nplt.xlabel('년-월')\nplt.ylabel('톤수 (백만)')\nplt.grid(True)\nplt.legend()\n\nplt.show()\n```\n```",
        "plot": "{\"data\":[{\"fill\":\"tozeroy\",\"line\":{\"color\":\"#ff6f91\"},\"name\":\"적컨 TEU (천)\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[1480.034,1386.836,1632.977,1473.259,1418.281,1462.543,1488.0,1481.185,1492.215,1634.533,1672.08,1606.644,1585.279,1441.487,1708.253,1675.725,1710.493,1655.437,1691.635,1605.839,1578.527,1712.036,1578.153,1602.182,1681.637,1466.85,1579.544,1610.511,1667.134,1561.736,1736.401,1604.819,1323.57,1544.64,1491.306,1437.9],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"fill\":\"tozeroy\",\"line\":{\"color\":\"#ff9671\"},\"name\":\"공컨 TEU (천)\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[324.938,349.837,354.947,355.992,327.938,295.743,277.008,262.094,243.123,269.867,262.27,271.544,265.684,245.338,308.538,282.995,304.278,267.926,269.618,232.298,220.41,268.897,232.288,262.744,285.118,276.109,296.119,288.917,295.832,248.436,272.201,286.808,236.311,284.381,297.932,302.505],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"fill\":\"tozeroy\",\"line\":{\"color\":\"#2c73d2\"},\"name\":\"톤수 (백만)\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[111.07195,126.478534,123.241457,110.521404,108.684364,107.795766,117.44919,112.753658,102.965941,113.38544,109.855189,109.443379,105.290224,95.678664,113.287226,99.064887,109.157894,103.630062,103.263432,96.714386,95.431213,107.998558,97.105918,99.565344,101.82665,97.044618,101.546515,104.522673,102.281592,96.65094,108.274752,103.666215,93.309833,112.586215,117.401907,107.090671],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y2\"},{\"line\":{\"color\":\"#ff6f91\",\"dash\":\"dash\"},\"name\":\"적컨 TEU Trend\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[null,null,1499.949,1497.6906666666669,1508.1723333333332,1451.361,1456.2746666666667,1477.2426666666668,1487.1333333333332,1535.9776666666667,1599.6093333333333,1637.7523333333334,1621.3343333333332,1544.47,1578.3396666666667,1608.4883333333332,1698.157,1680.5516666666667,1685.855,1650.9703333333332,1625.3336666666667,1632.134,1622.9053333333331,1630.7903333333334,1620.6573333333333,1583.5563333333332,1576.0103333333332,1552.3016666666667,1619.063,1613.127,1655.0903333333333,1634.3186666666668,1554.93,1491.0096666666668,1453.172,1491.282],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"line\":{\"color\":\"#ff9671\",\"dash\":\"dash\"},\"name\":\"공컨 TEU Trend\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[null,null,343.2406666666667,353.592,346.2923333333333,326.5576666666667,300.2296666666667,278.2816666666667,260.7416666666667,258.36133333333333,258.42,267.89366666666666,266.4993333333333,260.85533333333336,273.18666666666667,278.957,298.6036666666667,285.0663333333333,280.6073333333333,256.614,240.77533333333335,240.535,240.53166666666667,254.643,260.05,274.657,285.782,287.0483333333333,293.6226666666667,277.7283333333333,272.1563333333333,269.1483333333333,265.1066666666667,269.1666666666667,272.8746666666667,294.9393333333333],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"line\":{\"color\":\"#2c73d2\",\"dash\":\"dash\"},\"name\":\"톤수 Trend\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[null,null,120.26398033333332,120.080465,114.149075,109.00051133333332,111.30977333333333,112.66620466666667,111.056263,109.70167966666668,108.73552333333333,110.89466933333333,108.196264,103.47075566666668,104.752038,102.67692566666668,107.17000233333333,103.95094766666668,105.35046266666667,101.20262666666667,98.469677,100.04805233333333,100.178563,101.55660666666667,99.499304,99.47887066666667,100.139261,101.03793533333332,102.78359333333333,101.151735,102.402428,102.863969,101.75026666666668,103.187421,107.765985,112.35959766666667],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y2\"}],\"layout\":{\"template\":{\"data\":{\"histogram2dcontour\":[{\"type\":\"histogram2dcontour\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"choropleth\":[{\"type\":\"choropleth\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}],\"histogram2d\":[{\"type\":\"histogram2d\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"heatmap\":[{\"type\":\"heatmap\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"heatmapgl\":[{\"type\":\"heatmapgl\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"contourcarpet\":[{\"type\":\"contourcarpet\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}],\"contour\":[{\"type\":\"contour\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"surface\":[{\"type\":\"surface\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"mesh3d\":[{\"type\":\"mesh3d\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}],\"scatter\":[{\"fillpattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2},\"type\":\"scatter\"}],\"parcoords\":[{\"type\":\"parcoords\",\"line\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatterpolargl\":[{\"type\":\"scatterpolargl\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"bar\":[{\"error_x\":{\"color\":\"#2a3f5f\"},\"error_y\":{\"color\":\"#2a3f5f\"},\"marker\":{\"line\":{\"color\":\"#E5ECF6\",\"width\":0.5},\"pattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2}},\"type\":\"bar\"}],\"scattergeo\":[{\"type\":\"scattergeo\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatterpolar\":[{\"type\":\"scatterpolar\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"histogram\":[{\"marker\":{\"pattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2}},\"type\":\"histogram\"}],\"scattergl\":[{\"type\":\"scattergl\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatter3d\":[{\"type\":\"scatter3d\",\"line\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}},\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scattermapbox\":[{\"type\":\"scattermapbox\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatterternary\":[{\"type\":\"scatterternary\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scattercarpet\":[{\"type\":\"scattercarpet\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"carpet\":[{\"aaxis\":{\"endlinecolor\":\"#2a3f5f\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"minorgridcolor\":\"white\",\"startlinecolor\":\"#2a3f5f\"},\"baxis\":{\"endlinecolor\":\"#2a3f5f\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"minorgridcolor\":\"white\",\"startlinecolor\":\"#2a3f5f\"},\"type\":\"carpet\"}],\"table\":[{\"cells\":{\"fill\":{\"color\":\"#EBF0F8\"},\"line\":{\"color\":\"white\"}},\"header\":{\"fill\":{\"color\":\"#C8D4E3\"},\"line\":{\"color\":\"white\"}},\"type\":\"table\"}],\"barpolar\":[{\"marker\":{\"line\":{\"color\":\"#E5ECF6\",\"width\":0.5},\"pattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2}},\"type\":\"barpolar\"}],\"pie\":[{\"automargin\":true,\"type\":\"pie\"}]},\"layout\":{\"autotypenumbers\":\"strict\",\"colorway\":[\"#636efa\",\"#EF553B\",\"#00cc96\",\"#ab63fa\",\"#FFA15A\",\"#19d3f3\",\"#FF6692\",\"#B6E880\",\"#FF97FF\",\"#FECB52\"],\"font\":{\"color\":\"#2a3f5f\"},\"hovermode\":\"closest\",\"hoverlabel\":{\"align\":\"left\"},\"paper_bgcolor\":\"white\",\"plot_bgcolor\":\"#E5ECF6\",\"polar\":{\"bgcolor\":\"#E5ECF6\",\"angularaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"},\"radialaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"}},\"ternary\":{\"bgcolor\":\"#E5ECF6\",\"aaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"},\"baxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"},\"caxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"}},\"coloraxis\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}},\"colorscale\":{\"sequential\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]],\"sequentialminus\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]],\"diverging\":[[0,\"#8e0152\"],[0.1,\"#c51b7d\"],[0.2,\"#de77ae\"],[0.3,\"#f1b6da\"],[0.4,\"#fde0ef\"],[0.5,\"#f7f7f7\"],[0.6,\"#e6f5d0\"],[0.7,\"#b8e186\"],[0.8,\"#7fbc41\"],[0.9,\"#4d9221\"],[1,\"#276419\"]]},\"xaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\",\"title\":{\"standoff\":15},\"zerolinecolor\":\"white\",\"automargin\":true,\"zerolinewidth\":2},\"yaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\",\"title\":{\"standoff\":15},\"zerolinecolor\":\"white\",\"automargin\":true,\"zerolinewidth\":2},\"scene\":{\"xaxis\":{\"backgroundcolor\":\"#E5ECF6\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"showbackground\":true,\"ticks\":\"\",\"zerolinecolor\":\"white\",\"gridwidth\":2},\"yaxis\":{\"backgroundcolor\":\"#E5ECF6\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"showbackground\":true,\"ticks\":\"\",\"zerolinecolor\":\"white\",\"gridwidth\":2},\"zaxis\":{\"backgroundcolor\":\"#E5ECF6\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"showbackground\":true,\"ticks\":\"\",\"zerolinecolor\":\"white\",\"gridwidth\":2}},\"shapedefaults\":{\"line\":{\"color\":\"#2a3f5f\"}},\"annotationdefaults\":{\"arrowcolor\":\"#2a3f5f\",\"arrowhead\":0,\"arrowwidth\":1},\"geo\":{\"bgcolor\":\"white\",\"landcolor\":\"#E5ECF6\",\"subunitcolor\":\"white\",\"showland\":true,\"showlakes\":true,\"lakecolor\":\"white\"},\"title\":{\"x\":0.05},\"mapbox\":{\"style\":\"light\"}}},\"xaxis\":{\"anchor\":\"y\",\"domain\":[0.0,0.94],\"title\":{\"text\":\"년-월\"},\"showgrid\":true,\"gridcolor\":\"lightgray\",\"tickangle\":-45,\"ticks\":\"outside\",\"tickwidth\":2,\"ticklen\":5},\"yaxis\":{\"anchor\":\"x\",\"domain\":[0.0,1.0],\"title\":{\"text\":\"적컨\\u002f공컨 TEU (천)\"},\"showgrid\":true,\"gridcolor\":\"lightgray\",\"ticks\":\"outside\",\"tickwidth\":2,\"ticklen\":5},\"yaxis2\":{\"anchor\":\"x\",\"overlaying\":\"y\",\"side\":\"right\",\"title\":{\"text\":\"톤수 (백만)\"},\"showgrid\":false,\"ticks\":\"outside\",\"tickwidth\":2,\"ticklen\":5},\"legend\":{\"orientation\":\"h\",\"yanchor\":\"bottom\",\"y\":1.02,\"xanchor\":\"center\",\"x\":0.5},\"margin\":{\"l\":50,\"r\":50,\"t\":50,\"b\":100},\"plot_bgcolor\":\"white\",\"hovermode\":\"x unified\"}}",
        "relevant_query": ["2020년부터 2022년까지 부산항의 출항 선박 수는 어떻게 변했나요?", "2020년부터 2022년까지 부산항에서의 수입 환적 추이에 대해 알려주실 수 있나요?", "2023년 1월 부산항의 입항 선박 수는 얼마나 될까요?", "2024년 12월까지 부산항의 수출 환적 추이를 확인할 수 있을까요?"]
    }
    return dummy_data


def dummy_harbor2():
    dummy_data = {
        "source": [
            {
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
            }
        ],
        "data": "```sql\nSELECT \n    '부산항' AS 항구명,\n    data.YYYY AS 년,\n    data.MM AS 월,\n    SUM(CASE WHEN data.IO_TP = 'II' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수입,\n    SUM(CASE WHEN data.IO_TP = 'OO' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수출,\n    SUM(CASE WHEN data.IO_TP = 'IT' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수입환적,\n    SUM(CASE WHEN data.IO_TP = 'OT' THEN data.KOR_FULL_TEU + data.FOR_FULL_TEU ELSE 0 END) AS 수출환적\nFROM \n    data\nWHERE \n    data.PRT_AT_CODE IN (020, 021, 022) AND \n    data.YYYY = 2022\nGROUP BY \n    년, 월;\n```\n이 SQL 쿼리는 부산항(코드 020, 021, 022)에서 2022년에 발생한 수입, 수출, 수입환적, 수출환적의 적컨 TEU 수량을 월별로 집계합니다. 이때, 아국선과 외국선의 적컨 TEU 수량을 합산하여 결과를 제공합니다. | 항구명   |   년 |   월 |   수입 |   수출 |   수입환적 |   수출환적 |\n|:---------|-----:|-----:|-------:|-------:|-----------:|-----------:|\n| 부산항   | 2022 |    1 | 283138 | 362682 |     528216 |     507601 |\n| 부산항   | 2022 |    2 | 223267 | 346902 |     422894 |     473787 | ### 해석\n\n#### 총 적컨 TEU (Twenty-foot Equivalent Unit)\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 1.519M | 1.387M | 1.672M | 1.485M | 18.23M |\n| 2021 | 1.629M | 1.441M | 1.712M | 1.631M | 19.54M |\n| 2022 | 1.559M | 1.324M | 1.736M | 1.571M | 18.71M |\n\n2020년에서 2021년으로 넘어가면서 총 적컨 TEU의 평균이 약 7% 증가하였고, 이는 2021년에 더 많은 컨테이너가 처리되었음을 의미합니다. 그러나 2021년에서 2022년으로 넘어가면서 총 적컨 TEU의 평균은 약 4% 감소하였습니다.\n\n#### 총 공컨 TEU\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 299.6K | 243.1K | 355.9K | 286.3K | 3.595M |\n| 2021 | 263.4K | 220.4K | 308.5K | 266.8K | 3.161M |\n| 2022 | 280.9K | 236.3K | 302.5K | 285.9K | 3.371M |\n\n총 공컨 TEU의 경우, 2020년에서 2021년으로 넘어가면서 평균이 약 12% 감소하였으나, 2021년에서 2022년으로 넘어가면서 다시 약 6% 증가하였습니다.\n\n#### 총 톤수\n\n| 년도 | 평균 | 최소 | 최대 | 중앙값 | 합계 |\n|------|------|------|------|--------|------|\n| 2020 | 112.8M | 103.0M | 126.5M | 110.8M | 1.354B |\n| 2021 | 102.2M | 95.4M | 113.3M | 101.4M | 1.226B |\n| 2022 | 103.8M | 93.3M | 117.4M | 103.0M | 1.246B |\n\n총 톤수의 경우, 2020년에서 2021년으로 넘어가면서 평균이 약 9% 감소하였으나, 2021년에서 2022년으로 넘어가면서 약 2% 증가하였습니다.\n\n결론적으로, 부산항의 물동량은 2020년에서 2021년으로 넘어가면서 감소하였으나, 2021년에서 2022년으로 넘어가면서 다시 증가하였습니다. 이는 전 세계적인 공급망 혼란과 관련이 있을 수 있습니다. ```python\nimport plotly.graph_objects as go\nfrom plotly.subplots import make_subplots\n\n# Create figure with secondary y-axis\nfig = make_subplots(specs=[[{\"secondary_y\": True}]])\n\n# Add traces\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_적컨_TEU']/1000,\n               name=\"적컨 TEU (천)\",\n               line=dict(color='#ff6f91'),\n               fill='tozeroy'),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_공컨_TEU']/1000,\n               name=\"공컨 TEU (천)\",\n               line=dict(color='#ff9671'),\n               fill='tozeroy'),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_톤수']/1000000,\n               name=\"톤수 (백만)\",\n               line=dict(color='#2c73d2'),\n               fill='tozeroy'),\n    secondary_y=True,\n)\n\n# Add trendlines\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_적컨_TEU'].rolling(window=3).mean()/1000,\n               name=\"적컨 TEU Trend\",\n               line=dict(color='#ff6f91', dash='dash')),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_공컨_TEU'].rolling(window=3).mean()/1000,\n               name=\"공컨 TEU Trend\",\n               line=dict(color='#ff9671', dash='dash')),\n    secondary_y=False,\n)\n\nfig.add_trace(\n    go.Scatter(x=[str(int(str(i['년도'])[-2:]))+'.'+str(i['월']) for i in DF.to_dict('records')],\n               y=DF['총_톤수'].rolling(window=3).mean()/1000000,\n               name=\"톤수 Trend\",\n               line=dict(color='#2c73d2', dash='dash')),\n    secondary_y=True,\n)\n\n# Update layout\nfig.update_layout(\n    legend=dict(\n        orientation=\"h\",\n        yanchor=\"bottom\",\n        y=1.02,\n        xanchor=\"center\",\n        x=0.5\n    ),\n    plot_bgcolor='white',\n    xaxis=dict(\n        title=\"년-월\",\n        showgrid=True,\n        gridcolor='lightgray',\n        tickangle=-45,\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    yaxis=dict(\n        title=\"적컨/공컨 TEU (천)\",\n        showgrid=True,\n        gridcolor='lightgray',\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    yaxis2=dict(\n        title=\"톤수 (백만)\",\n        showgrid=False,\n        ticks=\"outside\",\n        tickwidth=2,\n        ticklen=5\n    ),\n    margin=dict(l=50, r=50, t=50, b=100),\n    hovermode='x unified'\n)\n\nfig.show()\n```\n``` ```python\nimport matplotlib.pyplot as plt\nimport pandas as pd\n\nplt.rcParams[\"font.family\"] = 'NanumGothic'\n\nDF['년도'] = DF['년도'].astype(str)\nDF['년월'] = DF['년도'].str[-2:] + '.' + DF['월'].astype(str)\n\nfig = plt.figure(figsize=(20,20))\n\n# subplot 1: 총_적컨_TEU\nplt.subplot(3,1,1)\nplt.plot(DF['년월'], DF['총_적컨_TEU']/1000, marker='o', label='적컨 TEU')\nplt.title('부산항 총 적컨 TEU 추이')\nplt.xlabel('년-월')\nplt.ylabel('적컨 TEU (천)')\nplt.grid(True)\nplt.legend()\n\n# subplot 2: 총_공컨_TEU\nplt.subplot(3,1,2)\nplt.plot(DF['년월'], DF['총_공컨_TEU']/1000, marker='^', label='공컨 TEU')\nplt.title('부산항 총 공컨 TEU 추이')\nplt.xlabel('년-월')\nplt.ylabel('공컨 TEU (천)')\nplt.grid(True)\nplt.legend()\n\n# subplot 3: 총_톤수\nplt.subplot(3,1,3)\nplt.bar(DF['년월'], DF['총_톤수']/1000000, color='green', label='총 톤수')\nplt.title('부산항 총 톤수 추이')\nplt.xlabel('년-월')\nplt.ylabel('톤수 (백만)')\nplt.grid(True)\nplt.legend()\n\nplt.show()\n```\n```",
        "plot": "{\"data\":[{\"fill\":\"tozeroy\",\"line\":{\"color\":\"#ff6f91\"},\"name\":\"적컨 TEU (천)\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[1480.034,1386.836,1632.977,1473.259,1418.281,1462.543,1488.0,1481.185,1492.215,1634.533,1672.08,1606.644,1585.279,1441.487,1708.253,1675.725,1710.493,1655.437,1691.635,1605.839,1578.527,1712.036,1578.153,1602.182,1681.637,1466.85,1579.544,1610.511,1667.134,1561.736,1736.401,1604.819,1323.57,1544.64,1491.306,1437.9],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"fill\":\"tozeroy\",\"line\":{\"color\":\"#ff9671\"},\"name\":\"공컨 TEU (천)\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[324.938,349.837,354.947,355.992,327.938,295.743,277.008,262.094,243.123,269.867,262.27,271.544,265.684,245.338,308.538,282.995,304.278,267.926,269.618,232.298,220.41,268.897,232.288,262.744,285.118,276.109,296.119,288.917,295.832,248.436,272.201,286.808,236.311,284.381,297.932,302.505],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"fill\":\"tozeroy\",\"line\":{\"color\":\"#2c73d2\"},\"name\":\"톤수 (백만)\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[111.07195,126.478534,123.241457,110.521404,108.684364,107.795766,117.44919,112.753658,102.965941,113.38544,109.855189,109.443379,105.290224,95.678664,113.287226,99.064887,109.157894,103.630062,103.263432,96.714386,95.431213,107.998558,97.105918,99.565344,101.82665,97.044618,101.546515,104.522673,102.281592,96.65094,108.274752,103.666215,93.309833,112.586215,117.401907,107.090671],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y2\"},{\"line\":{\"color\":\"#ff6f91\",\"dash\":\"dash\"},\"name\":\"적컨 TEU Trend\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[null,null,1499.949,1497.6906666666669,1508.1723333333332,1451.361,1456.2746666666667,1477.2426666666668,1487.1333333333332,1535.9776666666667,1599.6093333333333,1637.7523333333334,1621.3343333333332,1544.47,1578.3396666666667,1608.4883333333332,1698.157,1680.5516666666667,1685.855,1650.9703333333332,1625.3336666666667,1632.134,1622.9053333333331,1630.7903333333334,1620.6573333333333,1583.5563333333332,1576.0103333333332,1552.3016666666667,1619.063,1613.127,1655.0903333333333,1634.3186666666668,1554.93,1491.0096666666668,1453.172,1491.282],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"line\":{\"color\":\"#ff9671\",\"dash\":\"dash\"},\"name\":\"공컨 TEU Trend\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[null,null,343.2406666666667,353.592,346.2923333333333,326.5576666666667,300.2296666666667,278.2816666666667,260.7416666666667,258.36133333333333,258.42,267.89366666666666,266.4993333333333,260.85533333333336,273.18666666666667,278.957,298.6036666666667,285.0663333333333,280.6073333333333,256.614,240.77533333333335,240.535,240.53166666666667,254.643,260.05,274.657,285.782,287.0483333333333,293.6226666666667,277.7283333333333,272.1563333333333,269.1483333333333,265.1066666666667,269.1666666666667,272.8746666666667,294.9393333333333],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y\"},{\"line\":{\"color\":\"#2c73d2\",\"dash\":\"dash\"},\"name\":\"톤수 Trend\",\"x\":[\"20.1\",\"20.2\",\"20.3\",\"20.4\",\"20.5\",\"20.6\",\"20.7\",\"20.8\",\"20.9\",\"20.10\",\"20.11\",\"20.12\",\"21.1\",\"21.2\",\"21.3\",\"21.4\",\"21.5\",\"21.6\",\"21.7\",\"21.8\",\"21.9\",\"21.10\",\"21.11\",\"21.12\",\"22.1\",\"22.2\",\"22.3\",\"22.4\",\"22.5\",\"22.6\",\"22.7\",\"22.8\",\"22.9\",\"22.10\",\"22.11\",\"22.12\"],\"y\":[null,null,120.26398033333332,120.080465,114.149075,109.00051133333332,111.30977333333333,112.66620466666667,111.056263,109.70167966666668,108.73552333333333,110.89466933333333,108.196264,103.47075566666668,104.752038,102.67692566666668,107.17000233333333,103.95094766666668,105.35046266666667,101.20262666666667,98.469677,100.04805233333333,100.178563,101.55660666666667,99.499304,99.47887066666667,100.139261,101.03793533333332,102.78359333333333,101.151735,102.402428,102.863969,101.75026666666668,103.187421,107.765985,112.35959766666667],\"type\":\"scatter\",\"xaxis\":\"x\",\"yaxis\":\"y2\"}],\"layout\":{\"template\":{\"data\":{\"histogram2dcontour\":[{\"type\":\"histogram2dcontour\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"choropleth\":[{\"type\":\"choropleth\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}],\"histogram2d\":[{\"type\":\"histogram2d\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"heatmap\":[{\"type\":\"heatmap\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"heatmapgl\":[{\"type\":\"heatmapgl\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"contourcarpet\":[{\"type\":\"contourcarpet\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}],\"contour\":[{\"type\":\"contour\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"surface\":[{\"type\":\"surface\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"},\"colorscale\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]]}],\"mesh3d\":[{\"type\":\"mesh3d\",\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}],\"scatter\":[{\"fillpattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2},\"type\":\"scatter\"}],\"parcoords\":[{\"type\":\"parcoords\",\"line\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatterpolargl\":[{\"type\":\"scatterpolargl\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"bar\":[{\"error_x\":{\"color\":\"#2a3f5f\"},\"error_y\":{\"color\":\"#2a3f5f\"},\"marker\":{\"line\":{\"color\":\"#E5ECF6\",\"width\":0.5},\"pattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2}},\"type\":\"bar\"}],\"scattergeo\":[{\"type\":\"scattergeo\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatterpolar\":[{\"type\":\"scatterpolar\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"histogram\":[{\"marker\":{\"pattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2}},\"type\":\"histogram\"}],\"scattergl\":[{\"type\":\"scattergl\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatter3d\":[{\"type\":\"scatter3d\",\"line\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}},\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scattermapbox\":[{\"type\":\"scattermapbox\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scatterternary\":[{\"type\":\"scatterternary\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"scattercarpet\":[{\"type\":\"scattercarpet\",\"marker\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}}}],\"carpet\":[{\"aaxis\":{\"endlinecolor\":\"#2a3f5f\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"minorgridcolor\":\"white\",\"startlinecolor\":\"#2a3f5f\"},\"baxis\":{\"endlinecolor\":\"#2a3f5f\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"minorgridcolor\":\"white\",\"startlinecolor\":\"#2a3f5f\"},\"type\":\"carpet\"}],\"table\":[{\"cells\":{\"fill\":{\"color\":\"#EBF0F8\"},\"line\":{\"color\":\"white\"}},\"header\":{\"fill\":{\"color\":\"#C8D4E3\"},\"line\":{\"color\":\"white\"}},\"type\":\"table\"}],\"barpolar\":[{\"marker\":{\"line\":{\"color\":\"#E5ECF6\",\"width\":0.5},\"pattern\":{\"fillmode\":\"overlay\",\"size\":10,\"solidity\":0.2}},\"type\":\"barpolar\"}],\"pie\":[{\"automargin\":true,\"type\":\"pie\"}]},\"layout\":{\"autotypenumbers\":\"strict\",\"colorway\":[\"#636efa\",\"#EF553B\",\"#00cc96\",\"#ab63fa\",\"#FFA15A\",\"#19d3f3\",\"#FF6692\",\"#B6E880\",\"#FF97FF\",\"#FECB52\"],\"font\":{\"color\":\"#2a3f5f\"},\"hovermode\":\"closest\",\"hoverlabel\":{\"align\":\"left\"},\"paper_bgcolor\":\"white\",\"plot_bgcolor\":\"#E5ECF6\",\"polar\":{\"bgcolor\":\"#E5ECF6\",\"angularaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"},\"radialaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"}},\"ternary\":{\"bgcolor\":\"#E5ECF6\",\"aaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"},\"baxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"},\"caxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\"}},\"coloraxis\":{\"colorbar\":{\"outlinewidth\":0,\"ticks\":\"\"}},\"colorscale\":{\"sequential\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]],\"sequentialminus\":[[0.0,\"#0d0887\"],[0.1111111111111111,\"#46039f\"],[0.2222222222222222,\"#7201a8\"],[0.3333333333333333,\"#9c179e\"],[0.4444444444444444,\"#bd3786\"],[0.5555555555555556,\"#d8576b\"],[0.6666666666666666,\"#ed7953\"],[0.7777777777777778,\"#fb9f3a\"],[0.8888888888888888,\"#fdca26\"],[1.0,\"#f0f921\"]],\"diverging\":[[0,\"#8e0152\"],[0.1,\"#c51b7d\"],[0.2,\"#de77ae\"],[0.3,\"#f1b6da\"],[0.4,\"#fde0ef\"],[0.5,\"#f7f7f7\"],[0.6,\"#e6f5d0\"],[0.7,\"#b8e186\"],[0.8,\"#7fbc41\"],[0.9,\"#4d9221\"],[1,\"#276419\"]]},\"xaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\",\"title\":{\"standoff\":15},\"zerolinecolor\":\"white\",\"automargin\":true,\"zerolinewidth\":2},\"yaxis\":{\"gridcolor\":\"white\",\"linecolor\":\"white\",\"ticks\":\"\",\"title\":{\"standoff\":15},\"zerolinecolor\":\"white\",\"automargin\":true,\"zerolinewidth\":2},\"scene\":{\"xaxis\":{\"backgroundcolor\":\"#E5ECF6\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"showbackground\":true,\"ticks\":\"\",\"zerolinecolor\":\"white\",\"gridwidth\":2},\"yaxis\":{\"backgroundcolor\":\"#E5ECF6\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"showbackground\":true,\"ticks\":\"\",\"zerolinecolor\":\"white\",\"gridwidth\":2},\"zaxis\":{\"backgroundcolor\":\"#E5ECF6\",\"gridcolor\":\"white\",\"linecolor\":\"white\",\"showbackground\":true,\"ticks\":\"\",\"zerolinecolor\":\"white\",\"gridwidth\":2}},\"shapedefaults\":{\"line\":{\"color\":\"#2a3f5f\"}},\"annotationdefaults\":{\"arrowcolor\":\"#2a3f5f\",\"arrowhead\":0,\"arrowwidth\":1},\"geo\":{\"bgcolor\":\"white\",\"landcolor\":\"#E5ECF6\",\"subunitcolor\":\"white\",\"showland\":true,\"showlakes\":true,\"lakecolor\":\"white\"},\"title\":{\"x\":0.05},\"mapbox\":{\"style\":\"light\"}}},\"xaxis\":{\"anchor\":\"y\",\"domain\":[0.0,0.94],\"title\":{\"text\":\"년-월\"},\"showgrid\":true,\"gridcolor\":\"lightgray\",\"tickangle\":-45,\"ticks\":\"outside\",\"tickwidth\":2,\"ticklen\":5},\"yaxis\":{\"anchor\":\"x\",\"domain\":[0.0,1.0],\"title\":{\"text\":\"적컨\\u002f공컨 TEU (천)\"},\"showgrid\":true,\"gridcolor\":\"lightgray\",\"ticks\":\"outside\",\"tickwidth\":2,\"ticklen\":5},\"yaxis2\":{\"anchor\":\"x\",\"overlaying\":\"y\",\"side\":\"right\",\"title\":{\"text\":\"톤수 (백만)\"},\"showgrid\":false,\"ticks\":\"outside\",\"tickwidth\":2,\"ticklen\":5},\"legend\":{\"orientation\":\"h\",\"yanchor\":\"bottom\",\"y\":1.02,\"xanchor\":\"center\",\"x\":0.5},\"margin\":{\"l\":50,\"r\":50,\"t\":50,\"b\":100},\"plot_bgcolor\":\"white\",\"hovermode\":\"x unified\"}}",
        "relevant_query": ["2020년부터 2022년까지 부산항의 출항 선박 수는 어떻게 변했나요?", "2020년부터 2022년까지 부산항에서의 수입 환적 추이에 대해 알려주실 수 있나요?", "2023년 1월 부산항의 입항 선박 수는 얼마나 될까요?", "2024년 12월까지 부산항의 수출 환적 추이를 확인할 수 있을까요?"]
    }
    return dummy_data


def chain_statistics():
    return


def check_chain(message: str, extract_info: ExtractInfo):
    '''
    message : 사용자 입력 문장 / 이전대화 있을 경우 Chain__rewrite_request 으로 변경해서 적용
    extract_info : 항만기본 정보 class
    '''
    state = {
        "MESSAGE": message,
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
            return False, error_message, user_info
    return True, '', user_info


@app.post("/testchain")
async def testchain(
    request: Request,
    input_data: str,
    session_id: str = 'tmp_session_id'
):
    # tmp parameter
    category = 'statistics'
    conv_history = ConversationHistory(session_id)
    PREVIOUS_CHATS = conv_history.get_chats()
    if PREVIOUS_CHATS:
        MESSAGE = Chain__rewrite_request.invoke({
            "PREV_MESSAGE": PREVIOUS_CHATS[-1]["user"],
            "PREV_SQL": PREVIOUS_CHATS[-1].get("SQL"),
            "MESSAGE": input_data
        }).content
    else:
        MESSAGE = input_data
    logger.warning(f"PREVIOUS_CHATS : {PREVIOUS_CHATS}")
    info_check, response, statistics_info = check_chain(MESSAGE, extract_info)
    if info_check:
        # 일반 체인
        # 유저 정보 들고오기
        user_info = userDB.get_user_info(session_id, category)
        template_upload = user_info['btn1']
        use_template_cols = user_info['btn2']
        # 입력 데이터 prompt를 위한 class 모듈화
        excel_applier = ExcelTemplateApplier(copy.deepcopy(MESSAGE))
        # 프롬프트 유형 선택 반영
        if template_upload:  # temp : True
            excel_path = userDB.get_filename(session_id)
            if use_template_cols:  # temp : True / use : False
                excel_applier.yes_template_common_parts(excel_path)
            else:  # temp: True / use : False
                excel_applier.yes_template_common_parts(excel_path)
                excel_applier.COLS = []
        else:  # temp: False
            pass
        # 체인 정의
        sql_obj = SQLGenerator(
            MESSAGE,
            extract_info,
            excel_applier,
            category)
        # 데이터 베이스로부터 데이터 추출
        sql_obj.STATE = {
            "MESSAGE": MESSAGE,
            "PORT_DATA_LST": extract_info.PORT_NAME_LST,
            "FAC_NAME_LST": extract_info.FAC_NAME_LST,
            "COUNTRY_LIST": extract_info.COUNTRY_NAME_LST
        }
        sql_obj.USE_INFO = statistics_info
        sql_obj.Node__extract_info()

        logger.info("### SQL문 생성")
        SQL = ''
        for response in sql_obj.Node__generate_sql():
            print("\033[38;5;12m" + response + "\033[0m", end="", flush=True)
            SQL += response

        while True:
            logger.info("### SQL문 실행 유효성 검증")
            sql_obj.Node__validate_query()
            if not sql_obj.ERROR:
                logger.info("### SQL문 피드백 생성")
                sql_obj.Node__feedback()
                if sql_obj.RENERATE:
                    logger.info("### 답변 재생성")
                    SQL = ''
                    for response in sql_obj.Node__regenerate():
                        print("\033[38;5;12m" + response +
                              "\033[0m", end="", flush=True)
                        SQL += response
                else:
                    logger.info("### 📢 답변이 양호합니다. 프로세스 종료합니다.")
                    break
            else:
                logger.info("### SQL문 에러 처리")
                for response in sql_obj.Node__handle_error():
                    print("\033[38;5;12m" + response +
                          "\033[0m", end="", flush=True)

        SQL = SQL + '\n'
        excel_df = sql_obj.Node__get_data_from_db()
        # 추출된 데이터가 없을 경우
        if len(excel_df) == 0:
            message_text = "### 조건을 만족하는 데이터가 없습니다."
            logger.warning(message_text)
            SQL = SQL + message_text
        else:
            logger.info(
                f"{format_number(len(excel_df))}개의 데이터가 존재합니다.\n\n아래는 추출한 데이터 목록 일부입니다.")
            # .split(" ")
            for part in excel_df.head(2).to_markdown(index=False).split(" "):
                print("\033[38;5;12m" + part + "\033[0m", end="", flush=True)
                time.sleep(0.01)
                SQL = SQL + part
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

        conv_history.add_chat(
            {"user": input_data,
             "assistant": response,
             "SQL": sql_obj.STATE['SQL']}
        )

        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": {
                    "session_id": session_id,
                    "type": "1",
                    "source": [],
                    "data": SQL,
                    "plot": "",
                    "relevant_query": "",
                    "download": f"/{save_path}"
                },
                "message": "success"
            }
        )
    else:  # 정보부족
        conv_history.add_chat(
            {"user": input_data,
             "assistant": response}
        )
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": response,
                "message": "success"
            }
        )
    # 정보 체크
    # USE_INFO, error_messages = self.SQLOBJ.Node__check_essential_info()
    # for key, error_message in error_messages.items():
    #     if USE_INFO.get(key) != "YES":
    #         logger.warning(error_message)
    #         res = ""  # TODO : 실제로는 사용자에게 추가로 텍스트 입력받는 내용(누락됐던 정보=항구/시간) 들어감
    #         self.SQLOBJ.MESSAGE = self.SQLOBJ.MESSAGE+" "+res['output']
    # extract_info = ExtractInfo()
    # extract_info.load_name_lst()


########################


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
    response = userDB.set_btn_one(session_id, click_value, category)
    userDB.set_init(session_id, False, category)
    # 회신양식 업로드
    pre_text = f'Selected : {click_value}'
    userDB.set_history(session_id, pre_text, category, role='ai')

    # debug part
    user_info = userDB.get_user_info(session_id, category)
    logger.warning(f"user_info : {user_info}")
    if response:
        screen_type = '2'
        data = f"{pre_text}\n 양식에 기재된 컬럼명들을 동일하게 사용하시겠습니까??"
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
        screen_type = '4'
        # user init 초기화

        # chain 구현
        info_check, response = check_chain()
        if info_check:
            response = sql_chain()
            return
        else:
            return JSONResponse(
                content={
                    "state": status.HTTP_200_OK,
                    "result": {
                        "session_id": session_id,
                        "type": 4,
                        "source": [],
                        "data": response,
                        "plot": "",
                        "relevant_query": "",
                    },
                    "message": "success"
                }
            )

        data = dummy_statistics()
        data['session_id'] = session_id
        data['type'] = screen_type
        data['data'] = f"{pre_text}\n" + data['data']
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": data,
                "message": "success"
            }
        )
    #
    # else:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to save btn data to user information..")


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
    # pre_btn_message = userDB.pre_btn_message(
    #     session_id, category, step_number=1)
    if response:
        screen_type = '3'
        data = f'Selected : {click_value}'
        userDB.set_history(session_id, data, category, role='ai')

        user_info = userDB.get_user_info(session_id, category)
        logger.warning(f"user_info : {user_info}")
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
                    "download": ""
                },
                "message": "success"
            }
        )
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

    # 파일 갯수 체크
    if len(files) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Over file number..")
    # 파일 확장자 점검
    for fi in files:
        xlsx_path = check_save_xlsx(fi)
    response = userDB.set_filename(session_id, os.path.basename(xlsx_path))
    if response:
        screen_type = '4'
        userDB.set_init(session_id, True, category)
        # user init 초기화

        # chain 구현
        data = dummy_statistics()
        data['session_id'] = session_id
        data['type'] = screen_type

        user_info = userDB.get_user_info(session_id, category)
        logger.warning(f"user_info : {user_info}")
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": data,
                "message": "success"
            }
        )
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
    if len(session_id.strip()) == 0:
        session_id = userDB.gen_session_id()
    elif userDB.check_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is not exist..")
    userDB.set_history(session_id, input_data, category, role='user')
    user_info = userDB.get_user_info(session_id, category)
    if user_info['init']:
        logger.warning(f"user_info : {user_info}")
        screen_type = '1'
        data = "회신 양식 업로드를 하시겠습니까?"
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": {
                    "session_id": session_id,
                    "type": screen_type,
                    "source": [],
                    "data": data,
                    "plot": "",
                    "pre": "",
                },
                "message": "success"
            }
        )
    else:
        screen_type = '4'
        userDB.set_init(session_id, True, category)
        # user init 초기화

        # chain 구현
        data = dummy_statistics()
        data['session_id'] = session_id
        data['type'] = screen_type

        user_info = userDB.get_user_info(session_id, category)
        logger.warning(f"user_info : {user_info}")
        return JSONResponse(
            content={
                "state": status.HTTP_200_OK,
                "result": data,
                "message": "success"
            }
        )


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


@app.post("/harbor_llm")
async def harbor_llm(
    request: Request,
    input_data: str = Body(''),
    session_id: str = Body('')
) -> dict:
    '''
    항만데이터 분석 llm 추론 
    '''
    category = 'analysis'
    return JSONResponse(
        content={
            "state": status.HTTP_200_OK,
            "result": True,
            "message": "success"
        }
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host=args.host,
                port=args.port, workers=1)
