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
def sign_in_with_email(email, password):
    if email and password:
        st.session_state.user_email = email
        if email.endswith("@possa.edu.hk") or email == "admin@test.com":
            st.session_state.is_admin = True
        else:
            st.session_state.is_admin = False
        st.session_state.logged_in = True
        return True
    return False

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
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# --- 5. 側邊欄與登入邏輯 ---
st.sidebar.title("🏸 正覺壁球管理系統")

if not st.session_state.logged_in:
    st.sidebar.subheader("🔑 用戶登入")
    login_type = st.sidebar.selectbox("登入方式", ["管理員密碼", "電子郵件"])
    
    if login_type == "管理員密碼":
        pwd = st.sidebar.text_input("輸入 4 位密碼", type="password")
        if st.sidebar.button("登入"):
            if pwd == "8888":
                st.session_state.logged_in = True
                st.session_state.is_admin = True
                st.session_state.user_email = "admin@possa.edu.hk"
                st.rerun()
            else:
                st.sidebar.error("密碼錯誤")
    else:
        email = st.sidebar.text_input("電子郵件")
        password = st.sidebar.text_input("密碼", type="password")
        if st.sidebar.button("登入"):
            if sign_in_with_email(email, password):
                st.rerun()
            else:
                st.sidebar.error("驗證失敗")
    
    st.info("請登入後使用系統功能。")
    st.stop()

st.sidebar.success(f"👤 {st.session_state.user_email}")
if st.session_state.is_admin:
    st.sidebar.caption("🛡️ 管理員權限")

if st.sidebar.button("🔌 登出"):
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
    st.session_state.rank_df = load_cloud_data('rankings', [])
if 'attendance_records' not in st.session_state or force_refresh:
    st.session_state.attendance_records = load_cloud_data('attendance_records', pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單", "記錄人"]))
if 'announcements_df' not in st.session_state or force_refresh:
    st.session_state.announcements_df = load_cloud_data('announcements', pd.DataFrame(columns=["標題", "內容", "日期"]))
if 'tournaments_df' not in st.session_state or force_refresh:
    st.session_state.tournaments_df = load_cloud_data('tournaments', pd.DataFrame(columns=["比賽名稱", "日期", "截止日期", "連結", "備註"]))

# 菜單導航
menu_options = ["📅 訓練日程表", "🏆 隊員排行榜", "📝 考勤點名", "📢 活動公告", "🗓️ 比賽報名與賽程"]
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
    if st.session_state.is_admin:
        u_rank = st.file_uploader("匯入積分榜 Excel", type=["xlsx"])
        if u_rank:
            df_r = pd.read_excel(u_rank)
            if st.button("🚀 更新積分排名"):
                st.session_state.rank_df = df_r
                save_cloud_data('rankings', df_r)
                st.rerun()
    
    if not st.session_state.rank_df.empty:
        display_rank_df = st.session_state.rank_df.copy()
        display_rank_df.index = np.arange(1, len(display_rank_df) + 1)
        st.table(display_rank_df)
    else:
        st.info("暫無積分數據。")

elif menu == "📝 考勤點名":
    st.title("📝 考勤點名與報表")
    if st.session_state.is_admin:
        u_class = st.file_uploader("匯入學生名單 Excel (欄位：班級, 姓名, 年級)", type=["xlsx"])
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
        
        tab1, tab2 = st.tabs(["🎯 今日點名", "📊 考勤總表"])
        
        with tab1:
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
                        attendance_dict[name] = st.checkbox(f"{name}", value=(name in existing_list), key=f"chk_{name}_{sel_date}")
                
                if st.button("💾 儲存點名", type="primary"):
                    present_names = [n for n, p in attendance_dict.items() if p]
                    new_rec = {
                        "班級": sel_class, 
                        "日期": sel_date, 
                        "出席人數": len(present_names), 
                        "出席名單": ", ".join(present_names),
                        "記錄人": st.session_state.user_email
                    }
                    df_recs = st.session_state.attendance_records
                    df_recs = df_recs[~((df_recs["班級"] == sel_class) & (df_recs["日期"] == sel_date))]
                    st.session_state.attendance_records = pd.concat([df_recs, pd.DataFrame([new_rec])], ignore_index=True)
                    save_cloud_data('attendance_records', st.session_state.attendance_records)
                    st.success("✅ 儲存成功")
            else:
                st.info("該班別尚無名單數據。")

        with tab2:
            st.dataframe(st.session_state.attendance_records[st.session_state.attendance_records["班級"] == sel_class], use_container_width=True)

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
    st.title("💰 營運成本與學費預算核算")
    
    st.markdown("### 1️⃣ 收入預估 (手動輸入)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**校隊與精英班**")
        n_team = st.number_input("校隊/精英班總人數", value=20, min_value=0)
        fee_team = st.number_input("校隊學費 ($)", value=250, min_value=0)
    with col2:
        st.write("**培訓訓練班**")
        n_train = st.number_input("培訓班總人數", value=30, min_value=0)
        fee_train = st.number_input("培訓學費 ($)", value=250, min_value=0)
    with col3:
        st.write("**興趣班**")
        n_hobby = st.number_input("興趣班總人數", value=40, min_value=0)
        fee_hobby = st.number_input("興趣班學費 ($)", value=250, min_value=0)
    
    total_revenue = (n_team * fee_team) + (n_train * fee_train) + (n_hobby * fee_hobby)
    
    st.markdown("---")
    st.markdown("### 2️⃣ 支出預估 (手動輸入)")
    exp1, exp2, exp3 = st.columns(3)
    with exp1:
        st.write("**教練支出**")
        coach_rate = st.number_input("教練平均時薪 ($)", value=300)
        coach_hours = st.number_input("全學期預計總時數 (h)", value=150)
        total_coach_cost = coach_rate * coach_hours
        st.caption(f"小計: ${total_coach_cost:,}")
    with exp2:
        st.write("**場地租金**")
        court_rate = st.number_input("平均場地時租 ($)", value=24)
        court_hours = st.number_input("全學期租用總時數 (h)", value=120)
        total_court_cost = court_rate * court_hours
        st.caption(f"小計: ${total_court_cost:,}")
    with exp3:
        st.write("**其他支出**")
        misc_cost = st.number_input("行政/器材/獎品支出 ($)", value=1000)
        st.caption("手動輸入雜項金額")

    total_expense = total_coach_cost + total_court_cost + misc_cost
    net_profit = total_revenue - total_expense
    
    st.markdown("---")
    st.markdown("### 📊 核算結果")
    res1, res2, res3 = st.columns(3)
    res1.metric("預計總收入", f"${total_revenue:,}")
    res2.metric("預計總支出", f"${total_expense:,}", delta=f"-{total_expense:,}", delta_color="inverse")
    res3.metric("淨利潤 (盈餘/虧損)", f"${net_profit:,}", delta=f"{net_profit:,}")

    if net_profit < 0:
        st.error("⚠️ 目前預算顯示為虧損狀態，請考慮調整學費或教練時數。")
    else:
        st.success("✅ 目前預算運作良好。")
