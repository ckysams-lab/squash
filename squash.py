import streamlit as st
import pandas as pd
from datetime import datetime

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide")

# --- 1. 安全權限與數據初始化 ---
ADMIN_PASSWORD = "8888"

# 確保管理員狀態初始化
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# --- 強化初始化邏輯 ---
default_unit_costs = {
    "校隊班": 2750.0,
    "培訓班": 1350.0,
    "興趣班": 1200.0
}

if 'unit_costs' not in st.session_state:
    st.session_state.unit_costs = default_unit_costs.copy()
else:
    for key, val in default_unit_costs.items():
        if key not in st.session_state.unit_costs:
            st.session_state.unit_costs[key] = val

# 初始化訓練班日程
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = pd.DataFrame([
        {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8},
        {"班級": "星期六小型壁球興趣班", "地點": "學校室內操場", "時間": "A:10:15 / B:12:00", "日期": "2/7-5/23", "堂數": 8},
        {"班級": "校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "12/17-4/1", "堂數": 11},
        {"班級": "精英班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/8-3/26", "堂數": 10},
        {"班級": "中級訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/5-3/30", "堂數": 10},
    ])

# 初始化隊員名單
if 'players_df' not in st.session_state:
    st.session_state.players_df = pd.DataFrame([
        {"姓名": "陳大文", "年級": "5C", "積分": 98, "班級": "校隊訓練班", "出席率": "100%"},
        {"姓名": "李小明", "年級": "6A", "積分": 95, "班級": "校隊訓練班", "出席率": "95%"},
        {"姓名": "張一龍", "年級": "4B", "積分": 92, "班級": "精英班", "出席率": "90%"},
        {"姓名": "黃嘉嘉", "年級": "5A", "積分": 89, "班級": "精英班", "出席率": "100%"},
        {"姓名": "趙子龍", "年級": "3D", "積分": 88, "班級": "中級班", "出席率": "85%"},
    ])

# 初始化活動公告
if 'events_df' not in st.session_state:
    st.session_state.events_df = pd.DataFrame(columns=["活動", "日期", "地點", "類型", "狀態"])
    initial_events = [
        {"活動": "全港小學校際壁球比賽", "日期": "2026-03-15", "地點": "歌和老街壁球中心", "類型": "比賽", "狀態": "接受報名"},
        {"活動": "壁球同樂日", "日期": "2026-04-10", "地點": "香港壁球中心", "類型": "校外活動", "狀態": "尚未開始"}
    ]
    st.session_state.events_df = pd.DataFrame(initial_events)

# 密碼檢查函數
def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理員解鎖成功！")
    else:
        st.error("密碼錯誤，請重新輸入。")

# --- 側邊欄 ---
st.sidebar.title("🔐 管理員區域")
if not st.session_state.is_admin:
    st.sidebar.text_input("輸入管理員密碼以解鎖進階功能", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 已取得管理權限")
    if st.sidebar.button("登出管理員"):
        st.session_state.is_admin = False
        st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("功能選單", [
    "1. 學費預算計算 (需登入)", 
    "2. 訓練班日程表", 
    "3. 隊員排行榜", 
    "4. 點名與統計", 
    "5. 比賽活動公告"
])

# --- 1. 學費預算計算 (增加密碼保護邏輯) ---
if menu == "1. 學費預算計算 (需登入)":
    st.title("💰 下一期通告學費核算")
    
    if not st.session_state.is_admin:
        st.warning("⚠️ 此頁面包含機密財政預算，請先在左側邊欄輸入管理員密碼以查看內容。")
        st.info("提示：如果您是老師或負責人，請登入以調整各班別單價及人數。")
    else:
        st.subheader("⚙️ 第一步：成本單價設定")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state.unit_costs["校隊班"] = st.number_input("校隊班 單價 ($)", value=float(st.session_state.unit_costs["校隊班"]), key="input_uc_team")
        with c2:
            st.session_state.unit_costs["培訓班"] = st.number_input("初/中/精英班 單價 ($)", value=float(st.session_state.unit_costs["培訓班"]), key="input_uc_train")
        with c3:
            st.session_state.unit_costs["興趣班"] = st.number_input("興趣班 單價 ($)", value=float(st.session_state.unit_costs["興趣班"]), key="input_uc_hobby")

        st.markdown("---")
        st.subheader("👥 第二步：輸入報名班數及參加人數")
        col_in1, col_in2, col_in3 = st.columns(3)
        with col_in1:
            st.markdown("**校隊系列**")
            n_team = st.number_input("開辦班數", min_value=0, value=1, key="calc_n_t")
            s_team = st.number_input("參加總人數", min_value=0, value=12, key="calc_s_t")
        with col_in2:
            st.markdown("**培訓系列**")
            n_train = st.number_input("開辦班數 ", min_value=0, value=4, key="calc_n_tr")
            s_train = st.number_input("參加總人數 ", min_value=0, value=48, key="calc_s_tr")
        with col_in3:
            st.markdown("**興趣班系列**")
            n_hobby = st.number_input("開辦班數  ", min_value=0, value=3, key="calc_n_h")
            s_hobby = st.number_input("參加總人數  ", min_value=0, value=48, key="calc_s_h")

        st.markdown("---")
        st.subheader("📊 第三步：全校平均核算結果")
        notice_fee = st.number_input("通告擬定每位學生收費 ($)", value=250.0, key="notice_fee_input")
        
        total_cost = (n_team * st.session_state.unit_costs["校隊班"]) + \
                     (n_train * st.session_state.unit_costs["培訓班"]) + \
                     (n_hobby * st.session_state.unit_costs["興趣班"])
        total_students = s_team + s_train + s_hobby
        
        if total_students > 0:
            avg_cost = total_cost / total_students
            total_income = total_students * notice_fee
            subsidy = total_cost - total_income
            
            m1, m2, m3 = st.columns(3)
            m1.metric("三類總成本", f"${total_cost:,.0f}")
            m2.metric("平均每人成本", f"${avg_cost:.1f}")
            m3.metric("津貼需資助額", f"${max(0, subsidy):,.0f}")
            
            st.info(f"💡 公式說明：(${total_cost:,.0f} 總成本) / ({total_students} 總人數) = ${avg_cost:.1f} (平均每人成本)")
            if subsidy > 0:
                st.success(f"每位同學獲得資助：${avg_cost - notice_fee:.1f} 元")
        else:
            st.warning("請輸入參加人數以獲取計算結果。")

# --- 2. 訓練班日程表 (保持開放，但管理員可編輯) ---
elif menu == "2. 訓練班日程表":
    st.title("📅 訓練班日程管理")
    if st.session_state.is_admin:
        st.write("🔧 您現在具有編輯權限，可直接在表格中修改：")
        edited_df = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True, key="schedule_editor")
        if st.button("確認更新日程表"):
            st.session_state.schedule_df = edited_df
            st.success("日程表已儲存！")
    else:
        st.table(st.session_state.schedule_df)

# --- 3. 隊員排行榜 (保持開放) ---
elif menu == "3. 隊員排行榜":
    st.title("🏆 壁球隊 TOP 隊員排行榜")
    top_players = st.session_state.players_df.sort_values(by="積分", ascending=False).reset_index(drop=True)
    top_players.index += 1
    st.table(top_players)

# --- 4. 點名與統計 (保持開放查看，管理員可修改數據) ---
elif menu == "4. 點名與統計":
    st.title("📝 點名紀錄與出席率統計")
    if st.session_state.is_admin:
        edited_players = st.data_editor(st.session_state.players_df, use_container_width=True, key="attendance_editor")
        if st.button("儲存點名變更"):
            st.session_state.players_df = edited_players
            st.success("數據已更新！")
    else:
        st.dataframe(st.session_state.players_df[["姓名", "年級", "班級", "出席率"]], use_container_width=True)
    st.button("導出點名月報 (Excel格式預覽)")

# --- 5. 比賽活動公告 (保持開放) ---
elif menu == "5. 比賽活動公告":
    st.title("📅 壁球活動公告與報名日曆")
    
    if st.session_state.is_admin:
        with st.expander("➕ 發布新活動通知"):
            with st.form("new_event_form"):
                e_name = st.text_input("活動名稱")
                e_date = st.date_input("活動日期")
                e_loc = st.text_input("地點")
                e_type = st.selectbox("類型", ["比賽", "校外活動", "講座"])
                e_stat = st.selectbox("狀態", ["接受報名", "報名截止", "尚未開始"])
                if st.form_submit_button("確認發布"):
                    if e_name:
                        new_data = {"活動": e_name, "日期": str(e_date), "地點": e_loc, "類型": e_type, "狀態": e_stat}
                        st.session_state.events_df = pd.concat([st.session_state.events_df, pd.DataFrame([new_data])], ignore_index=True)
                        st.success("活動已發布！")
                        st.rerun()
                    else:
                        st.error("請輸入活動名稱")

    st.markdown("---")
    df = st.session_state.events_df
    if not df.empty and "活動" in df.columns:
        cols = st.columns(2)
        for idx, row in df.iterrows():
            with cols[idx % 2]:
                with st.container(border=True):
                    st.subheader(row.get('活動', '未命名活動'))
                    st.write(f"📅 日期: {row.get('日期', '-')} | 📍 地點: {row.get('地點', '-')}")
                    st.write(f"🏷️ 類型: {row.get('類型', '-')} | 📌 狀態: **{row.get('狀態', '-')}**")
                    if row.get('狀態') == "接受報名":
                        st.button(f"🔗 報名連結 (ID:{idx})", key=f"btn_ev_{idx}")
    else:
        st.info("目前沒有進行中的活動。")
