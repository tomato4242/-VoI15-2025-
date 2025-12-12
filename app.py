# --- モジュールのインポート ---
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_apscheduler import APScheduler
from datetime import datetime
import random
import os
from dotenv import load_dotenv

# ★ GoogleのAIライブラリをインポート
import google.generativeai as genai

# --- 初期設定 ---
load_dotenv()
app = Flask(__name__)
app.secret_key = 'social-guillotine-secret-key'

# ★ Google Gemini APIキーを設定
#   genai.configure() を使って設定します
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception as e:
    print(f"【APIキー設定エラー】: {e}")


# --- データ保管場所（簡易データベース） ---
tasks = []
task_id_counter = 1


# --- バックアップの褒め言葉生成関数（変更なし） ---
def generate_backup_praise_message():
    messages = [
        "素晴らしい！完璧な仕事ぶりですね！", "やりましたね！この調子でいきましょう！",
        "見事です！あなたは怠惰とは無縁ですね。", "お疲れ様でした。早期完了、さすがです！"
    ]
    return random.choice(messages)

# ★★★★★ ここからがGoogle Geminiを呼び出す機能です ★★★★★
def generate_praise_with_ai(task_title):
    """Google Gemini APIを使用してタスク完了の褒め言葉を生成"""
    try:
        model = genai.GenerativeModel('"gemini-3-pro-preview"')
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

# ★★★★★ ここまでがAI関連の機能です ★★★★★


# --- /delete ルート（変更なし） ---
@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    global tasks
    task_to_delete = next((task for task in tasks if task['id'] == task_id), None)
    
    if task_to_delete:
        if task_to_delete['deadline'] and task_to_delete['deadline'] > datetime.now():
            task_title = task_to_delete.get('title', '素晴らしいタスク')
            
            # ★ この関数の中身がGoogle Gemini用に変わっています
            message = generate_praise_with_ai(task_title)
            
            flash(message, 'success')
            print(f"【早期完了】Google AIからのメッセージ: {message}")

    tasks = [task for task in tasks if task['id'] != task_id]
    return redirect(url_for('index'))

# --- 他のルーティングやスケジューラ、アプリ起動のコード ---
# (中略：変更なし)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

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
    punished_tasks = []
    for task in tasks:
        if task.get('needs_popup'):
            punished_tasks.append({
                'title': task['title'],
                'penalty_text': task['penalty_text']
            })
            task['needs_popup'] = False
    return jsonify(punished_tasks)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)