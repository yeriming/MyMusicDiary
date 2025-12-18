import sqlite3

DB_NAME = "voca_diary.db"

def init_db():
    """
    데이터베이스와 테이블을 생성하고, 구버전 DB일 경우 컬럼/테이블을 추가합니다.

    이 앱은 초보자용이기 때문에 "마이그레이션 도구" 없이도
    앱 실행만으로 DB가 최신 구조로 맞춰지도록(=자동 보정) 설계합니다.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. 테이블 생성 (없을 경우)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            word TEXT NOT NULL,
            song_title TEXT,
            artist TEXT,
            reading TEXT,
            meaning TEXT NOT NULL,
            example TEXT,
            example_reading TEXT,
            example_pronunciation TEXT,
            example_meaning TEXT,
            pronunciation TEXT,
            UNIQUE(date, word) 
        )
    """)
    
    # 2. 기존 사용자를 위한 마이그레이션
    # - 이미 컬럼이 있으면 OperationalError가 나는데 정상입니다(무시).
    for col_name, col_type in (
        ("pronunciation", "TEXT"),
        ("reading", "TEXT"),
        ("song_title", "TEXT"),
        ("artist", "TEXT"),
        ("example_reading", "TEXT"),
        ("example_pronunciation", "TEXT"),
        ("example_meaning", "TEXT"),
    ):
        try:
            cursor.execute(f"ALTER TABLE study_log ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    # 3. 다꾸(레이아웃/메모) 저장용 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diary_layout (
            date TEXT PRIMARY KEY,
            layout_json TEXT NOT NULL
        )
    """)

    # 4. 다꾸 "노트 텍스트" 저장용 테이블 (날짜별 1개)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diary_text (
            date TEXT PRIMARY KEY,
            content TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def add_word(
    date,
    word,
    meaning,
    example,
    reading="",
    pronunciation="",
    song_title="",
    artist="",
    example_reading="",
    example_pronunciation="",
    example_meaning="",
):
    """
    단어를 DB에 저장합니다.

    - reading: 요미가나(후리가나)
    - pronunciation: 한국어 발음(예: 아이시테루)
    - song_title: 노래 제목
    - artist: 가수 이름
    - example_reading: 예문 후리가나(요미가나)
    - example_pronunciation: 예문 한국어 발음
    - example_meaning: 예문 한국어 뜻
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO study_log (
              date, word, song_title, artist,
              reading, meaning, example, pronunciation,
              example_reading, example_pronunciation, example_meaning
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date,
            word,
            (song_title or "").strip(),
            (artist or "").strip(),
            reading,
            meaning,
            example,
            pronunciation,
            example_reading,
            example_pronunciation,
            example_meaning,
        ))
        conn.commit()
    except Exception as e:
        print(f"Error adding word: {e}")
    finally:
        conn.close()

def get_words_by_date(date):
    """특정 날짜의 단어 목록을 가져옵니다."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM study_log WHERE date = ?", (date,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_recorded_dates():
    """기록이 있는 모든 날짜를 가져옵니다."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM study_log")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def delete_word(word_id: int) -> None:
    """id로 단어(행) 1개를 삭제합니다."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM study_log WHERE id = ?", (word_id,))
    conn.commit()
    conn.close()


def get_layout(date: str):
    """
    특정 날짜의 다꾸 레이아웃(JSON 문자열)을 가져옵니다.
    없으면 None을 반환합니다.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT layout_json FROM diary_layout WHERE date = ?", (date,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_layout(date: str, layout_json: str) -> None:
    """특정 날짜의 다꾸 레이아웃(JSON 문자열)을 저장(업서트)합니다."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO diary_layout (date, layout_json)
        VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET layout_json = excluded.layout_json
        """,
        (date, layout_json),
    )
    conn.commit()
    conn.close()


def get_diary_text(date: str) -> str:
    """특정 날짜의 '노트 텍스트'를 가져옵니다. 없으면 빈 문자열을 반환합니다."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM diary_text WHERE date = ?", (date,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else ""


def save_diary_text(date: str, content: str) -> None:
    """특정 날짜의 '노트 텍스트'를 저장(업서트)합니다."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO diary_text (date, content)
        VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET content = excluded.content
        """,
        (date, content),
    )
    conn.commit()
    conn.close()


def get_songs_summary(start_date: str, end_date: str):
    """
    기간(start_date~end_date) 동안 저장한 단어들을 '노래(제목/가수)' 기준으로 요약해 반환합니다.

    반환 예시:
    [
      {"song_title": "Lemon", "artist": "米津玄師", "word_count": 12, "study_days": 3, "last_saved_date": "2025-12-19"}
    ]
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
          COALESCE(song_title, '') AS song_title,
          COALESCE(artist, '') AS artist,
          COUNT(*) AS word_count,
          COUNT(DISTINCT date) AS study_days,
          MAX(date) AS last_saved_date
        FROM study_log
        WHERE date BETWEEN ? AND ?
          AND song_title IS NOT NULL
          AND TRIM(song_title) <> ''
        GROUP BY song_title, artist
        ORDER BY last_saved_date DESC, word_count DESC;
        """,
        (start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_words_by_song(song_title: str, artist: str, start_date: str, end_date: str):
    """
    특정 노래(제목/가수)에서 저장한 단어를 기간(start_date~end_date) 내에서 가져옵니다.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM study_log
        WHERE date BETWEEN ? AND ?
          AND TRIM(COALESCE(song_title, '')) = TRIM(?)
          AND TRIM(COALESCE(artist, '')) = TRIM(?)
        ORDER BY date DESC, id DESC;
        """,
        (start_date, end_date, song_title or "", artist or ""),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]