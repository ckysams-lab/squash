import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import time
import json
import streamlit.components.v1 as components

# ==========================================
# 1. 核心環境配置與安全性檢查
# ==========================================
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth, initialize_app, get_app
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# 頁面配置：強制使用寬屏模式，設置專業圖標
st.set_page_config(
    page_title="正覺壁球管理系統 - 全功能專業版", 
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="🏸"
)

# 定義系統常量
APP_ID = "squash-management-v1"
VERSION = "1.9.8"
LAST_UPDATE = "2026-01-09"

# 章別與獎勵機制配置
BADGE_CONFIG = {
    "白金章": {"min": 400, "icon": "💎", "color": "#e5e7eb", "desc": "卓越領袖級別"},
    "金章": {"min": 200, "icon": "🥇", "color": "#fbbf24", "desc": "精英核心成員"},
    "銀章": {"min": 100, "icon": "🥈", "color": "#94a3b8", "desc": "進階技術學員"},
    "銅章": {"min": 50, "icon": "🥉", "color": "#b45309", "desc": "潛力訓練學員"},
    "無": {"min": 0, "icon": "⚪", "color": "#f3f4f6", "desc": "新晉入隊學員"}
}

# ==========================================
# 2. Firebase 雲端連接引擎 (核心邏輯)
# ==========================================
def init_firebase_service():
    """建立安全雲端連接，實施單例模式防止重複初始化"""
    if not HAS_FIREBASE:
        st.sidebar.warning("⚠️ 檢測到環境缺少 Firebase 組件，已切換至本地快取模式。")
        return None
    
    if 'firebase_instance' not in st.session_state:
        try:
            try:
                # 嘗試連結現有應用
                app_inst = get_app()
            except ValueError:
                # 解析並修正加密私鑰
                if "firebase_config" in st.secrets:
                    cfg = dict(st.secrets["firebase_config"])
                    if "private_key" in cfg:
                        cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")
                    cred = credentials.Certificate(cfg)
                    app_inst = initialize_app(cred)
                else:
                    return None
            
            st.session_state.firebase_db = firestore.client()
            st.session_state.firebase_instance = True
            st.toast("🌐 雲端數據同步已激活")
        except Exception as err:
            st.error(f"❌ 雲端連接關鍵錯誤: {str(err)}")
            return None
    return st.session_state.get('firebase_db')

# 初始化客戶端
db = init_firebase_service()

# ==========================================
# 3. 數據存取與同步抽象層
# ==========================================
def fetch_cloud_dataframe(collection_id, default_schema):
    """
    從路徑 /artifacts/{appId}/public/data/{collection} 獲取數據。
    包含自動清洗與類型檢查邏輯。
    """
    storage_id = f"local_cache_{collection_id}"
    
    if db:
        try:
            # 構建 Firestore 查詢路徑
            ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection(collection_id)
            docs = ref.stream()
            raw_data = [d.to_dict() for d in docs]
            
            if raw_data:
                df_res = pd.DataFrame(raw_data)
                # 欄位規範化處理
                df_res.columns = [str(col).strip() for col in df_res.columns]
                # 確保數值欄位正確解析
                if '積分' in df_res.columns:
                    df_res['積分'] = pd.to_numeric(df_res['積分'], errors='coerce').fillna(0)
                
                st.session_state[storage_id] = df_res
                return df_res
        except Exception as e:
            st.warning(f"雲端讀取異常 ({collection_id}): {e}")
    
    # 失敗時的回退邏輯
    if storage_id in st.session_state:
        return st.session_state[storage_id]
    
    return pd.DataFrame(default_schema)

def commit_to_cloud(collection_id, df):
    """
    將 DataFrame 完整寫入雲端。
    實現邏輯：先清空舊文檔，再寫入新條目，確保數據一致性。
    """
    if df is None:
        return
    
    # 清理無效行與轉換欄位
    df_clean = df.dropna(how='all')
    df_clean.columns = [str(c).strip() for c in df_clean.columns]
    
    # 更新本地狀態
    st.session_state[f"local_cache_{collection_id}"] = df_clean
    
    if db:
        try:
            coll_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection(collection_id)
            
            # 刪除既有內容
            current_docs = coll_ref.stream()
            for d in current_docs:
                d.reference.delete()
            
            # 批次寫入新數據
            for i, row in df_clean.iterrows():
                # 生成唯一且穩定的文檔 ID
                if collection_id == 'rankings':
                    uid = f"{row.get('班級','NA')}_{row.get('姓名','USER')}_{i}"
                elif collection_id == 'attendance':
                    uid = f"{row.get('班級','NA')}_{row.get('日期','0000')}"
                else:
                    uid = f"entry_{int(time.time())}_{i}"
                
                # 格式化數據
                record = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
                coll_ref.document(uid).set(record)
            
            st.toast(f"✅ {collection_id} 數據同步成功")
        except Exception as e:
            st.error(f"⚠️ 同步至雲端時發生錯誤: {e}")

# ==========================================
# 4. 業務邏輯與計算引擎
# ==========================================
def get_badge_info(points):
    """根據分數返回完整的章別資訊對象"""
    try:
        p = float(points)
    except:
        return BADGE_CONFIG["無"]
    
    for key, val in BADGE_CONFIG.items():
        if key != "無" and p >= val["min"]:
            return val
    return BADGE_CONFIG["無"]

def auto_update_badges(df):
    """批量更新數據框中的章別標籤"""
    if '積分' in df.columns:
        df['章別'] = df['積分'].apply(lambda x: [k for k, v in BADGE_CONFIG.items() if (k != "無" and float(x) >= v["min"]) or k == "無"][0])
    return df

# ==========================================
# 5. 身份驗證機制 (不刪減完整版)
# ==========================================
if 'user_session' not in st.session_state:
    st.session_state.user_session = {"logged": False, "role": "visitor", "user_id": "", "login_time": None}

def perform_logout():
    st.session_state.user_session = {"logged": False, "role": "visitor", "user_id": "", "login_time": None}
    st.rerun()

# 側邊欄 UI 佈局
st.sidebar.markdown(f"### 🏸 正覺壁球管理系統 `v{VERSION}`")
st.sidebar.markdown(f"🗓️ 最後更新: {LAST_UPDATE}")
st.sidebar.divider()

if not st.session_state.user_session["logged"]:
    st.sidebar.subheader("🔑 系統登入")
    mode = st.sidebar.segmented_control("身份切換", ["學生查詢", "後台管理"], default="學生查詢")
    
    if mode == "後台管理":
        pwd = st.sidebar.text_input("輸入授權密碼", type="password")
        if st.sidebar.button("進入後台", use_container_width=True):
            if pwd == "8888":  # 此處可擴展為從 secrets 或 db 讀取
                st.session_state.user_session = {
                    "logged": True, 
                    "role": "admin", 
                    "user_id": "ADMIN_CENTER",
                    "login_time": datetime.now()
                }
                st.rerun()
            else:
                st.sidebar.error("密碼錯誤，請重新輸入。")
    else:
        st.sidebar.info("請輸入學員資料進行登入")
        st_c = st.sidebar.text_input("班別 (如: 5A)")
        st_n = st.sidebar.text_input("學號 (如: 12)")
        if st.sidebar.button("登入並查詢", use_container_width=True):
            if st_c and st_n:
                uid = f"{st_c.upper()}_{st_n.zfill(2)}"
                st.session_state.user_session = {
                    "logged": True, 
                    "role": "student", 
                    "user_id": uid,
                    "login_time": datetime.now()
                }
                st.rerun()
            else:
                st.sidebar.warning("班別或學號不可為空！")
    st.info("💡 請在左側面板完成驗證以開啟所有模組。")
    st.stop()

# 登入成功狀態欄
with st.sidebar:
    st.success(f"✅ 已登入: {st.session_state.user_session['user_id']}")
    if st.button("🚪 安全登出系統", use_container_width=True):
        perform_logout()

# ==========================================
# 6. 初始化載入數據集
# ==========================================
df_rankings = fetch_cloud_dataframe('rankings', {"年級":[], "班級":[], "姓名":[], "積分":[], "章別":[]})
df_schedules = fetch_cloud_dataframe('schedules', {"班級":[], "日期":[], "時間":[], "地點":[], "教練":[]})
df_attendance = fetch_cloud_dataframe('attendance', {"班級":[], "日期":[], "出席名單":[], "出席人數":[], "記錄人":[]})
df_awards = fetch_cloud_dataframe('awards', {"學生姓名":[], "比賽名稱":[], "獎項":[], "日期":[], "級別":[]})
df_news = fetch_cloud_dataframe('news', {"標題":[], "公告內容":[], "發布日期":[], "緊急度":[]})
df_tournaments = fetch_cloud_dataframe('tournaments', {"賽事名稱":[], "截止日期":[], "報名連結":[], "備註":[]})

# 功能主導航
menus = [
    "📅 訓練日程表", 
    "🏆 隊員排行榜", 
    "🤖 AI 動作深度分析", 
    "📝 考勤點名中心", 
    "🎖️ 學生得獎紀錄", 
    "📢 隊內最新公告", 
    "⚡ 比賽報名與賽程"
]
if st.session_state.user_session["role"] == "admin":
    menus.append("📊 營運預算核算")

selected_menu = st.sidebar.radio("📌 功能選擇", menus)

# ==========================================
# 7. 模組功能：訓練日程表
# ==========================================
if selected_menu == "📅 訓練日程表":
    st.title("📅 訓練日程管理")
    st.markdown("---")
    
    if st.session_state.user_session["role"] == "admin":
        with st.expander("📤 上傳新日程 (Excel/CSV)"):
            up_file = st.file_uploader("選擇日程表檔案", type=["xlsx", "csv"])
            if up_file:
                try:
                    if up_file.name.endswith('.xlsx'):
                        new_sched = pd.read_excel(up_file)
                    else:
                        new_sched = pd.read_csv(up_file)
                    st.write("預覽解析結果：")
                    st.dataframe(new_sched.head())
                    if st.button("🔥 全量覆蓋雲端日程"):
                        commit_to_cloud('schedules', new_sched)
                        st.success("日程數據已更新！")
                        st.rerun()
                except Exception as e:
                    st.error(f"讀取檔案失敗: {e}")
                    
    # 顯示日程
    if not df_schedules.empty:
        st.subheader("🗓️ 當期訓練安排")
        st.dataframe(df_schedules, use_container_width=True, hide_index=True)
    else:
        st.info("目前尚無訓練日程安排，請聯繫教練。")

# ==========================================
# 8. 模組功能：積分排行榜 (完整版)
# ==========================================
elif selected_menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分排行榜")
    st.markdown("---")
    
    if st.session_state.user_session["role"] == "admin":
        st.subheader("⚙️ 積分數據編輯後台")
        # 實施管理員數據編輯
        df_rankings['積分'] = pd.to_numeric(df_rankings['積分'], errors='coerce').fillna(0)
        edited_df = st.data_editor(
            df_rankings, 
            num_rows="dynamic", 
            use_container_width=True,
            key="ranking_editor"
        )
        
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("💾 儲存排行榜修改", use_container_width=True):
            # 存檔前重新計算章別
            edited_df['章別'] = edited_df['積分'].apply(lambda x: get_badge_info(x)['icon'] + " " + [k for k,v in BADGE_CONFIG.items() if (k!="無" and float(x)>=v["min"]) or k=="無"][0])
            commit_to_cloud('rankings', edited_df)
            st.rerun()
            
        if col_s2.button("🧹 清除全部紀錄 (慎用)", use_container_width=True):
            if st.checkbox("確認刪除所有積分紀錄？"):
                commit_to_cloud('rankings', pd.DataFrame(columns=["年級", "班級", "姓名", "積分", "章別"]))
                st.rerun()

    # 排行榜可視化
    st.subheader("🔥 榮譽排行")
    if not df_rankings.empty:
        df_display = df_rankings.sort_values(by="積分", ascending=False).reset_index(drop=True)
        
        # 繪製前三名獎牌
        top_cols = st.columns(3)
        for i in range(min(3, len(df_display))):
            with top_cols[i]:
                row = df_display.iloc[i]
                medals = ["🥇", "🥈", "🥉"]
                st.markdown(f"""
                <div style="background:#f8fafc; padding:20px; border-radius:15px; border:2px solid #e2e8f0; text-align:center;">
                    <h2 style="margin:0;">{medals[i]}</h2>
                    <h3 style="margin:5px 0; color:#1e293b;">{row['姓名']}</h3>
                    <p style="color:#64748b; font-size:14px;">{row['班級']}</p>
                    <p style="font-size:24px; font-weight:bold; color:#2563eb;">{int(row['積分'])} pts</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        st.table(df_display)
    else:
        st.info("目前尚無積分紀錄，快去訓練賺取積分吧！")

# ==========================================
# 9. 模組功能：AI 動作分析儀 (JS 注入不刪減)
# ==========================================
elif selected_menu == "🤖 AI 動作深度分析":
    st.title("🤖 AI 動作姿勢深度分析")
    st.markdown("此工具利用 Google MediaPipe 機器學習技術，自動檢測您的引拍角度。")
    
    st.warning("⚠️ 注意：您的影像僅會在本地瀏覽器處理，系統不會將視頻上傳至雲端，確保隱私安全。")
    
    # AI 分析儀 HTML 組件
    ai_html_code = """
    <div style="background:#f1f5f9; padding:30px; border-radius:20px; font-family: sans-serif;">
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js"></script>
        
        <div style="margin-bottom:20px; background:white; padding:15px; border-radius:10px;">
            <label style="font-weight:bold; display:block; margin-bottom:10px;">1. 上傳練習影片 (MP4格式)</label>
            <input type="file" id="ai-video-input" accept="video/*" style="width:100%;">
        </div>
        
        <div style="position:relative; width:100%; border-radius:15px; overflow:hidden; background:#000; display:flex; justify-content:center; align-items:center;">
            <video id="ai-video" controls style="max-width:100%; max-height:500px;"></video>
            <canvas id="ai-canvas" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;"></canvas>
        </div>
        
        <div style="margin-top:25px; display:grid; grid-template-columns: 1fr 2fr; gap:20px;">
            <div style="background:white; border:2px solid #2563eb; padding:20px; border-radius:15px; text-align:center;">
                <p style="margin:0; font-size:14px; color:#64748b;">即時肘部角度</p>
                <h1 id="angle-val" style="font-size:50px; color:#2563eb; margin:10px 0;">0.0°</h1>
            </div>
            <div id="ai-feedback" style="background:#dbeafe; padding:20px; border-radius:15px; display:flex; align-items:center; justify-content:center; font-weight:bold; color:#1e40af; font-size:18px; text-align:center;">
                等待分析中... 請點擊播放。
            </div>
        </div>
    </div>
    
    <script>
        const video = document.getElementById('ai-video');
        const canvas = document.getElementById('ai-canvas');
        const ctx = canvas.getContext('2d');
        const angleDisplay = document.getElementById('angle-val');
        const feedback = document.getElementById('ai-feedback');
        
        const poseObj = new Pose({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`});
        poseObj.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });
        
        poseObj.onResults((results) => {
            if (!results.poseLandmarks) return;
            
            // 修正畫布大小
            canvas.width = video.clientWidth;
            canvas.height = video.clientHeight;
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 繪製骨架與關鍵點
            drawConnectors(ctx, results.poseLandmarks, POSE_CONNECTIONS, {color: '#34d399', lineWidth: 3});
            drawLandmarks(ctx, results.poseLandmarks, {color: '#f87171', radius: 4});
            
            // 獲取 右肩(12), 右肘(14), 右腕(16)
            const s = results.poseLandmarks[12];
            const e = results.poseLandmarks[14];
            const w = results.poseLandmarks[16];
            
            if (s && e && w && e.visibility > 0.5) {
                // 向量角度算法
                const radians = Math.atan2(w.y - e.y, w.x - e.x) - Math.atan2(s.y - e.y, s.x - e.x);
                let angle = Math.abs(radians * 180.0 / Math.PI);
                if (angle > 180.0) angle = 360.0 - angle;
                
                angleDisplay.innerText = angle.toFixed(1) + "°";
                
                // 動態分析邏輯
                if (angle < 95) {
                    feedback.innerText = "❌ 引拍幅度過小：請將球拍向後拉，增加擊球蓄力。";
                    feedback.style.background = "#fee2e2"; feedback.style.color = "#991b1b";
                } else if (angle > 150) {
                    feedback.innerText = "✅ 揮拍姿勢完美：引拍非常飽滿，發力極佳！";
                    feedback.style.background = "#dcfce7"; feedback.style.color = "#166534";
                } else {
                    feedback.innerText = "🆗 姿勢良好：請保持揮拍的流暢度與穩定性。";
                    feedback.style.background = "#dbeafe"; feedback.style.color = "#1e40af";
                }
            }
        });

        document.getElementById('ai-video-input').onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                video.src = URL.createObjectURL(file);
                video.load();
                video.play();
            }
        };

        async function loop() {
            if (!video.paused && !video.ended) {
                await poseObj.send({image: video});
            }
            requestAnimationFrame(loop);
        }
        video.onplay = loop;
    </script>
    """
    components.html(ai_html_code, height=850)

# ==========================================
# 10. 模組功能：考勤點名中心
# ==========================================
elif selected_menu == "📝 考勤點名中心":
    st.title("📝 考勤與訓練記錄中心")
    
    c_l, c_r = st.columns(2)
    classes = df_schedules["班級"].unique() if not df_schedules.empty else ["無班級數據"]
    target_c = c_l.selectbox("選擇班級", classes)
    target_d = c_r.date_input("點名日期", datetime.now())
    
    st.divider()
    
    st.subheader("🖋️ 點名作業")
    st.info("💡 請輸入出席學員姓名，系統會自動統計人數。")
    input_names = st.text_area("出席名單 (可用空格、逗號或換行分隔)", height=150)
    
    if st.button("🚀 提交點名紀錄並上傳雲端", use_container_width=True):
        processed = [n.strip() for n in input_names.replace('\n', ',').replace(' ', ',').split(',') if n.strip()]
        if not processed:
            st.error("請輸入至少一名學員名單。")
        else:
            new_record = {
                "班級": target_c,
                "日期": str(target_d),
                "出席名單": ", ".join(processed),
                "出席人數": len(processed),
                "記錄人": st.session_state.user_session["user_id"]
            }
            df_attendance = pd.concat([df_attendance, pd.DataFrame([new_record])], ignore_index=True)
            commit_to_cloud('attendance', df_attendance)
            st.success("考勤紀錄已成功保存！")
            
    st.subheader("📜 歷史點名紀錄")
    st.dataframe(df_attendance, use_container_width=True)

# ==========================================
# 11. 模組功能：營運預算核算 (管理員專屬)
# ==========================================
elif selected_menu == "📊 營運預算核算":
    st.title("📊 隊伍營運與財務估算後台")
    st.markdown("---")
    
    with st.container():
        st.subheader("📥 收入參數設定")
        sc1, sc2 = st.columns(2)
        total_s = sc1.number_input("該期總學員人數", min_value=1, value=50)
        fee_p = sc2.number_input("每人收費預算 ($)", min_value=0, value=250)
        
        st.subheader("📤 支出開支預計")
        k1, k2, k3 = st.columns(3)
        n_t = k1.number_input("校隊訓練班數 ($2750/班)", value=1)
        n_m = k2.number_input("中級/初級訓練班 ($1350/班)", value=3)
        n_h = k3.number_input("興趣班班數 ($1200/班)", value=4)
        
    st.divider()
    
    # 計算公式
    rev_total = total_s * fee_p
    exp_total = (n_t * 2750) + (n_m * 1350) + (n_h * 1200)
    balance = rev_total - exp_total
    
    st.subheader("📈 結算摘要")
    m1, m2, m3 = st.columns(3)
    m1.metric("預計總收入", f"${rev_total:,}")
    m2.metric("預計總開支", f"${exp_total:,}")
    m3.metric("預算盈餘/虧損", f"${balance:,}", delta=f"{balance}")
    
    # 財務視覺化
    chart_data = pd.DataFrame({
        "分類": ["學費收入", "運營開支", "盈餘"],
        "金額": [rev_total, exp_total, balance]
    })
    st.bar_chart(chart_data, x="分類", y="金額", color="#2563eb")

# ==========================================
# 12. 模組功能：公告欄與比賽報名
# ==========================================
elif selected_menu == "📢 隊內最新公告":
    st.title("📢 隊伍動態與官方公告")
    if st.session_state.user_session["role"] == "admin":
        with st.expander("➕ 發布新公告"):
            with st.form("news_form"):
                nt = st.text_input("公告標題")
                nc = st.text_area("內容細節")
                nl = st.selectbox("緊急度", ["普通", "重要", "置頂"])
                if st.form_submit_button("立即發布"):
                    new_n = {"標題": nt, "公告內容": nc, "發布日期": str(datetime.now().date()), "緊急度": nl}
                    df_news = pd.concat([df_news, pd.DataFrame([new_n])], ignore_index=True)
                    commit_to_cloud('news', df_news)
                    st.rerun()
                    
    # 顯示公告內容
    for idx, row in df_news.iloc[::-1].iterrows():
        st.markdown(f"""
        <div style="background:white; padding:20px; border-radius:10px; border-left: 5px solid {'#ef4444' if row['緊急度']=='置頂' else '#3b82f6'}; margin-bottom:15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h4 style="margin:0;">{row['標題']} <span style="font-size:12px; color:#94a3b8; font-weight:normal;">({row['發布日期']})</span></h4>
            <p style="margin:10px 0; color:#475569;">{row['公告內容']}</p>
        </div>
        """, unsafe_allow_html=True)

elif selected_menu == "⚡ 比賽報名與賽程":
    st.title("⚡ 賽事報名與外部資訊連結")
    if st.session_state.user_session["role"] == "admin":
        edited_tour = st.data_editor(df_tournaments, num_rows="dynamic", use_container_width=True)
        if st.button("💾 更新賽事清單"):
            commit_to_cloud('tournaments', edited_tour)
            st.rerun()
            
    st.dataframe(df_tournaments, use_container_width=True, hide_index=True)

elif selected_menu == "🎖️ 學生得獎紀錄":
    st.title("🎖️ 學生個人與團體榮譽榜")
    if st.session_state.user_session["role"] == "admin":
        with st.form("award_input"):
            st.write("填寫獲獎資訊")
            st_name = st.text_input("獲獎學員姓名")
            st_match = st.text_input("賽事名稱")
            st_award = st.text_input("所得獎項")
            st_date = st.date_input("獲獎日期")
            if st.form_submit_button("新增榮譽"):
                new_a = {"學生姓名": st_name, "比賽名稱": st_match, "獎項": st_award, "日期": str(st_date), "級別": "School"}
                df_awards = pd.concat([df_awards, pd.DataFrame([new_a])], ignore_index=True)
                commit_to_cloud('awards', df_awards)
                st.rerun()
    
    st.table(df_awards)

# ==========================================
# 13. 系統底層日誌與頁尾
# ==========================================
st.sidebar.divider()
st.sidebar.markdown(f"""
<div style='font-size: 11px; color: #94a3b8;'>
    系統運行環境：Python 3.11 / Streamlit / Firebase Cloud<br>
    數據同步引擎：Active<br>
    用戶終端 ID: {st.session_state.user_session['user_id']}
</div>
""", unsafe_allow_html=True)
