import sys
from collections import Counter
from pathlib import Path
import jieba
import jieba.analyse

def tokenize(str: str) -> list[str]:
    """返回传入的字符串的词元列表"""
    token_list = jieba.lcut_for_search(str)
    return token_list

def fileToStr(file_path: str) -> str:
    """返回传入文件的内容"""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    return content

def getDirPathList(target_dir: str) -> list[str]:
    """返回传入的目录下的文件路径列表"""
    txt_paths = [str(p) for p in Path(target_dir).glob("*.txt") if p.is_file()]
    file_path_list = txt_paths
    return file_path_list

def calcTokenFreq(token_list: list[str]) -> Counter[str]:
    """返回传入的词元列表的各词元的频数"""
    return Counter(token_list)

def filePathIterator(file_path_list: list[str]) -> int:
    """目录下所有文件的词元总计数"""
    result = Counter({})
    for p in file_path_list:
        str = fileToStr(p)
        result += calcTokenFreq(tokenize(str))
    print(result)
    return 0
target_dir = sys.argv[1]
filePathIterator(getDirPathList(target_dir))
# result = jieba.analyse.extract_tags(str, topK=30, withWeight=False, allowPOS=())

