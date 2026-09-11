import sqlite3

DB_NAME = "ai_company.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS work_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    theme TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL
);
"""

SEED_LOGS = [
    (
        "2026-09-01 09:00:00",
        "公開済みラッシュアディクト投稿をキューへ反映",
        "楽天ROOMの投稿予約を確認し、次回配信キューに追加しました。",
        "完了",
    ),
    (
        "2026-09-01 08:40:00",
        "Pinterest投稿準備",
        "美容サロン向けピンのデザイン素材を作成中です。",
        "進行中",
    ),
    (
        "2026-09-01 08:10:00",
        "A8.net提携確認",
        "新規案件の提携申請を送信し、承認待ちです。",
        "進行中",
    ),
]


def main():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.executescript(SCHEMA)
  cursor.execute("SELECT COUNT(*) FROM work_logs")
  if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO work_logs (timestamp, theme, content, status) VALUES"
        " (?, ?, ?, ?)",
        SEED_LOGS,
    )
  conn.commit()
  conn.close()
  print(f"Initialized {DB_NAME}")


if __name__ == "__main__":
  main()
