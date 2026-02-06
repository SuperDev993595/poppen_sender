"""
Coordinator: run message_bot and account_remove_bot simultaneously with shared proxy and account.

Flow:
  1. Read one account and one proxy (from files or CLI).
  2. Start a single local proxy; both bots use it.
  3. Start message_bot and account_remove_bot in parallel (same proxy, same account).
  4. account_remove_bot runs the full removal process but does NOT click submit yet.
  5. When message_bot finishes sending all messages, it signals; account_remove_bot then clicks submit.

Usage:
  python run_coordinated.py                    # use first account and first proxy from files
  python run_coordinated.py email:password     # use this account, first proxy
  python run_coordinated.py email:password "proxy_line"  # account + proxy line (e.g. user:pass@host:port)
"""

import argparse
import sys
import threading

from extension import parse_proxy
from local_proxy import start_local_proxy

# Import bots so we can call their main()
import message_bot
import account_remove_bot


def load_first_account():
    with open("accounts.txt") as f:
        lines = [x.strip() for x in f.readlines() if x.strip() and not x.strip().startswith("#")]
    if not lines:
        raise SystemExit("[ERROR] No accounts in accounts.txt")
    return lines[0]


def load_first_proxy():
    with open("proxys.txt") as f:
        lines = [x.strip() for x in f.readlines() if x.strip() and not x.strip().startswith("#")]
    if not lines:
        raise SystemExit("[ERROR] No proxies in proxys.txt")
    return lines[0]


def build_proxy_config(proxy_line):
    """Parse proxy line and start local proxy; return dict for both bots."""
    parsed = parse_proxy(proxy_line)
    username = parsed["username"]
    password = parsed["password"]
    host = parsed["host"]
    port = parsed["port"]
    local_port = start_local_proxy(host, int(port), username, password)
    proxy_url = f"127.0.0.1:{local_port}"
    proxy_str = f"{username}:{password}@{host}:{port}"
    requests_proxy = {
        "http": "http://" + proxy_str,
        "https": "http://" + proxy_str,
    }
    return {
        "proxy_url": proxy_url,
        "requests_proxy": requests_proxy,
    }


def run_message_bot_thread(account, proxy_config, done_event):
    try:
        message_bot.main(account, proxy_config=proxy_config, done_event=done_event)
    except Exception as e:
        print(f"[ERROR] message_bot failed: {e}")
        done_event.set()  # unblock account_remove_bot even on failure


def run_account_remove_bot_thread(account, proxy_config, done_event):
    try:
        account_remove_bot.main(account, proxy_config=proxy_config, done_event=done_event)
    except Exception as e:
        print(f"[ERROR] account_remove_bot failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run message_bot and account_remove_bot with shared proxy and account.")
    parser.add_argument("account", nargs="?", default=None, help="Account as email:password (default: first from accounts.txt)")
    parser.add_argument("proxy", nargs="?", default=None, help="Proxy line (default: first from proxys.txt)")
    args = parser.parse_args()

    account = args.account or load_first_account()
    proxy_line = args.proxy or load_first_proxy()

    print(f"[INFO] Account: {account.split(':')[0]}...")
    print(f"[INFO] Proxy line: {proxy_line[:50]}...")

    proxy_config = build_proxy_config(proxy_line)
    print(f"[INFO] Shared proxy URL: {proxy_config['proxy_url']}")

    done_event = threading.Event()

    t1 = threading.Thread(target=run_message_bot_thread, args=(account, proxy_config, done_event), name="message_bot")
    t2 = threading.Thread(target=run_account_remove_bot_thread, args=(account, proxy_config, done_event), name="account_remove_bot")

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print("[INFO] Coordinated run finished.")


if __name__ == "__main__":
    main()
