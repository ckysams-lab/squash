import streamlit as st
import pandas as pd
import numpy as np
import json
from firebase_admin import credentials, firestore, initialize_app, get_app

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide")

# --- 1. Firebase 雲端儲存配置 (修正版) ---
def init_firebase():
    """初始化 Firebase 並返回 Firestore Client"""
    if 'db' not in st.session_state:
        try:
            # 嘗試獲取已存在的 Firebase App (避免重複初始化)
            app = get_app()
        except ValueError:
            # 如果不存在，則根據 Secrets 初始化
            try:
                # 檢查 Streamlit Secrets 中是否有 firebase_config
                if "firebase_config" in st.secrets:
                    key_dict = dict(st.secrets["firebase_config"])
                    # 關鍵：處理私鑰中的換行符號問題，這在雲端佈署時常發生
                    if "private_key" in key_dict:
                        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                    
                    cred = credentials.Certificate(key_dict)
                    app = initialize_app(cred)
                else:
                    st.warning("⚠️ 未偵測到 Firebase 憑證，系統將運行於離線模式。")
                    st.session_state.db = None
                    return None
            except Exception as e:
                st.error(f"Firebase 初始化失敗: {e}")
                st.session_state.db = None
                return None
        
        # 初始化 Firestore Client 並存入 Session State
        st.session_state.db = firestore.client()
    return st.session_state.db

# 執行初始化
db = init_firebase()
app_id = "squash-management-v1"

# --- 2. 雲端數據同步邏輯 (實作版) ---
def load_cloud_data(collection_name, default_data):
    """從雲端讀取指定集合的資料，若無則返回預設值"""
    key = f"cloud_{collection_name}"
    
    # 如果資料庫連線可用，優先從雲端抓取
    if st.session_state.get('db') is not None:
        try:
            # 依照指定路徑結構讀取：artifacts/{appId}/public/data/{collectionName}
            docs = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name).stream()
            data = [doc.to_dict() for doc in docs]
            if data:
                df = pd.DataFrame(data)
                st.session_state[key] = df
                return df
        except Exception as e:
            st.error(f"讀取雲端數據時出錯 ({collection_name}): {e}")

    # 若無雲端連線，則回傳目前 Session 內的資料或預設值
    if key in st.session_state:
        return st.session_state[key]
    
    st.session_state[key] = pd.DataFrame(default_data)
    return st.session_state[key]

def save_cloud_data(collection_name, df):
    """將 DataFrame 同步至雲端資料庫"""
    key = f"cloud_{collection_name}"
    st.session_state[key] = df
    
    if st.session_state.get('db') is not None:
        try:
            coll_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            
            # 先嘗試將數據寫入 (逐筆更新)
            for _, row in df.iterrows():
                # 建立唯一的 ID 以避免重複 (優先序：姓名 > 班級 > ID)
                doc_id = str(row.get('姓名', row.get('班級', row.get('id', np.random.randint(100000)))))
                # 將 NaN 轉為 None 以符合 Firestore 規範
                clean_row = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
                coll_ref.document(doc_id).set(clean_row)
            
            st.toast(f"✅ {collection_name} 已成功同步至雲端儲存")
        except Exception as e:
            st.error(f"同步至雲端失敗: {e}")
    else:
        st.toast(f"ℹ️ 資料已儲存於本次工作階段 (離線)")

# --- 3. 安全權限與初始化 ---
ADMIN_PASSWORD = "8888"
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# 資料刷新邏輯
force_refresh = st.sidebar.button("🔄 刷新雲端數據")

# 初始化載入各項資料
if 'schedule_df' not in st.session_state or force_refresh:
    default_sched = [
        {"班級": "校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "12/17-4/1", "堂數": 11, "類型": "校隊班", "具體日期": "12/17, 1/7, 1/14, 1/21, 2/4, 2/11, 2/18, 2/25, 3/4, 3/11, 3/18"},
        {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8, "類型": "興趣班", "具體日期": "1/20, 1/27, 2/3, 2/10, 2/17, 2/24, 3/3, 3/10"},
    ]
    st.session_state.schedule_df = load_cloud_data('schedules', default_sched)

if 'players_df' not in st.session_state or force_refresh:
    default_players = [{"姓名": "陳大文", "積分": 98, "年級": "P.5"}, {"姓名": "李小明", "積分": 95, "年級": "P.4"}]
    st.session_state.players_df = load_cloud_data('players', default_players)

if 'events_list' not in st.session_state or force_refresh:
    default_events = [{"id": 1, "活動": "全港小學校際比賽", "日期": "2026-03-15", "地點": "歌和老街", "狀態": "接受報名", "pdf_url": "", "interested": 12}]
    events_df = load_cloud_data('events', default_events)
    st.session_state.events_list = events_df.to_dict('records')

if 'attendance_data' not in st.session_state or force_refresh:
    default_attendance = [
        {"姓名": "陳大文", "班級": "校隊訓練班", "年級": "P.5", "T1": True, "T2": False},
        {"姓名": "李小明", "班級": "校隊訓練班", "年級": "P.4", "T1": True, "T2": True},
    ]
    st.session_state.attendance_data = load_cloud_data('attendance', default_attendance)

def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理員權限已解鎖！")
    else:
        st.error("密碼不正確。")

# --- 側邊欄 UI ---
st.sidebar.title("🏸 正覺壁球管理系統")
if not st.session_state.is_admin:
    st.sidebar.text_input("管理員密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 管理員模式")
    if st.sidebar.button("🔌 登出"):
        st.session_state.is_admin = False
        st.rerun()

menu_options = ["📢 比賽活動公告", "📅 訓練班日程表", "🏆 隊員排行榜", "📝 點名與統計"]
if st.session_state.is_admin:
    menu_options.append("💰 學費預算計算 (管理專用)")

menu = st.sidebar.radio("導覽選單", menu_options)

# --- 功能模組 1: 比賽活動公告 ---
if menu == "📢 比賽活動公告":
    st.title("📅 最新壁球活動與比賽")
    if st.session_state.is_admin:
        with st.expander("➕ 發布新活動"):
            with st.form("add_event_form", clear_on_submit=True):
                new_title = st.text_input("活動名稱")
                new_date = st.date_input("活動日期")
                new_loc = st.text_input("地點")
                new_pdf = st.text_input("報名表 PDF 連結")
                if st.form_submit_button("立即發布"):
                    new_ev = {
                        "id": int(np.random.randint(1000, 9999)),
                        "活動": str(new_title), "日期": str(new_date),
                        "地點": str(new_loc), "狀態": "接受報名", 
                        "pdf_url": str(new_pdf), "interested": 0
                    }
                    st.session_state.events_list.append(new_ev)
                    save_cloud_data('events', pd.DataFrame(st.session_state.events_list))
                    st.rerun()

    for idx, ev in enumerate(list(st.session_state.events_list)):
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(ev["活動"])
                st.write(f"📅 **日期**: {ev['日期']} | 📍 **地點**: {ev['地點']}")
                st.write(f"🔥 目前感興趣人數: {ev['interested']}")
            with col2:
                if st.button("🙋 感興趣", key=f"int_{idx}"):
                    st.session_state.events_list[idx]["interested"] += 1
                    save_cloud_data('events', pd.DataFrame(st.session_state.events_list))
                    st.rerun()
                if st.session_state.is_admin and st.button("🗑️ 刪除活動", key=f"del_{idx}"):
                    st.session_state.events_list.pop(idx)
                    save_cloud_data('events', pd.DataFrame(st.session_state.events_list))
                    st.rerun()

# --- 功能模組 2: 訓練班日程表 ---
elif menu == "📅 訓練班日程表":
    st.title("📅 2025-26 年度訓練日程管理")
    if st.session_state.is_admin:
        uploaded_file = st.file_uploader("匯入日程表 (Excel/CSV)", type=["xlsx", "csv"])
        if uploaded_file:
            try:
                new_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
                if st.button("🚀 確認匯入並同步雲端"):
                    st.session_state.schedule_df = new_df
                    save_cloud_data('schedules', new_df)
                    st.rerun()
            except Exception as e:
                st.error(f"檔案格式錯誤: {e}")

        st.divider()
        edited_df = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 儲存並更新日程"):
            st.session_state.schedule_df = edited_df
            save_cloud_data('schedules', edited_df)
            st.rerun()
    else:
        st.dataframe(st.session_state.schedule_df.drop(columns=["具體日期"]), use_container_width=True)

# --- 功能模組 3: 隊員排行榜 ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊員積分榜")
    rank_df = st.session_state.players_df.sort_values("積分", ascending=False).reset_index(drop=True)
    st.table(rank_df)
    
    if st.session_state.is_admin:
        st.divider()
        uploaded_p = st.file_uploader("匯入隊員名單 (Excel/CSV)", type=["xlsx", "csv"])
        if uploaded_p:
            try:
                new_p = pd.read_excel(uploaded_p) if uploaded_p.name.endswith('xlsx') else pd.read_csv(uploaded_p)
                if st.button("🚀 確認更新隊員清單"):
                    st.session_state.players_df = new_p
                    save_cloud_data('players', new_p)
                    st.rerun()
            except Exception as e:
                st.error(f"檔案讀取失敗: {e}")
        
        edited_p = st.data_editor(st.session_state.players_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 儲存隊員積分"):
            st.session_state.players_df = edited_p
            save_cloud_data('players', edited_p)
            st.rerun()

# --- 功能模組 4: 點名與統計 ---
elif menu == "📝 點名與統計":
    st.title("📝 訓練班出席記錄")
    class_list = st.session_state.schedule_df["班級"].tolist()
    if not class_list:
        st.warning("請先在日程表中建立班級。")
    else:
        sel_class = st.selectbox("請選擇班級", class_list)
        class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class].iloc[0]
        num_lessons = int(class_info["堂數"])
        dates_str = str(class_info.get("具體日期", ""))
        date_items = [d.strip() for d in dates_str.split(",") if d.strip()]
        
        # 動態列名稱映射 (T1, T2 -> 具體日期)
        col_map = {f"T{i}": (date_items[i-1] if i <= len(date_items) else f"第{i}堂") for i in range(1, num_lessons + 1)}
        att_df = st.session_state.attendance_data[st.session_state.attendance_data["班級"] == sel_class].copy()
        
        # 自動補齊列
        for i in range(1, num_lessons + 1):
            if f"T{i}" not in att_df.columns:
                att_df[f"T{i}"] = False
        
        display_cols = ["姓名", "年級"] + [f"T{i}" for i in range(1, num_lessons + 1)]
        actual_cols = [c for c in display_cols if c in att_df.columns]
        final_df = att_df[actual_cols].rename(columns=col_map)
        
        if st.session_state.is_admin:
            st.info("管理員：您可以直接在下方勾選出席狀況，完成後點擊儲存。")
            column_config = {v: st.column_config.CheckboxColumn(v) for v in col_map.values()}
            edited_att = st.data_editor(final_df, column_config=column_config, use_container_width=True, num_rows="dynamic")
            if st.button("💾 同步點名結果至雲端"):
                rev_map = {v: k for k, v in col_map.items()}
                to_save = edited_att.rename(columns=rev_map)
                to_save["班級"] = sel_class
                other_classes = st.session_state.attendance_data[st.session_state.attendance_data["班級"] != sel_class]
                st.session_state.attendance_data = pd.concat([other_classes, to_save], ignore_index=True).fillna(False)
                save_cloud_data('attendance', st.session_state.attendance_data)
                st.rerun()
        else:
            st.dataframe(final_df, use_container_width=True)

# --- 功能模組 5: 學費預算計算 ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 預算與營運核算")
    st.info("系統預設成本：校隊班 $2,750 / 培訓班 $1,350 / 興趣班 $1,200")
    
    c1, c2, c3 = st.columns(3)
    cost_team = c1.number_input("校隊班 成本", 2750)
    cost_train = c2.number_input("培訓班 成本", 1350)
    cost_hobby = c3.number_input("興趣班 成本", 1200)
    
    col1, col2, col3 = st.columns(3)
    with col1: n_t = st.number_input("校隊開班數", 1); p_t = st.number_input("校隊人數", 12)
    with col2: n_tr = st.number_input("培訓開班數", 4); p_tr = st.number_input("培訓人數", 48)
    with col3: n_h = st.number_input("興趣開班數", 5); p_h = st.number_input("興趣人數", 75)
    
    fee = st.number_input("每位學生預計收費", 250)
    total_cost = (n_t * cost_team) + (n_tr * cost_train) + (n_h * cost_hobby)
    total_income = (p_t + p_tr + p_h) * fee
    
    m1, m2, m3 = st.columns(3)
    m1.metric("預算支出", f"${total_cost:,}")
    m2.metric("預計收入", f"${total_income:,}")
    m3.metric("淨損益", f"${total_income - total_cost:,}", delta=f"{total_income - total_cost:,}")
