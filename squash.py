import streamlit as st
import pandas as pd
import numpy as np

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide")

# --- 1. 安全權限與數據初始化 ---
ADMIN_PASSWORD = "8888"

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# 初始化成本
if 'unit_costs' not in st.session_state:
    st.session_state.unit_costs = {"校隊班": 2750.0, "培訓班": 1350.0, "興趣班": 1200.0}

# --- 核心數據：班級日程與日期定義 ---
default_schedule = [
    {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8, "類型": "興趣班", "具體日期": "1/20, 1/27, 2/3, 2/10, 2/17, 2/24, 3/3, 3/10"},
    {"班級": "星期六小型壁球興趣班 (A班)", "地點": "學校室內操場", "時間": "10:15-11:15", "日期": "2/7-5/23", "堂數": 8, "類型": "興趣班", "具體日期": "2/7, 2/14, 2/21, 2/28, 3/7, 3/14, 3/21, 3/28"},
    {"班級": "星期六小型壁球興趣班 (B班)", "地點": "學校室內操場", "時間": "12:00-13:00", "日期": "2/7-5/23", "堂數": 8, "類型": "興趣班", "具體日期": "2/7, 2/14, 2/21, 2/28, 3/7, 3/14, 3/21, 3/28"},
    {"班級": "校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "12/17-4/1", "堂數": 11, "類型": "校隊班", "具體日期": "12/17, 1/7, 1/14, 1/21, 2/4, 2/11, 2/18, 2/25, 3/4, 3/11, 3/18"},
    {"班級": "精英班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/8-3/26", "堂數": 10, "類型": "培訓班", "具體日期": "1/8, 1/15, 1/22, 2/5, 2/12, 2/19, 2/26, 3/5, 3/12, 3/19"},
    {"班級": "中級訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/5-3/30", "堂數": 10, "類型": "培訓班", "具體日期": "1/5, 1/12, 1/19, 2/2, 2/9, 2/16, 2/23, 3/2, 3/9, 3/16"},
]

if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = pd.DataFrame(default_schedule)

# 初始化點名紀錄
if 'attendance_data' not in st.session_state:
    # 預設一些假數據供測試
    initial_att = [
        {"姓名": "陳大文", "班級": "校隊訓練班", "年級": "5C", "T1": True, "T2": True},
        {"姓名": "李小明", "班級": "校隊訓練班", "年級": "6A", "T1": True, "T2": False}
    ]
    st.session_state.attendance_data = pd.DataFrame(initial_att)

# 初始化隊員清單
if 'players_df' not in st.session_state:
    st.session_state.players_df = pd.DataFrame([
        {"姓名": "陳大文", "積分": 98},
        {"姓名": "李小明", "積分": 95},
        {"姓名": "張一龍", "積分": 92},
        {"姓名": "黃嘉嘉", "積分": 89},
        {"姓名": "趙子龍", "積分": 88},
    ])

# 密碼檢查函數
def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理員權限已解鎖！")
    else:
        st.error("密碼不正確。")

# --- 側邊欄導覽 ---
st.sidebar.title("🏸 正覺壁球管理系統")
if not st.session_state.is_admin:
    st.sidebar.text_input("輸入管理員密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 管理員模式")
    if st.sidebar.button("登出"):
        st.session_state.is_admin = False
        st.rerun()

menu_options = ["📢 比賽活動公告", "📅 訓練班日程表", "🏆 隊員排行榜", "📝 點名與統計"]
if st.session_state.is_admin:
    menu_options.append("💰 學費預算計算 (管理專用)")

menu = st.sidebar.radio("導覽選單", menu_options)

# --- 1. 比賽活動公告 ---
if menu == "📢 比賽活動公告":
    st.title("📅 最新壁球活動公告")
    events = [
        {"活動": "全港小學校際壁球比賽", "日期": "2026-03-15", "地點": "歌和老街", "狀態": "接受報名"},
        {"活動": "校際壁球個人賽", "日期": "2026-04-10", "地點": "香港壁球中心", "狀態": "尚未開始"}
    ]
    cols = st.columns(len(events))
    for i, ev in enumerate(events):
        with cols[i]:
            st.info(f"### {ev['活動']}\n\n**日期**: {ev['日期']}\n\n**地點**: {ev['地點']}\n\n**狀態**: {ev['狀態']}")

# --- 2. 訓練班日程表 ---
elif menu == "📅 訓練班日程表":
    st.title("📅 2025-26 年度訓練班日程")
    if st.session_state.is_admin:
        st.info("💡 **操作提示**：\n1. 在下方的「具體日期」欄位填入上課日（如：1/20, 1/27）。\n2. 點名頁面的欄位標題會隨之自動更新。\n3. 修改後請務必點擊「💾 儲存日程」。")
        
        edited_schedule = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True, key="sched_editor")
        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 儲存日程"):
                st.session_state.schedule_df = edited_schedule
                st.success("數據已儲存！")
                st.rerun()
        with c2:
            if st.button("🔄 重置為預設數據"):
                st.session_state.schedule_df = pd.DataFrame(default_schedule)
                st.rerun()
    else:
        st.dataframe(st.session_state.schedule_df.drop(columns=["具體日期"]), use_container_width=True)

# --- 3. 隊員排行榜 ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 壁球隊員積分排行榜")
    rank_df = st.session_state.players_df.sort_values("積分", ascending=False).reset_index(drop=True)
    rank_df.index += 1
    st.table(rank_df)
    if st.session_state.is_admin:
        with st.expander("編輯積分"):
            new_rank_df = st.data_editor(st.session_state.players_df, use_container_width=True)
            if st.button("儲存積分修改"):
                st.session_state.players_df = new_rank_df
                st.rerun()

# --- 4. 點名與統計 (日期對接關鍵區) ---
elif menu == "📝 點名與統計":
    st.title("📝 班級點名紀錄")
    
    class_list = st.session_state.schedule_df["班級"].tolist()
    sel_class = st.selectbox("請選擇班級：", class_list)
    
    # 獲取該班級的日程資料
    row = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class].iloc[0]
    num_lessons = int(row["堂數"])
    
    # 解析具體日期
    dates_str = str(row.get("具體日期", ""))
    date_items = [d.strip() for d in dates_str.split(",") if d.strip()]
    
    # 建立欄位顯示映射 (T1 -> 實體日期)
    col_map = {}
    for i in range(1, num_lessons + 1):
        display_name = date_items[i-1] if i <= len(date_items) else f"第{i}堂"
        col_map[f"T{i}"] = display_name
        
    # 過濾點名數據
    att_df = st.session_state.attendance_data[st.session_state.attendance_data["班級"] == sel_class].copy()
    
    # 確保所有需要的 T 欄位都存在於 DataFrame
    for i in range(1, num_lessons + 1):
        if f"T{i}" not in att_df.columns:
            att_df[f"T{i}"] = False
            
    # 準備展示用數據
    display_cols = ["姓名", "年級"] + [f"T{i}" for i in range(1, num_lessons + 1)]
    final_display_df = att_df[display_cols].rename(columns=col_map)
    
    st.subheader(f"📊 {sel_class} 點名表")
    if date_items:
        st.success(f"✅ 日期已同步：{len(date_items)} 堂課")
    else:
        st.warning("⚠️ 此班級尚未定義具體日期，顯示為預設堂數標題。")

    if st.session_state.is_admin:
        # 管理員可編輯
        edited_att = st.data_editor(
            final_display_df,
            column_config={v: st.column_config.CheckboxColumn() for v in col_map.values()},
            use_container_width=True,
            num_rows="dynamic",
            key=f"att_edit_{sel_class}"
        )
        
        if st.button("💾 儲存點名結果"):
            # 轉換回原始 T1... 標籤並存回 session_state
            rev_map = {v: k for k, v in col_map.items()}
            to_save = edited_att.rename(columns=rev_map)
            to_save["班級"] = sel_class
            
            # 更新全局數據：先刪除舊的，再加入新的
            st.session_state.attendance_data = st.session_state.attendance_data[st.session_state.attendance_data["班級"] != sel_class]
            st.session_state.attendance_data = pd.concat([st.session_state.attendance_data, to_save], ignore_index=True).fillna(False)
            st.success("點名紀錄已更新！")
    else:
        # 普通用戶僅查看
        st.dataframe(final_display_df, use_container_width=True)

# --- 5. 學費預算計算 ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 下期預算核算工具")
    
    st.markdown("### 1. 基礎成本設定 (每堂)")
    c1, c2, c3 = st.columns(3)
    cost_team = c1.number_input("校隊班 單價 ($)", value=2750)
    cost_train = c2.number_input("培訓班 單價 ($)", value=1350)
    cost_hobby = c3.number_input("興趣班 單價 ($)", value=1200)
    
    st.divider()
    
    st.markdown("### 2. 班級規模與人數預計")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**校隊**")
        n_team = st.number_input("開班數", value=1, key="nt")
        l_team = st.number_input("堂數", value=11, key="lt")
        p_team = st.number_input("預計人數", value=12, key="pt")
    with col2:
        st.write("**培訓**")
        n_train = st.number_input("開班數 ", value=4, key="ntr")
        l_train = st.number_input("堂數 ", value=10, key="ltr")
        p_train = st.number_input("預計人數 ", value=48, key="ptr")
    with col3:
        st.write("**興趣**")
        n_hobby = st.number_input("開班數  ", value=3, key="nh")
        l_hobby = st.number_input("堂數  ", value=8, key="lh")
        p_hobby = st.number_input("預計人數  ", value=60, key="ph")
        
    st.divider()
    
    st.markdown("### 3. 計算結果")
    fee_per_child = st.number_input("預計每位學生收費 ($)", value=250)
    
    total_cost = (n_team * l_team * cost_team) + (n_train * l_train * cost_train) + (n_hobby * l_hobby * cost_hobby)
    total_ppl = p_team + p_train + p_hobby
    total_income = total_ppl * fee_per_child
    balance = total_income - total_cost
    
    m1, m2, m3 = st.columns(3)
    m1.metric("預計總支出", f"${total_cost:,}")
    m2.metric("預計總收入", f"${total_income:,}")
    m3.metric("收支差額", f"${balance:,}", delta=f"{balance:,}")
    
    if balance < 0:
        st.error(f"⚠️ 預計需要校方補貼: ${abs(balance):,}")
    else:
        st.success(f"✅ 預計盈餘: ${balance:,}")
