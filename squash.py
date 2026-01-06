import streamlit as st
import pandas as pd
from datetime import datetime

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide")

# --- 1. 安全權限設置 ---
ADMIN_PASSWORD = "8888"

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("密碼正確，管理員權限已解鎖！")
    else:
        st.session_state.is_admin = False
        if "pwd_input" in st.session_state and st.session_state["pwd_input"] != "":
            st.error("密碼錯誤，請重試。")

# --- 2. 初始化數據 ---

# 訓練班日程
if 'schedule_df' not in st.session_state:
    initial_data = [
        {"班級": "星期二小型壁球興趣班", "負責教練": "外展教練 (LCSD)", "地點": "學校室內操場", "時間": "15:30-16:30", "日期內容": "1/20, 1/27, 2/3, 2/10, 2/24, 3/3, 3/24, 3/31", "堂數": 8},
        {"班級": "星期六小型壁球興趣班", "負責教練": "外展教練 (LCSD)", "地點": "學校室內操場", "時間": "A:10:15 / B:12:00", "日期內容": "2/7, 2/28, 3/21, 3/28, 4/25, 5/9, 5/16, 5/23", "堂數": 8},
        {"班級": "壁球興趣班", "負責教練": "外展教練 (LCSD)", "地點": "和興體育館", "時間": "16:00-17:30", "日期內容": "19/1, 26/1, 2/2, 9/2, 2/3, 23/3, 30/3, 20/4", "堂數": 8},
        {"班級": "壁球初級訓練班", "負責教練": "待定", "地點": "和興體育館", "時間": "16:00-17:30", "日期內容": "8/1, 15/1, 22/1, 29/1, 5/2, 12/2, 26/2, 5/3, 19/3, 26/3", "堂數": 10},
        {"班級": "壁球中級訓練班", "負責教練": "待定", "地點": "太和體育館", "時間": "16:00-17:30", "日期內容": "5/1, 12/1, 19/1, 26/1, 2/2, 9/2, 23/2, 2/3, 23/3, 30/3", "堂數": 10},
        {"班級": "正覺壁球精英班", "負責教練": "總教練", "地點": "太和體育館", "時間": "16:00-17:30", "日期內容": "8/1, 15/1, 22/1, 29/1, 5/2, 12/2, 26/2, 5/3, 19/3, 26/3", "堂數": 10},
        {"班級": "壁球校隊訓練班", "負責教練": "總教練", "地點": "太和體育館", "時間": "16:00-17:30", "日期內容": "17/12, 7/1, 14/1, 21/1, 28/1, 4/2, 11/2, 25/2, 4/3, 25/3, 1/4", "堂數": 11}
    ]
    st.session_state.schedule_df = pd.DataFrame(initial_data)

# 活動與比賽日曆數據
if 'events_df' not in st.session_state:
    event_data = [
        {"活動名稱": "全港小學校際壁球比賽", "日期": "2026-03-15", "地點": "歌和老街壁球中心", "類型": "比賽", "備註": "請校隊成員準時出席", "報名狀態": "接受報名"},
        {"活動名稱": "壁球同樂日 - 體育節", "日期": "2026-04-10", "地點": "香港壁球中心", "類型": "校外活動", "備註": "歡迎家長及同學參加", "報名狀態": "尚未開始"}
    ]
    st.session_state.events_df = pd.DataFrame(event_data)

if 'attendance_records' not in st.session_state:
    st.session_state.attendance_records = {}

if 'players' not in st.session_state:
    raw_players = [
        {"姓名": "陳大文", "年級": "5C", "積分": 98, "班級": "壁球校隊訓練班"},
        {"姓名": "李小明", "年級": "6A", "積分": 95, "班級": "壁球校隊訓練班"},
        {"姓名": "張一龍", "年級": "4B", "積分": 92, "班級": "正覺壁球精英班"},
        {"姓名": "黃嘉嘉", "年級": "5A", "積分": 89, "班級": "正覺壁球精英班"},
        {"姓名": "趙子龍", "年級": "3D", "積分": 88, "班級": "壁球中級訓練班"},
        {"姓名": "周杰倫", "年級": "6C", "積分": 85, "班級": "壁球中級訓練班"},
        {"姓名": "林俊傑", "年級": "4A", "積分": 82, "班級": "壁球初級訓練班"},
        {"姓名": "王力宏", "年級": "5B", "積分": 80, "班級": "壁球初級訓練班"}
    ]
    st.session_state.players = pd.DataFrame(raw_players)

# --- 側邊欄 ---
st.sidebar.title("🔐 管理員登入")
if not st.session_state.is_admin:
    st.sidebar.text_input("輸入管理員密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 管理員已登入")
    if st.sidebar.button("登出"):
        st.session_state.is_admin = False
        st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("功能選單", [
    "1. 學費預算計算", 
    "2. 訓練班日程表", 
    "3. 隊員 TOP 8 排行榜", 
    "4. 點名與出席率統計",
    "5. 壁球活動公告日曆"
])

# --- 5. 壁球活動公告日曆 (新功能) ---
if menu == "5. 壁球活動公告日曆":
    st.title("📅 壁球活動及比賽日曆")
    st.write("在這裡查看最新的比賽資訊、校外活動及報名連結。")
    
    if st.session_state.is_admin:
        with st.expander("➕ 發佈新活動"):
            with st.form("new_event"):
                e_name = st.text_input("活動名稱")
                e_date = st.date_input("活動日期")
                e_loc = st.text_input("地點")
                e_type = st.selectbox("類型", ["比賽", "校外活動", "校內講座", "教練培訓"])
                e_note = st.text_area("備註")
                e_status = st.selectbox("狀態", ["接受報名", "尚未開始", "報名已截止"])
                if st.form_submit_button("發佈活動"):
                    new_e = {"活動名稱": e_name, "日期": str(e_date), "地點": e_loc, "類型": e_type, "備註": e_note, "報名狀態": e_status}
                    st.session_state.events_df = pd.concat([st.session_state.events_df, pd.DataFrame([new_e])], ignore_index=True)
                    st.success("活動已發佈！")
                    st.rerun()

    # 展示卡片介面
    st.markdown("---")
    events = st.session_state.events_df.sort_values("日期")
    
    # 分成兩列顯示卡片
    cols = st.columns(2)
    for idx, row in events.iterrows():
        with cols[idx % 2]:
            with st.container(border=True):
                # 標籤顏色
                type_color = "red" if row['類型'] == "比賽" else "blue"
                status_color = "green" if row['報名狀態'] == "接受報名" else "grey"
                
                st.markdown(f"### {row['活動名稱']}")
                st.markdown(f"**🗓️ 日期：** `{row['日期']}`")
                st.markdown(f"**📍 地點：** {row['地點']}")
                st.markdown(f"**📌 類型：** :{type_color}[{row['類型']}]")
                st.write(f"💬 {row['備註']}")
                
                # 底部狀態按鈕 (模擬)
                st.divider()
                if row['報名狀態'] == "接受報名":
                    st.button(f"🔗 點我報名 ({row['活動名稱']})", key=f"btn_{idx}")
                else:
                    st.info(f"狀態：{row['報名狀態']}")

    if st.session_state.is_admin:
        with st.expander("🛠️ 管理/刪除現有活動"):
            edited_events = st.data_editor(st.session_state.events_df, num_rows="dynamic")
            if st.button("確認更新活動表"):
                st.session_state.events_df = edited_events
                st.rerun()

# --- 1, 2, 3, 4 功能保持不變 (省略顯示以節省篇幅) ---
elif menu == "1. 學費預算計算":
    st.title("💰 下一期通告學費核算")
    # ... 原有邏輯 ...
    st.info("此部分維持原本的學費核算邏輯")

elif menu == "2. 訓練班日程表":
    st.title("📅 訓練班日程及教練分配")
    if st.session_state.is_admin:
        edited = st.data_editor(st.session_state.schedule_df, use_container_width=True, num_rows="dynamic")
        if st.button("保存修改"):
            st.session_state.schedule_df = edited
            st.success("日程表已保存")
    else:
        st.table(st.session_state.schedule_df)

elif menu == "3. 隊員 TOP 8 排行榜":
    st.title("🏆 壁球隊精英排行榜 (TOP 8)")
    top_8 = st.session_state.players.sort_values(by="積分", ascending=False).head(8).reset_index(drop=True)
    top_8.index += 1
    st.table(top_8)

elif menu == "4. 點名與出席率統計":
    st.title("📝 教練點名系統")
    # ... 原有邏輯 ...
    st.info("管理員可在此點名並查閱所有學生的出席率百分比")
