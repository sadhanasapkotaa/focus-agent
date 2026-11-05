import asyncio
import time
from core.browser import BrowserSession
from core.state import load_state, update_mode


RESUME_SELECTORS = [
    "a:has-text('Resume Learning')",
    "button:has-text('Resume Learning')",
    "a:has-text('Resume')",
    "button:has-text('Resume')",
    "a:has-text('Continue Learning')",
    "button:has-text('Continue Learning')",
    "a:has-text('Go to course')",
    "button:has-text('Go to course')",
    "a:has-text('继续学习')",
    "button:has-text('继续学习')",
    "a[href*='/learn/'][href*='/home/']",
    "a[href*='/learn/']",
]


class CourseraMode:
    name = "coursera"

    def __init__(self, config: dict, guard=None, session_minutes: int = 0):
        self.config = config
        self.guard = guard
        self.session_minutes = session_minutes

    async def _one_session(self):
        state = load_state()[self.name]
        target = (state.get("last_course_url")
                  or state.get("last_seen_url")
                  or state.get("url")
                  or "https://www.coursera.org/programs/online-learning-from-your-dol-new-york-city-6jrvh?authProvider=nyslabor")

        bcfg = self.config.get("browser", {})
        session = BrowserSession(
            mode=self.name,
            base_dir=self.config["playwright_user_data"],
            executable_path=bcfg.get("executable_path"),
            channel=bcfg.get("channel"),
            headless=bcfg.get("headless", False),
            guard=self.guard,
        )
        page = await session.start(target)

        if "learn/home" in page.url or page.url.rstrip("/").endswith("coursera.org"):
            print("[coursera] Looking for Resume Learning button...")
            loc = await session.find_first(RESUME_SELECTORS, timeout_ms=10000)
            if loc is not None:
                try:
                    await loc.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    print(f"[coursera] Resumed → {page.url}")
                except Exception as e:
                    print(f"[coursera] Click failed ({e}); staying on dashboard.")
            else:
                print("[coursera] No Resume button found — "
                      "log in with Google if prompted.")

        final_url = await session.save_current_url()
        if final_url and "/learn/" in final_url:
            update_mode(self.name, last_course_url=final_url)
            print(f"[coursera] Saved resume URL: {final_url}")
        elif final_url and "coursera.org" in final_url:
            update_mode(self.name, last_seen_url=final_url)
            print(f"[coursera] Saved last-seen URL: {final_url}")

        print("[coursera] Session active. Close the browser window to exit.")
        await session.wait_forever()
        await session.stop()

    async def _run(self):
        if self.session_minutes <= 0:
            await self._one_session()
            return

        deadline = time.monotonic() + self.session_minutes * 60
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            remaining = int(deadline - time.monotonic())
            print(f"[coursera] Session {attempt} — "
                  f"{remaining // 60}m {remaining % 60}s remaining")
            try:
                await self._one_session()
            except Exception as e:
                print(f"[coursera] Session error: {e}")

            if time.monotonic() >= deadline:
                break

            print("[coursera] Browser closed. Restarting in 5s...")
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

        print("[coursera] Time budget exhausted.")

    def run(self):
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            print("[coursera] Stopped by user.")
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                pass
            else:
                raise