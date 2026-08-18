import copy
from datetime import datetime, timedelta, timezone
import functools
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Literal

from pydantic import BaseModel
import requests
from requests.exceptions import ConnectionError, Timeout

SCRIPT_PATH = Path(__file__).parents[0]
POOL_LIST_PATH = SCRIPT_PATH / "data" / "pool.json"
COMPRESSED_POOL_LIST_PATH = SCRIPT_PATH / "data" / "compressed_pool.json"


def should_skip_scraping() -> bool:
    """在 GitHub Actions 环境下检查是否需要跳过抓取。

    优先级1：若存在任意卡池的 end_time 日期正好是「昨天」（比今天的日少一天），
            则立即抓取，不严格按照几点走。
    优先级2：若存在任意卡池的 end_time 晚于当前北京时间（仍有活跃卡池），则跳过；
            若所有卡池均已过期，则抓取。
    本地运行时不做此检查，方便调试。
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return False

    if not POOL_LIST_PATH.exists():
        return False

    try:
        with open(POOL_LIST_PATH, "r", encoding="utf-8") as f:
            existing_pools = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
    yesterday = now.date() - timedelta(days=1)

    parsed: list[datetime] = []
    for pool in existing_pools:
        end_time_str = pool.get("end_time", "")
        if not end_time_str:
            continue
        try:
            parsed.append(datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue

    # 优先级1：有卡池的 end_time 日期正好是昨天 → 抓取
    for end_time in parsed:
        if end_time.date() == yesterday:
            return False

    # 优先级2：有活跃卡池 → 跳过；全部过期 → 抓取
    for end_time in parsed:
        if end_time > now:
            return True
    return False


if should_skip_scraping():
    print("存在尚未过期的卡池（end_time 晚于当前时间），跳过本次抓取")
    raise SystemExit(0)


class Character(BaseModel):
    char_id: str
    char_name: str
    star: int


class Weapon(BaseModel):
    weapon_id: str
    weapon_name: str
    star: int


"""
获取角色和武器数据
"""


print("获取角色和武器基础数据")


def fetch_character_data():
    res = requests.get("https://api-v2.encore.moe/api/zh-Hans/character")
    res.raise_for_status()
    value = res.json()
    return value["roleList"]


def fetch_weapon_data():
    res = requests.get("https://api-v2.encore.moe/api/zh-Hans/weapon")
    res.raise_for_status()
    value = res.json()
    return value["weapons"]


raw_character_data = fetch_character_data()
char_list: list[Character] = [
    Character.model_validate(
        {
            "char_id": str(char["Id"]),
            "char_name": char["Name"],
            "star": char["QualityId"],
        }
    )
    for char in raw_character_data
]
id2char_name = {c.char_id: c.char_name for c in char_list}
name2char_id = {c.char_name: c.char_id for c in char_list}

raw_weapon_data = fetch_weapon_data()
weapon_list: list[Weapon] = [
    Weapon.model_validate(
        {
            "weapon_id": str(weapon["Id"]),
            "weapon_name": weapon["Name"],
            "star": weapon["QualityId"],
        }
    )
    for weapon in raw_weapon_data
]
id2weapon_name = {w.weapon_id: w.weapon_name for w in weapon_list}
name2weapon_id = {w.weapon_name: w.weapon_id for w in weapon_list}

id2name = {**id2char_name, **id2weapon_name}
name2id = {**name2char_id, **name2weapon_id}


"""
开始获取卡池数据
"""

print("开始从库街区获取卡池数据")

name_pattern = r"「(.*?)」"
title_pattern_1 = r"&lt;(.*?)&gt;"
title_pattern_2 = r"\[(.*?)\]"
title_pattern_3 = r"<(.*?)>"

GAME_ID = 3
MAIN_URL = "https://api.kurobbs.com"
ANN_CONTENT_URL = f"{MAIN_URL}/forum/getPostDetail"
SEARCH_URL = f"{MAIN_URL}/forum/search/v2/join"
POST_PAGE_URL = "https://www.kurobbs.com/mc/post/"

headers = {
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Source": "h5",
    "Token": "",
    "devcode": "IvYsrF21ls8CMFfxo1CTGQsv8neo0t6x",
}


def normalize_name(name: str) -> str:
    """将 kurobbs API 返回名称中的日文间隔符替换为（U+中点（U+00B7）"""
    return name.replace("・", "·")


def extract_and_convert_time(text):
    # 匹配中文格式的日期时间
    pattern = r"(\d{4})年(\d{1,2})月(\d{1,2})日(\d{1,2}):(\d{1,2})"

    # 查找所有匹配项
    matches = re.findall(pattern, text)

    result = {}

    # 如果找到至少两个匹配项（开始和结束时间）
    if len(matches) >= 2:
        # 提取第一个匹配项作为开始时间
        start = matches[0]
        # 提取第二个匹配项作为结束时间
        end = matches[1]

        # 格式化为ISO格式
        result["start_at"] = f"{start[0]}-{start[1].zfill(2)}-{start[2].zfill(2)} {start[3].zfill(2)}:{start[4].zfill(2)}:00"
        result["end_at"] = f"{end[0]}-{end[1].zfill(2)}-{end[2].zfill(2)} {end[3].zfill(2)}:{end[4].zfill(2)}:59"
    elif len(matches) == 1:
        result["start_at"] = "版本更新时间"
        result["end_at"] = (
            f"{matches[0][0]}-{matches[0][1].zfill(2)}-{matches[0][2].zfill(2)} {matches[0][3].zfill(2)}:{matches[0][4].zfill(2)}:59"
        )
    else:
        raise ValueError(f"没有找到时间: {text}")

    return result


def retry(max_retries=3, delay=2, backoff=2, exceptions=(Timeout, ConnectionError)):
    """
    重试装饰器
    :param max_retries: 最大重试次数
    :param delay: 初始延迟（秒）
    :param backoff: 延迟倍增因子
    :param exceptions: 需要重试的异常类型元组
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise  # 最后一次重试仍失败，抛出异常
                    print(f"[重试] {func.__name__} 第 {attempt + 1} 次失败：{e}，{_delay}秒后重试...")
                    time.sleep(_delay)
                    _delay *= backoff  # 指数退避
            return None  # 不会执行到这里

        return wrapper

    return decorator


@retry(max_retries=3, delay=1, backoff=2)
def get_post_detail(post_id: str):
    _headers = copy.deepcopy(headers)
    _headers.update({"devcode": "", "token": "", "version": ""})
    data = {
        "isOnlyPublisher": 1,
        "postId": post_id,
        "showOrderType": 2,
    }
    res = requests.post(
        ANN_CONTENT_URL,
        headers=_headers,
        data=data,
        timeout=30,
    )
    return res.json()


@retry(max_retries=3, delay=1, backoff=2)
def search_pool_list(
    pageIndex: int,
    pageSize: int,
    keyword: Literal["角色活动唤取", "武器活动唤取", "角色联动唤取", "武器联动唤取", "角色忆旅唤取", "武器忆旅唤取"],
    gameId: int = GAME_ID,
    search_type: int = 3,
):
    data: dict[str, Any] = {
        "gameId": gameId,
        "keyword": keyword,
        "pageIndex": pageIndex,
        "pageSize": pageSize,
        "searchType": search_type,
    }
    _headers = copy.deepcopy(headers)
    res = requests.post(
        SEARCH_URL,
        headers=_headers,
        data=data,
        timeout=30,
    )
    return res.json()


pool_list = []
seen = {}  # 去重
pending_extra_list = []  # 额外处理内容


def add_pool(pool: dict[str, Any]):
    try:
        key = (
            pool.get("name"),
            pool.get("title"),
            pool["five_star_ids"][0],
            pool["pool_type"],
            pool["start_time"],
            pool["end_time"],
        )
    except Exception as e:
        print(f"item: {pool}\nError: {e}")
        return
    if key not in seen:
        seen[key] = "0"
        pool_list.append(pool)


def get_pool_detail(key: str, value: str, end_time: str | None = None):
    "指定关键字和值获取卡池详情"
    for pool in pool_list:
        if end_time is None:
            if pool[key] == value:
                return pool
        elif pool[key] == value and pool["end_time"] == end_time:
            return pool
    return None


def get_pool_list(
    keyword: Literal["角色活动唤取", "武器活动唤取", "角色联动唤取", "武器联动唤取", "角色忆旅唤取", "武器忆旅唤取"],
    end_page: int = 199,
):
    print(f" 开始查找: {keyword}")
    page = 1
    while page <= end_page:
        res = search_pool_list(page, 20, keyword)
        postList = res["data"]["post"]["postList"]
        hasNext = res["data"]["post"]["hasNext"]
        print(f"  {keyword} 当前第{page}页, 查到内容{len(postList)}条")
        if not hasNext:
            break
        page += 1
        for post in postList:
            post_id = post["postId"]
            post_title = post["postTitle"]
            user_id = post["userId"]
            if user_id != "10012001":  # 鸣潮官方
                continue

            if keyword not in post_title:
                continue
            if not post["imgContent"]:
                print(f"没有图片: {post_id} {post_title}")
                continue
            post_title = post_title.replace("<em>", "").replace("</em>", "")

            find_all = re.findall(name_pattern, post_title)
            if find_all:
                name = find_all[-1]
            else:
                name = ""
            find_all = re.findall(title_pattern_1, post_title)
            if find_all:
                title = find_all[0]
            else:
                find_all = re.findall(title_pattern_2, post_title)
                if find_all:
                    title = find_all[0]
                else:
                    find_all = re.findall(title_pattern_3, post_title)
                    if find_all:
                        title = find_all[0]
                    else:
                        find_all = re.findall(name_pattern, post_title)
                        if find_all:
                            title = find_all[0]
                        else:
                            title = ""

            url = post["imgContent"][0]["url"]

            post_detail = get_post_detail(post_id)
            post_content = post_detail["data"]["postDetail"]["postContent"]

            # 提取5星角色和4星角色
            five_star_names = []
            four_star_names = []
            five_star_ids = []
            four_star_ids = []
            pool_type = ""
            start_time = ""
            end_time = ""
            pending_extra = []  # 额外处理内容
            need_extra = False
            for content in post_content:
                if content["contentType"] != 1:
                    continue
                if "5星角色" in content["content"] and "4星角色" in content["content"]:
                    # 提取5星角色
                    five_star_text = re.search(r"5星角色(.*?)(?=4星角色|$)", content["content"])
                    if five_star_text:
                        five_star_text = five_star_text.group(1)
                        five_star_matches = re.findall(r"「(.*?)」", five_star_text)
                        for match in five_star_matches:
                            five_star_names.append([match])
                    # 提取4星角色 - 匹配"4星角色"后面的所有引号内容
                    four_star_text = re.search(r"4星角色(.*?)(?=唤取|$)", content["content"])
                    if four_star_text:
                        four_star_text = four_star_text.group(1)
                        four_star_names = re.findall(r"「(.*?)」", four_star_text)
                        four_star_ids.extend([name2id[normalize_name(name)] for name in four_star_names])
                    pool_type = "角色活动唤取"

                if "5星武器" in content["content"] and "4星武器" in content["content"]:
                    # 提取5星武器
                    five_star_text = re.search(r"5星武器(.*?)(?=4星武器|$)", content["content"])
                    if five_star_text:
                        five_star_text = five_star_text.group(1)
                        five_star_matches = re.findall(r"「(.*?)」", five_star_text)
                        for match in five_star_matches:
                            five_star_names.append([match])
                    # 提取4星武器 - 匹配"4星武器"后面的所有引号内容
                    four_star_text = re.search(r"4星武器(.*?)(?=唤取|$)", content["content"])
                    if four_star_text:
                        four_star_text = four_star_text.group(1)
                        four_star_names = re.findall(r"「(.*?)」", four_star_text)
                        four_star_ids.extend([name2id[normalize_name(name)] for name in four_star_names])
                    pool_type = "武器活动唤取"

                if "服务器时间" in content["content"] or " ~ " in content["content"]:
                    # 2025年3月6日10:00 ~ 2025年3月26日11:59（服务器时间）
                    # 1.4版本更新后 ~ 2024年12月12日09:59（服务器时间）
                    # 2024年6月6日10:00 ~ 2024年6月26日11:59
                    result = extract_and_convert_time(content["content"])
                    start_time = result["start_at"]
                    end_time = result["end_at"]

                if "角色/武器活动唤取" in title:
                    need_extra = True
                if need_extra and "角色活动唤取" in content["content"]:
                    pending_extra.append(content)

            if pending_extra:
                for content in pending_extra:
                    pending_extra_list.append(
                        {
                            "main": "角色/武器活动唤取",
                            "post_id": post_id,
                            "url": url,
                            "content": content["content"],
                            "start_time": start_time,
                            "end_time": end_time,
                        }
                    )
            else:
                for five_star in five_star_names:
                    five_star_ids = [name2id[normalize_name(name)] for name in five_star]
                    pool = {
                        "bbs": POST_PAGE_URL + post_id,
                        "name": name,
                        "title": title,
                        "pic": url,
                        "five_star_ids": five_star_ids,
                        "five_star_names": five_star,
                        "four_star_ids": four_star_ids,
                        "four_star_names": four_star_names,
                        "pool_type": pool_type,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                    add_pool(pool)


def get_extra_pool():
    for extra in pending_extra_list:
        if "角色/武器活动唤取" in extra["main"]:
            title = extra["main"]
            end_time = extra["end_time"]
            print(f"  {title} 结束时间: {end_time}，{extra['content']}")
            # 提取5星角色
            five_r_star_text = re.search(r"(.*?)(?=角色活动唤取|$)", extra["content"])
            if five_r_star_text:
                up_pool = None
                five_r_star_text = five_r_star_text.group(1)
                # 核心正则：(?:「|\[) 匹配 「 或 [ ，(?:」|\]) 匹配 」 或 ]
                five_star_matches = re.findall(r"(?:「|\[)(.*?)(?:」|\])", five_r_star_text)
                if len(five_star_matches) != 1:
                    first_up_pool = five_star_matches[0]
                    not_first_up_pool = five_star_matches[1:]
                    up_pool = get_pool_detail("title", first_up_pool, end_time)
                else:  # https://www.kurobbs.com/mc/post/1516482517426167808 与同期up四星不一致，单独写fix
                    print(" 角色/武器活动唤取 角色 ！需手动修复，写入fixed")
                #     not_first_up_pool = five_star_matches
                #     up_pool = get_pool_detail("pool_type", "角色活动唤取", end_time)
                if up_pool:
                    for title in not_first_up_pool:
                        pool = copy.deepcopy(up_pool)
                        detail = get_pool_detail("title", title)
                        if detail:
                            pool["bbs"] = POST_PAGE_URL + extra["post_id"]
                            pool["name"] = detail["name"]
                            pool["title"] = detail["title"]
                            pool["pic"] = extra["url"]
                            pool["five_star_ids"] = detail["five_star_ids"]
                            pool["five_star_names"] = detail["five_star_names"]
                            pool["start_time"] = extra["start_time"]

                            add_pool(pool)

            # 提取5星武器
            five_w_star_text = re.search(r"角色活动唤取(.*?)(?=武器活动唤取|$)", extra["content"])
            if five_w_star_text:
                up_pool = None
                five_w_star_text = five_w_star_text.group(1)
                # 核心正则：(?:「|\[) 匹配 「 或 [ ，(?:」|\]) 匹配 」 或 ]
                five_star_matches = re.findall(r"(?:「|\[)(.*?)(?:」|\])", five_w_star_text)
                if len(five_star_matches) != 1:
                    first_up_pool = five_star_matches[0]
                    not_first_up_pool = five_star_matches[1:]
                    up_pool = get_pool_detail("name", first_up_pool, end_time)
                else:
                    print(" 角色/武器活动唤取 武器 ！需手动修复，写入fixed")
                #     not_first_up_pool = five_star_matches
                #     up_pool = get_pool_detail("pool_type", "武器活动唤取", end_time)
                if up_pool:
                    for name in not_first_up_pool:
                        pool = copy.deepcopy(up_pool)
                        detail = get_pool_detail("name", name)
                        if detail:
                            pool["bbs"] = POST_PAGE_URL + extra["post_id"]
                            pool["name"] = detail["name"]
                            pool["title"] = detail["title"]
                            pool["pic"] = extra["url"]
                            pool["five_star_ids"] = detail["five_star_ids"]
                            pool["five_star_names"] = detail["five_star_names"]
                            pool["start_time"] = extra["start_time"]

                            add_pool(pool)


get_pool_list("角色活动唤取")
get_pool_list("武器活动唤取")
get_pool_list("角色联动唤取")
get_pool_list("武器联动唤取")
get_pool_list("角色忆旅唤取")
get_pool_list("武器忆旅唤取")

print("处理特殊情况")
get_extra_pool()

print("从库街区获取完毕，准备补充与排序")

fixed = [
    {
        "bbs": "https://www.kurobbs.com/mc/post/1242639245807484928",
        "name": "忌炎",
        "title": "夜将寒色去",
        "pic": "",
        "five_star_ids": ["1404"],
        "five_star_names": ["忌炎"],
        "four_star_ids": ["1602", "1202", "1204"],
        "four_star_names": ["丹瑾", "炽霞", "莫特斐"],
        "pool_type": "角色活动唤取",
        "start_time": "2024-05-23 10:00:00",
        "end_time": "2024-06-06 09:59:59",
    },
    {
        "bbs": "https://www.kurobbs.com/mc/post/1242884797941297152",
        "name": "苍鳞千嶂",
        "title": "浮声沉兵",
        "pic": "",
        "five_star_ids": ["21010016"],
        "five_star_names": ["苍鳞千嶂"],
        "four_star_ids": ["21010044", "21050024", "21040064"],
        "four_star_names": ["永夜长明", "奇幻变奏", "骇行"],
        "pool_type": "武器活动唤取",
        "start_time": "2024-05-23 10:00:00",
        "end_time": "2024-06-06 09:59:59",
    },
    {
        "bbs": "https://www.kurobbs.com/mc/post/1516482517426167808",
        "name": "卡提希娅",
        "title": "却也在风潮后轻舞",
        "pic": "https://prod-alicdn-community.kurobbs.com/forum/ef344a113afe4914be2a209bbd0f8be820260617.jpeg",
        "five_star_ids": [
            "1409"
        ],
        "five_star_names": [
            "卡提希娅"
        ],
        "four_star_ids": [
            "1402",
            "1303",
            "1204"
        ],
        "four_star_names": [
            "秧秧",
            "渊武",
            "莫特斐"
        ],
        "pool_type": "角色活动唤取",
        "start_time": "2026-06-18 10:00:00",
        "end_time": "2026-07-09 11:59:59"
    },
    {
        "bbs": "https://www.kurobbs.com/mc/post/1516482517426167808",
        "name": "不屈命定之冠",
        "title": "浮声沉兵",
        "pic": "https://prod-alicdn-community.kurobbs.com/forum/ef344a113afe4914be2a209bbd0f8be820260617.jpeg",
        "five_star_ids": [
            "21020056"
        ],
        "five_star_names": [
            "不屈命定之冠"
        ],
        "four_star_ids": [
            "21020084",
            "21040024",
            "21040044"
        ],
        "four_star_names": [
            "永续坍缩",
            "呼啸重音",
            "袍泽之固"
        ],
        "pool_type": "武器活动唤取",
        "start_time": "2026-06-18 10:00:00",
        "end_time": "2026-07-09 11:59:59"
    },
]

pool_list = fixed + pool_list

pool_type_priority = {"角色活动唤取": 0, "武器活动唤取": 1}
pool_list = sorted(
    pool_list,
    key=lambda x: (
        datetime.strptime(x["end_time"], "%Y-%m-%d %H:%M:%S"),
        pool_type_priority.get(x["pool_type"], 2),
        x["five_star_names"][0],
    ),
)

print("开始写入文件")

with open(POOL_LIST_PATH, "w", encoding="utf-8") as f:
    json.dump(pool_list, f, indent=4, ensure_ascii=False)

with open(COMPRESSED_POOL_LIST_PATH, "w", encoding="utf-8") as f:
    json.dump(pool_list, f, ensure_ascii=False, separators=(",", ":"))

print("完成")
