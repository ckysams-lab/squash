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
                if collection_name == 'attendance_records':
                    for col in ["班級", "日期", "出席人數", "出席名單"]:
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
            for doc in coll_ref.stream():
                doc.reference.delete()
            
            # 寫入新數據
            for _, row in df.iterrows():
                if collection_name == 'attendance_records':
                    doc_id = f"{row.get('班級', 'Unknown')}_{row.get('日期', 'Unknown')}".replace("/", "-")
                elif collection_name == 'announcements':
                    # 使用時間戳和標題生成 ID，避免重複
                    doc_id = f"{row.get('日期')}_{row.get('標題')}"
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
    st.session_state.attendance_records = load_cloud_data('attendance_records', pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單"]))
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
        st.info("暫無日程資料。")

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
        st.info("暫無積分數據。")

# --- 頁面 3: 考勤點名 ---
elif menu == "📝 考勤點名":
    st.title("📝 考勤點名與報表")
    if st.session_state.is_admin:
        with st.expander("📥 匯入學生名單"):
            u_class = st.file_uploader("上傳 Excel 名單 (欄位：班級, 姓名, 年級)", type=["xlsx"])
            if u_class:
                df_c = pd.read_excel(u_class)
                if st.button("🚀 確認更新名單"):
                    st.session_state.class_players_df = df_c
                    save_cloud_data('class_players', df_c)
                    st.rerun()

    if st.session_state.schedule_df.empty:
        st.warning("請先在『訓練日程表』匯入班級數據。")
    else:
        if "班級" in st.session_state.schedule_df.columns:
            class_list = st.session_state.schedule_df["班級"].unique().tolist()
            sel_class = st.selectbox("請選擇班別", class_list)
            
            class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class]
            raw_dates = str(class_info.iloc[0]["具體日期"])
            all_dates = [d.strip() for d in raw_dates.split(",") if d.strip()]
            
            tab1, tab2 = st.tabs(["🎯 今日點名", "📊 考勤總表"])
            
            with tab1:
                sel_date = st.selectbox("選擇日期", all_dates)
                current_players = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class] if not st.session_state.class_players_df.empty else pd.DataFrame()
                
                if not current_players.empty:
                    attendance_recs = st.session_state.attendance_records
                    if "班級" in attendance_recs.columns and "日期" in attendance_recs.columns:
                        existing_rec = attendance_recs[(attendance_recs["班級"] == sel_class) & (attendance_recs["日期"] == sel_date)]
                        existing_list = existing_rec.iloc[0]["出席名單"].split(", ") if not existing_rec.empty and pd.notna(existing_rec.iloc[0]["出席名單"]) else []
                    else:
                        existing_list = []

                    st.markdown(f"#### 📋 {sel_class} - {sel_date}")
                    cols = st.columns(4)
                    attendance_dict = {}
                    for i, row in enumerate(current_players.to_dict('records')):
                        name = str(row['姓名'])
                        with cols[i % 4]:
                            attendance_dict[name] = st.checkbox(f"{name}", value=(name in existing_list), key=f"chk_{name}_{sel_date}")
                    
                    if st.session_state.is_admin:
                        if st.button("💾 儲存點名", type="primary"):
                            present_names = [n for n, p in attendance_dict.items() if p]
                            new_rec = {"班級": sel_class, "日期": sel_date, "出席人數": len(present_names), "出席名單": ", ".join(present_names)}
                            df_recs = st.session_state.attendance_records
                            if "班級" not in df_recs.columns: df_recs = pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單"])
                            df_recs = df_recs[~((df_recs["班級"] == sel_class) & (df_recs["日期"] == sel_date))]
                            st.session_state.attendance_records = pd.concat([df_recs, pd.DataFrame([new_rec])], ignore_index=True)
                            save_cloud_data('attendance_records', st.session_state.attendance_records)
                            st.success("✅ 儲存成功")
                else:
                    st.info("暫無名單數據。")

            with tab2:
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
                            row[d] = "V" if not day_rec.empty and s in str(day_rec.iloc[0].get("出席名單", "")) else ""
                        report_data.append(row)
                    
                    summary_df = pd.DataFrame(report_data)
                    st.dataframe(summary_df, use_container_width=True)

# --- 頁面 4: 活動公告 ---
elif menu == "📢 活動公告":
    st.title("📢 賽事及活動公告")
    
    if st.session_state.is_admin:
        with st.form("new_post", clear_on_submit=True):
            p_title = st.text_input("公告標題")
            p_content = st.text_area("公告內容")
            if st.form_submit_button("發布公告"):
                if p_title and p_content:
                    new_p = pd.DataFrame([{"標題": p_title, "內容": p_content, "日期": datetime.now().strftime("%Y-%m-%d")}])
                    st.session_state.announcements_df = pd.concat([st.session_state.announcements_df, new_p], ignore_index=True)
                    save_cloud_data('announcements', st.session_state.announcements_df)
                    st.rerun()
                else:
                    st.error("請輸入內容")

    ann_df = st.session_state.announcements_df
    if not ann_df.empty:
        # 逆序顯示最新公告
        for index, row in ann_df.iloc[::-1].iterrows():
            with st.chat_message("user"):
                st.subheader(row.get('標題', '無標題'))
                st.caption(f"📅 {row.get('日期', '未知')}")
                st.write(row.get('內容', ''))
                
                # 只有管理員可以刪除
                if st.session_state.is_admin:
                    if st.button(f"🗑️ 刪除公告", key=f"del_{index}"):
                        st.session_state.announcements_df = st.session_state.announcements_df.drop(index)
                        save_cloud_data('announcements', st.session_state.announcements_df)
                        st.rerun()
    else:
        st.info("目前沒有公告。")

# --- 頁面 5: 學費預算計算 ---
elif menu == "💰 學費預算計算":
    st.title("💰 預算與營運核算")
    st.info("請輸入預計開班數與平均每班人數，系統將自動計算收益。")
    
    # 校隊、培訓、興趣班
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 🏆 校隊班")
        n_team = st.number_input("校隊開班數", value=1, step=1)
        p_team = st.number_input("校隊平均人數", value=12, step=1)
        fee_team = st.number_input("校隊學費/人 ($)", value=250)
        
    with c2:
        st.markdown("### 📈 培訓班")
        n_train = st.number_input("培訓開班數", value=3, step=1)
        p_train = st.number_input("培訓平均人數", value=10, step=1)
        fee_train = st.number_input("培訓學費/人 ($)", value=250)
        
    with c3:
        st.markdown("### 🎾 興趣班")
        n_hobby = st.number_input("興趣開班數", value=4, step=1)
        p_hobby = st.number_input("興趣平均人數", value=16, step=1)
        fee_hobby = st.number_input("興趣學費/人 ($)", value=250)

    st.divider()
    
    col_cost1, col_cost2 = st.columns(2)
    with col_cost1:
        coach_cost_per_class = st.number_input("預估每班教練總成本 ($)", value=2500, help="指該班別全期的教練費用")
    
    # 計算邏輯
    rev_team = n_team * p_team * fee_team
    rev_train = n_train * p_train * fee_train
    rev_hobby = n_hobby * p_hobby * fee_hobby
    total_revenue = rev_team + rev_train + rev_hobby
    
    total_classes = n_team + n_train + n_hobby
    total_cost = total_classes * coach_cost_per_class
    profit = total_revenue - total_cost

    # 顯示結果
    m1, m2, m3 = st.columns(3)
    m1.metric("預計總收入", f"${total_revenue:,}")
    m2.metric("預計總教練成本", f"${total_cost:,}")
    m3.metric("預計利潤", f"${profit:,}", delta=float(profit))

    # 詳細表格
    summary_data = {
        "班別": ["校隊班", "培訓班", "興趣班", "總計"],
        "班數": [n_team, n_train, n_hobby, total_classes],
        "預計人數": [n_team*p_team, n_train*p_train, n_hobby*p_hobby, (n_team*p_team + n_train*p_train + n_hobby*p_hobby)],
        "預計收入": [rev_team, rev_train, rev_hobby, total_revenue]
    }
    st.table(pd.DataFrame(summary_data))
