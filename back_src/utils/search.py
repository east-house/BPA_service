from . import *
from modules.chain import Chain__select_good_search, Chain__select_good_search_with_body


def get_search_contents(query):
    searches = DDGS().text(keywords=query+"news", max_results=100)
    good_searches = []
    for search in tqdm(searches):
        if any(ignore in search['href'] for ignore in ['blog', 'tistory', 'dbpia', 'report', 'pdf', 'hwp', 'scienceon', 'namu.wiki', 'questions', 'qna']):
            continue

        result = check_yes(Chain__select_good_search.invoke({"MESSAGE": query,
                                                             "WEB": f"제목 : {search['title']}\n일부 내용 : {search['body']}"}).content)
        if result == "YES":
            eval_target = get_body_contents([search])[0]['body']
            eval_result = check_yes(Chain__select_good_search_with_body.invoke({"MESSAGE": query,
                                                                                "WEB": f"제목 : {search['title']}\n내용 : {eval_target}"}).content)
        else:
            continue

        if eval_result == "YES":
            good_searches.append({
                "title": search["title"],
                "href": search["href"],
                "body": eval_target
            })

        if len(good_searches) == 4:
            break

    if good_searches:
        return good_searches
    else:
        if len(searches) > 4:
            searches = searches[:4]
        else:
            searches = copy.deepcopy(searches)

    return searches


def get_body_contents(searches):
    documents = []
    for search in searches:
        try:
            search_doc = requests.get(search['href'], headers={
                                      'User-Agent': 'Mozilla/5.0'})
            search_doc.encoding = search_doc.apparent_encoding  # 인코딩 해결
            soup = BeautifulSoup(
                search_doc.text, 'html.parser', from_encoding='utf-8')
            contents = soup.find('body')
            texts = [c.get_text() for c in contents.find_all('article')]
            texts += [c.get_text() for c in contents.find_all('p')]
            new_text = []
            for text in texts:
                text = text.replace("\xa0", " ")
                temp = [j.strip()
                        for j in text.split("\n") if len(j.strip()) > 40]
                if temp != []:
                    new_text.append("\n".join(temp))
            new_text = '\n'.join(new_text)
            new_text = re.sub(r'\n+', '\n', new_text)
            new_text = re.sub(r' +', ' ', new_text)
            new_text = new_text.replace("\t", "")
            if len(new_text) < 300:
                new_text = search["body"]
            elif len(new_text) >= 3000:
                new_text = new_text[:3000]
            document = {
                "title": search["title"],
                "href": search["href"],
                "body": new_text,
            }
            documents.append(document)
        except:
            document = {
                "title": search["title"],
                "href": search["href"],
                "body": search["body"],
            }
            documents.append(document)
    return documents
