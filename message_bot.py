import random
from queue import Queue
from threading import Thread
#import yaml
import string
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import time
import os
import re
from datetime import datetime
from pathlib import Path
import requests
from extension import parse_proxy, analyze_proxy_list
from local_proxy import start_local_proxy




global csrf, driver


def send_message(group_id, nickname, client_id, driver, csrf, requests_proxy=None):
    print(f"[INFO] Sending message to {nickname}, group_id: {group_id}, client_id: {client_id}")
    with open("nachricht1.txt") as f:
        messages1_list = f.readlines()
        messages1_list = [x.strip() for x in messages1_list]

    with open("nachricht2.txt") as f:
        messages2_list = f.readlines()
        messages2_list = [x.strip() for x in messages2_list]

    if requests_proxy is None:
        with open("proxys.txt") as f:
            proxy_list = f.readlines()
            proxy_list = [x.strip() for x in proxy_list]
    else:
        proxy_list = None  # use requests_proxy only

    message_part1 = random.choice(messages1_list)
    message_part2 = random.choice(messages2_list)
    final_message = []
    message = ""

    try:
        s1 = message_part1.split("(")
        for s in s1:
            splitted = s.split(")")
            if len(splitted) > 1:
                for part in splitted:
                    final = part.split(",")
                    if len(final) > 1:
                        message += random.choice(final)
                    else:
                        message += part
            else:
                message += s
        final_message.append(message)
    except:
        pass
        
        
    message = ""
        
    try:
        s2 = message_part2.split("(")
        for s in s2:
            splitted = s.split(")")
            if len(splitted) > 1:
                for part in splitted:
                    final = part.split(",")
                    if len(final) > 1:
                        message += random.choice(final)
                    else:
                        message += part
            else:
                message += s
        final_message.append(message)
    except:
        pass
        

    while True:
        try:
            status = "NO"
            payload = {'thread_id': nickname}
            r = requests.get('http://510147000.swh.strato-hosting.eu/test/poppen_messages.php', params=payload, timeout=10)
            output = r.json()
            status = output['status']
            break
        except:
            time.sleep(3)
    

    
    if status == "YES":
        for message in final_message:
            c = 1
            while True:
                try:
                    if requests_proxy is not None:
                        proxy_payload = requests_proxy
                    else:
                        proxy = random.choice(proxy_list)
                        # Parse proxy using the parse_proxy function
                        parsed_proxy = parse_proxy(proxy)
                        username = parsed_proxy["username"]
                        password = parsed_proxy["password"]
                        endpoint = parsed_proxy["host"]
                        port = parsed_proxy["port"]
                        proxy = username + ":" + password + "@" + endpoint + ":" + port
                        proxy_payload = {
                            'http': 'http://' + proxy,
                            'https': 'http://' + proxy,
                        }


                    payload = {
                        "client_id": (None, client_id),
                        "group_id": (None, group_id),
                        "nickname": (None, nickname),
                        "type": (None, "0"),
                        "data": (None, '{"content":"'+message+'"}')
                    }
                    
                    resp = requests.post(f"https://www.poppen.de/api/messenger/p2p/send/json", proxies=proxy_payload, headers={
                        "accept": "application/json",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                        #"content-type": "multipart/form-data;",
                        "origin": "https://www.poppen.de",
                        "referer": "https://www.poppen.de/inbox/p/" + nickname,
                        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                        "cookie": ";".join([f"{cookie['name']}={cookie['value']}" for cookie in driver.get_cookies()])
                    }, files=payload, timeout=10)
                    
                    if resp.status_code == 200:
                        resp_json = resp.json()
                        try:
                            client_id = resp_json["data"]["message_id"]
                            print("Message for " + nickname +" submitted.")
                        except:
                            print(resp_json)
                            print("Message nicht gesendet")
                    else:
                        print("ERROR")
                    break
                except Exception as e:
                    time.sleep(3)
                    pass
            
    else:
        print(str(nickname) + " blacklisted")

class MessageWorker(Thread):

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            item = self.queue.get()
            if len(item) == 6:
                group_id, nickname, client_id, driver, csrf, requests_proxy = item
            else:
                group_id, nickname, client_id, driver, csrf = item
                requests_proxy = None
            try:
                send_message(group_id, nickname, client_id, driver, csrf, requests_proxy)
            finally:
                self.queue.task_done()


def main(account, proxy_config=None, done_event=None):
    """
    Run message bot for one account.
    When proxy_config is provided (coordinated mode), use it instead of reading from file.
    When done_event is provided, set it after all messages are sent (before quitting driver).
    proxy_config dict: proxy_url, requests_proxy (for API requests), or None for standalone.
    """
    global driver
    try:
        email_text = account.split(":")[0]
        password_text = account.split(":")[1]
    except Exception:
        try:
            driver.quit()
        except Exception:
            pass
        return

    path = os.getcwd()
    proxy_url = None
    requests_proxy = None

    if proxy_config is not None:
        proxy_url = proxy_config["proxy_url"]
        requests_proxy = proxy_config["requests_proxy"]
        print(f"[INFO] Message bot using shared proxy: {proxy_url}")
    else:
        # Standalone: read proxy from file
        proxy_analysis = analyze_proxy_list("proxys.txt")
        with open("proxys.txt") as f:
            proxy_list = f.readlines()
            proxy_list = [x.strip() for x in proxy_list if x.strip() and not x.strip().startswith("#")]
        if not proxy_list:
            print("[ERROR] No valid proxies found in proxys.txt")
            return
        proxy = random.choice(proxy_list)
        try:
            parsed_proxy = parse_proxy(proxy)
            username = parsed_proxy["username"]
            password = parsed_proxy["password"]
            endpoint = parsed_proxy["host"]
            port = parsed_proxy["port"]
        except ValueError as e:
            print(f"[ERROR] Failed to parse proxy: {proxy} - {e}")
            return
        local_port = start_local_proxy(endpoint, int(port), username, password)
        proxy_url = f"127.0.0.1:{local_port}"
        print(f"[INFO] Proxy: {proxy_url} -> {endpoint}:{port} (credentials injected, no dialog)")

    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
    #options.add_argument("--headless")

    print(f"[INFO] Proxy: {proxy_url}")
    options.add_argument(f"--proxy-server={proxy_url}")
    options.add_extension(path + "\\addon.zip")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-impl-side-painting")
    options.add_argument("--disable-gpu-sandbox")
    options.add_argument("--log-level=3")
    driver = webdriver.Chrome(options=options)

    driver.get("https://httpbin.org/ip")
    ip_info = driver.page_source
    # Parse/print ip_info to check 'origin' field matches proxy IP
    print(ip_info)
    time.sleep(5)
    
    # Open Lovoo
    driver.get("https://www.poppen.de/")
    time.sleep(5)
    
    print("Poppen opened.")

    # Accept Cookie Modal
    # try:
        # time.sleep(3)
        # driver.find_element(By.XPATH, "/html/body/div[3]//div/div/div[2]/div[2]/div/div[2]/div/div[1]/div").click()
        # time.sleep(2)
        # print("✅\t Cookie Policy accepted.")
    # except:
        # pass
    time.sleep(3)    
    try:
        element = driver.find_element(By.XPATH, "/html/body/div[4]/div[1]/div/div[2]/div[2]/button[2]")
        element.click()
    except Exception as e:
        pass
        
    time.sleep(4)
    
    try:
        driver.find_element(By.ID, 'tab-signin').click()
        time.sleep(2)
    except:
        pass

    # Login
    try:
        email = driver.find_element(By.XPATH, '/html/body/div[3]/div[2]/div/div[2]/div[2]/div/div[2]/div[2]/form/div[1]/div/input')
        email.send_keys(email_text)
        password = driver.find_element(By.XPATH, '/html/body/div[3]/div[2]/div/div[2]/div[2]/div/div[2]/div[2]/form/div[2]/div/input')
        password.send_keys(password_text)
        time.sleep(1)
        button_login = driver.find_element(By.XPATH, "/html/body/div[3]/div[2]/div/div[2]/div[2]/div/div[2]/div[2]/form/div[3]/button")
        button_login.click()
        time.sleep(5)
    except Exception as e:
        try:
            driver.quit()
        except Exception:
            pass
        return
        
    try:
        driver.find_element(By.XPATH, "/html/body/div[2]/div[1]/div/ul/li[5]/a")
        print("User logged in.")
    except:
        f = open("gesperrt.txt", "a")
        f.write(account + "\n")
        f.close()
        with open("accounts.txt") as f:
            account_list = f.readlines()
            account_list = [x.strip() for x in account_list]
        f = open("accounts.txt", "w")
        for acc in account_list:
            if acc == account:
                pass
            else:
                f.write(acc + "\n")
        f.close()
        print("cant login")
        return
    

    try:
        cookies = driver.get_cookies()
        for cookie in cookies:
            if cookie['name'] == "csrf":
                csrf = cookie['value']
            
    except Exception as e:
        csrf = ""
        

    #check account blocked
    # try:
        # driver.get("https://www.markt.de/benutzer/postfach.htm")
        # time.sleep(3)
        # blocked = driver.find_element(By.XPATH, "/html/body/div[2]/main/div[1]/div/div[4]/div").text
        # if "Dein Profil ist derzeit eingeschränkt. Du kannst keine Nachrichten schreiben." == blocked:
            # f = open("gesperrt.txt", "a")
            # f.write(account + "\n")
            # f.close()
            # with open("accounts.txt") as f:
                # account_list = f.readlines()
                # account_list = [x.strip() for x in account_list]
            # f = open("accounts.txt", "w")
            # for acc in account_list:
                # if acc == account:
                    # pass
                # else:
                    # f.write(acc + "\n")
            # f.close()
            # print("✅\t " + account + " ist eingeschränkt")
            # driver.quit()
            # return
    # except:
        # pass

    queue = Queue()
    x = 35
    for _ in range(x):
        worker = MessageWorker(queue)
        worker.daemon = True
        worker.start()
    print(str(x)+" MessageWorker started.")

    offset = 0

    while True:
        try:
            if requests_proxy is not None:
                proxy_payload = requests_proxy
            else:
                proxy = random.choice(proxy_list)
                try:
                    parsed_proxy = parse_proxy(proxy)
                    username = parsed_proxy["username"]
                    password = parsed_proxy["password"]
                    endpoint = parsed_proxy["host"]
                    port = parsed_proxy["port"]
                except ValueError as e:
                    print(f"[ERROR] Failed to parse proxy: {proxy} - {e}")
                    time.sleep(5)
                    continue
                proxy = username + ":" + password + "@" + endpoint + ":" + port
                proxy_payload = {
                    'http': 'http://' + proxy,
                    'https': 'http://' + proxy,
                }

            payload = {
                "offset": offset,#rausfinden wie das genau berechnet wird
                "filter":0
            }

            cookies = ";".join([f"{cookie['name']}={cookie['value']}" for cookie in driver.get_cookies()])

            print(cookies)
            print(payload)
            print(proxy_payload)

            #https://www.poppen.de/api/messenger/group/list
            response = requests.post(f"https://www.poppen.de/api/messenger/group/list", proxies=proxy_payload, json=payload, timeout=10, headers={
                "authority": "www.poppen.de",
                "accept": "application/json",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                "content-type": "application/json",
                "origin": "https://www.poppen.de",
                "referer": "https://www.poppen.de/inbox",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                "cookie": cookies
            })

            print(response.status_code)
            if response.status_code == 200:
                response_json = response.json()
                if len(response_json["data"]["list"]) == 0:
                    break
                offset = response_json["data"]["next"]#wichtig für nächste anfrage
                if offset == 0 or offset == "0":
                    print("Alle Nachrichten geladen")
                    break
                print("Offset " + str(offset) + " wurden " + str(len(response_json["data"]["list"])) + " Nachrichten gefunden")

                for listdata in response_json["data"]["list"]:
                    group_id = listdata["group_id"]
                    nickname = listdata["group_data"]["nickname"]
                    client_id = listdata["last_message"]["message_id"]
                    if requests_proxy is not None:
                        queue.put((group_id, nickname, client_id, driver, csrf, requests_proxy))
                    else:
                        queue.put((group_id, nickname, client_id, driver, csrf))
            else:
                break

        except Exception as e:
            time.sleep(5)

    queue.join()

    print("All messages sent.")
    if done_event is not None:
        done_event.set()
    time.sleep(5)
    try:
        driver.quit()
    except Exception:
        pass  # Chrome/ChromeDriver may have already closed the connection


if __name__ == "__main__":
    with open("startzeiten.txt") as f:
        startzeiten = f.readlines()
        startzeiten = [x.strip() for x in startzeiten]

    for zeit in startzeiten:
        with open("accounts.txt") as f:
            account_list = f.readlines()
            account_list = [x.strip() for x in account_list]

        if zeit == 0 or zeit == "0":
            for account in account_list:
                main(account)
        else:
            time.sleep(int(zeit) * 60)
            for account in account_list:
                main(account)
        print("1 job done")
