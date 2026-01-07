import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# 嘗試匯入 Firebase 套件
try:
    from firebase_admin import credentials, firestore, initialize_app, get_app
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide", initial_sidebar_state="expanded")

# --- 1. Firebase 雲端儲存配置 ---
def init_firebase():
    """初始化 Firebase 並返回 Firestore Client"""
    if not HAS_FIREBASE:
        return None
    if 'db' not in st.session_state:
        try:
            app = get_app()
        except ValueError:
            try:
                if "firebase_config" in st.secrets:
                    key_dict = dict(st.secrets["firebase_config"])
                    if "private_key" in key_dict:
                        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                    cred = credentials.Certificate(key_dict)
                    app = initialize_app(cred)
                else:
                    st.session_state.db = None
                    return None
            except Exception:
                st.session_state.db = None
                return None
        st.session_state.db = firestore.client()
    return st.session_state.db

db = init_firebase()
app_id = "squash-management-v1"

# --- 2. 數據存取與同步函數 ---
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
                # 針對考勤表特別檢查，如果雲端有資料但缺欄位，強制補齊
                if collection_name == 'attendance_records':
                    for col in ["班級", "日期", "出席人數", "出席名單"]:
                        if col not in df.columns:
                            df[col] = ""
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
            for doc in coll_ref.stream():
                doc.reference.delete()
            
            for _, row in df.iterrows():
                if collection_name == 'attendance_records':
                    doc_id = f"{row.get('班級', 'Unknown')}_{row.get('日期', 'Unknown')}".replace("/", "-")
                elif '姓名' in row and '班級' in row:
                    doc_id = f"{row.get('班級')}_{row.get('姓名')}"
                else:
                    doc_id = str(np.random.randint(1000000))
                
                clean_row = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
                coll_ref.document(doc_id).set(clean_row)
            st.toast(f"✅ {collection_name} 同步成功")
        except Exception as e:
            st.error(f"同步失敗: {e}")

# --- 3. 權限檢查 ---
ADMIN_PASSWORD = "8888"
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
    else:
        st.error("密碼錯誤")

# --- 4. 數據初始化 ---
force_refresh = st.sidebar.button("🔄 強制刷新雲端數據")

if 'schedule_df' not in st.session_state or force_refresh:
    st.session_state.schedule_df = load_cloud_data('schedules', [])
if 'class_players_df' not in st.session_state or force_refresh:
    st.session_state.class_players_df = load_cloud_data('class_players', [])
if 'rank_df' not in st.session_state or force_refresh:
    st.session_state.rank_df = load_cloud_data('rankings', [])
if 'attendance_records' not in st.session_state or force_refresh:
    # 這裡明確傳入包含 4 個必要欄位的空 DataFrame 作為 default_data
    empty_att = pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單"])
    st.session_state.attendance_records = load_cloud_data('attendance_records', empty_att)
if 'announcements_df' not in st.session_state or force_refresh:
    st.session_state.announcements_df = load_cloud_data('announcements', pd.DataFrame(columns=["標題", "內容", "日期"]))

# --- 側邊欄導航 ---
st.sidebar.title("🏸 正覺壁球管理系統")
if not st.session_state.is_admin:
    st.sidebar.text_input("管理員密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 管理員模式")
    if st.sidebar.button("🔌 登出"):
        st.session_state.is_admin = False
        st.rerun()

menu = st.sidebar.radio("功能選單", ["📅 訓練日程表", "🏆 隊員排行榜", "📝 考勤點名", "📢 活動公告", "💰 學費預算計算"])

# --- 頁面 1: 訓練日程表 ---
if menu == "📅 訓練日程表":
    st.title("📅 訓練班日程管理")
    if st.session_state.is_admin:
        u_sched = st.file_uploader("匯入日程 Excel (欄位：班級, 地點, 時間, 日期, 堂數, 具體日期)", type=["xlsx"])
        if u_sched:
            df_new = pd.read_excel(u_sched)
            if st.button("🚀 確認更新日程"):
                st.session_state.schedule_df = df_new
                save_cloud_data('schedules', df_new)
                st.rerun()
    
    if not st.session_state.schedule_df.empty:
        st.dataframe(st.session_state.schedule_df, use_container_width=True)
    else:
        st.info("暫無日程資料，請管理員匯入。")

# --- 頁面 2: 隊員排行榜 ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分榜")
    if st.session_state.is_admin:
        u_rank = st.file_uploader("匯入積分榜 Excel", type=["xlsx"])
        if u_rank:
            df_r = pd.read_excel(u_rank)
            if st.button("🚀 更新積分排名"):
                st.session_state.rank_df = df_r
                save_cloud_data('rankings', df_r)
                st.rerun()
    
    if not st.session_state.rank_df.empty:
        st.table(st.session_state.rank_df)
    else:
        st.info("暫無積分排名數據。")

# --- 頁面 3: 考勤點名 ---
elif menu == "📝 考勤點名":
    st.title("📝 考勤點名與全期紀錄")
    
    if st.session_state.is_admin:
        with st.expander("📥 匯入學生名單 (欄位：班級, 姓名, 年級)"):
            u_class = st.file_uploader("上傳 Excel 名單", type=["xlsx"])
            if u_class:
                df_c = pd.read_excel(u_class)
                if st.button("🚀 確認更新訓練班名單"):
                    st.session_state.class_players_df = df_c
                    save_cloud_data('class_players', df_c)
                    st.rerun()

    if st.session_state.schedule_df.empty:
        st.warning("請先在『訓練日程表』匯入班級數據。")
    else:
        # 確保 schedule_df 含有班級欄位
        if "班級" in st.session_state.schedule_df.columns:
            class_list = st.session_state.schedule_df["班級"].unique().tolist()
            sel_class = st.selectbox("請選擇班別", class_list)
            
            class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class]
            raw_dates = str(class_info.iloc[0]["具體日期"])
            all_dates = [d.strip() for d in raw_dates.split(",") if d.strip()]
            
            tab1, tab2 = st.tabs(["🎯 今日點名", "📊 課程考勤總表 (匯出)"])
            
            with tab1:
                sel_date = st.selectbox("選擇點名日期", all_dates)
                current_players = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class] if not st.session_state.class_players_df.empty else pd.DataFrame()
                
                if not current_players.empty:
                    attendance_recs = st.session_state.attendance_records
                    
                    # 重要：增加檢查機制，避免 KeyError: '班級'
                    if "班級" in attendance_recs.columns and "日期" in attendance_recs.columns:
                        existing_rec = attendance_recs[(attendance_recs["班級"] == sel_class) & (attendance_recs["日期"] == sel_date)]
                        existing_list = existing_rec.iloc[0]["出席名單"].split(", ") if not existing_rec.empty and pd.notna(existing_rec.iloc[0]["出席名單"]) else []
                    else:
                        existing_list = []

                    st.markdown(f"#### 📋 {sel_class} - {sel_date} 名單")
                    cols = st.columns(4)
                    attendance_dict = {}
                    for i, row in enumerate(current_players.to_dict('records')):
                        name = str(row['姓名'])
                        grade = str(row.get('年級', '-'))
                        with cols[i % 4]:
                            attendance_dict[name] = st.checkbox(f"{name} ({grade})", value=(name in existing_list), key=f"chk_{name}_{sel_date}")
                    
                    if st.session_state.is_admin:
                        if st.button("💾 儲存今日點名紀錄", use_container_width=True, type="primary"):
                            present_names = [n for n, p in attendance_dict.items() if p]
                            new_rec = {
                                "班級": sel_class, "日期": sel_date, 
                                "出席人數": len(present_names), "出席名單": ", ".join(present_names)
                            }
                            df_recs = st.session_state.attendance_records
                            # 如果欄位不存在，先初始化欄位
                            if "班級" not in df_recs.columns:
                                df_recs = pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單"])
                            
                            # 移除重複項
                            df_recs = df_recs[~((df_recs["班級"] == sel_class) & (df_recs["日期"] == sel_date))]
                            st.session_state.attendance_records = pd.concat([df_recs, pd.DataFrame([new_rec])], ignore_index=True)
                            save_cloud_data('attendance_records', st.session_state.attendance_records)
                            st.success(f"✅ {sel_date} 點名紀錄已儲存")
                else:
                    st.info(f"找不到名單，請先匯入。")

            with tab2:
                st.markdown(f"#### 📊 {sel_class} 全期出席匯總表")
                students = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class]["姓名"].tolist() if not st.session_state.class_players_df.empty else []
                
                if students:
                    report_data = []
                    for s in students:
                        row = {"姓名": s}
                        for d in all_dates:
                            day_rec = st.session_state.attendance_records[
                                (st.session_state.attendance_records["班級"] == sel_class) & 
                                (st.session_state.attendance_records["日期"] == d)
                            ] if not st.session_state.attendance_records.empty and "班級" in st.session_state.attendance_records.columns else pd.DataFrame()
                            
                            if not day_rec.empty and s in str(day_rec.iloc[0].get("出席名單", "")):
                                row[d] = "V"
                            else:
                                row[d] = ""
                        report_data.append(row)
                    
                    summary_df = pd.DataFrame(report_data)
                    summary_df["總出席"] = summary_df[all_dates].apply(lambda x: (x == "V").sum(), axis=1)
                    summary_df["出席率%"] = ((summary_df["總出席"] / len(all_dates)) * 100).round(1)
                    
                    st.dataframe(summary_df, use_container_width=True)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        summary_df.to_excel(writer, index=False, sheet_name='考勤紀錄')
                    
                    st.download_button(
                        label="📥 下載全期考勤 Excel 報表",
                        data=output.getvalue(),
                        file_name=f"正覺壁球_{sel_class}_考勤表.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.write("目前尚無學生數據。")
        else:
            st.error("日程表格式不正確，缺少『班級』欄位。")

# --- 頁面 4: 活動公告 ---
elif menu == "📢 活動公告":
    st.title("📢 賽事及活動公告")
    if st.session_state.is_admin:
        with st.form("new_post"):
            p_title = st.text_input("公告標題")
            p_content = st.text_area("公告內容")
            if st.form_submit_button("發布公告"):
                if p_title and p_content:
                    new_p = pd.DataFrame([{"標題": p_title, "內容": p_content, "日期": datetime.now().strftime("%Y-%m-%d")}])
                    st.session_state.announcements_df = pd.concat([st.session_state.announcements_df, new_p], ignore_index=True)
                    save_cloud_data('announcements', st.session_state.announcements_df)
                    st.rerun()
                else:
                    st.error("請填寫標題與內容")
    
    ann_df = st.session_state.announcements_df
    if not ann_df.empty:
        ann_df.columns = [str(c).strip() for c in ann_df.columns]
        if "標題" in ann_df.columns:
            for _, row in ann_df.iloc[::-1].iterrows():
                with st.chat_message("user"):
                    st.subheader(row.get('標題', '無標題'))
                    st.caption(f"發布日期: {row.get('日期', '未知')}")
                    st.write(row.get('內容', ''))
    else:
        st.info("目前沒有公告。")

# --- 頁面 5: 學費預算計算 ---
elif menu == "💰 學費預算計算":
    st.title("💰 預算與營運核算 (管理員專用)")
    if not st.session_state.is_admin:
        st.warning("請登入管理員帳號以查看此功能。")
    else:
        st.info("根據各班數據估算營運收益")
        col1, col2 = st.columns(2)
        with col1:
            fee_standard = st.number_input("標準收費 ($)", value=250)
        with col2:
            coach_cost = st.number_input("每堂教練成本 ($)", value=400)
            
        if not st.session_state.class_players_df.empty:
            player_counts = st.session_state.class_players_df.groupby("班級").size().reset_index(name='人數')
            st.write("各班預計收益分析：")
            st.dataframe(player_counts, use_container_width=True)
            total_revenue = player_counts['人數'].sum() * fee_standard
            st.metric("總預計學費收入 (估算)", f"${total_revenue}")
        else:
            st.info("尚無學生名單可供計算。")
