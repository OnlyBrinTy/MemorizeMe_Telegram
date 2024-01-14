from bs4 import BeautifulSoup
from bs4.element import Tag
import requests
import re

URL = 'https://api.diffchecker.com/public/text?output_type=html&email=belowzero2009@yandex.ru'
HEADERS = {
    'Content-type': 'application/json'
}


def get_score(inlet, original, deleted):
    len_inlet = len(inlet.split())
    len_original = len(original.split())
    len_deleted = sum(map(lambda s: len(s.split()), map(Tag.getText, deleted)))

    return int((len_inlet - len_deleted) / len_original * 100)





def format_html(html):
    """Удаление лишних элементов после получения статьи"""
    soup = BeautifulSoup(html, 'html.parser')

    deleted = soup.find_all("span", {"class": "diff-chunk-removed"})

    charset = soup.new_tag('meta', charset='utf-8')
    soup.insert(0, charset)
    str_soup = str(soup).replace('line-height: 1rem;\n  ', '')
    str_soup = str_soup.replace('font-size: 13px;', 'font-size: 5vw;')

    return str_soup, deleted


def post_request(text1, text2):
    """Обращаемся к API DiffChecker для получения сравнения двух текстов в виде html"""

    # приводим два текста в один формат
    removed_signs1 = re.sub(r'[^\w\s]', '', text1).lower()
    removed_signs2 = re.sub(r'[^\w\s]', '', text2).lower()

    data = {"left": removed_signs1,
            "right": removed_signs2,
            "diff_level": "word"}

    response = requests.post(URL, json=data, headers=HEADERS)

    response, diff = format_html(response.text)

    score = get_score(removed_signs1, removed_signs2, diff)

    return response, score
