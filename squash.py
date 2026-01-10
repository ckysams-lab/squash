import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# 嘗試匯入 Firebase 套件
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth, initialize_app, get_app
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide", initial_sidebar_state="expanded")

# --- 0. UI 美化自定義 CSS ---
st.markdown("""
<style>
    /* 全局字體與背景 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
    }
    
    /* 側邊欄樣式 */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
    }
    [data-testid="stSidebarNav"] {
        padding-top: 20px;
    }
    
    /* 標題與副標題美化 */
    h1 {
        color: #1E3A8A;
        font-weight: 700 !important;
        border-bottom: 3px solid #3B82F6;
        padding-bottom: 10px;
        margin-bottom: 25px !important;
    }
    h2, h3 {
        color: #1F2937;
        font-weight: 600 !important;
    }

    /* 卡片式設計 */
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
    }
    
    /* 按鈕優化 */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* 消息框圓角 */
    .stAlert {
        border-radius: 12px;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 1. Firebase 初始化 ---
def init_firebase():
    """初始化 Firebase 並返回 Firestore Client"""
    if not HAS_FIREBASE:
        return None
    
    if 'firebase_initialized' not in st.session_state:
        try:
            try:
                app = get_app()
            except ValueError:
                if "firebase_config" in st.secrets:
                    key_dict = dict(st.secrets["firebase_config"])
                    if "private_key" in key_dict:
                        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                    cred = credentials.Certificate(key_dict)
                    app = initialize_app(cred)
                else:
                    return None
            
            st.session_state.db = firestore.client()
            st.session_state.firebase_initialized = True
        except Exception as e:
            st.error(f"Firebase 初始化失敗: {e}")
            return None
    return st.session_state.get('db')

db = init_firebase()
app_id = "squash-management-v1"

# --- 2. 身份驗證功能 ---
def get_admin_password():
    """從 Firebase 讀取管理員密碼，若失敗則返回預設值 8888"""
    default_pwd = "8888"
    if st.session_state.get('db') is not None:
        try:
            doc_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection('admin_settings').document('config')
            doc = doc_ref.get()
            if doc.exists:
                return str(doc.to_dict().get('password', default_pwd))
        except Exception:
            pass
    return default_pwd

# --- 3. 數據存取與同步函數 ---
def load_cloud_data(collection_name, default_data):
    key = f"cloud_{collection_name}"
    if st.session_state.get('db') is not None:
        try:
            coll_path = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            docs = coll_path.stream()
            data = [doc.to_dict() for doc in docs]
            if data:
                df = pd.DataFrame(data)
                df.columns = [str(c).strip() for c in df.columns]
                if collection_name == 'attendance_records':
                    for col in ["班級", "日期", "出席人數", "出席名單", "記錄人"]:
                        if col not in df.columns: df[col] = ""
                st.session_state[key] = df
                return df
        except Exception:
            pass
    
    if key in st.session_state:
        return st.session_state[key]
    
    df_default = pd.DataFrame(default_data)
    st.session_state[key] = df_default
    return df_default

def save_cloud_data(collection_name, df):
    if df is None: return
    df = df.dropna(how='all')
    df.columns = [str(c).strip() for c in df.columns]
    key = f"cloud_{collection_name}"
    st.session_state[key] = df
    if st.session_state.get('db') is not None:
        try:
            coll_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            # 刪除舊數據
            for doc in coll_ref.stream(): doc.reference.delete()
            # 寫入新數據
            for _, row in df.iterrows():
                if collection_name == 'attendance_records':
                    doc_id = f"{row.get('班級', 'Unknown')}_{row.get('日期', 'Unknown')}".replace("/", "-")
                elif collection_name == 'announcements':
                    doc_id = f"{row.get('日期')}_{row.get('標題', 'NoTitle')}"
                elif collection_name == 'tournaments':
                    doc_id = f"tm_{row.get('比賽名稱', 'NoName')}_{row.get('日期', 'NoDate')}"
                elif collection_name == 'student_awards':
                    doc_id = f"award_{row.get('學生姓名')}_{row.get('日期')}_{np.random.randint(1000)}"
                elif '姓名' in row and ('年級' in row or '班級' in row):
                    doc_id = f"{row.get('班級', row.get('年級', 'NA'))}_{row.get('姓名')}"
                else:
                    doc_id = str(np.random.randint(1000000))
                
                clean_row = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
                coll_ref.document(doc_id).set(clean_row)
            st.toast(f"✅ {collection_name} 已同步至雲端")
        except Exception as e:
            st.error(f"同步失敗: {e}")

# --- 4. 初始化 Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""

# 香港壁球總會章別獎勵設定
BADGE_AWARDS = {
    "白金章": {"points": 400, "icon": "💎"},
    "金章": {"points": 200, "icon": "🥇"},
    "銀章": {"points": 100, "icon": "🥈"},
    "銅章": {"points": 50, "icon": "🥉"},
    "無": {"points": 0, "icon": ""}
}

# --- 5. 側邊欄與登入邏輯 ---
with st.sidebar:
    st.markdown("<h2 style='text-align:center; color:#1E3A8A;'>🏸 正覺壁球</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#666; font-size:0.8em;'>Squash Management System</p>", unsafe_allow_html=True)
    st.divider()

if not st.session_state.logged_in:
    st.sidebar.subheader("🔑 系統登入")
    login_mode = st.sidebar.radio("身份選擇", ["學生/家長", "管理員"])
    
    if login_mode == "管理員":
        pwd = st.sidebar.text_input("管理員密碼", type="password")
        if st.sidebar.button("登入管理系統", use_container_width=True, type="primary"):
            admin_pwd = get_admin_password()
            if pwd == admin_pwd:
                st.session_state.logged_in = True
                st.session_state.is_admin = True
                st.session_state.user_id = "ADMIN"
                st.rerun()
            else:
                st.sidebar.error("密碼錯誤")
    else:
        st.sidebar.info("請輸入學生班別及學號 (例如: 1A 01)")
        c1, c2 = st.sidebar.columns(2)
        s_class = c1.text_input("班別", placeholder="如: 1A")
        s_num = c2.text_input("學號", placeholder="如: 01")
        if st.sidebar.button("登入", use_container_width=True, type="primary"):
            if s_class and s_num:
                st.session_state.logged_in = True
                st.session_state.is_admin = False
                st.session_state.user_id = f"{s_class.upper()}{s_num.zfill(2)}"
                st.rerun()
            else:
                st.sidebar.error("請填寫完整資訊")
    
    st.markdown("""
    <div style="background-color: #EEF2FF; padding: 20px; border-radius: 15px; border-left: 5px solid #3B82F6;">
        <h3 style="margin-top:0; color:#1E3A8A;">👋 歡迎使用</h3>
        <p>請在左側選單選擇身份並登入，以查看您的訓練日程、積分排行及最新公告。</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# 登入後的側邊欄顯示
if st.session_state.is_admin:
    st.sidebar.success(f"🛡️ 管理員已登入")
else:
    st.sidebar.success(f"👤 學生 {st.session_state.user_id}")

if st.sidebar.button("🔌 登出系統", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.is_admin = False
    st.rerun()

# --- 6. 數據加載 ---
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = load_cloud_data('schedules', [])
if 'class_players_df' not in st.session_state:
    st.session_state.class_players_df = load_cloud_data('class_players', [])
if 'rank_df' not in st.session_state:
    st.session_state.rank_df = load_cloud_data('rankings', pd.DataFrame(columns=["年級", "班級", "姓名", "積分", "章別"]))
if 'attendance_records' not in st.session_state:
    st.session_state.attendance_records = load_cloud_data('attendance_records', pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單", "記錄人"]))
if 'announcements_df' not in st.session_state:
    st.session_state.announcements_df = load_cloud_data('announcements', pd.DataFrame(columns=["標題", "內容", "日期"]))
if 'tournaments_df' not in st.session_state:
    st.session_state.tournaments_df = load_cloud_data('tournaments', pd.DataFrame(columns=["比賽名稱", "日期", "截止日期", "連結", "備註"]))
if 'awards_df' not in st.session_state:
    st.session_state.awards_df = load_cloud_data('student_awards', pd.DataFrame(columns=["學生姓名", "比賽名稱", "獎項", "日期", "備註"]))

# 菜單導航
menu_options = ["📅 訓練日程表", "🏆 隊員排行榜", "📝 考勤點名", "🏅 學生得獎紀錄", "📢 活動公告", "🗓️ 比賽報名與賽程"]
if st.session_state.is_admin:
    menu_options.append("💰 學費與預算核算")
menu = st.sidebar.radio("功能選單", menu_options)

# --- 7. 頁面模組 ---

if menu == "📅 訓練日程表":
    st.title("📅 訓練班日程管理")
    if st.session_state.is_admin:
        with st.expander("📤 匯入日程檔案"):
            u_sched = st.file_uploader("選擇 Excel 檔案 (.xlsx)", type=["xlsx"])
            if u_sched:
                df_new = pd.read_excel(u_sched)
                if st.button("🚀 確認更新日程", type="primary"):
                    st.session_state.schedule_df = df_new
                    save_cloud_data('schedules', df_new)
                    st.rerun()
    
    if not st.session_state.schedule_df.empty:
        st.dataframe(st.session_state.schedule_df, use_container_width=True, hide_index=True)
    else:
        st.info("暫無日程資訊。")

elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分榜")
    st.markdown("""
    <div style="background-color:#FFFBEB; padding:15px; border-radius:10px; border-left:4px solid #F59E0B; margin-bottom:20px;">
        💡 <b>積分規則：</b> 考取香港壁球總會章別獎勵：白金(+400), 金(+200), 銀(+100), 銅(+50)
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.is_admin:
        with st.expander("🛠️ 排行榜後台管理"):
            tab_upload, tab_badge, tab_manual, tab_export = st.tabs(["📤 批量同步", "🥇 章別登記", "✏️ 手動調整", "📥 數據匯出"])
            
            with tab_upload:
                if st.button("🔄 從點名名單同步學生", type="primary"):
                    if not st.session_state.class_players_df.empty:
                        df_r = st.session_state.rank_df
                        for col in ["年級", "班級", "姓名", "積分", "章別"]:
                            if col not in df_r.columns: df_r[col] = 0 if col == "積分" else "無"
                        
                        count_added = 0
                        for _, p_row in st.session_state.class_players_df.iterrows():
                            exists = ((df_r["姓名"].astype(str).str.strip() == str(p_row["姓名"]).strip()) & (df_r["年級"].astype(str).str.strip() == str(p_row.get("年級", "-")).strip())).any()
                            if not exists:
                                new_entry = pd.DataFrame([{
                                    "年級": str(p_row.get("年級", "-")).strip(),
                                    "班級": str(p_row["班級"]).strip(),
                                    "姓名": str(p_row["姓名"]).strip(),
                                    "積分": 100,
                                    "章別": "無"
                                }])
                                df_r = pd.concat([df_r, new_entry], ignore_index=True)
                                count_added += 1
                        
                        st.session_state.rank_df = df_r
                        save_cloud_data('rankings', df_r)
                        st.success(f"同步完成！新增了 {count_added} 位新學生。")
                        st.rerun()

                u_rank = st.file_uploader("手動匯入 Excel", type=["xlsx"])
                if u_rank:
                    df_r = pd.read_excel(u_rank)
                    if st.button("🚀 覆蓋現有排名數據"):
                        st.session_state.rank_df = df_r
                        save_cloud_data('rankings', df_r)
                        st.rerun()
            
            with tab_badge:
                with st.form("badge_award_form"):
                    c1, c2, c3 = st.columns(3)
                    b_name = c1.text_input("獲章學生姓名")
                    b_grade = c2.text_input("年級 (如: P4)")
                    b_class = c3.text_input("班別 (如: 4A)")
                    b_type = st.selectbox("所考獲章別", ["白金章", "金章", "銀章", "銅章"])
                    if st.form_submit_button("確認發放獎勵積分", type="primary"):
                        df_r = st.session_state.rank_df.copy()
                        for col in ["年級", "班級", "姓名", "積分", "章別"]:
                            if col not in df_r.columns: df_r[col] = 0 if col == "積分" else "無"
                        
                        mask = (df_r["姓名"].astype(str).str.strip() == b_name.strip()) & (df_r["年級"].astype(str).str.strip() == b_grade.strip())
                        if any(mask):
                            idx = df_r[mask].index[0]
                            df_r.at[idx, "章別"] = b_type
                            current_pts = pd.to_numeric(df_r.at[idx, "積分"], errors='coerce')
                            if pd.isna(current_pts): current_pts = 0
                            df_r.at[idx, "積分"] = int(current_pts + BADGE_AWARDS[b_type]["points"])
                        else:
                            new_row = pd.DataFrame([{
                                "年級": b_grade.strip(), "班級": b_class.strip(), "姓名": b_name.strip(), 
                                "積分": 100 + BADGE_AWARDS[b_type]["points"], "章別": b_type
                            }])
                            df_r = pd.concat([df_r, new_row], ignore_index=True)
                        
                        st.session_state.rank_df = df_r
                        save_cloud_data('rankings', df_r)
                        st.success(f"已更新 {b_name} 的紀錄")
                        st.rerun()

            with tab_manual:
                with st.form("manual_adjust_form"):
                    m_name = st.text_input("輸入學生姓名")
                    m_grade = st.text_input("輸入年級")
                    m_points = st.number_input("調整分數 (加分/扣分)", value=10)
                    if st.form_submit_button("執行調整"):
                        df_r = st.session_state.rank_df.copy()
                        mask = (df_r["姓名"].astype(str).str.strip() == m_name.strip()) & (df_r["年級"].astype(str).str.strip() == m_grade.strip())
                        if any(mask):
                            idx = df_r[mask].index[0]
                            old_pts = pd.to_numeric(df_r.at[idx, "積分"], errors='coerce')
                            df_r.at[idx, "積分"] = int((0 if pd.isna(old_pts) else old_pts) + m_points)
                            st.session_state.rank_df = df_r
                            save_cloud_data('rankings', df_r)
                            st.success("調整成功")
                            st.rerun()
                        else: st.error("查無此人")

            with tab_export:
                if not st.session_state.rank_df.empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        st.session_state.rank_df.to_excel(writer, index=False)
                    st.download_button("📥 下載排行榜 Excel", data=output.getvalue(), file_name="ranking.xlsx")

    if not st.session_state.rank_df.empty:
        display_rank_df = st.session_state.rank_df.copy()
        for col in ["年級", "班級", "姓名", "積分", "章別"]:
            if col not in display_rank_df.columns: display_rank_df[col] = 0 if col == "積分" else "-"

        display_rank_df["姓名"] = display_rank_df["姓名"].astype(str).str.strip()
        display_rank_df = display_rank_df.drop_duplicates(subset=["年級", "姓名"], keep='first')
        display_rank_df["積分"] = pd.to_numeric(display_rank_df["積分"], errors='coerce').fillna(0).astype(int)
        display_rank_df = display_rank_df.sort_values(by="積分", ascending=False)
        
        def get_rank_ui(row):
            badge = str(row.get("章別", "無"))
            icon_info = BADGE_AWARDS.get(badge, {"icon": ""})
            return f"{icon_info['icon']} {badge}" if badge != "無" and badge != "nan" else "-"

        display_rank_df["榮譽勳章"] = display_rank_df.apply(get_rank_ui, axis=1)
        display_rank_df.reset_index(drop=True, inplace=True)
        display_rank_df.index = np.arange(1, len(display_rank_df) + 1)
        
        st.table(display_rank_df[["年級", "班級", "姓名", "積分", "榮譽勳章"]])
    else:
        st.info("尚無數據。")

elif menu == "📝 考勤點名":
    st.title("📝 考勤點名與報表")
    if st.session_state.is_admin:
        with st.expander("📤 上傳學生名單"):
            u_class = st.file_uploader("上傳 Excel", type=["xlsx"])
            if u_class:
                df_c = pd.read_excel(u_class)
                if st.button("🚀 更新名單"):
                    st.session_state.class_players_df = df_c
                    save_cloud_data('class_players', df_c)
                    st.rerun()

    if st.session_state.schedule_df.empty:
        st.warning("請先匯入日程表。")
    else:
        class_list = st.session_state.schedule_df["班級"].unique().tolist()
        c_sel_1, c_sel_2 = st.columns(2)
        sel_class = c_sel_1.selectbox("選擇班別", class_list)
        
        class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class]
        raw_dates = str(class_info.iloc[0].get("具體日期", ""))
        all_dates = [d.strip() for d in raw_dates.split(",") if d.strip()]
        sel_date = c_sel_2.selectbox("選擇日期", all_dates)
        
        if st.session_state.is_admin:
            tab1, tab2 = st.tabs(["🎯 點名執行", "📊 數據統計"])
        else:
            tab1 = st.container(); tab2 = None

        with tab1:
            current_players = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class] if not st.session_state.class_players_df.empty else pd.DataFrame()
            if not current_players.empty:
                attendance_recs = st.session_state.attendance_records
                existing_rec = attendance_recs[(attendance_recs["班級"] == sel_class) & (attendance_recs["日期"] == sel_date)]
                existing_list = existing_rec.iloc[0]["出席名單"].split(", ") if not existing_rec.empty and pd.notna(existing_rec.iloc[0]["出席名單"]) else []

                st.markdown(f"#### 📋 名單列表 ({len(current_players)} 人)")
                
                cols = st.columns(4)
                attendance_dict = {}
                for i, row in enumerate(current_players.to_dict('records')):
                    name = str(row['姓名'])
                    with cols[i % 4]:
                        attendance_dict[name] = st.checkbox(name, value=(name in existing_list), key=f"chk_{name}_{sel_date}", disabled=not st.session_state.is_admin)
                
                if st.session_state.is_admin:
                    if st.button("💾 儲存今日點名紀錄", type="primary"):
                        present_names = [n for n, p in attendance_dict.items() if p]
                        new_rec = {"班級": sel_class, "日期": sel_date, "出席人數": len(present_names), "出席名單": ", ".join(present_names), "記錄人": st.session_state.user_id}
                        df_recs = st.session_state.attendance_records
                        df_recs = df_recs[~((df_recs["班級"] == sel_class) & (df_recs["日期"] == sel_date))]
                        st.session_state.attendance_records = pd.concat([df_recs, pd.DataFrame([new_rec])], ignore_index=True)
                        save_cloud_data('attendance_records', st.session_state.attendance_records)
                        st.success("✅ 已儲存")
            else: st.info("無名單。")

        if tab2:
            with tab2:
                class_records = st.session_state.attendance_records[st.session_state.attendance_records["班級"] == sel_class]
                if not class_records.empty:
                    st.dataframe(class_records[["日期", "出席人數", "記錄人"]], hide_index=True, use_container_width=True)
                else: st.info("無考勤紀錄。")

elif menu == "🏅 學生得獎紀錄":
    st.title("🏅 學生比賽榮譽榜")
    if st.session_state.is_admin:
        with st.expander("➕ 新增得獎"):
            with st.form("new_award_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                a_name = c1.text_input("學生姓名")
                a_prize = c2.text_input("獎項 (如: 冠軍)")
                a_comp = st.text_input("比賽名稱")
                a_date = st.date_input("日期")
                a_note = st.text_area("備註")
                if st.form_submit_button("儲存紀錄", type="primary"):
                    new_award = {"學生姓名": a_name, "比賽名稱": a_comp, "獎項": a_prize, "日期": str(a_date), "備註": a_note}
                    st.session_state.awards_df = pd.concat([st.session_state.awards_df, pd.DataFrame([new_award])], ignore_index=True)
                    save_cloud_data('student_awards', st.session_state.awards_df)
                    st.rerun()

    if not st.session_state.awards_df.empty:
        student_real_name = ""
        if not st.session_state.is_admin and not st.session_state.class_players_df.empty:
            df_cp = st.session_state.class_players_df
            match = df_cp[(df_cp["班級"].astype(str).str.upper() + df_cp["學號"].astype(str).str.zfill(2)) == st.session_state.user_id]
            if not match.empty: student_real_name = str(match.iloc[0]["姓名"])
            
        for index, row in st.session_state.awards_df.sort_values(by="日期", ascending=False).iterrows():
            is_own = (str(row["學生姓名"]).strip() == str(student_real_name).strip() and student_real_name != "")
            bg = "#EFF6FF" if is_own else "white"
            border = "2px solid #3B82F6" if is_own else "1px solid #E5E7EB"
            
            st.markdown(f"""
            <div style="background-color: {bg}; padding: 20px; border-radius: 12px; border: {border}; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin:0; color:#1E40AF;">🏆 {row['獎項']}</h3>
                    <span style="color:#6B7280; font-size:0.9em;">📅 {row['日期']}</span>
                </div>
                <p style="margin: 10px 0 5px 0;"><b>學生：</b>{row['學生姓名']} { ' <span style="color:#EF4444; font-weight:bold;">(⭐恭喜您！)</span>' if is_own else ''}</p>
                <p style="margin: 5px 0;"><b>比賽：</b>{row['比賽名稱']}</p>
                { f'<div style="margin-top:10px; padding-top:10px; border-top:1px dashed #DDD; color:#4B5563; font-style:italic;">{row["備註"]}</div>' if row["備註"] else '' }
            </div>
            """, unsafe_allow_html=True)
            if st.session_state.is_admin:
                if st.button(f"🗑️ 刪除紀錄", key=f"del_award_{index}"):
                    st.session_state.awards_df = st.session_state.awards_df.drop(index)
                    save_cloud_data('student_awards', st.session_state.awards_df)
                    st.rerun()
    else: st.info("目前尚無得獎紀錄。")

elif menu == "📢 活動公告":
    st.title("📢 賽事及活動公告")
    if st.session_state.is_admin:
        with st.expander("📝 發布新公告"):
            with st.form("new_post", clear_on_submit=True):
                p_title = st.text_input("公告標題")
                p_content = st.text_area("內容細節")
                if st.form_submit_button("發布公告", type="primary"):
                    new_p = pd.DataFrame([{"標題": p_title, "內容": p_content, "日期": datetime.now().strftime("%Y-%m-%d")}])
                    st.session_state.announcements_df = pd.concat([st.session_state.announcements_df, new_p], ignore_index=True)
                    save_cloud_data('announcements', st.session_state.announcements_df)
                    st.rerun()
    
    if not st.session_state.announcements_df.empty:
        for index, row in st.session_state.announcements_df.iloc[::-1].iterrows():
            with st.container():
                st.markdown(f"""
                <div style="background: white; padding: 20px; border-radius: 15px; border: 1px solid #EEE; margin-bottom: 20px;">
                    <span style="background:#DBEAFE; color:#1E40AF; padding:4px 10px; border-radius:20px; font-size:0.8em; font-weight:bold;">{row['日期']}</span>
                    <h3 style="margin-top:10px;">{row['標題']}</h3>
                    <p style="color:#4B5563; line-height:1.6;">{row['內容']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.session_state.is_admin:
                    if st.button(f"🗑️ 刪除公告", key=f"del_ann_{index}"):
                        st.session_state.announcements_df = st.session_state.announcements_df.drop(index)
                        save_cloud_data('announcements', st.session_state.announcements_df)
                        st.rerun()
    else: st.info("暫無公告。")

elif menu == "🗓️ 比賽報名與賽程":
    st.title("🗓️ 賽事報名與賽程管理")
    if st.session_state.is_admin:
        with st.expander("➕ 發布比賽資訊"):
            with st.form("new_tournament", clear_on_submit=True):
                t_name = st.text_input("比賽名稱")
                c1, c2 = st.columns(2)
                t_date = c1.date_input("比賽日期")
                t_due = c2.date_input("截止日期")
                t_link = st.text_input("報名連結")
                t_note = st.text_area("備註說明")
                if st.form_submit_button("確認發布", type="primary"):
                    new_t = pd.DataFrame([{"比賽名稱": t_name, "日期": str(t_date), "截止日期": str(t_due), "連結": t_link, "備註": t_note}])
                    st.session_state.tournaments_df = pd.concat([st.session_state.tournaments_df, new_t], ignore_index=True)
                    save_cloud_data('tournaments', st.session_state.tournaments_df)
                    st.rerun()
    
    if not st.session_state.tournaments_df.empty:
        st.dataframe(st.session_state.tournaments_df, use_container_width=True, hide_index=True)
    else: st.info("暫無賽事。")

elif menu == "💰 學費與預算核算":
    st.title("💰 預算與營運核算")
    
    col_input_left, col_input_right = st.columns([2, 1])
    with col_input_left:
        st.subheader("📋 支出設定 (康文署標準)")
        sc1, sc2, sc3 = st.columns(3)
        n_team = sc1.number_input("校隊訓練班 (班)", value=1, step=1); cost_team_unit = 2750
        n_train = sc2.number_input("非校隊訓練班 (班)", value=3, step=1); cost_train_unit = 1350
        n_hobby = sc3.number_input("簡易運動班 (班)", value=4, step=1); cost_hobby_unit = 1200
            
    with col_input_right:
        st.subheader("💵 收入設定")
        total_students = st.number_input("總人數", value=50, step=1)
        fee_per_student = st.number_input("學費 ($)", value=250)

    st.divider()
    
    total_rev = total_students * fee_per_student
    total_exp = (n_team * cost_team_unit) + (n_train * cost_train_unit) + (n_hobby * cost_hobby_unit)
    profit = total_rev - total_exp

    m1, m2, m3 = st.columns(3)
    m1.metric("預計總收入", f"${total_rev:,}")
    m2.metric("預計總支出", f"${total_exp:,}")
    m3.metric("預計淨利潤", f"${profit:,}", delta=float(profit))

    summary_data = {
        "項目": ["校隊班 (支出)", "非校隊班 (支出)", "簡易班 (支出)", "學生學費 (收入)"],
        "數量": [f"{n_team} 班", f"{n_train} 班", f"{n_hobby} 班", f"{total_students} 人"],
        "小計 ($)": [-(n_team*cost_team_unit), -(n_train*cost_train_unit), -(n_hobby*cost_hobby_unit), total_rev]
    }
    st.table(pd.DataFrame(summary_data))
