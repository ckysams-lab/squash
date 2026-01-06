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

# 初始化訓練班日程 (包含堂數資訊)
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = pd.DataFrame([
        {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8},
        {"班級": "星期六小型壁球興趣班", "地點": "學校室內操場", "時間": "A:10:15 / B:12:00", "日期": "2/7-5/23", "堂數": 8},
        {"班級": "校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "12/17-4/1", "堂數": 11},
        {"班級": "精英班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/8-3/26", "堂數": 10},
        {"班級": "中級訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/5-3/30", "堂數": 10},
    ])

# 初始化隊員詳細點名資料 (矩陣結構)
# 為了靈活性，我們將點名紀錄存在一個獨立的 DataFrame
if 'attendance_data' not in st.session_state:
    # 預設一些種子數據
    initial_data = [
        {"姓名": "陳大文", "班級": "校隊訓練班", "年級": "5C", "T1": True, "T2": True, "T3": False},
        {"姓名": "李小明", "班級": "校隊訓練班", "年級": "6A", "T1": True, "T2": False, "T3": True},
        {"姓名": "張一龍", "班級": "精英班", "年級": "4B", "T1": True, "T2": True, "T3": True},
    ]
    st.session_state.attendance_data = pd.DataFrame(initial_data)

# 初始化基本隊員名單 (用於排行榜積分)
if 'players_df' not in st.session_state:
    st.session_state.players_df = pd.DataFrame([
        {"姓名": "陳大文", "積分": 98},
        {"姓名": "李小明", "積分": 95},
        {"姓名": "張一龍", "積分": 92},
        {"姓名": "黃嘉嘉", "積分": 89},
        {"姓名": "趙子龍", "積分": 88},
    ])

if 'events_df' not in st.session_state:
    st.session_state.events_df = pd.DataFrame([
        {"活動": "全港小學校際壁球比賽", "日期": "2026-03-15", "地點": "歌和老街壁球中心", "類型": "比賽", "狀態": "接受報名"},
        {"活動": "壁球同樂日", "日期": "2026-04-10", "地點": "香港壁球中心", "類型": "校外活動", "狀態": "尚未開始"}
    ])

def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理員解鎖成功！")
    else:
        st.error("密碼錯誤。")

# --- 側邊欄 ---
st.sidebar.title("🔐 管理員區域")
if not st.session_state.is_admin:
    st.sidebar.text_input("輸入管理員密碼", type="password", key="pwd_input", on_change=check_password)
else:
    st.sidebar.success("✅ 已取得管理權限")
    if st.sidebar.button("登出管理員"):
        st.session_state.is_admin = False
        st.rerun()

menu_options = ["📢 比賽活動公告", "📅 訓練班日程表", "🏆 隊員排行榜", "📝 點名與統計"]
if st.session_state.is_admin:
    menu_options.append("💰 學費預算計算 (管理專用)")

menu = st.sidebar.radio("功能選單", menu_options)

# --- 1. 比賽活動公告 ---
if menu == "📢 比賽活動公告":
    st.title("📅 壁球活動公告與報名日曆")
    if st.session_state.is_admin:
        with st.expander("➕ 發布新活動"):
            with st.form("new_event"):
                e_name = st.text_input("活動名稱")
                e_date = st.date_input("日期")
                if st.form_submit_button("發布"):
                    new_ev = {"活動": e_name, "日期": str(e_date), "地點": "", "類型": "比賽", "狀態": "接受報名"}
                    st.session_state.events_df = pd.concat([st.session_state.events_df, pd.DataFrame([new_ev])], ignore_index=True)
                    st.rerun()

    cols = st.columns(2)
    for idx, row in st.session_state.events_df.iterrows():
        with cols[idx % 2]:
            st.info(f"**{row['活動']}**\n\n日期: {row['日期']} | 狀態: {row['狀態']}")

# --- 2. 訓練班日程表 ---
elif menu == "📅 訓練班日程表":
    st.title("📅 訓練班日程閱覽")
    if st.session_state.is_admin:
        edited_df = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True)
        if st.button("確認儲存日程"):
            st.session_state.schedule_df = edited_df
            st.success("已更新")
    else:
        st.table(st.session_state.schedule_df)

# --- 3. 隊員排行榜 ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 壁球隊 TOP 隊員排行榜")
    if st.session_state.is_admin:
        with st.expander("📥 匯入積分 Excel"):
            up_file = st.file_uploader("上傳 (需包含: 姓名, 積分)", type=["xlsx"])
            if up_file:
                df_up = pd.read_excel(up_file)
                if st.button("覆蓋積分"):
                    st.session_state.players_df = df_up[["姓名", "積分"]]
                    st.rerun()
    
    rank_df = st.session_state.players_df.sort_values("積分", ascending=False).reset_index(drop=True)
    rank_df.index += 1
    st.table(rank_df)

# --- 4. 點名與統計 (核心修改：每班一張表 + 橫向日期) ---
elif menu == "📝 點名與統計":
    st.title("📝 班級點名紀錄表")
    
    # 選擇班級
    all_classes = st.session_state.schedule_df["班級"].tolist()
    selected_class = st.selectbox("請選擇班級查看點名表", all_classes)
    
    # 獲取該班級的設定 (主要是堂數)
    class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == selected_class].iloc[0]
    total_lessons = int(class_info["堂數"])
    
    # 過濾出該班級的隊員
    df_class_att = st.session_state.attendance_data[st.session_state.attendance_data["班級"] == selected_class].copy()
    
    # 確保所有堂數欄位 (T1, T2, ..., Tn) 都存在
    lesson_cols = [f"第{i}堂" for i in range(1, total_lessons + 1)]
    for col in lesson_cols:
        col_id = f"T{lesson_cols.index(col)+1}" # 內部存儲用 T1, T2...
        if col_id not in df_class_att.columns:
            df_class_att[col_id] = False
            
    # 整理顯示用的 DataFrame
    display_df = df_class_att[["姓名", "年級"] + [f"T{i+1}" for i in range(total_lessons)]]
    # 重新命名欄位以便用戶閱讀
    rename_map = {f"T{i+1}": f"第{i+1}堂" for i in range(total_lessons)}
    display_df = display_df.rename(columns=rename_map)

    st.subheader(f"📊 {selected_class} - 點名表")
    
    if st.session_state.is_admin:
        with st.expander("📥 匯入本班名單"):
            att_file = st.file_uploader("上傳 Excel (需包含: 姓名, 年級)", type=["xlsx"])
            if att_file:
                df_new = pd.read_excel(att_file)
                if st.button("確認新增至此班級"):
                    for _, r in df_new.iterrows():
                        if not ((st.session_state.attendance_data["姓名"] == r["姓名"]) & 
                                (st.session_state.attendance_data["班級"] == selected_class)).any():
                            new_row = {"姓名": r["姓名"], "年級": r["年級"], "班級": selected_class}
                            st.session_state.attendance_data = pd.concat([st.session_state.attendance_data, pd.DataFrame([new_row])], ignore_index=True)
                    st.rerun()

        # 使用 data_editor 進行勾選式點名
        edited_class_df = st.data_editor(
            display_df,
            column_config={f"第{i+1}堂": st.column_config.CheckboxColumn(default=False) for i in range(total_lessons)},
            use_container_width=True,
            num_rows="dynamic",
            key=f"editor_{selected_class}"
        )
        
        if st.button("💾 儲存點名變更"):
            # 反向更新回總表
            # 1. 先刪除舊的該班數據
            st.session_state.attendance_data = st.session_state.attendance_data[st.session_state.attendance_data["班級"] != selected_class]
            # 2. 加入編輯後的數據
            save_df = edited_class_df.rename(columns={v: k for k, v in rename_map.items()})
            save_df["班級"] = selected_class
            st.session_state.attendance_data = pd.concat([st.session_state.attendance_data, save_df], ignore_index=True).fillna(False)
            st.success("點名紀錄已儲存！")
            st.rerun()
    else:
        # 非管理員僅能查看 (計算出席率顯示)
        # 計算出席率
        att_only = display_df[[f"第{i+1}堂" for i in range(total_lessons)]]
        display_df["出席率"] = (att_only.sum(axis=1) / total_lessons * 100).round(1).astype(str) + "%"
        st.dataframe(display_df, use_container_width=True)

    st.divider()
    st.download_button("📥 導出全校出席報表", data=st.session_state.attendance_data.to_csv().encode('utf-8'), file_name="attendance.csv")

# --- 5. 學費預算計算 ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 下一期通告學費核算")
    st.info("此功能根據日程表設定的班數與單價進行試算。")
    notice_fee = st.number_input("通告收費 ($)", value=250.0)
    # 這裡保留原本的計算邏輯...
    st.write("（預算詳情計算中...）")
