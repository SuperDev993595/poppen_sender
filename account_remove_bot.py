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


def safe_quit(drv):
    """Quit the browser without raising if it is already closed."""
    try:
        if drv is not None:
            drv.quit()
    except Exception:
        pass


def complete_profile_deletion(drv, password, done_event=None):
    """
    After step 1 submit: go to delete step 2, fill password, and click delete profile.
    When done_event is provided, wait for it before performing step 2.
    Returns True if all steps succeeded, False otherwise.
    """
    try:
        drv.get("https://www.poppen.de/delete-profile-page/step/2/")
        time.sleep(3)

        # Password input: type="password" name="password" id="password"
        pwd_input = drv.find_element(By.CSS_SELECTOR, 'input[type="password"][name="password"]#password')
        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(1)

        # Delete profile button: type="submit" class="btn btn-danger"
        delete_btn = drv.find_element(By.CSS_SELECTOR, 'button[type="submit"].btn.btn-danger')

        delete_btn.click()
        time.sleep(1)

        # Modal "Are you sure?" – click Confirm (btn-primary in modal-footer)
        try:
            confirm_btn = drv.find_element(
                By.CSS_SELECTOR,
                '.modal-dialog .modal-footer .btn.btn-primary'
            )

            if done_event is not None:
                print("[INFO] Waiting for message_bot to finish sending all messages before completing profile deletion...")
                done_event.wait()
                
            confirm_btn.click()
            time.sleep(2)
        except NoSuchElementException:
            print("[WARN] Modal confirm button not found – modal may have different structure.")

        print("[INFO] Delete profile step 2 completed – password entered, delete and confirm clicked.")
        return True
    except NoSuchElementException as e:
        print(f"[WARN] complete_profile_deletion: element not found – {e}")
        return False
    except Exception as e:
        print(f"[WARN] complete_profile_deletion failed – {e}")
        return False


def main(account, proxy_config=None, done_event=None):
    """
    Run account removal bot for one account.
    When proxy_config is provided (coordinated mode), use it instead of reading from file.
    When done_event is provided, wait for it before clicking the submit/delete button.
    proxy_config dict: proxy_url (for Chrome); done_event: set by message_bot when all messages sent.
    """
    try:
        email_text = account.split(":")[0]
        password_text = account.split(":")[1]
    except Exception:
        try:
            safe_quit(driver)
        except NameError:
            pass
        return

    path = os.getcwd()
    proxy_url = None

    if proxy_config is not None:
        proxy_url = proxy_config["proxy_url"]
        print(f"[INFO] Account remove bot using shared proxy: {proxy_url}")
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
        safe_quit(driver)
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
    
    # Navigate to delete profile page after login
    driver.get("https://www.poppen.de/delete-profile-page/")
    time.sleep(5)

    # Fill reason textarea
    try:
        reason_textarea = driver.find_element(By.ID, "reason")
        reason_textarea.send_keys("sorry for that, but I'll come soon")
        time.sleep(1)
    except Exception as e:
        print(f"[WARN] Could not find/fill reason textarea: {e}")

    # Validate submit button exists before proceeding
    submit_btn = None
    try:
        submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"].btn.btn-default')
        if submit_btn and submit_btn.is_displayed():
            print("[INFO] Submit button found and visible.")
        else:
            submit_btn = None
            print("[WARN] Submit button not visible.")
    except NoSuchElementException:
        print("[WARN] Submit button not found in DOM.")
    except Exception as e:
        print(f"[WARN] Could not validate submit button: {e}")

    if submit_btn:
        if done_event is not None:
            submit_btn.click()
            time.sleep(2)
            complete_profile_deletion(driver, password_text, done_event=done_event)
        else:
            # Standalone: do not click by default (original behavior)
            time.sleep(1)
    else:
        print("[WARN] Skipping submit – button not available.")

    

    safe_quit(driver)


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
