#!/usr/bin/env python3
"""Download the original JRKJ competition data over SFTP."""

import os
from pathlib import Path

SERVER_HOST = os.getenv("JRKJ_SFTP_HOST", "221.226.39.110")
SFTP_PORT = int(os.getenv("JRKJ_SFTP_PORT", "2222"))
USERNAME = os.getenv("JRKJ_SFTP_USERNAME")
PASSWORD = os.getenv("JRKJ_SFTP_PASSWORD")
REMOTE_FILE = "/14-知识图谱与智能推荐赛道-东吴证券-基于 Agentic AI 的金融长上下文推理、图谱穿透与财报反欺诈智能问答算法探索.zip"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / Path(REMOTE_FILE).name

def download_with_progress(output: Path = DEFAULT_OUTPUT) -> None:
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set JRKJ_SFTP_USERNAME and JRKJ_SFTP_PASSWORD before downloading.")

    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("Install the optional 'download' dependencies first.") from exc

    transport = paramiko.Transport((SERVER_HOST, SFTP_PORT))
    try:
        transport.connect(username=USERNAME, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            total_size = sftp.stat(REMOTE_FILE).st_size
            print(f"Downloading {total_size / 1024 / 1024:.1f} MB to {output}")

            def callback(current: int, total: int) -> None:
                print(f"\r{current / total:6.1%}", end="", flush=True)

            sftp.get(REMOTE_FILE, str(output), callback=callback)
            print("\nDownload complete.")
        finally:
            sftp.close()
    finally:
        transport.close()

if __name__ == "__main__":
    download_with_progress()
