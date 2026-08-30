"""Module for fetching JavDB cookies interactively using Edge CDP"""
import os
import sys
import time
import json
import shutil
import socket
import struct
import base64
import tempfile
import subprocess
import urllib.request
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_executable_browser() -> str | None:
    """Detect available Chromium-based browser executable across Windows, macOS, and Linux"""
    # 1. Check system PATH first
    for binary_name in [
        'msedge', 'google-chrome', 'chrome', 'chromium',
        'chromium-browser', 'microsoft-edge', 'brave-browser', 'vivaldi'
    ]:
        path = shutil.which(binary_name)
        if path and Path(path).is_file():
            return str(path)

    # 2. Windows specific registry and path candidates
    if sys.platform == 'win32':
        # Registry lookup for exact installed binary path
        try:
            import winreg
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            ]
            for hkey, subkey in reg_paths:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and Path(val).is_file():
                            return str(val)
                except Exception:
                    pass
        except Exception:
            pass

        # Candidate path fallback
        pf = os.getenv('ProgramFiles', r'C:\Program Files')
        pfx86 = os.getenv('ProgramFiles(x86)', r'C:\Program Files (x86)')
        local = os.getenv('LOCALAPPDATA', r'C:\Users\Default\AppData\Local')

        candidates = [
            Path(pfx86) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
            Path(pf) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
            Path(pf) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(pfx86) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(local) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(local) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
            Path(pf) / 'BraveSoftware' / 'Brave-Browser' / 'Application' / 'brave.exe',
            Path(pfx86) / 'BraveSoftware' / 'Brave-Browser' / 'Application' / 'brave.exe',
        ]
        for c in candidates:
            if c.is_file():
                return str(c)

    # 3. macOS candidates
    elif sys.platform == 'darwin':
        mac_candidates = [
            Path('/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'),
            Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
            Path('/Applications/Chromium.app/Contents/MacOS/Chromium'),
            Path('/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'),
            Path('/Applications/Vivaldi.app/Contents/MacOS/Vivaldi'),
            Path.home() / 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            Path.home() / 'Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
        ]
        for c in mac_candidates:
            if c.is_file():
                return str(c)

    # 4. Linux candidates
    elif sys.platform.startswith('linux'):
        linux_candidates = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/usr/bin/microsoft-edge',
            '/usr/bin/microsoft-edge-stable',
            '/usr/bin/brave-browser',
        ]
        for c in linux_candidates:
            if Path(c).is_file():
                return c

    return None


def send_ws_message(sock: socket.socket, msg: str) -> None:
    """Send text frame over WebSocket socket"""
    data = msg.encode('utf-8')
    length = len(data)
    mask = os.urandom(4)
    masked_data = bytearray(length)
    for i in range(length):
        masked_data[i] = data[i] ^ mask[i % 4]
    
    header = bytearray()
    header.append(0x81)  # Text frame, FIN=1
    if length <= 125:
        header.append(0x80 | length)
    elif length <= 65535:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    
    sock.sendall(header + mask + masked_data)


def recv_ws_message(sock: socket.socket) -> str | None:
    """Receive text frame from WebSocket socket"""
    try:
        header = sock.recv(2)
        if not header or len(header) < 2:
            return None
        b1, b2 = header[0], header[1]
        payload_len = b2 & 0x7f
        if payload_len == 126:
            ext = sock.recv(2)
            payload_len = struct.unpack("!H", ext)[0]
        elif payload_len == 127:
            ext = sock.recv(8)
            payload_len = struct.unpack("!Q", ext)[0]
        
        is_masked = (b2 & 0x80) != 0
        if is_masked:
            mask = sock.recv(4)
        
        payload = bytearray()
        while len(payload) < payload_len:
            chunk = sock.recv(payload_len - len(payload))
            if not chunk:
                break
            payload.extend(chunk)
            
        if is_masked:
            for i in range(len(payload)):
                payload[i] ^= mask[i % 4]
                
        return payload.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.debug(f"Error receiving WebSocket message: {e}")
        return None


def fetch_cookies_from_cdp(port: int = 9222) -> dict[str, str]:
    """Connect to Chrome DevTools Protocol port and fetch all cookies"""
    try:
        req = urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=2)
        targets = json.loads(req.read().decode('utf-8'))
        ws_url = None
        for t in targets:
            if t.get('type') == 'page' and 'javdb' in t.get('url', ''):
                ws_url = t.get('webSocketDebuggerUrl')
                break
        if not ws_url and targets:
            for t in targets:
                if t.get('type') == 'page':
                    ws_url = t.get('webSocketDebuggerUrl')
                    break

        if not ws_url:
            return {}

        ws_path = '/' + ws_url.split('/', 3)[3]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(('127.0.0.1', port))
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        req_str = (
            f"GET {ws_path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s.sendall(req_str.encode('utf-8'))
        resp = s.recv(1024)
        if b"101" not in resp:
            s.close()
            return {}

        send_ws_message(s, json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        msg = recv_ws_message(s)
        s.close()

        if not msg:
            return {}

        res = json.loads(msg)
        cookies_list = res.get('result', {}).get('cookies', [])
        result = {}
        for c in cookies_list:
            domain = c.get('domain', '')
            if 'javdb' in domain:
                result[c.get('name')] = c.get('value')
        return result
    except Exception as e:
        logger.debug(f"CDP cookie extraction error: {e}")
        return {}


def _pick_free_port() -> int:
    """Pick a free local port to avoid collision with other apps or concurrent runs."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class _CdpWs:
    """Minimal WebSocket client for CDP request/response calls (events are skipped)"""

    def __init__(self, ws_url: str, port: int):
        self.sock = socket.create_connection(('127.0.0.1', port), timeout=10)
        path = '/' + ws_url.split('/', 3)[3]
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        req_str = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req_str.encode('utf-8'))
        resp = b''
        while b'\r\n\r\n' not in resp:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError('WebSocket handshake failed')
            resp += chunk
        if b'101' not in resp.split(b'\r\n', 1)[0]:
            raise ConnectionError(f'WebSocket handshake rejected: {resp[:120]!r}')
        self._next_id = 0

    def call(self, method: str, params: dict | None = None, timeout: float = 10):
        """Send a CDP command and wait for the response with the matching id"""
        self._next_id += 1
        mid = self._next_id
        send_ws_message(self.sock, json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        self.sock.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = recv_ws_message(self.sock)
            except socket.timeout:
                raise TimeoutError(f'CDP call timeout: {method}')
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError(f"CDP error: {msg['error']}")
                return msg.get('result', {})
            # 其他消息（事件/其他请求的响应）直接忽略
        raise TimeoutError(f'CDP call timeout: {method}')

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class CdpBrowser:
    """Persistent Chromium instance driven via CDP for fetching pages blocked by Cloudflare.

    所有请求都由真实浏览器发出（天然携带正确的 TLS/HTTP2 指纹和过盾状态），
    导航完成后提取渲染好的 HTML 交给 lxml 解析。
    """

    def __init__(self):
        self.port: int | None = None
        self.proc: subprocess.Popen | None = None
        self.temp_dir: Path | None = None

    def ensure_started(self) -> None:
        if self.proc is not None and self.proc.poll() is None and self.port:
            return
        browser_bin = find_executable_browser()
        if not browser_bin or not Path(browser_bin).exists():
            raise RuntimeError('No valid Chromium-based browser found on system.')
        self.port = _pick_free_port()
        self.temp_dir = Path(tempfile.mkdtemp(prefix='javsp_cdp_run_'))
        cmd = [
            browser_bin,
            f'--remote-debugging-port={self.port}',
            f'--user-data-dir={self.temp_dir}',
            '--no-first-run',
            '--no-default-browser-check',
            # 阻止 Edge 用 Windows 账号静默登录后弹同步提示框干扰验证
            '--disable-sync',
            '--disable-features=msImplicitSignin,msSignInPromo',
            'about:blank'
        ]
        self.proc = subprocess.Popen(cmd)
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/version', timeout=2)
                return
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError('Browser process exited unexpectedly during CDP startup')
                time.sleep(0.5)
        raise RuntimeError('CDP endpoint did not become ready in time')

    def fetch_html(self, url: str, timeout: float = 60) -> str | None:
        """Navigate a new tab to url and return rendered HTML, or None if not ready in time.

        遇到 Cloudflare 挑战页时会持续等待，用户可在弹出的窗口中手动完成验证。
        """
        self.ensure_started()
        # 新建标签页（Chrome 111+ 要求 PUT，旧版本接受 GET）
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{self.port}/json/new?about:blank', method='PUT')
            tab = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))
        except Exception:
            tab = json.loads(urllib.request.urlopen(
                f'http://127.0.0.1:{self.port}/json/new?about:blank', timeout=5).read().decode('utf-8'))
        tab_id, ws_url = tab['id'], tab['webSocketDebuggerUrl']
        ws = None
        try:
            ws = _CdpWs(ws_url, self.port)
            ws.call('Page.enable')
            ws.call('Page.navigate', {'url': url})
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(1)
                try:
                    # 先确认导航已离开初始空白页，避免抓到空白文档
                    loc = ws.call('Runtime.evaluate',
                                  {'expression': 'location.href', 'returnByValue': True}, timeout=8)
                    if 'about:blank' in (loc.get('result', {}).get('value') or ''):
                        continue
                    state = ws.call('Runtime.evaluate',
                                    {'expression': 'document.readyState', 'returnByValue': True}, timeout=8)
                    if state.get('result', {}).get('value') != 'complete':
                        continue
                    html_res = ws.call('Runtime.evaluate',
                                       {'expression': 'document.documentElement.outerHTML', 'returnByValue': True},
                                       timeout=15)
                    text = html_res.get('result', {}).get('value') or ''
                    # 内容过短视为导航尚未完成
                    if len(text) < 500:
                        continue
                    # Cloudflare 挑战页特征：等待自动通过或用户手动完成
                    if 'Just a moment' in text or 'cf-chl' in text:
                        logger.debug('CDP fetch: Cloudflare challenge page, waiting...')
                        continue
                    return text
                except (TimeoutError, RuntimeError, ConnectionError, socket.timeout) as e:
                    logger.debug(f'CDP poll error (will retry): {e}')
            logger.warning(f'CDP fetch timed out after {timeout}s: {url}')
            return None
        finally:
            if ws is not None:
                ws.close()
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/close/{tab_id}', timeout=5)
            except Exception:
                pass

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None
        self.port = None
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None


def _get_browser_ua(port: int) -> str | None:
    """Fetch the browser's real User-Agent via CDP (cf_clearance is UA-bound)"""
    try:
        req = urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=2)
        info = json.loads(req.read().decode('utf-8'))
        return info.get('User-Agent')
    except Exception as e:
        logger.debug(f"Failed to fetch browser UA: {e}")
        return None


def interactive_fetch_cookie_full(target_url: str = 'https://javdb.com', port: int | None = None, timeout: int = 180) -> tuple[str, str | None]:
    """Launch isolated Chromium browser, wait for real Cloudflare clearance, return (cookie_str, user_agent)"""
    if port is None:
        port = _pick_free_port()
    browser_bin = find_executable_browser()
    if not browser_bin or not Path(browser_bin).exists():
        logger.error("No valid Chromium-based browser (Edge/Chrome/Chromium/Brave) found on system.")
        return "", None

    temp_dir = Path(tempfile.mkdtemp(prefix='javsp_cdp_'))
    cmd = [
        browser_bin,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={temp_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        target_url
    ]

    logger.info("=" * 60)
    logger.info("JavSP: 正在启动浏览器窗口进行 Cloudflare 过盾...")
    logger.info("提示: 请在弹出的窗口中完成人机验证（出现 JavDB 页面内容即成功）。")
    logger.info("如需抓取 FC2 等登录后可见的内容，请趁窗口打开时登录 JavDB 账号。")
    logger.info("过盾（以及登录，若进行）完成后，本工具会自动捕获凭证并关闭浏览器窗口。")
    logger.info("=" * 60)

    proc = subprocess.Popen(cmd)
    start_time = time.time()
    cookies_dict = {}
    user_agent = None
    anonymous_session = None  # 首次捕获到过盾凭证时的匿名 _jdb_session，用于判断登录状态变化

    try:
        while time.time() - start_time < timeout:
            time.sleep(2)
            c_dict = fetch_cookies_from_cdp(port)
            if 'cf_clearance' not in c_dict:
                # JavDB 对匿名访客也会下发 _jdb_session，它不能用于过盾，忽略之并继续等待
                if proc.poll() is not None:
                    logger.warning("用户手动关闭了浏览器窗口。")
                    break
                continue
            if not cookies_dict:
                cookies_dict = c_dict
                user_agent = _get_browser_ua(port)
                anonymous_session = c_dict.get('_jdb_session')
                logger.info("成功检测到 Cloudflare 过盾凭证 (cf_clearance)!")
            if anonymous_session and c_dict.get('_jdb_session') != anonymous_session:
                logger.info("检测到登录成功 (会话已更新)!")
                cookies_dict = c_dict
                break
            if proc.poll() is not None:
                logger.warning("用户手动关闭了浏览器窗口。")
                break
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    if cookies_dict:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
        return cookie_str, user_agent
    return "", None


def interactive_fetch_cookie(target_url: str = 'https://javdb.com', port: int | None = None, timeout: int = 180) -> str:
    """Launch isolated Chromium browser window for user verification and auto extract cookie string"""
    cookie_str, _ = interactive_fetch_cookie_full(target_url, port=port, timeout=timeout)
    return cookie_str


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print("正在启动 JavDB 登录/过盾弹窗助手...")
    c_str, c_ua = interactive_fetch_cookie_full("https://javdb.com")
    if c_str:
        print("\n" + "=" * 60)
        print("提取成功! 捕获的 JavDB Cookie:")
        print(c_str)
        if c_ua:
            print("浏览器 UA:")
            print(c_ua)
        print("=" * 60)
        from javsp.config import save_javdb_cookie_to_config
        save_javdb_cookie_to_config(c_str, c_ua)
        print("已自动将 Cookie 和 UA 写入配置文件 config.yml 和 dist/config.yml")
    else:
        print("未能捕获到 Cookie 或操作超时/关闭。")
