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

# 初始化日程表數據 (完整版本)
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
    # 預設一些範例點名數據
    st.session_state.attendance_data = pd.DataFrame([
        {"姓名": "陳大文", "班級": "校隊訓練班", "年級": "P.5", "T1": True, "T2": False},
        {"姓名": "李小明", "班級": "校隊訓練班", "年級": "P.4", "T1": True, "T2": True},
    ])

if 'players_df' not in st.session_state:
    st.session_state.players_df = pd.DataFrame([
        {"姓名": "陳大文", "積分": 98},
        {"姓名": "李小明", "積分": 95},
        {"姓名": "張家輝", "積分": 90},
        {"姓名": "林青霞", "積分": 88},
    ])

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
    
    if st.session_state.is_admin:
        with st.expander("➕ 發布新比賽/活動"):
            with st.form("add_event_form", clear_on_submit=True):
                new_title = st.text_input("活動名稱")
                new_date = st.date_input("活動日期")
                new_loc = st.text_input("地點")
                new_pdf = st.text_input("報名表 PDF 連結 (例如 https://...)")
                submitted = st.form_submit_button("立即發布")
                if submitted and new_title:
                    max_id = max([e["id"] for e in st.session_state.events_list]) if st.session_state.events_list else 0
                    st.session_state.events_list.append({
                        "id": int(max_id + 1), 
                        "活動": str(new_title), 
                        "日期": str(new_date),
                        "地點": str(new_loc), 
                        "狀態": "接受報名", 
                        "pdf_url": str(new_pdf).strip() if new_pdf else "", 
                        "interested": 0
                    })
                    st.success("活動已發布！")
                    st.rerun()

    if not st.session_state.events_list:
        st.write("目前沒有進行中的活動。")
    else:
        for idx, ev in enumerate(list(st.session_state.events_list)):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(ev["活動"])
                    st.write(f"📅 **日期**: {ev['日期']} | 📍 **地點**: {ev['地點']}")
                    st.write(f"🔥 目前已有 **{ev['interested']}** 人表示有興趣")
                with col2:
                    e_id = ev.get("id", idx)
                    
                    if st.button("🙋 我感興趣", key=f"int_btn_{e_id}"):
                        st.session_state.events_list[idx]["interested"] += 1
                        st.toast("已記錄你的興趣！")
                        st.rerun()
                    
                    # --- 終極防護機制 (防止 TypeError) ---
                    raw_url = ev.get("pdf_url", "")
                    is_valid_url = isinstance(raw_url, str) and raw_url.lower().startswith(("http://", "https://")) and len(raw_url) > 10
                    
                    if is_valid_url:
                        try:
                            st.link_button("📄 下載報名表", raw_url, key=f"lnk_{e_id}_{idx}")
                        except Exception:
                            st.button("📄 連結格式錯誤", disabled=True, key=f"err_{e_id}_{idx}")
                    else:
                        st.button("📄 無報名表", disabled=True, key=f"none_{e_id}_{idx}", help="尚未提供有效網址")
                    
                    if st.session_state.is_admin:
                        if st.button("🗑️ 刪除活動", key=f"del_btn_{e_id}", type="primary"):
                            st.session_state.events_list.pop(idx)
                            st.rerun()

# --- 2. 訓練班日程表 ---
elif menu == "📅 訓練班日程表":
    st.title("📅 2025-26 年度訓練班日程")
    if st.session_state.is_admin:
        st.info("💡 修改「具體日期」後請點擊「💾 儲存日程」。各日期請以逗號分隔。")
        edited_schedule = st.data_editor(st.session_state.schedule_df, num_rows="dynamic", use_container_width=True, key="sched_editor")
        
        c1, c2 = st.columns([1, 5])
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
        # 非管理員隱藏「具體日期」欄位以保持簡潔
        st.dataframe(st.session_state.schedule_df.drop(columns=["具體日期"]), use_container_width=True)

# --- 3. 隊員排行榜 ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 壁球隊員積分排行榜")
    if not st.session_state.players_df.empty:
        rank_df = st.session_state.players_df.sort_values("積分", ascending=False).reset_index(drop=True)
        rank_df.index += 1
        st.table(rank_df[["姓名", "積分"]])
    
    if st.session_state.is_admin:
        st.divider()
        st.subheader("✍️ 快速編輯積分")
        new_players = st.data_editor(st.session_state.players_df, num_rows="dynamic", use_container_width=True, key="player_editor")
        if st.button("💾 儲存積分"):
            st.session_state.players_df = new_players
            st.success("更新成功")
            st.rerun()

# --- 4. 點名與統計 ---
elif menu == "📝 點名與統計":
    st.title("📝 班級點名紀錄")
    class_list = st.session_state.schedule_df["班級"].tolist()
    
    if class_list:
        sel_class = st.selectbox("請選擇班級：", class_list)
        
        # 取得選定班級的詳細資訊
        class_info = st.session_state.schedule_df[st.session_state.schedule_df["班級"] == sel_class].iloc[0]
        num_lessons = int(class_info["堂數"])
        dates_str = str(class_info.get("具體日期", ""))
        date_items = [d.strip() for d in dates_str.split(",") if d.strip()]
        
        # 建立列名映射 (T1 -> 實際日期)
        col_map = {f"T{i}": (date_items[i-1] if i <= len(date_items) else f"第{i}堂") for i in range(1, num_lessons + 1)}
        
        # 過濾點名數據
        att_df = st.session_state.attendance_data[st.session_state.attendance_data["班級"] == sel_class].copy()
        
        # 補足缺失的堂數欄位
        for i in range(1, num_lessons + 1):
            col_name = f"T{i}"
            if col_name not in att_df.columns:
                att_df[col_name] = False
        
        # 整理要顯示的欄位
        display_cols = ["姓名", "年級"] + [f"T{i}" for i in range(1, num_lessons + 1)]
        # 排除數據中不存在的欄位防止報錯
        actual_cols = [c for c in display_cols if c in att_df.columns]
        
        final_df = att_df[actual_cols].rename(columns=col_map)
        
        if st.session_state.is_admin:
            st.info(f"💡 正在編輯：{sel_class}。你可以直接新增行來加入新隊員。")
            # 使用 CheckboxColumn 讓介面更好看
            column_config = {v: st.column_config.CheckboxColumn(v) for v in col_map.values()}
            
            edited_att = st.data_editor(
                final_df, 
                column_config=column_config,
                use_container_width=True, 
                num_rows="dynamic",
                key=f"att_editor_{sel_class}"
            )
            
            if st.button("💾 儲存點名紀錄"):
                # 反向映射回 T1, T2 格式儲存
                rev_map = {v: k for k, v in col_map.items()}
                to_save = edited_att.rename(columns=rev_map)
                to_save["班級"] = sel_class
                
                # 更新全局 session_state
                st.session_state.attendance_data = pd.concat([
                    st.session_state.attendance_data[st.session_state.attendance_data["班級"] != sel_class],
                    to_save
                ], ignore_index=True).fillna(False)
                
                st.success(f"已儲存 {sel_class} 的點名資料")
                st.rerun()
        else:
            st.dataframe(final_df, use_container_width=True)
    else:
        st.warning("請先在「日程表」中建立班級。")

# --- 5. 學費預算計算 ---
elif menu == "💰 學費預算計算 (管理專用)":
    st.title("💰 下期預算核算工具")
    st.info("💡 根據您的要求，此計算工具直接以「班級總成本」進行估算，無需輸入堂數。")
    
    c1, c2, c3 = st.columns(3)
    cost_team = c1.number_input("校隊班 總成本 (單班)", 30250, help="教練費總計")
    cost_train = c2.number_input("培訓班 總成本 (單班)", 13500)
    cost_hobby = c3.number_input("興趣班 總成本 (單班)", 9600)
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("校隊類別")
        n_t = st.number_input("開班數量", 1, key="n_t")
        p_t = st.number_input("預計總人數", 12, key="p_t")
    with col2:
        st.subheader("培訓類別")
        n_tr = st.number_input("開班數量", 4, key="n_tr")
        p_tr = st.number_input("預計總人數", 48, key="p_tr")
    with col3:
        st.subheader("興趣類別")
        n_h = st.number_input("開班數量", 5, key="n_h")
        p_h = st.number_input("預計總人數", 75, key="p_h")
    
    st.divider()
    fee = st.number_input("每位學生預計收費 ($)", 250)
    
    # 計算邏輯
    total_cost = (n_t * cost_team) + (n_tr * cost_train) + (n_h * cost_hobby)
    total_income = (p_t + p_tr + p_h) * fee
    balance = total_income - total_cost
    
    m1, m2, m3 = st.columns(3)
    m1.metric("總支出預算", f"${total_cost:,}")
    m2.metric("總收入預算", f"${total_income:,}")
    m3.metric("損益差額", f"${balance:,}", delta=f"{balance:,}"),}")
