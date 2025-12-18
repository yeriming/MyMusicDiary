import streamlit as st
import openai
import json
import db_manager
from datetime import datetime, timedelta
from streamlit_calendar import calendar

# --- 1. 페이지 설정 & 다꾸 스타일 CSS ---
st.set_page_config(page_title="My Music Diary", layout="wide")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap" rel="stylesheet">
<style>
    /* 폰트 강제 적용 */
    html, body, [class*="css"], p, div, h1, h2, h3, button, input, textarea {
        font-family: 'Gamja Flower', cursive !important;
        font-size: 22px !important;
    }

    .stApp {
        background-color: #f9f7f1;
    }

    /* 버튼 */
    .stButton>button {
        background-color: #ff8e8e;
        color: white;
        border-radius: 15px 5px 20px 5px;
        border: 2px dashed #fff;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        transition: transform 0.1s;
    }
    .stButton>button:hover {
        background-color: #ff7676;
        transform: scale(1.02);
    }

    /* 다이어리 내지 */
    .diary-paper {
        background-color: #fff;
        background-image: linear-gradient(#e5e5e5 1px, transparent 1px);
        background-size: 100% 40px;
        line-height: 40px;
        padding: 40px 40px 60px 50px;
        margin-top: 20px;
        border-radius: 5px;
        box-shadow: 5px 5px 15px rgba(0,0,0,0.1);
        /* 노트 크기 키우기 */
        min-height: 780px;
        position: relative;
        color: #555;
    }
    .diary-paper::before {
        content: "";
        position: absolute;
        left: 20px;
        top: 0;
        bottom: 0;
        width: 2px;
        border-left: 2px dashed #ccc;
    }

    /* 스티커 카드 */
    .sticker-card {
        background-color: white;
        padding: 15px;
        margin: 15px 0;
        border: 1px solid #eee;
        box-shadow: 3px 3px 8px rgba(0,0,0,0.15);
        position: relative;
        transition: transform 0.2s;
        text-align: center;
    }
    .sticker-card, .sticker-card * {
        font-family: 'Gamja Flower', cursive !important;
    }
    .sticker-card::before {
        content: "";
        position: absolute;
        top: -12px;
        left: 50%;
        transform: translateX(-50%);
        width: 60px;
        height: 25px;
        background-color: rgba(255, 213, 79, 0.7);
        transform: translateX(-50%) rotate(-2deg);
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    div[data-testid="column"]:nth-of-type(1) .sticker-card { transform: rotate(-1deg); }
    div[data-testid="column"]:nth-of-type(2) .sticker-card { transform: rotate(1deg); }
    div[data-testid="column"]:nth-of-type(3) .sticker-card { transform: rotate(-2deg); }
    .sticker-card:hover {
        transform: scale(1.05) rotate(0deg) !important;
        z-index: 99;
    }

    .fc-event { border: none !important; background: none !important; cursor: pointer; }
    .fc-event-title { font-size: 1.5em !important; }

    /* 캘린더 전체 크기 살짝 줄이기 */
    .fc { font-size: 0.85em; }
</style>
""", unsafe_allow_html=True)

# --- 2. 사이드바 ---
with st.sidebar:
    st.title("📒 My Music Diary")
    api_key = st.text_input("API Key 입력 🔑", type="password")
    st.write("")
    # 라디오 버튼의 "표시 텍스트"와 아래 if/elif 비교 문자열이 100% 동일해야 화면이 정상적으로 갈립니다.
    # (띄어쓰기/괄호 하나만 달라도 조건이 매칭되지 않아서 아무 화면도 안 뜰 수 있어요.)
    menu = st.radio("오늘의 할 일", ["🎵 노래 듣고 줍줍", "📅 다꾸 기록장"])
    st.markdown("---")

db_manager.init_db()

# --- 2.5 상단 큰 타이틀(처음 접속/어느 메뉴든 공통으로 보이게) ---
st.markdown(
    """
<div style="padding: 10px 0 6px 0;">
  <div style="font-size: 56px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.05;">
    My Music Diary
  </div>
  <div style="font-size: 18px; opacity: 0.75; margin-top: 6px;">
    오늘 들은 노래로 단어 스티커를 만들고, 다꾸처럼 기록해요.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if 'analyzed_data' not in st.session_state:
    st.session_state['analyzed_data'] = None

# JSON 파싱
def parse_json_garbage(text):
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1]
        return json.loads(text.strip())
    except Exception as e:
        return None

# --- 3. 메인 기능 ---

# [메뉴 1] 가사 학습
if menu == "🎵 노래 듣고 줍줍":
    st.title("오늘의 노래는? 🎧")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # (추가) 노래 정보 입력: 제목/가수
        song_title = st.text_input("노래 제목", placeholder="예) Lemon")
        artist = st.text_input("가수 이름", placeholder="예) 米津玄師")
        lyrics = st.text_area("가사 입력", height=300, placeholder="가사를 여기에 쏙 넣어주세요...", label_visibility="collapsed")
        analyze_btn = st.button("✨ 스티커 만들기 (분석)")

    if analyze_btn and lyrics:
        if not api_key:
            st.warning("API Key가 필요해요!")
        else:
            client = openai.OpenAI(api_key=api_key)
            with st.spinner("한국어 발음도 적는 중... ✍️"):
                try:
                    # 프롬프트 수정: pronunciation 필드 추가 요청
                    prompt = f"""
                    너는 친절한 일본어 튜터야. 사용자는 일본어를 전혀 읽지 못해.
                    가사: {lyrics}
                    
                    JLPT N3~N1 수준의 단어 5개를 JSON으로 뽑아줘.
                    중요: 'pronunciation' 필드에 반드시 한국어 발음을 적어줘 (예: 아이시테루).
                    그리고 각 단어마다, 위 가사에서 그 단어가 실제로 등장하는 '예문(가사 한 줄/한 문장)'을 1개 골라서
                    예문도 함께 JSON에 넣어줘.
                    예문은 아래 4가지를 모두 포함해야 해:
                    - example: 일본어 예문(가사 원문 그대로)
                    - example_reading: 예문 후리가나(요미가나)
                    - example_pronunciation: 예문 한국어 발음
                    - example_meaning: 예문 한국어 뜻
                    
                    형식: 
                    {{
                        "translation": "전체 한국어 번역", 
                        "vocab": [
                            {{
                                "word": "단어(한자)", 
                                "reading": "요미가나", 
                                "pronunciation": "한국어 발음",
                                "meaning": "뜻", 
                                "example": "예문(가사에서 발췌)",
                                "example_reading": "예문 후리가나",
                                "example_pronunciation": "예문 한국어 발음",
                                "example_meaning": "예문 한국어 뜻"
                            }}
                        ]
                    }}
                    """
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    result = parse_json_garbage(response.choices[0].message.content)
                    if result:
                        st.session_state['analyzed_data'] = result
                except Exception as e:
                    st.error(f"오류: {e}")

    if st.session_state['analyzed_data']:
        data = st.session_state['analyzed_data']
        with col2:
            st.success(data['translation'])
        
        st.markdown("---")
        st.subheader("✂️ 단어 스티커")
        
        vocab_list = data.get('vocab', [])
        cols = st.columns(3)
        
        for idx, item in enumerate(vocab_list):
            with cols[idx % 3]:
                # 한국어 발음(pronunciation) 추가 표시
                pron = item.get('pronunciation', '')
                
                # HTML 들여쓰기 제거
                card_html = f"""
<div class="sticker-card">
    <div style="font-size: 1.5em; color: #d81b60; margin-bottom:5px;"><b>{item['word']}</b></div>
    <div style="color: #555; font-size: 0.9em;">{item['reading']}</div>
    <div style="color: #3f51b5; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">[{pron}]</div>
    <div style="margin:5px 0; border-top:1px dashed #eee; padding-top:5px;"><b>{item['meaning']}</b></div>
    <div style="font-size: 0.85em; color: #888;">"{item['example']}"</div>
</div>
"""
                st.markdown(card_html, unsafe_allow_html=True)
                
                if st.button("📌 붙이기", key=f"save_{idx}"):
                    today = datetime.now().strftime("%Y-%m-%d")
                    # 후리가나(reading) + 한국어 발음(pronunciation)까지 함께 저장
                    reading = item.get('reading', '')
                    ex_reading = item.get('example_reading', '')
                    ex_pron = item.get('example_pronunciation', '')
                    ex_mean = item.get('example_meaning', '')
                    db_manager.add_word(
                        today,
                        item.get('word', ''),
                        item.get('meaning', ''),
                        item.get('example', ''),
                        reading,
                        pron,
                        song_title,
                        artist,
                        ex_reading,
                        ex_pron,
                        ex_mean,
                    )
                    st.toast(f"'{item['word']}' 붙이기 완료! 📒")

# [메뉴 2] 다꾸 기록장
elif menu == "📅 다꾸 기록장":
    st.title("나의 다꾸 기록장 📖")
    
    recorded_dates = db_manager.get_recorded_dates()
    calendar_events = []
    for date in recorded_dates:
        calendar_events.append({"title": "🌸", "start": date, "allDay": True, "display": "background", "backgroundColor": "#ffeb3b"})
        calendar_events.append({"title": "🌸참 잘했어요", "start": date})

    # 월간 캘린더가 너무 크지 않게 옵션을 조정
    calendar(
        events=calendar_events,
        options={
            "initialView": "dayGridMonth",
            "height": 360,
            "headerToolbar": {"left": "prev,next", "center": "title", "right": "today"},
        },
        custom_css="""
            /* 전체 캘린더 배경을 종이 느낌으로 */
            .fc {
              background: rgba(255,255,255,0.75);
              border: 1px solid rgba(0,0,0,0.06);
              border-radius: 14px;
              padding: 10px 10px 6px 10px;
              box-shadow: 4px 4px 14px rgba(0,0,0,0.08);
            }
            /* 타이틀(월) */
            .fc .fc-toolbar-title {
              font-size: 20px;
              letter-spacing: -0.2px;
            }
            /* 헤더 버튼(이전/다음/오늘) 귀엽게 */
            .fc .fc-button {
              background: rgba(255, 142, 142, 0.85) !important;
              border: none !important;
              border-radius: 12px !important;
              box-shadow: 2px 2px 6px rgba(0,0,0,0.08) !important;
              padding: 6px 10px !important;
            }
            .fc .fc-button:disabled { opacity: 0.5 !important; }
            /* 요일 헤더 */
            .fc .fc-col-header-cell-cushion {
              font-size: 14px;
              opacity: 0.75;
            }
            /* 날짜 숫자 */
            .fc .fc-daygrid-day-number {
              padding: 6px 8px;
              font-size: 14px;
              opacity: 0.85;
            }
            /* 오늘 날짜 하이라이트(스티커 느낌) */
            .fc .fc-day-today {
              background: rgba(255, 235, 59, 0.22) !important;
            }
            /* 이벤트(🌸)는 둥근 스티커처럼 */
            .fc .fc-event {
              border-radius: 999px;
              padding: 2px 8px;
              border: 1px dashed rgba(0,0,0,0.12);
              background: rgba(255, 255, 255, 0.6);
            }
            /* 날짜 칸에 살짝 연필선 느낌 */
            .fc .fc-daygrid-day-frame {
              border-radius: 10px;
            }
        """,
        key="mini_month_calendar",
    )
    
    st.markdown("---")
    col_date, col_content = st.columns([1, 3])
    
    with col_date:
        st.markdown("### 📅 날짜 선택")
        # Streamlit 버전에 따라 query_params API가 다를 수 있어, 호환 레이어를 둡니다.
        def _get_qp():
            try:
                return dict(st.query_params)
            except Exception:
                return st.experimental_get_query_params()

        def _clear_qp():
            try:
                st.query_params.clear()
            except Exception:
                st.experimental_set_query_params()

        qp = _get_qp()
        qp_date = qp.get("date")
        if isinstance(qp_date, list):
            qp_date = qp_date[0] if qp_date else None

        # 쿼리파라미터에 date가 있으면, 그 날짜를 기본 선택으로 사용(삭제 클릭 시 날짜가 유지되게)
        default_selected_date = datetime.now().date()
        if qp_date:
            try:
                default_selected_date = datetime.strptime(str(qp_date)[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        selected_date = st.date_input(
            "label",
            value=default_selected_date,
            label_visibility="collapsed",
            key="diary_selected_date",
        )
        date_str = selected_date.strftime("%Y-%m-%d")
    
    with col_content:
        st.markdown(f"### ✏️ {date_str}의 기록")
        # --- 유틸: None 정리 ---
        def _clean(v):
            return "" if v is None else str(v)

        # --- DB에서 단어 목록 로딩 (항상 id 오름차순) ---
        words = db_manager.get_words_by_date(date_str)

        # (요청) 텍스트 추가 창은 제거합니다.

        # --- 단어들을 '노트 위에' 스티커 카드 형태로 그대로 붙이기 ---
        # (요청) Study에서 보던 카드 스타일을 Diary 노트에서도 그대로 사용합니다.
        #
        # (요청) X 삭제 버튼이 "브라우저 새로고침"을 일으키지 않게:
        # - form/GET 방식 삭제를 제거하고
        # - Streamlit 버튼으로 삭제(DB 삭제 → st.rerun)만 수행합니다.
        # 노트를 HTML div로 감싸면 Streamlit 위젯(카드/버튼)이 그 안으로 못 들어가서
        # "노트 밖으로 벗어난 것처럼" 보일 수 있습니다.
        # 그래서 노트는 Streamlit 컨테이너(border=True)에 스타일을 입혀서,
        # 내부 위젯이 전부 "노트 안"에 포함되도록 만듭니다.
        st.markdown(
            """
<style>
/* border=True 컨테이너(노트) 스타일 */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background-color: #fff !important;
  background-image: linear-gradient(#e5e5e5 1px, transparent 1px) !important;
  background-size: 100% 40px !important;
  border-radius: 6px !important;
  box-shadow: 5px 5px 15px rgba(0,0,0,0.1) !important;
  padding: 20px 18px !important;
}
/* 왼쪽 점선 세로줄(노트 제본 느낌) */
div[data-testid="stVerticalBlockBorderWrapper"]::before {
  content: "" !important;
  position: absolute !important;
  left: 18px !important;
  top: 0 !important;
  bottom: 0 !important;
  width: 2px !important;
  border-left: 2px dashed #ccc !important;
  pointer-events: none !important;
}
</style>
""",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            if not words:
                st.write("(아직 저장된 단어가 없어요)")
            else:
                for w in words:
                    wid = w.get("id")
                    song_line = f"🎵 {_clean(w.get('song_title'))}{(' - ' + _clean(w.get('artist'))) if _clean(w.get('artist')) else ''}"

                    word = _clean(w.get("word"))
                    reading = _clean(w.get("reading"))
                    pron = _clean(w.get("pronunciation"))
                    meaning = _clean(w.get("meaning"))

                    example = _clean(w.get("example"))
                    ex_reading = _clean(w.get("example_reading"))
                    ex_pron = _clean(w.get("example_pronunciation"))
                    ex_meaning = _clean(w.get("example_meaning"))

                    left, right = st.columns([14, 1])
                    with left:
                        card_html = f"""
<div class="sticker-card">
  <div style="font-size: 0.85em; color: #666; margin-bottom: 6px;">{song_line}</div>
  <div style="font-size: 1.5em; color: #d81b60; margin-bottom:5px;"><b>{word}</b></div>
  <div style="color: #555; font-size: 0.9em;">{reading}</div>
  <div style="color: #3f51b5; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">[{pron}]</div>
  <div style="margin:5px 0; border-top:1px dashed #eee; padding-top:5px;"><b>{meaning}</b></div>
  <div style="margin-top:10px; font-size: 0.95em; color: #444;"><b>예문</b>: {example}</div>
  <div style="font-size: 0.9em; color: #555;">{ex_reading}</div>
  <div style="font-size: 0.95em; color: #3f51b5; font-weight:bold;">[{ex_pron}]</div>
  <div style="font-size: 0.95em; color: #666;">뜻: {ex_meaning}</div>
</div>
"""
                        st.markdown(card_html, unsafe_allow_html=True)
                    with right:
                        if st.button("✕", key=f"del_note_{date_str}_{wid}", help="삭제"):
                            db_manager.delete_word(int(wid))
                            st.rerun()

        st.markdown("---")
        st.markdown("### 🎧 이번주 / 이번달 / 이번연도 들은 노래 정리")

        today = datetime.now().date()

        def _fmt(d):
            return d.strftime("%Y-%m-%d")

        # 이번주(월~일)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # 이번달
        month_start = today.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1, day=1)
        month_end = next_month - timedelta(days=1)

        # 이번연도
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)

        tab_week, tab_month, tab_year = st.tabs(["이번주", "이번달", "이번연도"])

        def _render_song_table(label: str, start_d, end_d):
            start_s, end_s = _fmt(start_d), _fmt(end_d)
            st.caption(f"{label}: {start_s} ~ {end_s}")

            summary = db_manager.get_songs_summary(start_s, end_s)
            if not summary:
                st.info("이 기간에는 저장된 노래 기록이 없어요. (Study에서 제목/가수 입력 후 단어를 붙여보세요!)")
                return

            # 표 표시
            st.dataframe(
                summary,
                use_container_width=True,
                hide_index=True,
            )

            # '표에서 선택' UX가 Streamlit 버전에 따라 제한될 수 있어, 안정적으로 selectbox도 제공합니다.
            options = [
                f"{r.get('song_title','')} - {r.get('artist','')}".strip()
                for r in summary
            ]
            selected = st.selectbox("노래 선택", options, key=f"song_pick_{label}_{start_s}_{end_s}")
            if not selected:
                return

            # 선택값 파싱(마지막 ' - ' 기준)
            if " - " in selected:
                s_title, s_artist = selected.split(" - ", 1)
            else:
                s_title, s_artist = selected, ""
            s_title = (s_title or "").strip()
            s_artist = (s_artist or "").strip()

            words = db_manager.get_words_by_song(s_title, s_artist, start_s, end_s)
            st.markdown("#### 📌 이 노래에서 저장한 단어")
            if not words:
                st.write("저장된 단어가 없어요.")
                return

            for w in words:
                word = _clean(w.get("word"))
                reading = _clean(w.get("reading"))
                pron = _clean(w.get("pronunciation"))
                meaning = _clean(w.get("meaning"))
                example = _clean(w.get("example"))
                saved_date = _clean(w.get("date"))

                st.markdown(
                    f"""
<div class="sticker-card">
  <div style="font-size: 0.85em; color: #666; margin-bottom: 6px;">📅 {saved_date}</div>
  <div style="font-size: 1.5em; color: #d81b60; margin-bottom:5px;"><b>{word}</b></div>
  <div style="color: #555; font-size: 0.9em;">{reading}</div>
  <div style="color: #3f51b5; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">[{pron}]</div>
  <div style="margin:5px 0; border-top:1px dashed #eee; padding-top:5px;"><b>{meaning}</b></div>
  <div style="font-size: 0.85em; color: #888;">"{example}"</div>
</div>
""",
                    unsafe_allow_html=True,
                )

        with tab_week:
            _render_song_table("이번주", week_start, week_end)
        with tab_month:
            _render_song_table("이번달", month_start, month_end)
        with tab_year:
            _render_song_table("이번연도", year_start, year_end)

else:
    # 혹시라도 메뉴 문자열이 바뀌었는데 if/elif가 못 따라가면,
    # "빈 화면" 대신 원인을 알려주기 위해 안전장치를 둡니다.
    st.warning("메뉴 선택을 확인해 주세요. (메뉴 문자열이 일치하지 않으면 화면이 비어 보일 수 있어요.)")