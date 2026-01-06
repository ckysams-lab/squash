import streamlit as st
import pandas as pd

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide")

# --- 1. 安全權限設置 ---
ADMIN_PASSWORD = "8888"
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

def check_password():
    if st.session_state.get("pwd_input") == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理員權限已解鎖！")
    else:
        if st.session_state.get("pwd_input"):
            st.error("密碼錯誤，請重新輸入。")

# --- 2. 數據初始化 ---
# 初始化班級單價 (依據 PDF 原始成本單價)
if 'unit_costs' not in st.session_state:
    st.session_state.unit_costs = {
        "校隊班": 2750.0,
        "培訓班": 1350.0,
        "興趣班": 1200.0
    }

# --- 側邊欄 ---
st.sidebar.title("🔐 管理員登入")
if not st.session_state.is_admin:
    st.sidebar.text_input("輸入密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    if st.sidebar.button("登出管理員"):
        st.session_state.is_admin = False
        st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("功能選單", ["1. 學費預算計算", "2. 訓練班日程表", "3. 隊員排行榜", "4. 點名系統", "5. 活動公告"])

# --- 1. 學費預算計算 (修正公式版) ---
if menu == "1. 學費預算計算":
    st.title("💰 下一期通告學費核算")
    
    # 步驟一：設定單價
    st.subheader("⚙️ 第一步：設定各類班別成本單價 (每班總價)")
    if st.session_state.is_admin:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state.unit_costs["校隊班"] = st.number_input("校隊班 單價 ($)", value=st.session_state.unit_costs["校隊班"])
        with c2:
            st.session_state.unit_costs["培訓班"] = st.number_input("初/中/精英班 單價 ($)", value=st.session_state.unit_costs["培訓班"])
        with c3:
            st.session_state.unit_costs["興趣班"] = st.number_input("小型壁球興趣班 單價 ($)", value=st.session_state.unit_costs["興趣班"])
    else:
        st.info(f"當前設定：校隊班 ${st.session_state.unit_costs['校隊班']} | 培訓班 ${st.session_state.unit_costs['培訓班']} | 興趣班 ${st.session_state.unit_costs['興趣班']}")

    st.markdown("---")
    
    # 步驟二：輸入具體報名情況
    st.subheader("👥 第二步：分別輸入報名班數及人數")
    col_in1, col_in2, col_in3 = st.columns(3)
    
    with col_in1:
        st.markdown("**【校隊系列】**")
        n_team = st.number_input("校隊班 開辦班數", min_value=0, value=1, key="n_t")
        s_team = st.number_input("校隊班 報名總人數", min_value=0, value=12, key="s_t")
        
    with col_in2:
        st.markdown("**【培訓系列】**")
        n_train = st.number_input("初/中/精英班 開辦班數", min_value=0, value=4, key="n_tr")
        s_train = st.number_input("培訓系列 報名總人數", min_value=0, value=48, key="s_tr")
        
    with col_in3:
        st.markdown("**【興趣班系列】**")
        n_hobby = st.number_input("小型壁球興趣班 開辦班數", min_value=0, value=3, key="n_h")
        s_hobby = st.number_input("興趣班 報名總人數", min_value=0, value=48, key="s_h")

    st.markdown("---")
    
    # 步驟三：執行公式計算
    st.subheader("📊 第三步：按總人數平均核算結果")
    notice_fee = st.number_input("通告擬定每位學生收費 ($)", value=250)
    
    # 計算總開支
    total_cost = (n_team * st.session_state.unit_costs["校隊班"]) + \
                 (n_train * st.session_state.unit_costs["培訓班"]) + \
                 (n_hobby * st.session_state.unit_costs["興趣班"])
                 
    # 計算總人數
    total_students = s_team + s_train + s_hobby
    
    if total_students > 0:
        # 核心公式：三類總價 / 所有參加人數
        avg_cost_per_student = total_cost / total_students
        total_income = total_students * notice_fee
        subsidy_needed = total_cost - total_income
        
        # 顯示大指標
        m1, m2, m3 = st.columns(3)
        m1.metric("三類班別總成本", f"${total_cost:,.0f}")
        m2.metric("全校平均每人成本", f"${avg_cost_per_student:.1f}")
        m3.metric("總計需資助額 (全方位津貼)", f"${max(0, subsidy_needed):,.0f}", delta=f"-${subsidy_needed:,.0f}" if subsidy_needed > 0 else None)
        
        # 公式解析
        st.info(f"**計算公式解析：**\n\n"
                f"($ {n_team}班×{st.session_state.unit_costs['校隊班']} + "
                f"{n_train}班×{st.session_state.unit_costs['培訓班']} + "
                f"{n_hobby}班×{st.session_state.unit_costs['興趣班']} $) "
                f"÷ **{total_students}位學生** = **平均成本 ${avg_cost_per_student:.1f}**")
        
        if subsidy_needed > 0:
            st.success(f"💡 每位學生實際獲得資助：${avg_cost_per_student - notice_fee:.1f} 元")
    else:
        st.warning("請在上方輸入學生人數以計算平均成本。")

# --- 其他功能模組 (省略以保持焦點，邏輯與前版一致) ---
elif menu == "2. 訓練班日程表":
    st.title("📅 訓練班日程表")
    st.write("此處顯示訓練日期，管理員可進入修改。")
    # ... 原有代碼 ...
