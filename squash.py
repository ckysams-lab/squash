import streamlit as st
import pandas as pd
import numpy as np

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide")

# --- 1. 安全權限與數據初始化 ---
ADMIN_PASSWORD = "8888"

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# 初始化活動公告數據
if 'events_list' not in st.session_state:
    st.session_state.events_list = [
        {"id": 1, "活動": "全港小學校際壁球比賽", "日期": "2026-03-15", "地點": "歌和老街", "狀態": "接受報名", "pdf_url": "https://example.com/form1.pdf", "interested": 12},
        {"id": 2, "活動": "校際壁球個人賽", "日期": "2026-04-10", "地點": "香港壁球中心", "狀態": "尚未開始", "pdf_url": "", "interested": 5}
    ]

# 初始化日程表數據 (包含所有班級及對應日期)
default_schedule = [
    {"班級": "星期二小型壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8, "類型": "興趣班", "具體日期": "1/20, 1/27, 2/3, 2/10, 2/17, 2/24, 3/3, 3/10"},
    {"班級": "星期六小型壁球興趣班 (A班)", "地點": "學校室內操場", "時間": "10:15-11:15", "日期": "2/7-5/23", "堂數": 8, "類型": "興趣班", "具體日期": "2/7, 2/14, 2/21, 2/28, 3/7, 3/14, 3/21, 3/28"},
    {"班級": "星期六小型壁球興趣班 (B班)", "地點": "學校室內操場", "時間": "12:00-13:00", "日期": "2/7-5/23", "堂數": 8, "類型": "興趣班", "具體日期": "2/7, 2/14, 2/21, 2/28, 3/7, 3/14, 3/21, 3/28"},
    {"班級": "壁球初級班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8, "類型": "興趣班", "具體日期": "1/20, 1/27, 2/3, 2/10, 2/17, 2/24, 3/3, 3/10"},
    {"班級": "壁球興趣班", "地點": "學校室內操場", "時間": "15:30-16:30", "日期": "1/20-3/31", "堂數": 8, "類型": "興趣班", "具體日期": "1/20, 1/27, 2/3, 2/10, 2/17, 2/24, 3/3, 3/10"},
    {"班級": "校隊訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "12/17-4/1", "堂數": 11, "類型": "校隊班", "具體日期": "12/17, 1/7, 1/14, 1/21, 2/4, 2/11, 2/18, 2/25, 3/4, 3/11, 3/18"},
    {"班級": "精英班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/8-3/26", "堂數": 10, "類型": "培訓班", "具體日期": "1/8, 1/15, 1/22, 2/5, 2/12, 2/19, 2/26, 3/5, 3/12, 3/19"},
    {"班級": "中級訓練班", "地點": "太和體育館", "時間": "16:00-17:30", "日期": "1/5-3/30", "堂數": 10, "類型": "培訓班", "具體日期": "1/5, 1/12, 1/19, 2/2, 2/9, 2/16, 2/23, 3/2, 3/9, 3/16"},
]

if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = pd.DataFrame(default_schedule)

if 'attendance_data' not in st.session_state:
    st.session_state.attendance_data = pd.DataFrame(columns=["姓名", "班級", "年級"])

if 'players_df' not in st.session_state:
    st.session_state.players_df = pd.DataFrame([{"姓名": "陳大文", "積分": 98}, {"姓名": "李小明", "積分": 95}])

# 密碼檢查
def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理員權限已解鎖！")
    else:
        st.error("密碼不正確。")

# --- 側邊欄 ---
st.sidebar.title("🏸 正覺壁球管理系統")
if not st.session_state.is_admin:
    st.sidebar.text_input("管理員密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
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
    
    # 管理員發布新活動
    if st.session_state.is_admin:
        with st.expander("➕ 發布新比賽/活動"):
            with st.form("add_event_form", clear_on_submit=True):
                new_title = st.text_input("活動名稱")
                new_date = st.date_input("活動日期")
                new_loc = st.text_input("地點")
                new_pdf = st.text_input("報名表 PDF 連結 (可選)")
                submitted = st.form_submit_button("立即發布")
                if submitted and new_title:
                    new_id = max([e["id"] for e in st.session_state.events_list]) + 1 if st.session_state.events_list else 1
                    st.session_state.events_list.append({
                        "id": new_id,
                        "活動": new_title,
                        "日期": str(new_date),
                        "地點": new_loc,
                        "狀態": "接受報名",
                        "pdf_url": new_pdf,
                        "interested": 0
                    })
                    st.success("活動已發布！")
                    st.rerun()

    # 顯示活動列表
    if not st.session_state.events_list:
        st.write("目前沒有進行中的活動。")
    else:
        for i, ev in enumerate(st.session_state.events_list):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(ev["活動"])
                    st.write(f"📅 **日期**: {ev['日期']} | 📍 **地點**: {ev['地點']}")
                    st.write(f"🔥 目前已有 **{ev['interested']}** 人表示有興趣")
                
                with col2:
                    st.write(f"**狀態**: {ev['狀態']}")
                    # 學生功能：感興趣按鈕
                    if st.button("🙋 我感興趣", key=f"int_{ev['id']}"):
                        ev["interested"] += 1
                        st.toast("已記錄你的興趣！")
                        st.rerun()
                    
                    # 下載 PDF 功能
                    if ev["pdf_url"]:
                        st.link_button("📄 下載報名表", ev["pdf_url"])
                    else:
                        st.button("📄 下載報名表", disabled=True, help="此活動未提供電子表單")

                    # 管理員功能：刪除按鈕
                    if st.session_state.is_admin:
                        if st.button("🗑️ 刪除活動", key=f"del_{ev['id']}", type="primary"):
                            st.session_state.events_list.pop(i)
                            st.rerun()

# --- 2. 訓練班日程表 ---
elif menu == "📅 訓練班日程表":
    st.title("📅 2025-26 年度訓練班日程")
    if st.session_state.is_admin:
        st.info("💡 修改「具體日期」後請點擊「💾 儲存日程」。若看不到新增的班級，請點擊下方「🔄 重置」。")
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
        with st.expander("管理積分"):
            new_players = st.data_editor(st.session_state.players_df, num_rows="dynamic", use_container_width=True)
            if st.button("更新積分表"):
                st.session_state.players_df = new_players
                st.rerun()

# --- 4. 點名與統計 ---
elif menu == "📝 點名與統計":
    st.title("📝 班級點名紀錄")
    class_list = st.session_state.schedule_df["班級"].tolist()
    sel_class = st.selectbox("請選擇班級：", class_list)
    
    # 獲取班級詳細資訊
    row = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class].iloc[0]
    num_lessons = int(row["堂數"])
    dates_str = str(row.get("具體日期", ""))
    date_items = [d.strip() for d in dates_str.split(",") if d.strip()]
    
    # 映射欄位名稱 (T1 -> 具體日期)
    col_map = {f"T{i}": (date_items[i-1] if i <= len(date_items) else f"第{i}堂") for i in range(1, num_lessons + 1)}
    
    # 獲取點名數據
    att_df = st.session_state.attendance_data[st.session_state.attendance_data["班級"] == sel_class].copy()
    for i in range(1, num_lessons + 1):
        if f"T{i}" not in att_df.columns: att_df[f"T{i}"] = False
            
    # 展示與編輯
    final_display_df = att_df[["姓名", "年級"] + [f"T{i}" for i in range(1, num_lessons + 1)]].rename(columns=col_map)
    
    st.subheader(f"📊 {sel_class}")
    if st.session_state.is_admin:
        edited_att = st.data_editor(
            final_display_df, 
            column_config={v: st.column_config.CheckboxColumn() for v in col_map.values()}, 
            use_container_width=True, 
            num_rows="dynamic",
            key=f"att_edit_{sel_class}"
        )
        if st.button("💾 儲存點名結果"):
            rev_map = {v: k for k, v in col_map.items()}
            to_save = edited_att.rename(columns=rev_map)
            to_save["班級"] = sel_class
            st.session_state.attendance_data = st.session_state.attendance_data[st.session_state.attendance_data["班級"] != sel_class]
            st.session_state.attendance_data = pd.concat([st.session_state.attendance_data, to_save], ignore_index=True).fillna(False)
            st.success("點名紀錄已更新！")
    else:
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
        n_hobby = st.number_input("開班數  ", value=5, key="nh") # 包含星期二、六(A/B)、初級、興趣
        l_hobby = st.number_input("堂數  ", value=8, key="lh")
        p_hobby = st.number_input("預計人數  ", value=75, key="ph")
    
    st.divider()
    
    fee = st.number_input("預計每位學生收費 ($)", value=250)
    total_cost = (n_team * l_team * cost_team) + (n_train * l_train * cost_train) + (n_hobby * l_hobby * cost_hobby)
    total_income = (p_team + p_train + p_hobby) * fee
    balance = total_income - total_cost
    
    m1, m2, m3 = st.columns(3)
    m1.metric("預計總支出", f"${total_cost:,}")
    m2.metric("預計總收入", f"${total_income:,}")
    m3.metric("收支差額", f"${balance:,}", delta=f"{balance:,}")
    
    if balance < 0:
        st.error(f"⚠️ 預計需要校方補貼: ${abs(balance):,}")
    else:
        st.success(f"✅ 預計盈餘: ${balance:,}")
