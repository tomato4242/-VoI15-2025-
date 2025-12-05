# app.py

# Flaskというライブラリから、必要な機能（Flask本体、ページの表示、リクエストの受け取りなど）を読み込む。
from flask import Flask, render_template, request, redirect, url_for

# Flaskアプリの本体を作成する。
app = Flask(__name__)

# --- データ保管場所 ---
# 本来はデータベースを使うが、今回は簡単にするため、Pythonのリスト（配列）にタスクを保存する。
# そのため、サーバーを再起動するとデータは消える。ハッカソンのデモとしてはまずこの形でOK。
tasks = []
# タスクにユニークなIDを振るためのカウンター。
task_id_counter = 1


# --- ルーティング（URLとプログラムの紐付け） ---

# ルートURL ('/') にアクセスがあったときの処理を定義する。
# GETメソッド（通常のページアクセス）の場合にこの関数が呼ばれる。
@app.route('/')
def index():
    # 'index.html'というファイルをブラウザに表示する。
    # このとき、'tasks'という名前でPythonのtasksリストをHTML側に渡す。
    return render_template('index.html', tasks=tasks)


# '/add' というURLにPOSTメソッド（フォーム送信など）でアクセスがあったときの処理を定義する。
@app.route('/add', methods=['POST'])
def add_task():
    # グローバル変数を関数内で変更するために宣言する。
    global task_id_counter
    
    # 送信されたフォームの中から'task_title'という名前のデータを取得する。
    title = request.form.get('task_title')
    
    # titleが空でなく、中身がある場合のみ処理を実行する。
    if title:
        # 新しいタスクを辞書（キーと値のペア）として作成する。
        new_task = {
            'id': task_id_counter,
            'title': title,
        }
        # 作成したタスクをtasksリストに追加する。
        tasks.append(new_task)
        # 次のタスクのためにIDカウンターを1増やす。
        task_id_counter += 1
        
    # すべての処理が終わったら、ルートURL('/')にリダイレクト（ページを移動）させる。
    # これにより、タスク追加後にトップページが再表示され、最新のリストが見える。
    return redirect(url_for('index'))


# '/delete/<int:task_id>' というURLにアクセスがあったときの処理を定義する。
# URLの一部（<int:task_id>）を引数として受け取れる。
@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    # global tasks  # リストの要素を変更するだけなので、global宣言は不要
    
    # tasksリストから、指定されたidと一致しないタスクだけを残す。
    # これにより、指定されたidのタスクが事実上削除される。
    # list comprehensionというPythonの書き方。
    tasks[:] = [task for task in tasks if task['id'] != task_id]

    # 処理が終わったら、ルートURL('/')にリダイレクトする。
    return redirect(url_for('index'))


# --- サーバーの起動 ---

# このファイルが直接実行された場合にのみ、以下の処理を行う。
if __name__ == '__main__':
    # Flaskの開発用サーバーを起動する。
    # debug=Trueにすると、コードを変更したときに自動でサーバーが再起動して便利。
    app.run(debug=True)