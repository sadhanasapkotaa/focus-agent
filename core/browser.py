import asyncio
import fnmatch
import os
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page


STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process,AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
    "--start-maximized",
]

IGNORE_DEFAULT_ARGS = ["--enable-automation"]


class NavigationLock:
    def __init__(self, patterns, home_url: str):
        self.patterns = list(patterns)
        self.home_url = home_url
        self._last_allowed: dict[int, str] = {}
        self._armed = False
        self._redirecting: set[int] = set()

    def arm(self):
        self._armed = True

    def allows(self, url: str) -> bool:
        if not url or url.startswith(("about:", "data:", "blob:")):
            return True
        for pat in self.patterns:
            if fnmatch.fnmatch(url, pat):
                return True
        return False

    async def attach(self, context, page):
        self._wire_page(page)
        context.on("page", lambda p: asyncio.create_task(self._on_new_page(p)))

        async def route_handler(route):
            if self.allows(route.request.url):
                await route.continue_()
            else:
                print(f"[lock] Blocked request: {route.request.url}")
                await route.abort()

        await context.route("**/*", route_handler)

    def _wire_page(self, page):
        pid = id(page)
        self._last_allowed[pid] = page.url or self.home_url

        async def on_navigated(frame):
            if frame != page.main_frame:
                return
            url = frame.url
            if self.allows(url):
                self._last_allowed[pid] = url
                return
            if not self._armed:
                return
            if pid in self._redirecting:
                return
            self._redirecting.add(pid)
            print(f"[lock] Navigation blocked: {url}")
            try:
                await page.goto(self._last_allowed[pid],
                                wait_until="domcontentloaded")
            except Exception as e:
                print(f"[lock] Redirect failed: {e}")
            finally:
                self._redirecting.discard(pid)

        page.on("framenavigated", lambda f: asyncio.create_task(on_navigated(f)))
        page.on("popup", lambda p: asyncio.create_task(self._on_new_page(p)))

    async def _on_new_page(self, page):
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        if not self.allows(page.url):
            print(f"[lock] Closing off-limits tab: {page.url}")
            await page.close()
        else:
            self._wire_page(page)


class BrowserSession:
    def __init__(
        self,
        mode: str,
        base_dir: str = "./.browser_profiles",
        executable_path: str | None = None,
        channel: str | None = None,
        headless: bool = False,
        guard=None,
        allow_patterns=None,
    ):
        self.mode = mode
        self.user_data_dir = str(Path(base_dir).expanduser().resolve() / mode)
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        self.executable_path = executable_path
        self.channel = channel
        self.headless = headless
        self.guard = guard
        self.allow_patterns = allow_patterns or []
        self._pw = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._lock: NavigationLock | None = None

    async def start(self, url: str = "about:blank") -> Page:
        self._pw = await async_playwright().start()

        launch_kwargs = dict(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            args=STEALTH_ARGS,
            ignore_default_args=IGNORE_DEFAULT_ARGS,
            no_viewport=True,
        )
        if self.executable_path:
            launch_kwargs["executable_path"] = self.executable_path
        if self.channel:
            launch_kwargs["channel"] = self.channel

        self.context = await self._pw.chromium.launch_persistent_context(**launch_kwargs)

        await self.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        if self.guard is not None:
            await asyncio.sleep(1.5)
            self._register_with_guard()

        pages = self.context.pages
        self.page = pages[0] if pages else await self.context.new_page()

        if self.allow_patterns:
            self._lock = NavigationLock(self.allow_patterns, home_url=url)
            await self._lock.attach(self.context, self.page)
            print(f"[browser] Navigation lock active: "
                  f"{len(self.allow_patterns)} pattern(s)")

        if url and url != "about:blank":
            try:
                await self.page.goto(url, wait_until="domcontentloaded",
                                     timeout=20000)
            except Exception as e:
                print(f"[browser] Initial navigation interrupted: {e}")

        if self._lock:
            self._lock.arm()
        return self.page

    def _register_with_guard(self):
        try:
            import psutil
            marker = f"--user-data-dir={self.user_data_dir}"
            found = 0
            for p in psutil.process_iter(["pid", "cmdline"]):
                try:
                    cmdline = " ".join(p.info["cmdline"] or [])
                    if marker in cmdline and p.pid != os.getpid():
                        self.guard.register_child(p.pid)
                        found += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if found:
                print(f"[browser] registered {found} process(es) with guard")
            else:
                print("[browser] WARNING: no browser process matched user_data_dir")
        except Exception as e:
            print(f"[browser] guard registration failed: {e}")

    async def find_first(self, selectors, timeout_ms: int = 8000):
        assert self.page
        per = max(500, timeout_ms // max(1, len(selectors)))
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                await loc.wait_for(state="visible", timeout=per)
                return loc
            except Exception:
                continue
        return None

    async def save_current_url(self):
        assert self.page
        return self.page.url

    async def stop(self):
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    async def open_url(self, url: str):
        assert self.page, "Browser not started"
        await self.page.goto(url, wait_until="domcontentloaded")

    async def wait_forever(self):
        assert self.context
        closed = asyncio.Event()
        self.context.on("close", lambda *_: closed.set())
        await closed.wait()
