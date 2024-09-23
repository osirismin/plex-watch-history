import argparse
import datetime
import os
import textwrap
import time
import logging
import requests

from plexapi import CONFIG
from plexapi.exceptions import BadRequest, Unauthorized
from plexapi.myplex import MyPlexAccount
from plexapi.utils import getMyPlexAccount

COMMUNITY = "https://community.plex.tv/api"

GET_WATCH_HISTORY_QUERY = """\ (省略不变)"""
REMOVE_WATCH_HISTORY_QUERY = """\ (省略不变)"""

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def plex_format(item):
    item_type = item["type"].lower()
    parent = item.get("parent")
    grandparent = item.get("grandparent")

    if item_type == "season":
        return f"{parent['title']}: Season {item['index']}"
    if item_type == "episode":
        return f"{grandparent['title']}: Season {parent['index']}: Episode {item['index']:2d} - {item['title']}"
    return f"{item['title']} ({item['year']})"

def community_query(account, params, retries=3):
    """执行社区 API 查询并增加重试机制"""
    for attempt in range(retries):
        try:
            response = account.query(
                COMMUNITY,
                json=params,
                method=account._session.post,
                headers={"Content-Type": "application/json"},
            )
            return response
        except (requests.exceptions.RequestException, BadRequest) as e:
            logging.warning(f"API 请求失败: {e}, 尝试重试 {attempt + 1}/{retries}")
            time.sleep(2 ** attempt)  # 指数退避策略
        except Unauthorized as e:
            logging.error("认证失败，请检查你的 Plex token 或账户信息")
            raise
    raise Exception("多次尝试后 API 请求仍然失败")

def get_watch_history(account, first=100, after=None, user_state=False, all_=True):
    params = {
        "query": GET_WATCH_HISTORY_QUERY,
        "operationName": "GetWatchHistoryHub",
        "variables": {
            "uuid": account.uuid,
            "first": first,
            "after": after,
            "skipUserState": not user_state,
        },
    }
    while True:
        try:
            response = community_query(account, params)
            watch_history = response.get("data", {}).get("user", {}).get("watchHistory", {})
            nodes = watch_history.get("nodes", [])
            page_info = watch_history.get("pageInfo", {})

            yield from nodes

            if not all_ or not page_info.get("hasNextPage"):
                break

            params["variables"]["after"] = page_info.get("endCursor", None)
            time.sleep(2)  # 控制 API 调用频率

        except Exception as e:
            logging.error(f"获取观看历史时出错: {e}")
            time.sleep(30)

def remove_watch_history(account, item):
    params = {
        "query": REMOVE_WATCH_HISTORY_QUERY,
        "operationName": "removeActivity",
        "variables": {
            "input": {
                "id": item["id"],
                "type": "WATCH_HISTORY",
            },
        },
    }
    try:
        response = community_query(account, params)
        return response.get("data", {}).get("removeActivity")
    except Exception as e:
        logging.error(f"删除观看历史时出错: {e}")
        raise

def plex_format_entry(entry):
    date = datetime.datetime.fromisoformat(entry["date"]).strftime("%c")
    formatted_entry = plex_format(entry["metadataItem"])
    return f"{date}: {formatted_entry}"

def list_watch_history(account):
    logging.info("开始列出观看历史")
    for entry in get_watch_history(account):
        print(plex_format_entry(entry))

def delete_watch_history(account):
    logging.info("开始删除观看历史")
    while True:
        history = list(get_watch_history(account))
        if not history:
            logging.info("观看历史已全部删除")
            break

        logging.info(f"正在删除 {len(history)} 条观看历史")
        for entry in history:
            print(plex_format_entry(entry))

            while True:
                try:
                    remove_watch_history(account, entry)
                    time.sleep(1)
                    break
                except Exception as e:
                    logging.warning(f"删除观看历史出错: {e}, 重试中...")
                    time.sleep(30)

def main():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent("""
            Manage your Plex watch history.

            Note: This works with the watch history that is synced to your Plex account."""),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(required=True)

    parser_list = subparsers.add_parser(
        "list",
        help="Display all your watched movies and shows, along with the date you watched them.",
        description="Display all your watched movies and shows, along with the date you watched them.",
    )
    parser_list.set_defaults(func=list_watch_history)

    parser_delete = subparsers.add_parser(
        "delete",
        help="Permanently delete your entire watch history.",
        description="Permanently delete your entire watch history.",
    )
    parser_delete.set_defaults(func=delete_watch_history)

    for subparser in (parser_list, parser_delete):
        subparser.add_argument("--token", help="Your Plex token", default=CONFIG.get("auth.server_token"))
        subparser.add_argument("--username", help="Your Plex username", default=CONFIG.get("auth.myplex_username"))
        subparser.add_argument("--password", help="Your Plex password", default=CONFIG.get("auth.myplex_password"))

    args = parser.parse_args()

    if bool(args.username) != bool(args.password):
        parser.error("both username and password must be given together")

    try:
        if args.token:
            account = MyPlexAccount(token=args.token)
        else:
            account = getMyPlexAccount(args)
        
        args.func(account)
    except Exception as e:
        logging.error(f"程序执行时出错: {e}")

if __name__ == "__main__":
    main()
