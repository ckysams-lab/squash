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

# 初始化訓練班日程 (已增加星期六 A、B 兩班並補全日期)
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = pd.DataFrame([
        {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8, "類型": "興趣班", "具體日期": "1/20, 1/27, 2/3, 2/10, 2/17, 2/24, 3/3, 3/10"},
        {"班級": "星期六小型壁球興趣班 (A班)", "地點": "學校室內操場", "時間": "10:15-11:15", "日期": "2/7-5/23", "堂數": 8, "類型": "興趣班", "具體日期": "2/7, 2/14, 2/21, 2/28, 3/7, 3/14, 3/21, 3/28"},
        {"班級": "星期六小型壁球興趣班 (B班)", "地點": "學校室內操場", "時間": "12:00-13:00", "日期": "2/7-5/23", "堂數": 8, "類型": "興趣班", "具體日期": "2/7, 2/14, 2/21, 2/28, 3/7, 3/14, 3/21, 3/28"},
        {"班級": "校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "12/17-4/1", "堂數": 11, "類型": "校隊班", "具體日期": "12/17, 1/7, 1/14, 1/21, 2/4, 2/11, 2/18, 2/25, 3/4, 3/11, 3/18"},
        {"班級": "精英班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/8-3/26", "堂數": 10, "類型": "培訓班", "具體日期": ""},
        {"班級": "中級訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/5-3/30", "堂數": 10, "類型": "培訓班", "具體日期": ""},
    ])

# 初始化點名資料
if 'attendance_data' not in st.session_state:
    initial_data = [
        {"姓名": "陳大文", "班級": "校隊訓練班", "年級": "5C", "T1": True, "T2": True, "T3": False},
        {"姓名": "李小明", "班級": "校隊訓練班", "年級": "6A", "T1": True, "T2": False, "T3": True},
        {"姓名": "張一龍", "班級": "精英班", "年級": "4B", "T1": True, "T2": True, "T3": True},
    ]
    st.session_state.attendance_data = pd.DataFrame(initial_data)

# 初始化基本隊員名單
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
        st.warning("⚠️ 重要：請在「具體日期」欄位輸入以逗號隔開的日期（例如：1/20, 1/27），系統會自動將這些日期對接到「點名頁面」的欄位名稱。")
        edited_df = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True)
        if st.button("確認儲存日程"):
            st.session_state.schedule_df = edited_df
            st.success("已更新日程表並連結至點名系統")
    else:
        # 非管理員隱藏編輯用的具體日期欄位
        display_cols = [c for c in st.session_state.schedule_df.columns if c != "具體日期"]
        st.table(st.session_state.schedule_df[display_cols])

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

# --- 4. 點名與統計 ---
elif menu == "📝 點名與統計":
    st.title("📝 班級點名紀錄表")
    
    all_classes = st.session_state.schedule_df["班級"].tolist()
    if not all_classes:
        st.warning("請先在日程表新增班級")
    else:
        selected_class = st.selectbox("請選擇班級查看點名表", all_classes)
        
        # 獲取日程表中該班級的所有資訊
        class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == selected_class].iloc[0]
        total_lessons = int(class_info["堂數"])
        
        # 從日程表中讀取「具體日期」
        raw_dates = str(class_info.get("具體日期", ""))
        date_list = [d.strip() for d in raw_dates.split(",") if d.strip()]
        
        # 建立欄位名稱映射
        rename_map = {}
        for i in range(1, total_lessons + 1):
            if i <= len(date_list):
                rename_map[f"T{i}"] = date_list[i-1]
            else:
                rename_map[f"T{i}"] = f"第{i}堂"
        
        # 獲取隊員數據
        df_class_att = st.session_state.attendance_data[st.session_state.attendance_data["班級"] == selected_class].copy()
        
        # 確保內部數據結構 T1...Tn 齊全
        for i in range(1, total_lessons + 1):
            col_id = f"T{i}"
            if col_id not in df_class_att.columns:
                df_class_att[col_id] = False
                
        # 準備顯示用的 DataFrame
        lesson_ids = [f"T{i}" for i in range(1, total_lessons + 1)]
        display_df = df_class_att[["姓名", "年級"] + lesson_ids]
        display_df = display_df.rename(columns=rename_map)

        st.subheader(f"📊 {selected_class}")
        if date_list:
            st.success(f"🔗 已成功從日程表連結 {len(date_list)} 個上課日期")
        else:
            st.info("💡 提示：若要在表格標題顯示日期，請在「訓練班日程表」的「具體日期」欄位輸入日期。")
        
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

            # 點名編輯器
            edited_class_df = st.data_editor(
                display_df,
                column_config={val: st.column_config.CheckboxColumn(default=False) for val in rename_map.values()},
                use_container_width=True,
                num_rows="dynamic",
                key=f"editor_{selected_class}"
            )
            
            if st.button("💾 儲存點名變更"):
                reverse_map = {v: k for k, v in rename_map.items()}
                save_df = edited_class_df.rename(columns=reverse_map)
                
                st.session_state.attendance_data = st.session_state.attendance_data[st.session_state.attendance_data["班級"] != selected_class]
                save_df["班級"] = selected_class
                st.session_state.attendance_data = pd.concat([st.session_state.attendance_data, save_df], ignore_index=True).fillna(False)
                st.success("點名紀錄已成功儲存！")
                st.rerun()
        else:
            # 唯讀模式
            att_only = display_df[list(rename_map.values())]
            display_df["出席率"] = (att_only.sum(axis=1) / total_lessons * 100).round(1).astype(str) + "%"
            st.dataframe(display_df, use_container_width=True)

    st.divider()
    st.download_button("📥 導出全校出席報表 (CSV)", data=st.session_state.attendance_data.to_csv().encode('utf-8'), file_name="attendance.csv")

# --- 5. 學費預算計算 ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 下一期通告學費核算 (管理員手動試算)")
    
    st.subheader("⚙️ 第一步：成本單價設定 (每堂課)")
    c1, c2, c3 = st.columns(3)
    with c1:
        u_team = st.number_input("校隊班 單價 ($)", value=2750.0)
    with c2:
        u_train = st.number_input("培訓班 單價 ($)", value=1350.0)
    with c3:
        u_hobby = st.number_input("興趣班 單價 ($)", value=1200.0)

    st.divider()
    st.subheader("👥 第二步：手動輸入班數與參加人數")
    col_in1, col_in2, col_in3 = st.columns(3)
    with col_in1:
        st.markdown("**校隊系列**")
        n_team = st.number_input("預計開辦班數", min_value=0, value=1, key="n_t")
        l_team = st.number_input("每班堂數", min_value=0, value=11, key="l_t")
        s_team = st.number_input("預計參加人數", min_value=0, value=12, key="s_t")
    with col_in2:
        st.markdown("**培訓系列**")
        n_train = st.number_input("預計開辦班數 ", min_value=0, value=4, key="n_tr")
        l_train = st.number_input("每班堂數 ", min_value=0, value=10, key="l_tr")
        s_train = st.number_input("預計參加人數 ", min_value=0, value=48, key="s_tr")
    with col_in3:
        st.markdown("**興趣班系列**")
        n_hobby = st.number_input("預計開辦班數  ", min_value=0, value=3, key="n_h") # 已改為3 (二+六A+六B)
        l_hobby = st.number_input("每班堂數  ", min_value=0, value=8, key="l_h")
        s_hobby = st.number_input("預計參加人數  ", min_value=0, value=48, key="s_h")

    st.divider()
    st.subheader("📊 第三步：核算結果")
    notice_fee = st.number_input("通告擬定每位學生收費 ($)", value=250.0)
    
    total_cost = (n_team * l_team * u_team) + (n_train * l_train * u_train) + (n_hobby * l_hobby * u_hobby)
    total_students = s_team + s_train + s_hobby
    total_income = total_students * notice_fee
    subsidy_needed = total_cost - total_income
    
    if total_students > 0:
        avg_cost = total_cost / total_students
        m1, m2, m3 = st.columns(3)
        m1.metric("總預算開支", f"${total_cost:,.0f}")
        m2.metric("每人平均真實成本", f"${avg_cost:.1f}")
        m3.metric("預計資助/虧損額", f"${max(0, subsidy_needed):,.0f}", delta=f"{subsidy_needed:,.0f}", delta_color="inverse")
        
        st.info(f"💡 核算公式：(總成本 ${total_cost:,.0f}) / (總人數 {total_students}) = 每人成本 ${avg_cost:.1f}")
    else:
        st.warning("請在上方輸入參加人數以進行核算。")
