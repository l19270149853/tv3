import requests
import re
import time
import concurrent.futures
from urllib.parse import urljoin, urlparse, urlunparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import traceback

# ======================
# 配置参数
# ======================
MAX_WORKERS = 15  # 增加并发数
SPEED_THRESHOLD = 0.1  # KB/s
REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
RETRY_STRATEGY = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('iptv_updater.log'),
        logging.StreamHandler()
    ]
)

class EnhancedIPTVUpdater:
    def __init__(self):
        self.channels = []
        self.session = self._create_session()
        self.failed_sources = set()
        self.valid_sources = [
            "https://d.kstore.dev/download/10694/zmtvid.txt",
            
            
        ]
        self.backup_sources = [
            "",
            ""
        ]

    def _create_session(self):
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        return session

    def _fetch_with_retry(self, url):
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logging.warning(f"获取源失败: {url} - {str(e)}")
            self.failed_sources.add(url)
            return None

    def _parse_source(self, text):
        patterns = [
            r"(?:https?://)?(?:[\w\-]+\.)+[\w\-]+(?::\d+)?/?",
            r"#EXTINF:-1.*?(http[^\s]+)",
            r"(?:host|url)\s*=\s*[\"'](http[^\"']+)"
        ]
        urls = set()
        for pattern in patterns:
            urls.update(re.findall(pattern, text))
        return [self._standardize_url(u) for u in urls if u]

    def _standardize_url(self, raw_url):
        try:
            parsed = urlparse(raw_url)
            if not parsed.netloc:
                return None
            return urlunparse((
                parsed.scheme or 'http',
                parsed.netloc,
                '/iptv/live/1000.json',
                '',
                'key=txiptv',
                ''
            ))
        except:
            return None

    def _speed_test(self, url):
        try:
            start = time.time()
            with self.session.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                size = 0
                for chunk in r.iter_content(chunk_size=4096):
                    size += len(chunk)
                    if time.time() - start > 10:  # 延长测速时间
                        break
                duration = time.time() - start
                return size / duration / 1024 if duration > 0 else 0
        except Exception as e:
            logging.debug(f"测速失败 {url}: {str(e)}")
            return 0

    def _process_api(self, api_url):
        try:
            logging.info(f"Processing: {api_url}")
            response = self.session.get(api_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            try:
                data = response.json()
                if not isinstance(data.get('data'), list):
                    raise ValueError("Invalid data format")
            except ValueError:
                logging.warning(f"无效的JSON格式: {api_url}")
                return

            futures = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for channel in data['data']:
                    if not all(k in channel for k in ('name', 'url')):
                        continue
                    try:
                        full_url = urljoin(api_url, channel['url'])
                        futures.append((
                            channel['name'],
                            full_url,
                            executor.submit(self._speed_test, full_url)
                        ))
                    except Exception as e:
                        logging.error(f"URL处理错误: {e}")

                for name, url, future in futures:
                    try:
                        speed = future.result()
                        if speed >= SPEED_THRESHOLD:
                            self.channels.append(f"{name},{url}")
                            logging.info(f"有效: {name} ({speed:.2f} KB/s)")
                        else:
                            logging.debug(f"速度不足: {name}")
                    except Exception as e:
                        logging.error(f"测速异常: {name} - {e}")

        except requests.RequestException as e:
            logging.error(f"请求失败: {api_url} - {e}")
        except Exception as e:
            logging.error(f"处理异常: {traceback.format_exc()}")

    def _save_channels(self):
        # 分类逻辑保持不变...
        # 添加文件存在性检查
        try:
            with open("zby.txt", "w", encoding="utf-8") as f:
                # 写入内容...
                pass
            logging.info("文件保存成功")
        except IOError as e:
            logging.error(f"文件保存失败: {e}")
            raise

    def _report_status(self):
        logging.info(f"\n{'='*30}")
        logging.info(f"总有效源: {len(self.valid_sources)}")
        logging.info(f"失败源: {len(self.failed_sources)}")
        logging.info(f"最终有效频道: {len(self.channels)}")
        logging.info(f"更新时间: {time.strftime('%Y-%m-%d %H:%M')}")
        logging.info(f"{'='*30}\n")

    def run(self):
        try:
            # 阶段1：收集源
            all_urls = set()
            for source in self.valid_sources + self.backup_sources:
                if content := self._fetch_with_retry(source):
                    all_urls.update(self._parse_source(content))
            
            # 阶段2：处理API
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(self._process_api, all_urls)
            
            # 阶段3：保存结果
            self._save_channels()
            self._report_status()
            return True
        except Exception as e:
            logging.critical(f"主程序错误: {traceback.format_exc()}")
            return False

if __name__ == "__main__":
    updater = EnhancedIPTVUpdater()
    if updater.run():
        exit(0)
    else:
        exit(1)
