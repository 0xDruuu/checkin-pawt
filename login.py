import requests
import schedule
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, init

init(convert=True, autoreset=True)

load_dotenv()
TOKEN = os.getenv("PAWTATO_TOKEN")  # JWT userId: 

MAGIC_LINK_URL = "https://aws-nextjs.pawtato.app/api/auth/magic-link"
CHECKIN_URL = "https://aws-nextjs.pawtato.app/api/protected/user/checkin"
USER_URL = "https://aws-nextjs.pawtato.app/api/protected/user"
STATS_URL = "https://aws-nextjs.pawtato.app/api/protected/user/stats"

def get_magic_link():
    print(Fore.GREEN + f"[{datetime.now()}] Ambil magic link...")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) Chrome/137.0.0.0 Mobile Safari/537.36"
    }
    try:
        response = requests.get(MAGIC_LINK_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("magicLink"), data.get("magicCode")
    except requests.RequestException as e:
        print(Fore.RED + f"[{datetime.now()}] Gagal ambil magic link: {e}")
        if hasattr(response, 'status_code') and response.status_code == 401:
            print(Fore.RED + f"[{datetime.now()}] Token kadaluarsa, update PAWTATO_TOKEN di .env")
        return None, None

def check_checkin_status():
    print(Fore.YELLOW + f"[{datetime.now()}] Cek status check-in...")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) Chrome/137.0.0.0 Mobile Safari/537.36"
    }
    try:
        response = requests.get(USER_URL, headers=headers)
        response.raise_for_status()
        user_data = response.json().get("user", {})
        updated_at = user_data.get("updated_at")
        if not updated_at:
            print(Fore.YELLOW + f"[{datetime.now()}] Nggak ada updated_at, asumsikan belum check-in.")
            return False

        updated_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        time_diff = now - updated_time
        same_day = now.date() == updated_time.date()
        if time_diff.total_seconds() < 24 * 3600 and same_day:
            print(Fore.YELLOW + f"[{datetime.now()}] Udah check-in hari ini pada {updated_at}.")
            return True
        print(Fore.BLUE + f"[{datetime.now()}] Belum check-in hari ini.")
        return False
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Gagal cek status: {e}")
        if hasattr(response, 'status_code') and response.status_code == 401:
            print(f"[{datetime.now()}] Token kadaluarsa, update PAWTATO_TOKEN di .env")
        return False

def checkin_with_browser():
    print(Fore.RED + f"[{datetime.now()}] Mulai check-in...")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) Chrome/137.0.0.0 Mobile Safari/537.36"
    }

    # Check stats regardless of check-in status
    try:
        stats_response = requests.get(STATS_URL, headers=headers)
        stats_response.raise_for_status()
        stats_data = stats_response.json()

        # Extract streak and check-in info
        streak_count = stats_data.get("currentStreak", {}).get("streakCount", "Tidak tersedia")
        checked_in_today = stats_data.get("currentStreak", {}).get("checkedInToday", False)
        check_ins = stats_data.get("checkIns", [])

        # Get yesterday's check-in status
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()[:10]
        yesterday_checkin = next((item for item in check_ins if item["date"].startswith(yesterday)), None)
        yesterday_status = "Ya" if yesterday_checkin and yesterday_checkin["active"] else "Tidak"

        # Get last check-in date
        last_checkin = next((item["date"] for item in check_ins if item["active"]), "Tidak tersedia")
        if last_checkin != "Tidak tersedia":
            last_checkin_dt = datetime.fromisoformat(last_checkin.replace("Z", "+00:00"))
            last_checkin = last_checkin_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

        # Display stats
        print(Fore.BLUE + f"[{datetime.now()}] Status Check-in Hari Ini: {'Selesai' if checked_in_today else 'Belum'}")
        print(Fore.BLUE + f"[{datetime.now()}] Streak Check-in: {streak_count} hari")
        print(Fore.BLUE + f"[{datetime.now()}] Terakhir Check-in: {last_checkin}")
        print(Fore.BLUE + f"[{datetime.now()}] Check-in Kemarin: {yesterday_status}")

    except requests.RequestException as e:
        print(f"[{datetime.now()}] Gagal ambil stats: {e}")
        if hasattr(stats_response, 'status_code') and stats_response.status_code == 401:
            print(f"[{datetime.now()}] Token kadaluarsa, update PAWTATO_TOKEN di .env")

    # Proceed with check-in only if not done today
    if check_checkin_status():
        print(Fore.BLUE + f"[{datetime.now()}] Skip check-in, udah dilakukan.")
        return

    magic_link, magic_code = get_magic_link()
    if not magic_link:
        print(Fore.RED + f"[{datetime.now()}] Magic link nggak ada, cek token.")
        return

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) Chrome/137.0.0.0 Mobile Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(Fore.YELLOW + f"[{datetime.now()}] Buka magic link: {magic_link}")
        driver.get(magic_link)
        
        WebDriverWait(driver, 10).until(
            EC.url_contains("pawtato.app/board")
        )
        print(Fore.YELLOW + f"[{datetime.now()}] Login sukses, di /board")

        time.sleep(random.uniform(2, 5))
        driver.get("https://pawtato.app/profile")
        print(f"[{datetime.now()}] Buka /profile")

        payload = {"platformType": "board"}
        response = requests.post(CHECKIN_URL, json=payload, headers=headers)
        response.raise_for_status()
        print(Fore.YELLOW + f"[{datetime.now()}] Check-in sukses: {response.json()}")

    except requests.RequestException as e:
        print(f"[{datetime.now()}] Check-in gagal: {e}")
        if hasattr(response, 'status_code') and response.status_code == 401:
            print(f"[{datetime.now()}] Token kadaluarsa, update PAWTATO_TOKEN di .env")
    except Exception as e:
        print(f"[{datetime.now()}] Gagal: {e}")
    finally:
        driver.quit()

hour = random.randint(5, 7)
minute = random.randint(0, 59)
schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(checkin_with_browser)

print(Fore.RED + f"Menunggu jadwal check-in...")
checkin_with_browser()

while True:
    schedule.run_pending()
    time.sleep(60)