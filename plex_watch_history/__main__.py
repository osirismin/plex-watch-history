import argparse
import datetime
import os
import textwrap
import time

from plexapi import CONFIG
from plexapi.exceptions import BadRequest
from plexapi.myplex import MyPlexAccount
from plexapi.utils import getMyPlexAccount


COMMUNITY = "https://community.plex.tv/api"

GET_WATCH_HISTORY_QUERY = """..."""  # 省略长字符串
REMOVE_WATCH_HISTORY_QUERY = """..."""  # 省略长字符串


def plex_format(item):
    item_type = item["type"].lower()
    parent = item["parent"]
    grandparent = item["grandparent"]

    if item_type == "season":
        return f"{parent['title']}: Season {item['index']}"

    if item_type == "episode":
        return (
            f"{grandparent['title']}: Season {parent['index']}: "
            f"Episode {item['index']:2d} - {item['title']}"
        )

    return f"{item['title']} ({item['year']})"


def community_query(account, params):
    try:
        response = account.query(
            COMMUNITY,
            json=params,
            method=account._session.post,
            headers={"Content-Type": "application/json"},
        )
        if False:  # 这里是调试代码，可以考虑打开调试信息以打印响应内容
            import json
            print(json.dumps(response, indent=4))
        return response
    except Exception as e:
        print(f"Error while making community query with params {params}: {e}")
        return None


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
            if response is None:
                print("Failed to get valid response from community_query")
                return
            
            if 'data' not in response or 'user' not in response['data']:
                print(f"Invalid response structure: {response}")
                return
            
            watch_history = response["data"]["user"]["watchHistory"]
            page_info = watch_history["pageInfo"]

            yield from watch_history["nodes"]

            if not all_ or not page_info["hasNextPage"]:
                return

            params["variables"]["after"] = page_info["endCursor"]

            # Try to avoid API rate limiting
            time.sleep(2)

        except BadRequest:
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

    response = community_query(account, params)
    
    if response is None:
        print(f"Failed to get a valid response from community_query for item {item}")
        return None
    
    if "data" in response and "removeActivity" in response["data"]:
        return response["data"]["removeActivity"]
    else:
        print(f"Unexpected response format or missing data for item {item}: {response}")
        return None


def plex_format_entry(entry):
    date = datetime.datetime.fromisoformat(entry["date"]).strftime("%c")
    entry = plex_format(entry["metadataItem"])

    return f"{date}: {entry}"


def list_watch_history(account):
    for entry in get_watch_history(account):
        print(plex_format_entry(entry))


def delete_watch_history(account):
    while True:
        history = list(get_watch_history(account))
        if len(history) == 0:
            break

        print(f"Deleting {len(history)} watch history entries\n")

        for entry in history:
            print(plex_format_entry(entry))

            while True:
                try:
                    result = remove_watch_history(account, entry)

                    if result is None:
                        print(f"Failed to remove entry with id: {entry['id']}, entry data: {entry}")
                        break

                    # Try to avoid API rate limiting
                    time.sleep(1)
                    break

                except BadRequest as e:
                    print(f"BadRequest error on entry {entry['id']}: {e}")
                    time.sleep(30)
                except Exception as e:
                    print(f"Unexpected error on entry {entry['id']}: {e}")
                    break


def main():
    # 配置参数解析器
    parser = argparse.ArgumentParser(
        description=textwrap.dedent("""
            Manage your Plex watch history.

            Note: This works with the watch history that is synced to your Plex account."""),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(required=True)

    # "list" 子命令
    parser_list = subparsers.add_parser(
        "list",
        help="Display all your watched movies and shows, along with the date you watched them.",
        description="Display all your watched movies and shows, along with the date you watched them.",
    )
    parser_list.set_defaults(func=list_watch_history)

    # "delete" 子命令
    parser_delete = subparsers.add_parser(
        "delete",
        help="Permanently delete your entire watch history.",
        description="Permanently delete your entire watch history.",
    )
    parser_delete.set_defaults(func=delete_watch_history)

    # 为两个子命令添加通用参数
    for subparser in (parser_list, parser_delete):
        subparser.add_argument(
            "--token",
            help="Your Plex token",
            default=CONFIG.get("auth.server_token"),
        )
        subparser.add_argument(
            "--username",
            help="Your Plex username",
            default=CONFIG.get("auth.myplex_username"),
        )
        subparser.add_argument(
            "--password",
            help="Your Plex password",
            default=CONFIG.get("auth.myplex_password"),
        )

    args = parser.parse_args()

    if bool(args.username) != bool(args.password):
        parser.error("both username and password must be given together")

    if args.token:
        account = MyPlexAccount(token=args.token)
    else:
        account = getMyPlexAccount(args)

    args.func(account)
