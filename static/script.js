// static/script.js

// DOM（HTMLの要素）の読み込みが完了したら、中のコードを実行する。
document.addEventListener('DOMContentLoaded', function() {
    // HTMLから必要な要素を取得して、変数に格納する。
    const modal = document.getElementById('addTaskModal');
    const openModalBtn = document.getElementById('openModalBtn');
    const closeModalBtn = document.querySelector('.close-btn');

    // 「新しいタスクを追加」ボタンがクリックされたときの処理
    openModalBtn.onclick = function() {
        modal.style.display = 'block'; // モーダルを表示する
    }

    // モーダルの閉じるボタン（×）がクリックされたときの処理
    closeModalBtn.onclick = function() {
        modal.style.display = 'none'; // モーダルを非表示にする
    }

    // モーダルの外側（背景部分）がクリックされたときの処理
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none'; // モーダルを非表示にする
        }
    }
});