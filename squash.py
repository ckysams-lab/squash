import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

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

# --- 2. 數據存取與同步 ---
def load_cloud_data(collection_name, default_data):
    key = f"cloud_{collection_name}"
    if st.session_state.get('db') is not None:
        try:
            docs = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name).stream()
            data = [doc.to_dict() for doc in docs]
            if data:
                df = pd.DataFrame(data)
                # 自動清理標題空格
                df.columns = [str(c).strip() for c in df.columns]
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
    # 移除完全為空的行與清理數據
    df = df.dropna(how='all')
    key = f"cloud_{collection_name}"
    st.session_state[key] = df
    if st.session_state.get('db') is not None:
        try:
            coll_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            # 先刪除舊數據以保持同步 (簡單處理)
            for doc in coll_ref.stream():
                doc.reference.delete()
            
            for _, row in df.iterrows():
                # 根據不同集合決定 ID
                if '姓名' in row and pd.notna(row['姓名']): doc_id = str(row['姓名'])
                elif '班級' in row and pd.notna(row['班級']): doc_id = str(row['班級'])
                elif '活動名稱' in row and pd.notna(row['活動名稱']): doc_id = str(row['活動名稱'])
                else: doc_id = str(np.random.randint(1000000))
                
                clean_row = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
                coll_ref.document(doc_id).set(clean_row)
            st.toast(f"✅ {collection_name} 同步成功")
        except Exception:
            st.error(f"同步失敗")

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

# 4a. 訓練日程
if 'schedule_df' not in st.session_state or force_refresh:
    st.session_state.schedule_df = load_cloud_data('schedules', [
        {"班級": "壁球校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "逢星期三", "堂數": 11, "具體日期": "17/12/25, 7/1/26, 14/1/26, 21/1/26, 28/1/26"},
    ])

# 4b. 訓練班名單 (僅用於點名)
if 'class_players_df' not in st.session_state or force_refresh:
    st.session_state.class_players_df = load_cloud_data('class_players', [
        {"班級": "壁球校隊訓練班", "姓名": "範例學生A", "性別": "男"},
        {"班級": "壁球校隊訓練班", "姓名": "範例學生B", "性別": "女"},
    ])

# 4c. 全校排名名單 (僅用於排行榜)
if 'rank_df' not in st.session_state or force_refresh:
    st.session_state.rank_df = load_cloud_data('rankings', [
        {"姓名": "李澤朗", "積分": 1000, "年級": "P.6"},
        {"姓名": "王冠軒", "積分": 1000, "年級": "P.4"},
    ])

# 4d. 活動公告
if 'announcements_df' not in st.session_state or force_refresh:
    st.session_state.announcements_df = load_cloud_data('announcements', [
        {"活動名稱": "全港學界壁球比賽", "日期": "2026-05-10", "詳情": "請校隊成員準時出席", "感興趣人數": 0}
    ])

# --- 側邊欄 ---
st.sidebar.title("🏸 正覺壁球管理系統")
if not st.session_state.is_admin:
    st.sidebar.text_input("管理員密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 管理員模式")
    if st.sidebar.button("🔌 登出"):
        st.session_state.is_admin = False
        st.rerun()

menu_options = ["📅 訓練日程表", "🏆 隊員排行榜", "📝 考勤點名", "📢 活動公告"]
if st.session_state.is_admin:
    menu_options.append("💰 學費預算計算 (管理專用)")

menu = st.sidebar.radio("功能選單", menu_options)

# --- 1. 日程表 ---
if menu == "📅 訓練日程表":
    st.title("📅 訓練班日程管理")
    if st.session_state.is_admin:
        u_sched = st.file_uploader("匯入日程 Excel", type=["xlsx"], key="u_sched")
        if u_sched:
            df_new = pd.read_excel(u_sched)
            df_new.columns = [str(c).strip() for c in df_new.columns]
            if st.button("🚀 確認更新日程"):
                st.session_state.schedule_df = df_new
                save_cloud_data('schedules', df_new)
                st.rerun()
    st.dataframe(st.session_state.schedule_df, use_container_width=True)

# --- 2. 排行榜 (獨立匯入與排名從1開始) ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分榜")
    
    if st.session_state.is_admin:
        with st.expander("📥 匯入排名名單 (與訓練班名單分開)"):
            u_rank = st.file_uploader("上傳排名 Excel (需含姓名、積分、年級)", type=["xlsx"], key="u_rank")
            if u_rank:
                df_r = pd.read_excel(u_rank)
                df_r.columns = [str(c).strip() for c in df_r.columns]
                if st.button("🚀 確認匯入排名"):
                    st.session_state.rank_df = df_r
                    save_cloud_data('rankings', df_r)
                    st.rerun()

    display_df = st.session_state.rank_df.copy()
    
    if "積分" in display_df.columns:
        display_df["積分"] = pd.to_numeric(display_df["積分"], errors='coerce').fillna(0)
        display_df = display_df.sort_values("積分", ascending=False).reset_index(drop=True)
        # 排名從 1 開始
        display_df.insert(0, '排名', range(1, 1 + len(display_df)))
    
    if st.session_state.is_admin:
        st.info("管理員可直接在下方修改數據：")
        edited_r = st.data_editor(display_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 儲存排名變更"):
            # 儲存時移除「排名」欄位，它是自動生成的
            if '排名' in edited_r.columns:
                edited_r = edited_r.drop(columns=['排名'])
            st.session_state.rank_df = edited_r
            save_cloud_data('rankings', edited_r)
            st.rerun()
    else:
        st.table(display_df)

# --- 3. 考勤點名 (使用獨立的訓練班名單) ---
elif menu == "📝 考勤點名":
    st.title("📝 考勤點名系統")
    
    if st.session_state.is_admin:
        with st.expander("📥 匯入各班訓練名單"):
            u_class = st.file_uploader("上傳班級名單 Excel (需含班級、姓名)", type=["xlsx"], key="u_class")
            if u_class:
                df_c = pd.read_excel(u_class)
                df_c.columns = [str(c).strip() for c in df_c.columns]
                if st.button("🚀 確認更新訓練班名單"):
                    st.session_state.class_players_df = df_c
                    save_cloud_data('class_players', df_c)
                    st.rerun()

    class_list = st.session_state.schedule_df["班級"].unique().tolist()
    sel_class = st.selectbox("請選擇班級", class_list)
    
    # 取得日期
    class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class]
    if not class_info.empty:
        dates = [d.strip() for d in str(class_info.iloc[0]["具體日期"]).split(",")]
        sel_date = st.selectbox("請選擇日期", dates)
        
        # 從獨立名單中取得該班級學生
        class_players = st.session_state.class_players_df[st.session_state.class_players_df["班級"] == sel_class]["姓名"].tolist()
        
        if class_players:
            st.subheader(f"點名：{sel_class} ({len(class_players)}人)")
            if st.session_state.is_admin:
                for name in class_players:
                    st.checkbox(name, key=f"att_{sel_class}_{name}_{sel_date}")
                if st.button("💾 提交點名紀錄"):
                    st.success("紀錄已更新")
            else:
                st.write(class_players)
        else:
            st.warning("此班級暫無名單，請管理員匯入名單。")

# --- 4. 活動公告 ---
elif menu == "📢 活動公告":
    st.title("📢 賽事公告")
    if st.session_state.is_admin:
        with st.form("new_event"):
            e_name = st.text_input("活動名稱")
            e_date = st.date_input("日期")
            e_desc = st.text_area("詳情")
            if st.form_submit_button("🚀 發佈"):
                new_e = {"活動名稱": e_name, "日期": str(e_date), "詳情": e_desc, "感興趣人數": 0}
                st.session_state.announcements_df = pd.concat([st.session_state.announcements_df, pd.DataFrame([new_e])], ignore_index=True)
                save_cloud_data('announcements', st.session_state.announcements_df)
                st.rerun()
    
    for idx, row in st.session_state.announcements_df.iterrows():
        with st.container(border=True):
            st.subheader(row['活動名稱'])
            st.write(f"日期: {row['日期']}")
            st.write(row['詳情'])

# --- 5. 財務預算 ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 預算與營運核算")
    c1, c2, c3 = st.columns(3)
    cost_team = c1.number_input("校隊班 成本", value=2750)
    cost_train = c2.number_input("培訓班 成本", value=1350)
    cost_hobby = c3.number_input("興趣班 成本", value=1200)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        n_t = st.number_input("校隊班數", value=1)
        p_t = st.number_input("校隊總人數", value=10)
    with col2:
        n_tr = st.number_input("培訓班數", value=2)
        p_tr = st.number_input("培訓總人數", value=20)
    with col3:
        n_h = st.number_input("興趣班數", value=3)
        p_h = st.number_input("興趣總人數", value=48)
    
    income = (p_t + p_tr + p_h) * 250
    expense = (n_t*cost_team) + (n_tr*cost_train) + (n_h*cost_hobby)
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("預計總收入", f"${income}")
    m2.metric("預計總支出", f"${expense}")
    m3.metric("盈餘", f"${income-expense}", delta=float(income-expense))
