from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_apscheduler import APScheduler # スケジュール実行用
from datetime import datetime # 時間管理用
from plyer import notification # PC通知用（補助的）

# --- 設定クラス ---
class Config:
    SCHEDULER_API_ENABLED = True

app = Flask(__name__)
app.config.from_object(Config())

# --- データ保管場所（簡易データベース） ---
# ここにタスクを保存します。
tasks = []
task_id_counter = 1

# スケジューラの初期化（定期実行ツールの起動）
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# --- 定期実行する関数（監視役） ---
# 5秒ごとに実行して、期限切れがないかチェックします
@scheduler.task('interval', id='check_deadlines', seconds=5)
def check_deadlines():
    now = datetime.now()
    
    with app.app_context(): # Flaskのアプリ内で実行
        for task in tasks:
            # 「まだ罰を受けていない」かつ「期限を過ぎている」場合
            if not task['is_punished'] and task['deadline'] and task['deadline'] < now:
                
                # 1. データを更新（執行済みにする）
                task['is_punished'] = True
                task['needs_popup'] = True # ブラウザでポップアップを出すための合図
                
                # 2. PCのデスクトップ通知（念の為の補助通知）
                try:
                    notification.notify(
                        title='💀 社会的死 執行 💀',
                        message=f"仮想ツイートが送信されました。\n罰: {task['penalty_text']}",
                        app_name='Social Guillotine',
                        timeout=10
                    )
                except:
                    pass # Mac/Winの環境差でエラーが出ても止まらないようにする
                
                print(f"【執行】タスク「{task['title']}」が期限切れ。仮想ツイートフラグを立てました。")

# --- ルーティング（画面遷移の設定） ---

@app.route('/')
def index():
    # トップページを表示。タスク一覧を渡す。
    return render_template('index.html', tasks=tasks)

@app.route('/add', methods=['POST'])
def add_task():
    global task_id_counter
    # フォームからデータを受け取る
    title = request.form.get('task_title')
    deadline_str = request.form.get('deadline') 
    penalty_text = request.form.get('penalty_text')

    if title:
        # 日付文字列をdatetimeオブジェクトに変換
        deadline_dt = None
        if deadline_str:
            try:
                deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass 

        # 新しいタスクを作成
        new_task = {
            'id': task_id_counter,
            'title': title,
            'deadline': deadline_dt,       
            'penalty_text': penalty_text,  
            'is_punished': False,          # 期限切れか？
            'needs_popup': False           # フロントエンドで演出を表示すべきか？
        }
        tasks.append(new_task)
        task_id_counter += 1
        
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    # タスクを削除（完了）
    # リスト内包表記を使って、指定ID以外のタスクだけを残す
    global tasks
    tasks = [task for task in tasks if task['id'] != task_id]
    return redirect(url_for('index'))

# --- 【重要】フロントエンドからのポーリング用API ---
# ブラウザが「何か爆発したタスクある？」と定期的に聞きに来る場所
@app.route('/check_punishments')
def check_punishments():
    punished_tasks = []
    for task in tasks:
        # ポップアップ表示が必要なタスクを探す
        if task.get('needs_popup'):
            punished_tasks.append({
                'title': task['title'],
                'penalty_text': task['penalty_text']
            })
            task['needs_popup'] = False # 一度送ったらフラグを下ろす（何度も出ないように）
    
    # JSON形式でブラウザに返す
    return jsonify(punished_tasks)

if __name__ == '__main__':
    # アプリ起動
    app.run(debug=True, use_reloader=False)