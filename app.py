# app.py

# --- モジュールのインポート ---
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_apscheduler import APScheduler
from datetime import datetime
import random
import os
from dotenv import load_dotenv

# ★ GoogleのAIライブラリをインポート
import google.generativeai as genai

# ★ Discord連携用にrequestsをインポート
import requests

# --- 初期設定 ---
load_dotenv()
app = Flask(__name__)
app.secret_key = 'social-guillotine-secret-key'

# ★ Google Gemini APIキーを設定
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception as e:
    print(f"【APIキー設定エラー】: {e}")


# --- データ保管場所（簡易データベース） ---
tasks = []
task_id_counter = 1


# --- バックアップの褒め言葉生成関数 ---
def generate_backup_praise_message():
    messages = [
        "素晴らしい！いい仕事ぶりですね！", "やりましたね！この調子でいきましょう！",
        "えらい！！この調子で頑張っていきましょう", "お疲れ様でした。早期完了、さすがです！"
    ]
    return random.choice(messages)

# --- Google Geminiを呼び出す機能 ---
def generate_praise_with_ai(task_title):
    """Google Gemini APIを使用してタスク完了の褒め言葉を生成"""
    try:
        model = genai.GenerativeModel('gemini-pro') # モデル名を修正（previewなどが不要な場合が多いです）
        prompt = f"""
        あなたは、ユーザーを励ますのが得意な、非常にポジティブなAIアシスタントです。
        ユーザーが完了したタスク「{task_title}」を褒めてください。
        簡潔に、日本語で、絵文字を交えて賞賛の言葉を生成してください。
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Google AI APIエラー: {e}")
        return generate_backup_praise_message()


# --- ★★★ Discord通知機能 (新規追加) ★★★ ---
def send_discord_punishment(task_title, penalty_text):
    """Discord Webhookに制裁メッセージを送信する"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    # URLが設定されていない場合は何もしない
    if not webhook_url:
        print("Discord Webhook URLが設定されていません。")
        return

    # メッセージ内容（埋め込みメッセージ）
    data = {
        "username": "Social Guillotine 執行人",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/260/260226.png", # 任意のアイコン
        "embeds": [
            {
                "title": "☠️ 社会的制裁が執行されました",
                "description": "愚かな人間が、自ら定めた期限を守れませんでした。\nここにその罪と罰を晒します。",
                "color": 15158332, # 赤色 (Decimal Color)
                "fields": [
                    {
                        "name": "破られた誓い（タスク）",
                        "value": f"「{task_title}」",
                        "inline": False
                    },
                    {
                        "name": "執行された罰",
                        "value": f"**{penalty_text}**",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "怠惰は死に値する。"
                }
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            print("Discordへの制裁通知に成功しました。")
        else:
            print(f"Discordへの送信失敗: {response.status_code}")
    except Exception as e:
        print(f"Discord通信エラー: {e}")


# --- ★★★ 期限監視ジョブ (新規追加) ★★★ ---
def check_deadlines():
    """定期的に実行され、期限切れタスクを検出して処理する"""
    global tasks
    now = datetime.now()
    
    # Flaskのコンテキスト内で実行（DB操作などが必要になった場合に備えて）
    with app.app_context():
        for task in tasks:
            # 期限が設定されており、現在時刻を過ぎていて、まだ処刑フラグが立っていない場合
            if task['deadline'] and task['deadline'] < now and not task['is_punished']:
                
                # 1. フラグを更新（二重送信防止）
                task['is_punished'] = True
                task['needs_popup'] = True # フロントエンドでの演出用フラグ
                
                print(f"【期限切れ】タスク: {task['title']}")
                
                # 2. Discordに通知を送信
                send_discord_punishment(task['title'], task['penalty_text'])


# --- /delete ルート ---
@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    global tasks
    task_to_delete = next((task for task in tasks if task['id'] == task_id), None)
    
    if task_to_delete:
        # 期限内でまだ処刑されていない場合のみ褒める
        if task_to_delete['deadline'] and task_to_delete['deadline'] > datetime.now() and not task_to_delete['is_punished']:
            task_title = task_to_delete.get('title', '素晴らしいタスク')
            
            # Google Geminiで褒め言葉生成
            message = generate_praise_with_ai(task_title)
            
            flash(message, 'success')
            print(f"【早期完了】Google AIからのメッセージ: {message}")

    tasks = [task for task in tasks if task['id'] != task_id]
    return redirect(url_for('index'))


# --- スケジューラ設定 ---
scheduler = APScheduler()
scheduler.init_app(app)

# ★ 10秒ごとに check_deadlines を実行するジョブを追加
scheduler.add_job(id='deadline_check_job', func=check_deadlines, trigger='interval', seconds=10)

scheduler.start()


# --- ルーティング ---
@app.route('/')
def index():
    return render_template('index.html', tasks=tasks)

@app.route('/add', methods=['POST'])
def add_task():
    global task_id_counter
    title = request.form.get('task_title')
    deadline_str = request.form.get('deadline') 
    penalty_text = request.form.get('penalty_text')

    if title:
        deadline_dt = None
        if deadline_str:
            try:
                deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass 

        new_task = {
            'id': task_id_counter,
            'title': title,
            'deadline': deadline_dt,       
            'penalty_text': penalty_text,  
            'is_punished': False,
            'needs_popup': False
        }
        tasks.append(new_task)
        task_id_counter += 1
        
    return redirect(url_for('index'))

@app.route('/check_punishments')
def check_punishments():
    """フロントエンドからのポーリング用API"""
    punished_tasks = []
    for task in tasks:
        # サーバー側の監視ジョブ(check_deadlines)によって needs_popup が True になったものを返す
        if task.get('needs_popup'):
            punished_tasks.append({
                'title': task['title'],
                'penalty_text': task['penalty_text']
            })
            # 一度ポップアップ用データを返したらフラグを下ろす（再表示防止）
            task['needs_popup'] = False
    return jsonify(punished_tasks)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)