import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import streamlit.components.v1 as components

# 嘗試匯入 Firebase 套件
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth, initialize_app, get_app
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# 頁面配置
st.set_page_config(page_title="正覺壁球管理系統", layout="wide", initial_sidebar_state="expanded")

# --- 1. Firebase 初始化 ---
def init_firebase():
    """初始化 Firebase 並返回 Firestore Client"""
    if not HAS_FIREBASE:
        return None
    
    if 'firebase_initialized' not in st.session_state:
        try:
            try:
                app = get_app()
            except ValueError:
                if "firebase_config" in st.secrets:
                    key_dict = dict(st.secrets["firebase_config"])
                    if "private_key" in key_dict:
                        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                    cred = credentials.Certificate(key_dict)
                    app = initialize_app(cred)
                else:
                    return None
            
            st.session_state.db = firestore.client()
            st.session_state.firebase_initialized = True
        except Exception as e:
            st.error(f"Firebase 初始化失敗: {e}")
            return None
    return st.session_state.get('db')

db = init_firebase()
app_id = "squash-management-v1"

# --- 2. 身份驗證功能 ---
def get_admin_password():
    """從 Firebase 讀取管理員密碼，若失敗則返回預設值 8888"""
    default_pwd = "8888"
    if st.session_state.get('db') is not None:
        try:
            # 存取路徑遵循 RULE 1
            doc_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection('admin_settings').document('config')
            doc = doc_ref.get()
            if doc.exists:
                return str(doc.to_dict().get('password', default_pwd))
        except Exception:
            pass
    return default_pwd

# --- 3. 數據存取與同步函數 (詳細處理邏輯) ---
def load_cloud_data(collection_name, default_data):
    """
    從雲端載入數據，並進行格式檢查與容錯處理。
    遵循 RULE 2: 不使用複雜查詢，在內存中過濾。
    """
    key = f"cloud_{collection_name}"
    if st.session_state.get('db') is not None:
        try:
            coll_path = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            docs = coll_path.stream()
            data = [doc.to_dict() for doc in docs]
            if data:
                df = pd.DataFrame(data)
                df.columns = [str(c).strip() for c in df.columns]
                
                # 數據清理與補全
                if collection_name == 'attendance_records':
                    required = ["班級", "日期", "出席人數", "出席名單", "記錄人"]
                    for col in required:
                        if col not in df.columns: df[col] = ""
                
                if collection_name == 'rankings':
                    required = ["年級", "班級", "姓名", "積分", "章別"]
                    for col in required:
                        if col not in df.columns: df[col] = "-" if col != "積分" else 0
                
                st.session_state[key] = df
                return df
        except Exception as e:
            print(f"Error loading {collection_name}: {e}")
    
    # 備援：返回 session 或預設
    if key in st.session_state:
        return st.session_state[key]
    
    df_default = pd.DataFrame(default_data)
    st.session_state[key] = df_default
    return df_default

def save_cloud_data(collection_name, df):
    """
    同步本地數據至 Firestore 雲端。
    包含分批處理 logic 以符合 Firestore 限制。
    """
    if df is None: return
    df = df.dropna(how='all')
    df.columns = [str(c).strip() for c in df.columns]
    
    # 更新本地快照
    key = f"cloud_{collection_name}"
    st.session_state[key] = df
    
    if st.session_state.get('db') is not None:
        try:
            coll_ref = st.session_state.db.collection('artifacts').document(app_id).collection('public').document('data').collection(collection_name)
            
            # 1. 批量刪除舊數據 (Firestore 每批上限 500)
            batch = st.session_state.db.batch()
            count = 0
            for doc in coll_ref.stream():
                batch.delete(doc.reference)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = st.session_state.db.batch()
                    count = 0
            batch.commit()
            
            # 2. 寫入新數據
            for _, row in df.iterrows():
                # 決定 Document ID 的生成邏輯
                if collection_name == 'attendance_records':
                    doc_id = f"{row.get('班級', 'Unknown')}_{row.get('日期', 'Unknown')}".replace("/", "-")
                elif collection_name == 'announcements':
                    # 使用日期與標題前綴
                    dt_str = row.get('日期', '2025-01-01')
                    doc_id = f"{dt_str}_{row.get('標題', 'NoTitle')[:10]}"
                elif collection_name == 'tournaments':
                    doc_id = f"tm_{row.get('比賽名稱', 'NoName')}_{row.get('日期', 'NoDate')}"
                elif collection_name == 'student_awards':
                    doc_id = f"award_{row.get('學生姓名')}_{row.get('日期')}_{np.random.randint(1000)}"
                elif '姓名' in row and ('年級' in row or '班級' in row):
                    doc_id = f"{row.get('班級', row.get('年級', 'NA'))}_{row.get('姓名')}"
                else:
                    doc_id = str(np.random.randint(10000000))
                
                # 清洗數據（移除 NaN）
                clean_row = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
                coll_ref.document(doc_id).set(clean_row)
            
            st.toast(f"✅ {collection_name} 已成功同步至雲端")
        except Exception as e:
            st.error(f"同步至雲端失敗: {e}")

# --- 4. 初始化 Session State 變數 ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'user_id' not in st.session_state: st.session_state.user_id = ""

# 積分常量定義
BADGE_AWARDS = {
    "白金章": {"points": 400, "icon": "💎"},
    "金章": {"points": 200, "icon": "🥇"},
    "銀章": {"points": 100, "icon": "🥈"},
    "銅章": {"points": 50, "icon": "🥉"},
    "無": {"points": 0, "icon": ""}
}

# --- 5. 側邊欄與導航介面 ---
st.sidebar.title("🏸 正覺壁球管理系統")

if not st.session_state.logged_in:
    st.sidebar.subheader("🔑 系統登入")
    login_mode = st.sidebar.radio("身份選擇", ["學生/家長", "管理員"])
    
    if login_mode == "管理員":
        pwd = st.sidebar.text_input("管理員密碼", type="password")
        if st.sidebar.button("登入管理系統"):
            admin_pwd = get_admin_password()
            if pwd == admin_pwd:
                st.session_state.logged_in, st.session_state.is_admin, st.session_state.user_id = True, True, "ADMIN"
                st.rerun()
            else:
                st.sidebar.error("密碼錯誤")
    else:
        st.sidebar.info("請輸入班別及學號 (如: 1A 01)")
        sc1, sc2 = st.sidebar.columns(2)
        s_class = sc1.text_input("班別", placeholder="1A")
        s_num = sc2.text_input("學號", placeholder="01")
        if st.sidebar.button("登入系統"):
            if s_class and s_num:
                st.session_state.logged_in, st.session_state.is_admin, st.session_state.user_id = True, False, f"{s_class.upper()}{s_num.zfill(2)}"
                st.rerun()
            else:
                st.sidebar.error("資訊不足")
    st.stop()

# 登入成功後的側邊欄顯示
if st.session_state.is_admin:
    st.sidebar.success(f"🛡️ 管理員已登入")
else:
    st.sidebar.success(f"👤 學生 {st.session_state.user_id} 已登入")

if st.sidebar.button("🔌 登出系統"):
    st.session_state.logged_in = False
    st.session_state.is_admin = False
    st.rerun()

# --- 6. 數據加載流程 ---
schedule_df = load_cloud_data('schedules', [])
class_players_df = load_cloud_data('class_players', [])
rank_df = load_cloud_data('rankings', pd.DataFrame(columns=["年級", "班級", "姓名", "積分", "章別"]))
attendance_records = load_cloud_data('attendance_records', pd.DataFrame(columns=["班級", "日期", "出席人數", "出席名單", "記錄人"]))
announcements_df = load_cloud_data('announcements', pd.DataFrame(columns=["標題", "內容", "日期"]))
tournaments_df = load_cloud_data('tournaments', pd.DataFrame(columns=["比賽名稱", "日期", "截止日期", "連結", "備註"]))
awards_df = load_cloud_data('student_awards', pd.DataFrame(columns=["學生姓名", "比賽名稱", "獎項", "日期", "備註"]))

# 功能選單導航
menu_options = [
    "📅 訓練日程表", 
    "🏆 隊員排行榜", 
    "🤖 AI 智能動作分析", 
    "📝 考勤點名", 
    "🏅 學生得獎紀錄", 
    "📢 活動公告", 
    "🗓️ 比賽報名與賽程"
]
if st.session_state.is_admin:
    menu_options.append("💰 學費與預算核算")
menu = st.sidebar.radio("功能選單", menu_options)

# --- 7. 頁面模組實現 ---

# --- 7.1 AI 智能分析模組 ---
if menu == "🤖 AI 智能動作分析":
    st.title("🤖 AI 動作自動分析儀")
    st.info("💡 指引：上傳訓練影片後，AI 會自動追蹤人體骨骼點並分析手肘揮拍角度。")
    
    ai_component = """
    <div style="background: #f1f5f9; padding: 20px; border-radius: 12px; border: 1px solid #cbd5e1; font-family: system-ui, -apple-system, sans-serif;">
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js"></script>
        
        <div style="margin-bottom: 15px;">
            <label style="font-weight: bold; color: #334155;">1. 上傳訓練影片檔案 (建議長度 < 30秒)</label>
            <input type="file" id="videoUpload" accept="video/*" style="display: block; width: 100%; margin-top: 5px; padding: 8px; border: 1px dashed #64748b; border-radius: 6px;">
        </div>

        <div style="position: relative; background: #000; border-radius: 8px; overflow: hidden; display: flex; justify-content: center; min-height: 400px;">
            <video id="vidSource" controls style="max-width: 100%; height: auto;"></video>
            <canvas id="overlayCanvas" style="position: absolute; top: 0; left: 0; pointer-events: none; width: 100%; height: 100%;"></canvas>
        </div>

        <div style="margin-top: 15px; display: flex; gap: 15px; flex-wrap: wrap;">
            <div style="background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center; min-width: 120px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); flex: 1;">
                <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">手肘揮拍角度</div>
                <div id="angleDisplay" style="font-size: 32px; font-weight: bold; color: #2563eb;">0°</div>
            </div>
            <div id="aiAdvice" style="background: #dbeafe; padding: 15px; border-radius: 8px; flex: 3; border: 1px solid #bfdbfe; font-size: 15px; color: #1e3a8a; display: flex; align-items: center; min-width: 280px;">
                系統準備就緒。請上傳並播放影片，AI 將實時標註關節點並給予姿勢建議。
            </div>
        </div>
    </div>

    <script>
        const video = document.getElementById('vidSource');
        const canvas = document.getElementById('overlayCanvas');
        const ctx = canvas.getContext('2d');
        const angleTxt = document.getElementById('angleDisplay');
        const adviceBox = document.getElementById('aiAdvice');

        // 初始化 MediaPipe Pose
        const pose = new Pose({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`});
        pose.setOptions({ modelComplexity: 1, smoothLandmarks: true, minDetectionConfidence: 0.5, minTrackingConfidence: 0.5 });

        // 角度計算函數
        function calculateAngle(A, B, C) {
            let angle = Math.abs(Math.atan2(C.y - B.y, C.x - B.x) - Math.atan2(A.y - B.y, A.x - B.x)) * 180 / Math.PI;
            if (angle > 180) angle = 360 - angle;
            return angle.toFixed(1);
        }

        pose.onResults((results) => {
            if (!results.poseLandmarks) return;
            
            // 同步 Canvas 尺寸
            if (canvas.width !== video.clientWidth) {
                canvas.width = video.clientWidth;
                canvas.height = video.clientHeight;
            }

            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 繪製骨架
            drawConnectors(ctx, results.poseLandmarks, POSE_CONNECTIONS, {color: '#10b981', lineWidth: 3});
            drawLandmarks(ctx, results.poseLandmarks, {color: '#ef4444', lineWidth: 1, radius: 3});

            // 提取關鍵點 (12:肩, 14:肘, 16:腕)
            const shoulder = results.poseLandmarks[12];
            const elbow = results.poseLandmarks[14];
            const wrist = results.poseLandmarks[16];

            if (shoulder && elbow && wrist && elbow.visibility > 0.6) {
                const angle = calculateAngle(shoulder, elbow, wrist);
                angleTxt.innerText = angle + "°";
                
                // 智能建議邏輯
                if (angle < 80) {
                    adviceBox.innerHTML = "⚠️ <b>姿勢優化建議：</b>收手過於急促。壁球揮拍需要更大幅度的引拍，請嘗試讓手臂向後延伸更多。";
                } else if (angle > 168) {
                    adviceBox.innerHTML = "⚠️ <b>姿勢優化建議：</b>手臂伸得太直了。過直的關節會減少擊球彈性並增加受傷風險，請保持微彎。";
                } else {
                    adviceBox.innerHTML = "✅ <b>AI 評定：</b>揮拍弧度良好。請保持此節奏，專注於擊球點的控制。";
                }
            }
        });

        document.getElementById('videoUpload').onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                video.src = URL.createObjectURL(file);
                video.style.display = 'block';
                video.play();
            }
        };

        async function detect() {
            if (!video.paused && !video.ended) {
                await pose.send({image: video});
            }
            requestAnimationFrame(detect);
        }
        video.onplay = detect;
    </script>
    """
    components.html(ai_component, height=780)

# --- 7.2 訓練日程表 ---
elif menu == "📅 訓練日程表":
    st.title("📅 訓練班日程管理")
    if st.session_state.is_admin:
        with st.expander("📤 管理員：匯入新日程"):
            st.info("請上傳包含「班級、地點、時間、具體日期」等欄位的 Excel 檔案。")
            u_sched = st.file_uploader("選擇 Excel 檔案 (xlsx)", type=["xlsx"])
            if u_sched:
                df_new = pd.read_excel(u_sched)
                st.write("預覽上傳數據：")
                st.dataframe(df_new.head())
                if st.button("🚀 確認覆蓋並更新雲端"):
                    save_cloud_data('schedules', df_new)
                    st.success("日程表已成功覆蓋！")
                    st.rerun()
                    
    if not schedule_df.empty:
        st.subheader("目前日程清單")
        st.dataframe(schedule_df, use_container_width=True)
        
        # 額外的視圖：按班級過濾
        cls_filter = st.multiselect("按班級過濾顯示", schedule_df["班級"].unique())
        if cls_filter:
            st.table(schedule_df[schedule_df["班級"].isin(cls_filter)])
    else:
        st.warning("目前尚無日程數據，管理員可從 Excel 匯入。")

# --- 7.3 隊員排行榜 ---
elif menu == "🏆 隊員排行榜":
    st.title("🏆 正覺壁球隊積分榜")
    st.info("💡 積分獎勵機制：白金(+400), 金(+200), 銀(+100), 銅(+50)。所有新入隊員預設 100 分。")
    
    if st.session_state.is_admin:
        with st.expander("🛠️ 排行榜後台維護系統", expanded=False):
            t1, t2, t3, t4 = st.tabs(["📤 同步球員名單", "🥇 考章獎勵發放", "✏️ 手動積分微調", "📥 導出資料"])
            
            with t1:
                st.write("此功能會將『隊員名單』中尚未出現在排行榜的球員自動加入。")
                if st.button("🔄 開始自動同步"):
                    if not class_players_df.empty:
                        updated_rank = rank_df.copy()
                        new_added = 0
                        for _, p in class_players_df.iterrows():
                            # 判定唯一性：姓名 + 班級
                            mask = (updated_rank["姓名"].astype(str).str.strip() == str(p["姓名"]).strip()) & \
                                   (updated_rank["班級"].astype(str).str.strip() == str(p["班級"]).strip())
                            if not any(mask):
                                new_row = {
                                    "年級": p.get("年級","-"), 
                                    "班級": p["班級"], 
                                    "姓名": p["姓名"], 
                                    "積分": 100, 
                                    "章別": "無"
                                }
                                updated_rank = pd.concat([updated_rank, pd.DataFrame([new_row])], ignore_index=True)
                                new_added += 1
                        save_cloud_data('rankings', updated_rank)
                        st.success(f"同步完畢！成功新增 {new_added} 名新球員至積分榜。")
                        st.rerun()
                    else:
                        st.error("請先在『考勤點名』分頁匯入球員名單！")

            with t2:
                with st.form("award_form"):
                    st.write("### 登記章別獎勵")
                    col_a1, col_a2 = st.columns(2)
                    b_name = col_a1.text_input("獲獎學生姓名")
                    b_class = col_a2.text_input("學生所屬班別")
                    b_type = st.selectbox("獲得章別", ["白金章", "金章", "銀章", "銅章"])
                    if st.form_submit_button("確認發放"):
                        df = rank_df.copy()
                        mask = (df["姓名"].astype(str).str.strip() == b_name.strip()) & (df["班級"].astype(str).str.strip() == b_class.strip())
                        if any(mask):
                            idx = df[mask].index[0]
                            df.at[idx, "章別"] = b_type
                            old_p = pd.to_numeric(df.at[idx, "積分"], errors='coerce') or 0
                            df.at[idx, "積分"] = int(old_p + BADGE_AWARDS[b_type]["points"])
                            save_cloud_data('rankings', df)
                            st.success(f"獎勵已入帳！{b_name} 的積分已更新。")
                            st.rerun()
                        else:
                            st.error("找不到該隊員，請確認姓名與班別輸入是否完全正確。")

            with t3:
                with st.form("manual_adj"):
                    st.write("### 積分手動增減 (例如比賽表現、遲到扣分等)")
                    m_name = st.text_input("球員姓名")
                    m_class = st.text_input("球員班別")
                    m_pts = st.number_input("增減分數 (負數為扣分)", value=0, step=1)
                    m_reason = st.text_input("調整備註")
                    if st.form_submit_button("執行調整"):
                        df = rank_df.copy()
                        mask = (df["姓名"].astype(str).str.strip() == m_name.strip()) & (df["班級"].astype(str).str.strip() == m_class.strip())
                        if any(mask):
                            idx = df[mask].index[0]
                            current_val = pd.to_numeric(df.at[idx, "積分"], errors='coerce') or 0
                            df.at[idx, "積分"] = int(current_val + m_pts)
                            save_cloud_data('rankings', df)
                            st.success(f"已更新 {m_name} 的積分。")
                            st.rerun()
                        else:
                            st.error("找不到該隊員")

            with t4:
                if not rank_df.empty:
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        rank_df.to_excel(writer, index=False)
                    st.download_button("📥 下載全隊積分 Excel 表", buf.getvalue(), "squash_ranking_data.xlsx")

    # 顯示主排行榜
    if not rank_df.empty:
        # 資料預處理
        disp_df = rank_df.copy()
        disp_df["積分"] = pd.to_numeric(disp_df["積分"], errors='coerce').fillna(0).astype(int)
        disp_df = disp_df.sort_values("積分", ascending=False).reset_index(drop=True)
        disp_df.index += 1
        
        # 視覺化展示
        top_3 = disp_df.head(3)
        if not top_3.empty:
            st.write("### 👑 本季三強")
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f"🥇 **{top_3.iloc[0]['姓名']}**\n\n{top_3.iloc[0]['積分']} pts")
            if len(top_3) > 1:
                with c2: st.markdown(f"🥈 **{top_3.iloc[1]['姓名']}**\n\n{top_3.iloc[1]['積分']} pts")
            if len(top_3) > 2:
                with c3: st.markdown(f"🥉 **{top_3.iloc[2]['姓名']}**\n\n{top_3.iloc[2]['積分']} pts")
        
        st.write("### 📊 完整積分列表")
        st.table(disp_df[["年級", "班級", "姓名", "積分", "章別"]])
    else:
        st.info("目前排行榜為空。")

# --- 7.4 考勤點名 ---
elif menu == "📝 考勤點名":
    st.title("📝 考勤點名系統")
    if st.session_state.is_admin:
        with st.expander("👤 學生名單維護"):
            u_p = st.file_uploader("匯入全校球員總名單 (xlsx)", type=["xlsx"])
            if u_p and st.button("確認更新名單"):
                save_cloud_data('class_players', pd.read_excel(u_p))
                st.rerun()

    if schedule_df.empty:
        st.warning("請先於『訓練日程表』匯入班級與日期數據。")
    else:
        c_list = schedule_df["班級"].unique()
        sel_c = st.selectbox("1. 選擇班級", c_list)
        
        dates_raw = schedule_df[schedule_df["班級"]==sel_c]["具體日期"].iloc[0]
        dates_list = [d.strip() for d in str(dates_raw).split(",") if d.strip()]
        sel_d = st.selectbox("2. 選擇訓練日期", dates_list)
        
        curr_players = class_players_df[class_players_df["班級"]==sel_c]
        if not curr_players.empty:
            # 讀取現有紀錄
            exist_rec = attendance_records[(attendance_records["班級"]==sel_c) & (attendance_records["日期"]==sel_d)]
            present_list = exist_rec.iloc[0]["出席名單"].split(", ") if not exist_rec.empty else []
            
            st.subheader(f"📍 點名區域：{sel_c} ({sel_d})")
            st.write(f"當前出席人數：{len(present_list)}")
            
            att_dict = {}
            col_count = 4
            grid = st.columns(col_count)
            for i, name in enumerate(sorted(curr_players["姓名"])):
                with grid[i % col_count]:
                    # 只有管理員可以修改，學生僅能查看
                    is_present = st.checkbox(name, value=(name in present_list), disabled=not st.session_state.is_admin)
                    att_dict[name] = is_present
            
            if st.session_state.is_admin:
                if st.button("💾 儲存點名結果"):
                    final_present = [n for n, v in att_dict.items() if v]
                    new_rec = {
                        "班級": sel_c, 
                        "日期": sel_d, 
                        "出席人數": len(final_present), 
                        "出席名單": ", ".join(final_present), 
                        "記錄人": st.session_state.user_id
                    }
                    # 更新邏輯：先移除舊的再加入新的
                    updated_att = attendance_records.copy()
                    updated_att = updated_att[~((updated_att["班級"]==sel_c) & (updated_att["日期"]==sel_d))]
                    updated_att = pd.concat([updated_att, pd.DataFrame([new_rec])], ignore_index=True)
                    save_cloud_data('attendance_records', updated_att)
                    st.success("考勤資料已同步至雲端。")
                    st.rerun()
        else:
            st.error("名單內找不到該班級的球員，請檢查學生名單是否已正確上傳。")

# --- 7.5 學費與預算核算 (管理員專屬) ---
elif menu == "💰 學費與預算核算":
    st.title("💰 預算與營運核算系統")
    st.write("這是一個基於當前班級配置與收生情況的財務預算模擬工具。")
    
    col_input_left, col_input_right = st.columns(2)
    
    with col_input_left:
        st.subheader("🏫 訓練班規模設定")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            n_team = st.number_input("校隊班數", value=1, step=1)
            p_team = 2750 # 每班支出預算
        with sc2:
            n_train = st.number_input("非校隊班數", value=3, step=1)
            p_train = 1350
        with sc3:
            n_hobby = st.number_input("興趣班數", value=4, step=1)
            p_hobby = 1200
            
    with col_input_right:
        st.subheader("💵 收入設定")
        total_stu = st.number_input("預計收生總人數", value=50, step=1)
        fee_per = st.number_input("每位學生收費 (HKD)", value=250)

    st.divider()
    
    # 計算邏輯
    total_rev = total_stu * fee_per
    total_cost = (n_team * p_team) + (n_train * p_train) + (n_hobby * p_hobby)
    net_profit = total_rev - total_cost
    
    m1, m2, m3 = st.columns(3)
    m1.metric("預期總收入 (學費)", f"${total_rev:,}")
    m2.metric("預期總支出 (教練/場地)", f"${total_cost:,}")
    m3.metric("淨盈餘 (Profit)", f"${net_profit:,}", delta=float(net_profit))
    
    if net_profit < 0:
        st.error("⚠️ 注意：目前預算模型顯示赤字！請考慮調整學費或優化開班數量。")
    else:
        st.success("✅ 財務模型目前處於健康獲利狀態。")
        
    with st.expander("📊 詳細成本拆解"):
        cost_data = {
            "班別": ["校隊訓練班", "非校隊訓練班", "興趣/簡易班", "總計"],
            "數量": [n_team, n_train, n_hobby, n_team+n_train+n_hobby],
            "單班支出": [p_team, p_train, p_hobby, "-"],
            "小計": [n_team*p_team, n_train*p_train, n_hobby*p_hobby, total_cost]
        }
        st.table(pd.DataFrame(cost_data))

# --- 7.6 學生得獎紀錄 ---
elif menu == "🏅 學生得獎紀錄":
    st.title("🏅 校外比賽榮譽榜")
    if st.session_state.is_admin:
        with st.form("award_input", clear_on_submit=True):
            st.write("### 新增得獎紀錄")
            aw_c1, aw_c2 = st.columns(2)
            aw_name = aw_c1.text_input("獲獎學生姓名")
            aw_tourn = aw_c2.text_input("賽事名稱")
            aw_prize = aw_c1.text_input("獲得獎項")
            aw_date = aw_c2.date_input("獲獎日期")
            aw_memo = st.text_input("備註 (選填)")
            if st.form_submit_button("正式發布"):
                new_award = {
                    "學生姓名": aw_name, 
                    "比賽名稱": aw_tourn, 
                    "獎項": aw_prize, 
                    "日期": str(aw_date), 
                    "備註": aw_memo
                }
                save_cloud_data('student_awards', pd.concat([awards_df, pd.DataFrame([new_award])], ignore_index=True))
                st.rerun()
                
    if not awards_df.empty:
        # 按日期降序排列
        disp_awards = awards_df.sort_values("日期", ascending=False)
        st.dataframe(disp_awards, use_container_width=True)
    else:
        st.info("尚無紀錄。")

# --- 7.7 活動公告 ---
elif menu == "📢 活動公告":
    st.title("📢 隊內最新公告")
    if st.session_state.is_admin:
        with st.expander("📝 撰寫新公告", expanded=False):
            with st.form("ann_form"):
                ann_title = st.text_input("公告標題", placeholder="例如：颱風停課通知")
                ann_content = st.text_area("詳細內容")
                if st.form_submit_button("立即發布"):
                    new_ann = {
                        "標題": ann_title, 
                        "內容": ann_content, 
                        "日期": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    save_cloud_data('announcements', pd.concat([announcements_df, pd.DataFrame([new_ann])], ignore_index=True))
                    st.rerun()
                    
    if not announcements_df.empty:
        for _, row in announcements_df.iloc[::-1].iterrows():
            with st.chat_message("user"):
                st.write(f"**【{row['標題']}】**")
                st.caption(f"發佈時間：{row['日期']}")
                st.write(row['內容'])
                st.divider()
    else:
        st.info("目前沒有新的公告。")

# --- 7.8 比賽報名與賽程 ---
elif menu == "🗓️ 比賽報名與賽程":
    st.title("🗓️ 比賽資訊與快捷報名")
    
    if st.session_state.is_admin:
        with st.expander("🆕 發布新比賽資訊"):
            with st.form("tourn_form"):
                t_name = st.text_input("賽事正式名稱")
                t_date = st.text_input("比賽日期 (文字描述或具體日期)")
                t_deadline = st.date_input("報名截止日期")
                t_link = st.text_input("官方報名網址/連結")
                t_note = st.text_area("參賽資格或其他備註")
                if st.form_submit_button("確認新增"):
                    new_t = {
                        "比賽名稱": t_name, 
                        "日期": t_date, 
                        "截止日期": str(t_deadline), 
                        "連結": t_link, 
                        "備註": t_note
                    }
                    save_cloud_data('tournaments', pd.concat([tournaments_df, pd.DataFrame([new_t])], ignore_index=True))
                    st.rerun()

    if not tournaments_df.empty:
        st.write("### 🏆 近期賽事一覽")
        for _, t in tournaments_df.iterrows():
            with st.container(border=True):
                col_t1, col_t2 = st.columns([3, 1])
                with col_t1:
                    st.subheader(t['比賽名稱'])
                    st.write(f"📅 **比賽日期：** {t['日期']}")
                    st.write(f"⏳ **截止報名：** {t['截止日期']}")
                    if t['備註']: st.info(f"💡 {t['備註']}")
                with col_t2:
                    if t['連結']:
                        st.link_button("🔗 立即前往報名", t['連結'], use_container_width=True)
                    else:
                        st.button("尚未開放", disabled=True, use_container_width=True)
    else:
        st.info("目前尚無比賽資訊。")

# 頁尾資訊
st.sidebar.divider()
st.sidebar.caption("© 2026 正覺壁球隊管理系統 | V1.5.0")
