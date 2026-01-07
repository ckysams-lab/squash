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
                st.session_state[key] = df
                return df
        except Exception:
            pass
    if key in st.session_state:
        return st.session_state[key]
    st.session_state[key] = pd.DataFrame(default_data)
    return st.session_state[key]

def save_cloud_data(collection_name, df):
    # 移除完全為空的行
    df = df.dropna(how='all')
    key = f"cloud_{collection_name}"
    st.session_state[key] = df
    if st.session_state.get('db') is not None:
        try:
            coll_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            for _, row in df.iterrows():
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

if 'schedule_df' not in st.session_state or force_refresh:
    default_sched = [
        {"班級": "壁球中級訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "逢星期一", "堂數": 10, "具體日期": "5/1/26, 12/1/26, 19/1/26, 26/1/26, 2/2/26, 9/2/26, 23/2/26, 2/3/26, 23/3/26, 30/3/26"},
        {"班級": "壁球興趣班", "地點": "和興體育館", "時間": "16:00-17:30", "日期": "逢星期一", "堂數": 8, "具體日期": "19/1/26, 26/1/26, 2/2/26, 9/2/26, 2/3/26, 23/3/26, 30/3/26, 20/4/26"},
        {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "逢星期二", "堂數": 8, "具體日期": "1/20/26, 1/27/26, 2/3/26, 2/10/26, 2/24/26, 3/3/26, 3/24/26, 3/31/26"},
        {"班級": "壁球校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "逢星期三", "堂數": 11, "具體日期": "17/12/25, 7/1/26, 14/1/26, 21/1/26, 28/1/26, 4/2/26, 11/2/26, 25/2/26, 4/3/26, 25/3/26, 1/4/26"},
        {"班級": "正覺壁球精英班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "逢星期四", "堂數": 10, "具體日期": "8/1/26, 15/1/26, 22/1/26, 29/1/26, 5/2/26, 12/2/26, 26/2/26, 5/3/26, 19/3/26, 26/3/26"},
        {"班級": "壁球初級訓練班", "地點": "和興體育館", "時間": "16:00-17:30", "日期": "逢星期四", "堂數": 10, "具體日期": "8/1/26, 15/1/26, 22/1/26, 29/1/26, 5/2/26, 12/2/26, 26/2/26, 5/3/26, 19/3/26, 26/3/26"},
        {"班級": "星期六小型壁球興趣班 (A班)", "地點": "學校室內操場", "時間": "10:15-11:15", "日期": "逢星期六", "堂數": 8, "具體日期": "2/7/26, 2/28/26, 3/21/26, 3/28/26, 4/25/26, 5/9/26, 5/16/26, 5/23/26"},
        {"班級": "星期六小型壁球興趣班 (B班)", "地點": "學校室內操場", "時間": "12:00-13:00", "日期": "逢星期六", "堂數": 8, "具體日期": "2/7/26, 2/28/26, 3/21/26, 3/28/26, 4/25/26, 5/9/26, 5/16/26, 5/23/26"},
    ]
    st.session_state.schedule_df = load_cloud_data('schedules', default_sched)

if 'players_df' not in st.session_state or force_refresh:
    st.session_state.players_df = load_cloud_data('players', [
        {"姓名": "範例學生A", "積分": 100, "年級": "P.4", "組別": "男子"},
        {"姓名": "範例學生B", "積分": 85, "年級": "P.5", "組別": "女子"}
    ])

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

# 根據權限定義菜單清單
menu_options = ["📅 訓練日程表", "🏆 隊員排行榜", "📝 考勤點名", "📢 活動公告"]
if st.session_state.is_admin:
    menu_options.append("💰 學費預算計算 (管理專用)")

menu = st.sidebar.radio("功能選單", menu_options)

# --- 1. 日程表 ---
if menu == "📅 訓練日程表":
    st.title("📅 訓練班日程管理")
    if st.session_state.is_admin:
        u_sched = st.file_uploader("匯入日程 Excel/CSV", type=["xlsx", "csv"], key="u_sched")
        if u_sched:
            try:
                df_new = pd.read_excel(u_sched) if u_sched.name.endswith('xlsx') else pd.read_csv(u_sched)
                if st.button("🚀 確認更新日程數據"):
                    st.session_state.schedule_df = df_new
                    save_cloud_data('schedules', df_new)
                    st.rerun()
            except Exception as e: st.error(f"讀取錯誤: {e}")
        st.divider()
        edited_sched = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 手動儲存日程變更"):
            st.session_state.schedule_df = edited_sched
            save_cloud_data('schedules', edited_sched)
            st.rerun()
    else:
        st.dataframe(st.session_state.schedule_df, use_container_width=True)

# --- 2. 排行榜 (修復 KeyError 並加強容錯) ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分榜")
    
    if st.session_state.is_admin:
        with st.expander("📥 匯入/更新隊員名單"):
            u_players = st.file_uploader("上傳隊員 Excel (需含姓名、積分、年級)", type=["xlsx"], key="u_players")
            if u_players:
                try:
                    df_p = pd.read_excel(u_players)
                    if st.button("🚀 確認匯入名單"):
                        st.session_state.players_df = df_p
                        save_cloud_data('players', df_p)
                        st.rerun()
                except Exception as e: st.error(f"讀取錯誤: {e}")

    sort_option = st.selectbox("排序依據", ["積分 (由高到低)", "姓名", "年級"])
    display_p = st.session_state.players_df.copy()
    
    # 修復：檢查欄位是否存在，防止 KeyError
    if "積分" in display_p.columns:
        if "積分" in sort_option:
            # 確保積分欄位是數值類型以便正確排序
            display_p["積分"] = pd.to_numeric(display_p["積分"], errors='coerce').fillna(0)
            display_p = display_p.sort_values("積分", ascending=False)
    elif "積分" in sort_option:
        st.warning("⚠️ 當前數據中找不到『積分』欄位，無法進行積分排序。請檢查匯入的 Excel 標題。")

    if st.session_state.is_admin:
        edited_p = st.data_editor(display_p, num_rows="dynamic", use_container_width=True)
        if st.button("💾 儲存隊員資料"):
            st.session_state.players_df = edited_p
            save_cloud_data('players', edited_p)
            st.rerun()
    else:
        st.table(display_p)

# --- 3. 考勤點名 ---
elif menu == "📝 考勤點名":
    st.title("📝 考勤點名系統")
    class_list = st.session_state.schedule_df["班級"].tolist()
    sel_class = st.selectbox("請選擇班級", class_list)
    
    class_row = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class].iloc[0]
    dates = [d.strip() for d in str(class_row["具體日期"]).split(",")]
    sel_date = st.selectbox("請選擇堂數日期", dates)
    
    st.subheader(f"名單：{sel_class} - {sel_date}")
    player_names = st.session_state.players_df["姓名"].tolist()
    
    if st.session_state.is_admin:
        att_results = []
        for name in player_names:
            c1, c2 = st.columns([1, 4])
            status = c1.checkbox("", key=f"chk_{name}_{sel_date}")
            c2.write(f"{name} {'✅ 已出席' if status else '❌ 未到'}")
            if status: att_results.append(name)
        
        if st.button("💾 提交今日點名紀錄"):
            st.success(f"已記錄 {len(att_results)} 名出席。")
    else:
        st.info("僅供查閱，請聯絡教練進行點名。")

# --- 4. 活動公告 ---
elif menu == "📢 活動公告":
    st.title("📢 賽事公告與感興趣統計")
    if st.session_state.is_admin:
        with st.expander("➕ 發佈新活動"):
            with st.form("new_event"):
                e_name = st.text_input("活動名稱")
                e_date = st.date_input("日期")
                e_desc = st.text_area("詳情內容")
                if st.form_submit_button("🚀 發佈公告"):
                    new_e = {"活動名稱": e_name, "日期": str(e_date), "詳情": e_desc, "感興趣人數": 0}
                    st.session_state.announcements_df = pd.concat([st.session_state.announcements_df, pd.DataFrame([new_e])], ignore_index=True)
                    save_cloud_data('announcements', st.session_state.announcements_df)
                    st.rerun()

    for index, row in st.session_state.announcements_df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(row['活動名稱'])
                st.write(f"📅 日期: {row['日期']}")
                st.write(f"ℹ️ {row['詳情']}")
            with col2:
                st.metric("感興趣人數", row['感興趣人數'])
                if st.button("🙋 我感興趣", key=f"int_{index}"):
                    st.session_state.announcements_df.at[index, '感興趣人數'] += 1
                    save_cloud_data('announcements', st.session_state.announcements_df)
                    st.success("感謝登記！")
                    st.rerun()
            if st.session_state.is_admin:
                if st.button("🗑️ 刪除公告", key=f"del_{index}"):
                    st.session_state.announcements_df = st.session_state.announcements_df.drop(index)
                    save_cloud_data('announcements', st.session_state.announcements_df)
                    st.rerun()

# --- 5. 財務預算 (手動輸入版本) ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 預算與營運核算")
    st.info("系統預設成本：校隊班 $2,750 / 培訓班 $1,350 / 興趣班 $1,200")
    c1, c2, c3 = st.columns(3)
    cost_team = c1.number_input("校隊班 成本", value=2750)
    cost_train = c2.number_input("培訓班 成本", value=1350)
    cost_hobby = c3.number_input("興趣班 成本", value=1200)
    col1, col2, col3 = st.columns(3)
    with col1:
        n_t = st.number_input("校隊開班數", value=1)
        p_t = st.number_input("校隊人數 (預計)", value=10)
    with col2:
        n_tr = st.number_input("培訓開班數", value=2)
        p_tr = st.number_input("培訓人數 (預計)", value=20)
    with col3:
        n_h = st.number_input("興趣開班數", value=3)
        p_h = st.number_input("興趣人數 (預計)", value=48)
    st.divider()
    total_income = (p_t + p_tr + p_h) * 250
    total_cost = (n_t * cost_team) + (n_tr * cost_train) + (n_h * cost_hobby)
    balance = total_income - total_cost
    m1, m2, m3 = st.columns(3)
    m1.metric("預計總收入", f"${total_income:,}")
    m2.metric("預計總支出", f"${total_cost:,}")
    m3.metric("預計收支盈餘", f"${balance:,}", delta=float(balance))
