from . import *

# 요약
Chain__summary = prompt_query_summary | LLM

# 민원상담
Chain__customer_service_generate = prompt_customer_service | LLM  # (히스토리 o)

# 요청 재작성
Chain__rewrite_request = prompt_rewrite_request | LLM

# 요청구분
Chain__classify_request = prompt_classify_request | LLM | PARSER_OBJ.check_query_parser

# 추출여부
Chain__check_port = prompt_check_port | LLM  # | PARSER_OBJ.check_port_parser
Chain__check_time = prompt_check_time | LLM
Chain__check_facil = prompt_check_facil | LLM  # | PARSER_OBJ.check_facil_parser
Chain__check_io = prompt_check_iotype | LLM  # | PARSER_OBJ.check_io_parser
Chain__check_country = prompt_check_country | LLM

# 추출
Chain__extract_port = prompt_extract_port | LLM
Chain__extract_time = prompt_extract_time | LLM
Chain__extract_facil = prompt_extract_facil | LLM
Chain__extract_io = prompt_extract_iotype | LLM | PARSER_OBJ.extract_io_parser
Chain__extract_country = prompt_extract_country | LLM | PARSER_OBJ.extract_country_parser

# 생성, 에러, 피드백, 재생성
Chain__generate_sql = prompt_generate_sql | LLM
# (히스토리 o)
Chain__generate_general_answer = prompt_generate_general_answer | LLM
# (히스토리 o)
Chain__generate_answer_with_context = prompt_generate_answer_with_context | LLM
Chain__generate_analysis = prompt_generate_analysis | LLM  # (히스토리 o)
Chain__handle_error = prompt_handle_error | LLM
Chain__get_feedback = prompt_feedback | LLM
Chain__regenerate = prompt_regenerate | LLM

# 추천질문
Chain__relevant_query_with_database = prompt_relevant_query_with_database_prompt | LLM | PARSER_OBJ.relevant_query_parser
Chain__relevant_query_with_search = prompt_relevant_query_with_search_prompt | LLM | PARSER_OBJ.relevant_query_parser


# 시각화
Chain__check_plot = prompt_check_plot | LLM
Chain__generate_pyplot = prompt_generate_pyplot | LLM
Chain__generate_plotly = prompt_generate_plotly | LLM

# 검색
Chain__generate_search_text = prompt_generate_search_text | LLM
Chain__select_good_search = prompt_select_good_search | LLM
Chain__select_good_search_with_body = prompt_select_good_search_with_body | LLM
