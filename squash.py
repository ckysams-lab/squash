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
        st.error("密碼錯誤，請重新輸入。")

# --- 2. 數據初始化 ---
# 初始化班級單價 (根據 PDF 原始成本估算)
if 'unit_costs' not in st.session_state:
    st.session_state.unit_costs = {
        "校隊訓練班": 2750.0,
        "初/中級/精英訓練班": 1350.0,
        "小型壁球興趣班": 1200.0
    }

# --- 側邊欄導覽 ---
st.sidebar.title("🔐 管理員登入")
if not st.session_state.is_admin:
    st.sidebar.text_input("輸入密碼 (8888)", type="password", key="pwd_input", on_change=check_password)
else:
    if st.sidebar.button("登出管理員"):
        st.session_state.is_admin = False
        st.rerun()

menu = st.sidebar.radio("功能選單", ["1. 學費預算計算", "2. 訓練班日程表", "3. 隊員排行榜", "4. 點名系統", "5. 活動公告"])

# --- 1. 學費預算計算 (分班人數輸入版) ---
if menu == "1. 學費預算計算":
    st.title("💰 下一期通告學費核算")
    
    st.subheader("⚙️ 第一步：設定各類班級的成本單價 (每班總費用)")
    if st.session_state.is_admin:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state.unit_costs["校隊訓練班"] = st.number_input("校隊訓練班 單價", value=st.session_state.unit_costs["校隊訓練班"])
        with c2:
            st.session_state.unit_costs["初/中級/精英訓練班"] = st.number_input("初/中級/精英班 單價", value=st.session_state.unit_costs["初/中級/精英訓練班"])
        with c3:
            st.session_state.unit_costs["小型壁球興趣班"] = st.number_input("興趣班 單價", value=st.session_state.unit_costs["小型壁球興趣班"])
    else:
        st.info("唯讀模式：校隊班 ${} | 訓練班 ${} | 興趣班 ${}".format(
            st.session_state.unit_costs["校隊訓練班"], 
            st.session_state.unit_costs["初/中級/精英訓練班"], 
            st.session_state.unit_costs["小型壁球興趣班"]))

    st.markdown("---")
    
    st.subheader("👥 第二步：輸入各班別的實際/預計報名人數")
    
    col_in1, col_in2, col_in3 = st.columns(3)
    
    with col_in1:
        st.markdown("**校隊系列**")
        n_team_class = st.number_input("校隊訓練班 (班數)", min_value=0, value=1, key="ntc")
        s_team_count = st.number_input("校隊班 總學生人數", min_value=0, value=12, key="stc")
        
    with col_in2:
        st.markdown("**培訓系列**")
        n_train_class = st.number_input("初/中/精英班 (總班數)", min_value=0, value=3, key="ntrc")
        s_train_count = st.number_input("培訓系列 總學生人數", min_value=0, value=36, key="strc")
        
    with col_in3:
        st.markdown("**興趣班系列**")
        n_hobby_class = st.number_input("小型壁球興趣班 (班數)", min_value=0, value=3, key="nhc")
        s_hobby_count = st.number_input("興趣班 總學生人數", min_value=0, value=48, key="shc")

    st.markdown("---")
    st.subheader("📊 第三步：核算與津貼分析")
    
    # 通告統一收費
    notice_price = st.number_input("通告擬定每位學生收費 ($)", value=250)

    # 計算各組別成本
    cost_team = n_team_class * st.session_state.unit_costs["校隊訓練班"]
    cost_train = n_train_class * st.session_state.unit_costs["初/中級/精英訓練班"]
    cost_hobby = n_hobby_class * st.session_state.unit_costs["小型壁球興趣班"]
    
    total_cost = cost_team + cost_train + cost_hobby
    total_students = s_team_count + s_train_count + s_hobby_count
    
    if total_students > 0:
        raw_fee_avg = total_cost / total_students
        total_income = total_students * notice_price
        total_subsidy = total_cost - total_income
        
        m1, m2, m3 = st.columns(3)
        m1.metric("總開支成本", f"${total_cost:,.0f}")
        m2.metric("平均每人成本", f"${raw_fee_avg:.1f}")
        m3.metric("需資助總總額", f"${max(0, total_subsidy):,.0f}", delta=f"{total_subsidy:.0f}")

        # 詳細分班分析
        st.write("#### 🔍 分組明細分析")
        analysis_data = [
            {"類別": "校隊系列", "總成本": cost_team, "人數": s_team_count, "人均成本": cost_team/s_team_count if s_team_count > 0 else 0},
            {"類別": "培訓系列", "總成本": cost_train, "人數": s_train_count, "人均成本": cost_train/s_train_count if s_train_count > 0 else 0},
            {"類別": "興趣班系列", "總成本": cost_hobby, "人數": s_hobby_count, "人均成本": cost_hobby/s_hobby_count if s_hobby_count > 0 else 0},
        ]
        st.table(pd.DataFrame(analysis_data))
        
        st.info(f"💡 總結：本期共開辦 {n_team_class+n_train_class+n_hobby_class} 班，服務 {total_students} 名學生。")
    else:
        st.warning("請在上方輸入學生人數以進行計算。")

# --- 其他模組保持不變 ---
elif menu == "2. 訓練班日程表":
    st.title("📅 訓練班日程表管理")
    # ... (保持之前的代碼)
