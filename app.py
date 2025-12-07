# sqlite3を操作するためのライブラリを読み込む。
import sqlite3
from flask import Flask, render_template, request, redirect, url_for

# Flaskアプリの本体を作成する。
app = Flask(__name__)

# --- データベース設定 ---
DATABASE = 'tasks.db' # データベースファイルの名前を定義

# データベースへの接続を確立する関数
def get_db():
    # データベースに接続する。ファイルがなければ新しく作成される。
    conn = sqlite3.connect(DATABASE)
    # 辞書形式で結果を取得できるように設定する
    conn.row_factory = sqlite3.Row
    return conn

# アプリ起動時に一度だけ実行される、データベースの初期化関数
def init_db():
    # get_db()を使ってデータベースに接続
    with get_db() as conn:
        # 'schema.sql'というファイルからSQL文を読み込んで実行する
        # （直接SQL文を記述する）
        
        # テーブルを作成するSQL文
        # "IF NOT EXISTS" をつけておくことで、既にテーブルが存在する場合にエラーになるのを防ぐ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL
            );
        ''')
        # 変更を確定する
        conn.commit()


# --- ルーティング（URLとプログラムの紐付け） ---

# ルートURL ('/') にアクセスがあったときの処理
@app.route('/')
def index():
    # データベースに接続
    conn = get_db()
    # tasksテーブルからすべてのデータを取得するSQLを実行
    # ORDER BY id DESC で、新しいタスクが上にくるように並び替える
    cursor = conn.execute('SELECT id, title FROM tasks ORDER BY id DESC')
    # 実行結果をすべて取得する
    tasks = cursor.fetchall()
    # データベース接続を閉じる
    conn.close()
    
    # 取得したtasksデータをHTML側に渡して表示する
    return render_template('index.html', tasks=tasks)


# '/add' というURLにPOSTメソッドでアクセスがあったときの処理
@app.route('/add', methods=['POST'])
def add_task():
    # 送信されたフォームの中から'task_title'という名前のデータを取得する
    title = request.form.get('task_title')
    
    # titleが空でない場合のみ処理を実行
    if title:
        # データベースに接続
        conn = get_db()
        # tasksテーブルに新しいデータを挿入するSQLを実行
        # '?' はプレースホルダと呼ばれ、後から安全に値を埋め込むためのもの
        conn.execute('INSERT INTO tasks (title) VALUES (?)', (title,))
        # 変更を確定（コミット）する
        conn.commit()
        # データベース接続を閉じる
        conn.close()
        
    # 処理が終わったら、ルートURL('/')にリダイレクトする
    return redirect(url_for('index'))


# '/delete/<int:task_id>' というURLにアクセスがあったときの処理
@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    # データベースに接続
    conn = get_db()
    # 指定されたidのデータをtasksテーブルから削除するSQLを実行
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    # 変更を確定する
    conn.commit()
    # データベース接続を閉じる
    conn.close()
    
    # 処理が終わったら、ルートURL('/')にリダイレクトする
    return redirect(url_for('index'))


# --- サーバーの起動 ---
if __name__ == '__main__':
    # アプリを起動する前に、データベースの初期化を行う
    init_db()
    # Flaskの開発用サーバーを起動する
    app.run(debug=True)