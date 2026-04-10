import sqlite3
from datetime import datetime

import streamlit as st

DB_PATH = "hr_profiles.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            organization TEXT NOT NULL,
            role TEXT NOT NULL,
            interests TEXT,
            introduction TEXT,
            contact TEXT,
            photo BLOB,
            photo_mime TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()

def to_text(value: str | None) -> str:
    return value or ""


def save_profile(
    conn: sqlite3.Connection,
    profile_id: int | None,
    name: str,
    organization: str,
    role: str,
    interests: str,
    introduction: str,
    contact: str,
    photo_bytes: bytes | None,
    photo_mime: str | None,
) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if profile_id is None:
        conn.execute(
            """
            INSERT INTO profiles (
                name, organization, role, interests, introduction, contact,
                photo, photo_mime, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                organization,
                role,
                interests,
                introduction,
                contact,
                photo_bytes,
                photo_mime,
                now,
                now,
            ),
        )
    else:
        if photo_bytes is None:
            conn.execute(
                """
                UPDATE profiles
                SET name=?, organization=?, role=?, interests=?, introduction=?,
                    contact=?, updated_at=?
                WHERE id=?
                """,
                (name, organization, role, interests, introduction, contact, now, profile_id),
            )
        else:
            conn.execute(
                """
                UPDATE profiles
                SET name=?, organization=?, role=?, interests=?, introduction=?,
                    contact=?, photo=?, photo_mime=?, updated_at=?
                WHERE id=?
                """,
                (
                    name,
                    organization,
                    role,
                    interests,
                    introduction,
                    contact,
                    photo_bytes,
                    photo_mime,
                    now,
                    profile_id,
                ),
            )
    conn.commit()


def delete_profile(conn: sqlite3.Connection, profile_id: int) -> None:
    conn.execute("DELETE FROM comments WHERE profile_id=?", (profile_id,))
    conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
    conn.commit()


def fetch_profiles(conn: sqlite3.Connection, keyword: str = "") -> list[sqlite3.Row]:
    if keyword:
        like = f"%{keyword.strip()}%"
        cursor = conn.execute(
            """
            SELECT * FROM profiles
            WHERE name LIKE ? OR organization LIKE ? OR role LIKE ? OR interests LIKE ?
            ORDER BY updated_at DESC
            """,
            (like, like, like, like),
        )
    else:
        cursor = conn.execute("SELECT * FROM profiles ORDER BY updated_at DESC")
    return cursor.fetchall()


def add_comment(conn: sqlite3.Connection, profile_id: int, author: str, content: str) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn.execute(
        "INSERT INTO comments (profile_id, author, content, created_at) VALUES (?, ?, ?, ?)",
        (profile_id, author, content, now),
    )
    conn.commit()


def fetch_comments(conn: sqlite3.Connection, profile_id: int) -> list[sqlite3.Row]:
    cursor = conn.execute(
        "SELECT author, content, created_at FROM comments WHERE profile_id=? ORDER BY id DESC",
        (profile_id,),
    )
    return cursor.fetchall()


def render_photo(photo: bytes | None) -> None:
    if photo:
        st.image(photo, use_container_width=True)
    else:
        st.info("등록된 프로필 사진이 없습니다.")


st.set_page_config(page_title="HR 학회 프로필 공유", layout="wide")
st.title("👥 HR 학회 프로필 공유 홈페이지")
st.caption("학회원이 직접 프로필을 등록하고, 서로의 전문성과 관심사를 확인할 수 있습니다.")

conn = get_connection()
init_db(conn)

menu_col1, menu_col2 = st.columns([2, 1])
with menu_col1:
    mode = st.radio("모드 선택", ["프로필 등록/수정", "회원 프로필 보기"], horizontal=True)
with menu_col2:
    search_keyword = st.text_input("검색", placeholder="이름, 소속, 관심사")

profiles = fetch_profiles(conn, search_keyword)

if mode == "프로필 등록/수정":
    st.subheader("내 프로필 등록")

    profile_options = {"새 프로필 등록": None}
    for row in profiles:
        profile_options[f"{row['name']} ({row['organization']})"] = row["id"]

    selected_label = st.selectbox("수정할 프로필 선택", list(profile_options.keys()))
    selected_id = profile_options[selected_label]

    selected_profile = None
    if selected_id is not None:
        selected_profile = conn.execute("SELECT * FROM profiles WHERE id=?", (selected_id,)).fetchone()

    with st.form("profile_form", clear_on_submit=False):
        name = st.text_input("이름 *", value=to_text(selected_profile["name"]) if selected_profile else "")
        organization = st.text_input("소속(학교/회사/팀) *", value=to_text(selected_profile["organization"]) if selected_profile else "")
        role = st.text_input("직무/관심 분야 *", value=to_text(selected_profile["role"]) if selected_profile else "")
        interests = st.text_input("관심 키워드", value=to_text(selected_profile["interests"]) if selected_profile else "")
        introduction = st.text_area(
            "자기소개",
            value=to_text(selected_profile["introduction"]) if selected_profile else "",
            height=150,
        )
        contact = st.text_input("연락처/링크드인/이메일", value=to_text(selected_profile["contact"]) if selected_profile else "")
        photo_file = st.file_uploader("프로필 사진 업로드 (선택)", type=["png", "jpg", "jpeg"])

        save_clicked = st.form_submit_button("저장")

    if save_clicked:
        if not name.strip() or not organization.strip() or not role.strip():
            st.error("이름, 소속, 직무/관심 분야는 필수 입력 항목입니다.")
        else:
            photo_bytes = photo_file.read() if photo_file else None
            photo_mime = photo_file.type if photo_file else None
            save_profile(
                conn,
                selected_id,
                name.strip(),
                organization.strip(),
                role.strip(),
                interests.strip(),
                introduction.strip(),
                contact.strip(),
                photo_bytes,
                photo_mime,
            )
            st.success("프로필이 저장되었습니다.")
            st.rerun()

    if selected_id is not None and st.button("선택 프로필 삭제", type="secondary"):
        delete_profile(conn, selected_id)
        st.success("프로필이 삭제되었습니다.")
        st.rerun()

st.divider()
st.subheader("학회원 프로필")

if not profiles:
    st.warning("등록된 프로필이 없습니다. 첫 프로필을 등록해 주세요!")
else:
    cols = st.columns(3)
    for idx, profile in enumerate(profiles):
        with cols[idx % 3]:
            st.markdown(f"### {profile['name']}")
            st.caption(f"{profile['organization']} · {profile['role']}")
            render_photo(profile["photo"])
            if profile["interests"]:
                st.write(f"**관심 키워드:** {profile['interests']}")
            if profile["introduction"]:
                st.write(profile["introduction"])
            if profile["contact"]:
                st.write(f"🔗 {profile['contact']}")
            st.caption(f"최근 수정: {profile['updated_at']}")

            st.markdown("#### 💬 댓글")
            comments = fetch_comments(conn, profile["id"])
            if comments:
                for c in comments:
                    st.markdown(f"- **{c['author']}**: {c['content']}")
                    st.caption(f"작성: {c['created_at']}")
            else:
                st.caption("아직 댓글이 없습니다. 첫 댓글을 남겨보세요!")

            with st.form(f"comment_form_{profile['id']}", clear_on_submit=True):
                author = st.text_input("작성자", key=f"author_{profile['id']}")
                comment_text = st.text_area("댓글 내용", key=f"content_{profile['id']}", height=80)
                comment_submitted = st.form_submit_button("댓글 등록")

            if comment_submitted:
                if not author.strip() or not comment_text.strip():
                    st.error("작성자와 댓글 내용을 모두 입력해 주세요.")
                else:
                    add_comment(conn, profile["id"], author.strip(), comment_text.strip())
                    st.success("댓글이 등록되었습니다.")
                    st.rerun()
