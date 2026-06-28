import os, json, time
from pathlib import Path

ACCOUNTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts")

class Uploader:
    @staticmethod
    def _get_cookies_path(platform: str) -> str:
        return os.path.join(ACCOUNTS_DIR, platform.lower(), "cookies.json")

    @staticmethod
    def cookies_exist(platform: str) -> bool:
        return Path(Uploader._get_cookies_path(platform)).exists()

    @staticmethod
    def save_cookies(platform: str, cookies: list):
        path = Uploader._get_cookies_path(platform)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(cookies, f, indent=2)

    @staticmethod
    def load_cookies(platform: str) -> list:
        path = Uploader._get_cookies_path(platform)
        if not Path(path).exists(): return []
        with open(path) as f:
            return json.load(f)

    @staticmethod
    def login(platform: str):
        import warnings
        warnings.filterwarnings("ignore")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("Playwright tidak terinstall. Jalankan: playwright install chromium")

        PLATFORM_URLS = {
            "youtube": "https://www.youtube.com",
            "tiktok": "https://www.tiktok.com",
            "facebook": "https://www.facebook.com",
        }
        url = PLATFORM_URLS.get(platform.lower())
        if not url: raise ValueError(f"Platform {platform} tidak didukung")

        print(f"""
{'='*50}
  LOGIN {platform.upper()}
{'='*50}

Browser akan terbuka secara otomatis.

Langkah-langkah:
  1. Login ke akun {platform} di browser yang terbuka
  2. SETELAH login berhasil, balik ke jendela ini
  3. Tekan ENTER di sini untuk menyimpan cookie

Tekan ENTER setelah login selesai...
{'='*50}
""")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-logging",
                    "--log-level=3",
                    "--silent-debugger",
                    "--disable-breakpad",
                ]
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            print("  Browser terbuka. Login, lalu tekan ENTER di jendela ini...")

            # Tunggu user tekan Enter
            try:
                input()
            except:
                pass

            # Ambil cookies
            try:
                cookies = ctx.cookies()
            except:
                cookies = []

            if cookies:
                Uploader.save_cookies(platform, cookies)
                print(f"  Login {platform} BERHASIL! ({len(cookies)} cookies)")
            else:
                print(f"  Gagal: tidak ada cookies. Coba lagi.")

            try:
                browser.close()
            except:
                pass

    @staticmethod
    def upload_youtube(video_path: str, title: str, description: str = "",
                       schedule_ts: int = None):
        cookies = Uploader.load_cookies("youtube")
        if not cookies:
            raise Exception("Login dulu! Jalankan: python farm.py --login youtube")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("Playwright tidak terinstall. Jalankan: playwright install chromium")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            page.goto("https://studio.youtube.com")
            time.sleep(3)

            page.goto("https://studio.youtube.com/upload")
            time.sleep(2)

            file_input = page.locator("input[type=file]").first
            file_input.set_input_files(video_path)
            time.sleep(3)

            page.locator("#title-textarea").click()
            page.locator("#title-textarea").fill(title)
            time.sleep(1)

            if description:
                page.locator("#description-textarea").click()
                page.locator("#description-textarea").fill(description)

            if schedule_ts:
                page.click("text=Jadwalkan")
                time.sleep(1)

            page.click("[aria-label='Berikutnya']")
            time.sleep(2)
            page.click("[aria-label='Berikutnya']")
            time.sleep(2)
            page.click("[aria-label='Berikutnya']")
            time.sleep(2)
            page.click("[aria-label='Publikasikan']")

            print(f"[UPLOAD] YouTube: {title}")
            time.sleep(5)
            browser.close()

    @staticmethod
    def upload_tiktok(video_path: str, caption: str = ""):
        cookies = Uploader.load_cookies("tiktok")
        if not cookies:
            raise Exception("Login dulu! Jalankan: python farm.py --login tiktok")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("Playwright tidak terinstall. Jalankan: playwright install chromium")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            page.goto("https://www.tiktok.com/upload")
            time.sleep(3)

            file_input = page.locator("input[type=file]").first
            file_input.set_input_files(video_path)
            time.sleep(5)

            if caption:
                page.locator(".public-DraftEditor-content").click()
                page.locator(".public-DraftEditor-content").fill(caption)
                time.sleep(1)

            page.click("[data-e2e='post_video_btn']")
            print(f"[UPLOAD] TikTok: {caption[:50]}")
            time.sleep(5)
            browser.close()

    @staticmethod
    def upload_facebook(video_path: str, caption: str = ""):
        cookies = Uploader.load_cookies("facebook")
        if not cookies:
            raise Exception("Login dulu! Jalankan: python farm.py --login facebook")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("Playwright tidak terinstall. Jalankan: playwright install chromium")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            page.goto("https://www.facebook.com")
            time.sleep(3)

            page.goto("https://www.facebook.com/upload")
            time.sleep(3)

            file_input = page.locator("input[type=file]").first
            file_input.set_input_files(video_path)
            time.sleep(5)

            if caption:
                page.locator("[contenteditable='true']").first.click()
                page.keyboard.type(caption, delay=50)
                time.sleep(1)

            page.click("text=Posting")
            print(f"[UPLOAD] Facebook: {caption[:50]}")
            time.sleep(5)
            browser.close()

    @staticmethod
    def upload(platform: str, video_path: str, title: str, description: str = "",
               schedule_ts: int = None):
        platform = platform.lower()
        if platform == "youtube":
            Uploader.upload_youtube(video_path, title, description, schedule_ts)
        elif platform == "tiktok":
            Uploader.upload_tiktok(video_path, title)
        elif platform == "facebook":
            Uploader.upload_facebook(video_path, title)
        else:
            raise ValueError(f"Platform {platform} tidak didukung")
