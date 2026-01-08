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
            for doc in coll_ref.stream(): doc.reference.delete()
            for _, row in df.iterrows():
                if collection_name == 'attendance_records':
                    doc_id = f"{row.get('班級', 'Unknown')}_{row.get('日期', 'Unknown')}".replace("/", "-")
                elif collection_name == 'announcements':
                    doc_id = f"{row.get('日期')}_{row.get('標題', 'NoTitle')}"
                elif collection_name == 'tournaments':
                    doc_id = f"tm_{row.get('比賽名稱', 'NoName')}_{row.get('日期', 'NoDate')}"
                elif collection_name == 'student_awards':
                    doc_id = f"award_{row.get('學生姓名')}_{row.get('日期')}_{np.random.randint(1000)}"
                elif '姓名' in row and '班級' in row:
                    doc_id = f"{row.get('班級')}_{row.get('姓名')}"
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
st.sidebar.title("🏸 正覺壁球管理系統")

if not st.session_state.logged_in:
    st.sidebar.subheader("🔑 系統登入")
    login_mode = st.sidebar.radio("身份選擇", ["學生/家長", "管理員"])
    
    if login_mode == "管理員":
        pwd = st.sidebar.text_input("管理員密碼", type="password")
        if st.sidebar.button("登入管理系統"):
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
        if st.sidebar.button("登入"):
            if s_class and s_num:
                st.session_state.logged_in = True
                st.session_state.is_admin = False
                st.session_state.user_id = f"{s_class.upper()}{s_num.zfill(2)}"
                st.rerun()
            else:
                st.sidebar.error("請填寫完整資訊")
    
    st.info("👋 歡迎！請先在左側選單登入系統。")
    st.stop()

# 登入後的側邊欄顯示
if st.session_state.is_admin:
    st.sidebar.success(f"🛡️ 管理員已登入")
else:
    st.sidebar.success(f"👤 學生 {st.session_state.user_id} 已登入")

if st.sidebar.button("🔌 登出系統"):
    st.session_state.logged_in = False
    st.session_state.is_admin = False
    st.rerun()

# --- 6. 數據加載 ---
force_refresh = st.sidebar.button("🔄 刷新雲端數據")
if 'schedule_df' not in st.session_state or force_refresh:
    st.session_state.schedule_df = load_cloud_data('schedules', [])
if 'class_players_df' not in st.session_state or force_refresh:
    st.session_state.class_players_df = load_cloud_data('class_players', [])
if 'rank_df' not in st.session_state or force_refresh:
    st.session_state.rank_df = load_cloud_data('rankings', pd.DataFrame(columns=["班級", "姓名", "積分", "章別"]))
if 'attendance_records' not in st.session_state or force_refresh:
    st.session_state.attendance_records = load_cloud_data('attendance_records', pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單", "記錄人"]))
if 'announcements_df' not in st.session_state or force_refresh:
    st.session_state.announcements_df = load_cloud_data('announcements', pd.DataFrame(columns=["標題", "內容", "日期"]))
if 'tournaments_df' not in st.session_state or force_refresh:
    st.session_state.tournaments_df = load_cloud_data('tournaments', pd.DataFrame(columns=["比賽名稱", "日期", "截止日期", "連結", "備註"]))
if 'awards_df' not in st.session_state or force_refresh:
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
        u_sched = st.file_uploader("匯入日程 Excel", type=["xlsx"])
        if u_sched:
            df_new = pd.read_excel(u_sched)
            if st.button("🚀 確認更新日程"):
                st.session_state.schedule_df = df_new
                save_cloud_data('schedules', df_new)
                st.rerun()
    if not st.session_state.schedule_df.empty:
        st.dataframe(st.session_state.schedule_df, use_container_width=True)
    else:
        st.info("暫無日程。")

elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分榜")
    st.info("💡 考取香港壁球總會章別獎勵：白金(+400), 金(+200), 銀(+100), 銅(+50)")
    
    if st.session_state.is_admin:
        with st.expander("🛠️ 排行榜管理"):
            tab_upload, tab_badge, tab_manual, tab_export = st.tabs(["📤 批量匯入/同步", "🥇 章別獎勵登記", "✏️ 手動調整分數", "📥 匯出排行榜"])
            
            with tab_upload:
                st.write("您可以從「學生名單」自動同步或手動匯入 Excel。")
                if st.button("🔄 從壁球班名單同步所有學生", help="將點名系統中的學生自動加入排行榜"):
                    if not st.session_state.class_players_df.empty:
                        df_r = st.session_state.rank_df
                        for col in ["班級", "姓名", "積分", "章別"]:
                            if col not in df_r.columns: df_r[col] = 0 if col == "積分" else "無"
                        
                        count_added = 0
                        for _, p_row in st.session_state.class_players_df.iterrows():
                            exists = ((df_r["姓名"] == p_row["姓名"]) & (df_r["班級"] == p_row["班級"])).any()
                            if not exists:
                                new_entry = pd.DataFrame([{
                                    "班級": p_row["班級"],
                                    "姓名": p_row["姓名"],
                                    "積分": 100,
                                    "章別": "無"
                                }])
                                df_r = pd.concat([df_r, new_entry], ignore_index=True)
                                count_added += 1
                        
                        st.session_state.rank_df = df_r
                        save_cloud_data('rankings', df_r)
                        st.success(f"同步完成！新增了 {count_added} 位學生。")
                        st.rerun()

                u_rank = st.file_uploader("匯入積分榜 Excel (需包含: 班級, 姓名, 積分)", type=["xlsx"])
                if u_rank:
                    df_r = pd.read_excel(u_rank)
                    if st.button("🚀 確認更新積分排名"):
                        st.session_state.rank_df = df_r
                        save_cloud_data('rankings', df_r)
                        st.rerun()
            
            with tab_badge:
                with st.form("badge_award_form"):
                    b_name = st.text_input("獲章學生姓名")
                    b_class = st.text_input("班別 (如: 4A)")
                    b_type = st.selectbox("所考獲章別", ["白金章", "金章", "銀章", "銅章"])
                    if st.form_submit_button("確認發放獎勵積分"):
                        df_r = st.session_state.rank_df
                        for col in ["班級", "姓名", "積分", "章別"]:
                            if col not in df_r.columns: df_r[col] = 0 if col == "積分" else "無"
                        
                        mask = (df_r["姓名"] == b_name) & (df_r["班級"] == b_class)
                        if any(mask):
                            idx = df_r[mask].index[0]
                            df_r.at[idx, "章別"] = b_type
                            current_pts = pd.to_numeric(df_r.at[idx, "積分"], errors='coerce')
                            if pd.isna(current_pts): current_pts = 0
                            df_r.at[idx, "積分"] = current_pts + BADGE_AWARDS[b_type]["points"]
                        else:
                            new_row = pd.DataFrame([{
                                "班級": b_class, "姓名": b_name, 
                                "積分": 100 + BADGE_AWARDS[b_type]["points"],
                                "章別": b_type
                            }])
                            df_r = pd.concat([df_r, new_row], ignore_index=True)
                        
                        save_cloud_data('rankings', df_r)
                        st.success(f"已登記 {b_name} 的 {b_type} 分數。")
                        st.rerun()

            with tab_manual:
                with st.form("manual_adjust_form"):
                    m_name = st.text_input("學生姓名")
                    m_class = st.text_input("班別")
                    m_points = st.number_input("調整分數 (加分輸入正數，扣分輸入負數)", value=10, step=1)
                    if st.form_submit_button("執行分數調整"):
                        df_r = st.session_state.rank_df
                        for col in ["班級", "姓名", "積分", "章別"]:
                            if col not in df_r.columns: df_r[col] = 0 if col == "積分" else "無"
                        
                        mask = (df_r["姓名"] == m_name) & (df_r["班級"] == m_class)
                        if any(mask):
                            idx = df_r[mask].index[0]
                            old_pts = pd.to_numeric(df_r.at[idx, "積分"], errors='coerce')
                            if pd.isna(old_pts): old_pts = 0
                            df_r.at[idx, "積分"] = old_pts + m_points
                            save_cloud_data('rankings', df_r)
                            st.success(f"已調整 {m_name} 的分數 ({old_pts} -> {old_pts + m_points})")
                            st.rerun()
                        else:
                            st.error("找不到該學生，請確認姓名及班別是否正確。")

            with tab_export:
                st.write("將目前的排行榜內容匯出為 Excel 檔案以供存檔或列印。")
                if not st.session_state.rank_df.empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        # 整理並排序後匯出
                        export_df = st.session_state.rank_df.copy()
                        export_df["積分"] = pd.to_numeric(export_df["積分"], errors='coerce').fillna(0).astype(int)
                        export_df = export_df.sort_values(by="積分", ascending=False)
                        export_df.to_excel(writer, index=False, sheet_name='積分榜')
                    
                    st.download_button(
                        label="📥 下載積分排行榜 (Excel)",
                        data=output.getvalue(),
                        file_name=f"squash_ranking_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("目前無數據可供匯出。")
    
    if not st.session_state.rank_df.empty:
        display_rank_df = st.session_state.rank_df.copy()
        required_cols = ["班級", "姓名", "積分", "章別"]
        for col in required_cols:
            if col not in display_rank_df.columns:
                display_rank_df[col] = 0 if col == "積分" else "無"

        display_rank_df["積分"] = pd.to_numeric(display_rank_df["積分"], errors='coerce').fillna(0).astype(int)
        display_rank_df = display_rank_df.sort_values(by="積分", ascending=False)
        
        def get_rank_ui(row):
            badge = str(row.get("章別", "無"))
            icon_info = BADGE_AWARDS.get(badge, {"icon": ""})
            return f"{icon_info['icon']} {badge}" if badge != "無" and badge != "nan" else "-"

        display_rank_df["榮譽勳章"] = display_rank_df.apply(get_rank_ui, axis=1)
        display_rank_df.reset_index(drop=True, inplace=True)
        display_rank_df.index = np.arange(1, len(display_rank_df) + 1)
        
        cols_to_show = ["班級", "姓名", "積分", "榮譽勳章"]
        st.table(display_rank_df[cols_to_show])
    else:
        st.info("暫無積分數據。")

elif menu == "📝 考勤點名":
    st.title("📝 考勤點名與報表")
    if st.session_state.is_admin:
        u_class = st.file_uploader("匯入學生名單 Excel (欄位：班級, 姓名, 年級, 學號[選填])", type=["xlsx"])
        if u_class:
            df_c = pd.read_excel(u_class)
            if st.button("🚀 確認更新名單"):
                st.session_state.class_players_df = df_c
                save_cloud_data('class_players', df_c)
                st.rerun()

    if st.session_state.schedule_df.empty:
        st.warning("請先在『訓練日程表』匯入班級數據。")
    else:
        class_list = st.session_state.schedule_df["班級"].unique().tolist()
        sel_class = st.selectbox("請選擇班別", class_list)
        
        class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class]
        raw_dates = str(class_info.iloc[0].get("具體日期", ""))
        all_dates = [d.strip() for d in raw_dates.split(",") if d.strip()]
        
        if st.session_state.is_admin:
            tabs = st.tabs(["🎯 今日點名", "📊 考勤總表"])
            tab1 = tabs[0]
            tab2 = tabs[1]
        else:
            tab1 = st.container()
            tab2 = None

        with tab1:
            if not st.session_state.is_admin:
                st.markdown("### 🎯 今日點名紀錄")
            sel_date = st.selectbox("選擇日期", all_dates)
            current_players = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class] if not st.session_state.class_players_df.empty else pd.DataFrame()
            
            if not current_players.empty:
                attendance_recs = st.session_state.attendance_records
                existing_rec = attendance_recs[(attendance_recs["班級"] == sel_class) & (attendance_recs["日期"] == sel_date)]
                existing_list = existing_rec.iloc[0]["出席名單"].split(", ") if not existing_rec.empty and pd.notna(existing_rec.iloc[0]["出席名單"]) else []

                st.markdown(f"#### 📋 {sel_class} - {sel_date}")
                if not existing_rec.empty:
                    st.caption(f"上次更新由: {existing_rec.iloc[0].get('記錄人', '系統')}")

                cols = st.columns(4)
                attendance_dict = {}
                for i, row in enumerate(current_players.to_dict('records')):
                    name = str(row['姓名'])
                    with cols[i % 4]:
                        attendance_dict[name] = st.checkbox(
                            f"{name}", 
                            value=(name in existing_list), 
                            key=f"chk_{name}_{sel_date}",
                            disabled=not st.session_state.is_admin
                        )
                
                if st.session_state.is_admin:
                    if st.button("💾 儲存點名", type="primary"):
                        present_names = [n for n, p in attendance_dict.items() if p]
                        new_rec = {
                            "班級": sel_class, 
                            "日期": sel_date, 
                            "出席人數": len(present_names), 
                            "出席名單": ", ".join(present_names),
                            "記錄人": st.session_state.user_id
                        }
                        df_recs = st.session_state.attendance_records
                        df_recs = df_recs[~((df_recs["班級"] == sel_class) & (df_recs["日期"] == sel_date))]
                        st.session_state.attendance_records = pd.concat([df_recs, pd.DataFrame([new_rec])], ignore_index=True)
                        save_cloud_data('attendance_records', st.session_state.attendance_records)
                        st.success("✅ 儲存成功")
                else:
                    st.info("ℹ️ 您目前的權限僅能查看點名紀錄，無法進行修改。")
            else:
                st.info("該班別尚無名單數據。")

        if tab2 is not None:
            with tab2:
                st.markdown(f"### 📊 {sel_class} 考勤總表")
                class_records = st.session_state.attendance_records[st.session_state.attendance_records["班級"] == sel_class]
                class_players = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class]
                
                if class_players.empty:
                    st.info("尚無學生名單數據。")
                elif class_records.empty:
                    st.info("尚無考勤紀錄。")
                else:
                    report_dates = all_dates
                    student_names = class_players["姓名"].unique().tolist()
                    
                    matrix_data = []
                    for name in student_names:
                        row_data = {"學生姓名": name}
                        for date in report_dates:
                            daily_rec = class_records[class_records["日期"] == date]
                            if not daily_rec.empty:
                                present_list = str(daily_rec.iloc[0]["出席名單"]).split(", ")
                                row_data[date] = "✅" if name in present_list else "✘"
                            else:
                                row_data[date] = "-" 
                        matrix_data.append(row_data)
                    
                    report_df = pd.DataFrame(matrix_data)
                    st.dataframe(report_df.set_index("學生姓名"), use_container_width=True)
                    
                    csv = report_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 下載考勤報表 (CSV)",
                        data=csv,
                        file_name=f"{sel_class}_attendance_report.csv",
                        mime="text/csv",
                    )

elif menu == "🏅 學生得獎紀錄":
    st.title("🏅 學生比賽榮譽榜")
    
    if st.session_state.is_admin:
        with st.expander("➕ 新增得獎紀錄"):
            with st.form("new_award_form", clear_on_submit=True):
                a_name = st.text_input("學生姓名 (如: 張小明)")
                a_comp = st.text_input("比賽名稱 (如: 全港青少年壁球錦標賽)")
                a_prize = st.text_input("獎項 (如: 冠軍 / 優異獎)")
                a_date = st.date_input("獲獎日期")
                a_note = st.text_area("備註")
                if st.form_submit_button("儲存紀錄"):
                    new_award = {
                        "學生姓名": a_name,
                        "比賽名稱": a_comp,
                        "獎項": a_prize,
                        "日期": str(a_date),
                        "備註": a_note
                    }
                    st.session_state.awards_df = pd.concat([st.session_state.awards_df, pd.DataFrame([new_award])], ignore_index=True)
                    save_cloud_data('student_awards', st.session_state.awards_df)
                    st.rerun()

    if not st.session_state.awards_df.empty:
        student_real_name = ""
        if not st.session_state.is_admin and not st.session_state.class_players_df.empty:
            df_cp = st.session_state.class_players_df
            if "班級" in df_cp.columns and "學號" in df_cp.columns:
                match = df_cp[(df_cp["班級"].astype(str).str.upper() + df_cp["學號"].astype(str).str.zfill(2)) == st.session_state.user_id]
                if not match.empty:
                    student_real_name = str(match.iloc[0]["姓名"])
            
        st.markdown("### 🏆 榮譽榜單")
        
        for index, row in st.session_state.awards_df.sort_values(by="日期", ascending=False).iterrows():
            is_own_award = (str(row["學生姓名"]).strip() == str(student_real_name).strip() and student_real_name != "")
            bg_color = "#e8f0fe" if is_own_award else "#ffffff"
            border = "2px solid #1a73e8" if is_own_award else "1px solid #e0e0e0"
            text_color = "#202124"
            
            st.markdown(f"""
            <div style="background-color: {bg_color}; padding: 18px; border-radius: 12px; border: {border}; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h3 style="margin:0; color: #1a73e8; font-size: 1.4em;">🏆 {row['獎項']}</h3>
                <div style="color: {text_color}; margin-top: 10px;">
                    <p style="margin:4px 0;"><b>比賽名稱：</b>{row['比賽名稱']}</p>
                    <p style="margin:4px 0;"><b>獲獎學生：</b>{row['學生姓名']} { ' <span style="color:#d93025; font-weight:bold;">(⭐ 恭喜您！)</span>' if is_own_award else ''}</p>
                    <p style="margin:4px 0; font-size: 0.9em; color: #5f6368;">📅 獲獎日期：{row['日期']}</p>
                    { f'<p style="margin:8px 0 0 0; font-style: italic; border-top: 1px dashed #ccc; padding-top: 8px;">{row["備註"]}</p>' if row["備註"] else '' }
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.is_admin:
                if st.button(f"🗑️ 刪除此項紀錄", key=f"del_award_{index}"):
                    st.session_state.awards_df = st.session_state.awards_df.drop(index)
                    save_cloud_data('student_awards', st.session_state.awards_df)
                    st.rerun()
    else:
        st.info("目前尚無得獎紀錄。")

elif menu == "📢 活動公告":
    st.title("📢 賽事及活動公告")
    if st.session_state.is_admin:
        with st.form("new_post", clear_on_submit=True):
            p_title = st.text_input("公告標題")
            p_content = st.text_area("公告內容")
            if st.form_submit_button("發布公告"):
                new_p = pd.DataFrame([{"標題": p_title, "內容": p_content, "日期": datetime.now().strftime("%Y-%m-%d")}])
                st.session_state.announcements_df = pd.concat([st.session_state.announcements_df, new_p], ignore_index=True)
                save_cloud_data('announcements', st.session_state.announcements_df)
                st.rerun()
    
    if not st.session_state.announcements_df.empty:
        for index, row in st.session_state.announcements_df.iloc[::-1].iterrows():
            with st.chat_message("user"):
                st.subheader(row['標題'])
                st.caption(f"📅 {row['日期']}")
                st.write(row['內容'])
                if st.session_state.is_admin:
                    if st.button(f"🗑️ 刪除", key=f"del_ann_{index}"):
                        st.session_state.announcements_df = st.session_state.announcements_df.drop(index)
                        save_cloud_data('announcements', st.session_state.announcements_df)
                        st.rerun()

elif menu == "🗓️ 比賽報名與賽程":
    st.title("🗓️ 賽事報名與賽程管理")
    if st.session_state.is_admin:
        with st.expander("➕ 新增比賽"):
            with st.form("new_tournament", clear_on_submit=True):
                t_name = st.text_input("比賽名稱")
                c1, c2 = st.columns(2)
                t_date = c1.date_input("比賽日期")
                t_due = c2.date_input("報名截止")
                t_link = st.text_input("連結")
                t_note = st.text_area("備註")
                if st.form_submit_button("發布賽事"):
                    new_t = pd.DataFrame([{"比賽名稱": t_name, "日期": str(t_date), "截止日期": str(t_due), "連結": t_link, "備註": t_note}])
                    st.session_state.tournaments_df = pd.concat([st.session_state.tournaments_df, new_t], ignore_index=True)
                    save_cloud_data('tournaments', st.session_state.tournaments_df)
                    st.rerun()
    st.dataframe(st.session_state.tournaments_df, use_container_width=True)

elif menu == "💰 學費與預算核算":
    st.title("💰 預算與營運核算 (康文署標準)")
    st.info("收入：該期學生總人數 × 學費。支出：學校按開班數支付給康文署的費用。")
    
    col_input_left, col_input_right = st.columns([2, 1])
    
    with col_input_left:
        st.subheader("📋 支出設定 (開班數)")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            n_team = st.number_input("校隊訓練班 (班)", value=1, step=1)
            cost_team_unit = 2750
        with sc2:
            n_train = st.number_input("非校隊訓練班 (班)", value=3, step=1)
            cost_train_unit = 1350
        with sc3:
            n_hobby = st.number_input("簡易運動班 (班)", value=4, step=1)
            cost_hobby_unit = 1200
            
    with col_input_right:
        st.subheader("💵 收入設定")
        total_students = st.number_input("該期學生總人數", value=50, step=1)
        fee_per_student = st.number_input("每位學生學費 ($)", value=250)

    st.divider()
    
    total_revenue = total_students * fee_per_student
    exp_team = n_team * cost_team_unit
    exp_train = n_train * cost_train_unit
    exp_hobby = n_hobby * cost_hobby_unit
    total_expense = exp_team + exp_train + exp_hobby
    profit = total_revenue - total_expense

    m1, m2, m3 = st.columns(3)
    m1.metric("預計總收入 (學費)", f"${total_revenue:,}")
    m2.metric("預計總支出 (開班費)", f"${total_expense:,}")
    m3.metric("預計淨利潤", f"${profit:,}", delta=float(profit))

    summary_data = {
        "項目": ["校隊訓練班 (支出)", "非校隊訓練班 (支出)", "簡易運動班 (支出)", "學生學費 (總收入)"],
        "數量 / 人數": [f"{n_team} 班", f"{n_train} 班", f"{n_hobby} 班", f"{total_students} 人"],
        "單位金額 ($)": [cost_team_unit, cost_train_unit, cost_hobby_unit, fee_per_student],
        "小計 ($)": [-exp_team, -exp_train, -exp_hobby, total_revenue]
    }
    st.table(pd.DataFrame(summary_data))
    st.success(f"💡 結算：本期預計營運利潤為 HK$ {profit:,}")
