import asyncio
import time
from core.browser import BrowserSession
from core.state import load_state, update_mode


class DSAMode:
    name = "dsa"

    def __init__(self, config: dict, guard=None, session_minutes: int = 0):
        self.config = config
        self.guard = guard
        self.session_minutes = session_minutes

    async def _one_session(self):
        state = load_state().get(self.name, {})
        target = state.get("last_seen_url") or "https://claude.ai/"

        bcfg = self.config.get("browser", {})
        allow = self.config.get("allow_list", {}).get(self.name, [])
        session = BrowserSession(
            mode=self.name,
            base_dir=self.config["playwright_user_data"],
            executable_path=bcfg.get("executable_path"),
            channel=bcfg.get("channel"),
            headless=bcfg.get("headless", False),
            guard=self.guard,
            allow_patterns=allow,
        )
        page = await session.start(target)

        final_url = await session.save_current_url()
        if final_url and "claude.ai" in final_url:
            update_mode(self.name, last_seen_url=final_url)
            print(f"[dsa] Saved last-seen URL: {final_url}")

        print("[dsa] Session active. Close the browser window to exit.")
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
            print(f"[dsa] Session {attempt} — "
                  f"{remaining // 60}m {remaining % 60}s remaining")
            try:
                await self._one_session()
            except Exception as e:
                print(f"[dsa] Session error: {e}")

            if time.monotonic() >= deadline:
                break

            print("[dsa] Browser closed. Restarting in 5s...")
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

        print("[dsa] Time budget exhausted.")

    def run(self):
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            print("[dsa] Stopped by user.")
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                pass
            else:
                raise