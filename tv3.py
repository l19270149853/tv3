import requests
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置参数
TIMEOUT = 5  # 单次请求超时时间（秒）
DOWNLOAD_DURATION = 6  # 下载测试时长（秒）
MIN_SPEED = 1.0  # 最小有效速度（KB/s）
THREADS = 10  # 并发线程数
RETRIES = 3  # 请求失败重试次数
INPUT_URL = "https://raw.githubusercontent.com/l19270149853/ZBY/refs/heads/main/tv2.txt"
OUTPUT_FILE = "tv3.txt"

# 配置日志
logging.basicConfig(
    filename='tv3.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_speed(url):
    """
    测试 URL 的下载速度，支持重试
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "http://example.com/",
    }

    for attempt in range(RETRIES):
        try:
            # 测试下载速度
            start_time = time.time()
            response = requests.get(
                url,
                stream=True,
                timeout=TIMEOUT,
                headers=headers
            )
            response.raise_for_status()

            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    downloaded_size += len(chunk)
                    if time.time() - start_time >= DOWNLOAD_DURATION:
                        break

            elapsed_time = time.time() - start_time
            if elapsed_time == 0:
                logging.warning(f"下载时间为零: {url}")
                return None

            speed = (downloaded_size / 1024) / elapsed_time  # 计算速度（KB/s）
            if speed >= MIN_SPEED:
                logging.info(f"有效地址: {url} (速度: {speed:.2f} KB/s)")
                return url, speed
            else:
                logging.warning(f"速度不足: {url} (速度: {speed:.2f} KB/s)")
                return None

        except requests.RequestException as e:
            logging.warning(f"请求失败 (尝试 {attempt + 1}/{RETRIES}): {url}, 错误: {e}")
            if attempt == RETRIES - 1:
                return None
            time.sleep(1)  # 重试前等待 1 秒

def process_file():
    """
    处理输入文件并生成有效地址列表
    """
    valid_urls = []

    try:
        # 从指定的URL获取数据
        response = requests.get(INPUT_URL)
        response.raise_for_status()
        lines = response.text.splitlines()

        # 提取 URL
        urls = [line.strip().split(",")[1] for line in lines if line.strip()]

        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = {executor.submit(test_speed, url): url for url in urls}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    url, speed = result
                    valid_urls.append(url)
                    print(f"有效地址: {url} (速度: {speed:.2f} KB/s)")

        # 保存有效地址到文件
        with open(OUTPUT_FILE, "w") as outfile:
            for url in valid_urls:
                outfile.write(url + "\n")

        logging.info(f"测试完成，有效地址已保存到 {OUTPUT_FILE}")
        print(f"测试完成，有效地址已保存到 {OUTPUT_FILE}")

    except Exception as e:
        logging.error(f"处理文件时出错: {e}")
        print(f"处理文件时出错: {e}")

if __name__ == "__main__":
    process_file()
