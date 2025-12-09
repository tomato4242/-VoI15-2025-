// static/script.js

document.addEventListener('DOMContentLoaded', function() {
    // --- 要素の取得 ---
    const modal = document.getElementById('addTaskModal');
    const openModalBtn = document.getElementById('openModalBtn');
    const closeBtns = document.querySelectorAll('.close-btn');
    const fakeTweetModal = document.getElementById('fakeTweetModal');
    const tweetTextDisplay = document.getElementById('tweetTextDisplay');

    // --- タスク追加モーダルの開閉 ---
    
    // 「契約書に署名」ボタン
    openModalBtn.onclick = function() {
        modal.style.display = 'block';
    }

    // ×ボタンで閉じる（全ての×ボタンに対応）
    closeBtns.forEach(btn => {
        btn.onclick = function() {
            modal.style.display = 'none';
        }
    });

    // 背景クリックで閉じる
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }

    // --- 【重要】サーバー監視と演出トリガー ---
    
    // 3秒ごとにサーバーに「爆発したタスクある？」と聞きに行く
    setInterval(checkForPunishments, 3000);

    function checkForPunishments() {
        // FlaskのAPIを呼び出す
        fetch('/check_punishments')
            .then(response => response.json())
            .then(punishedTasks => {
                // もし「執行が必要なタスク」があれば
                if (punishedTasks.length > 0) {
                    // 最新の1件を取得して演出を表示
                    const task = punishedTasks[0];
                    showFakeTweet(task);
                }
            })
            .catch(error => console.error('Error:', error));
    }

    // 偽ツイートモーダルを表示する関数
    function showFakeTweet(task) {
        // ツイート本文をセット
        const tweetContent = `
            【自動投稿】<br>
            私は怠惰な学生です。期限を守れませんでした。<br>
            <br>
            <b>${task.penalty_text}</b><br>
            <br>
            <span style="color:#1da1f2">#怠惰是正アプリ #SocialGuillotine</span>
        `;
        tweetTextDisplay.innerHTML = tweetContent;

        // モーダルを表示
        fakeTweetModal.style.display = 'block';

        // ページのリロード（リストの見た目を更新するため）は、ユーザーが閉じた後でも良いが、
        // ここでは裏側でリストを更新したいので、少し待ってからリロードしてもよい。
        // デモ用なので、モーダルを閉じたタイミングでリロードさせるようにします。
    }

    // 偽ツイートモーダルを閉じるボタン（グローバル関数として定義）
    window.closeTweetModal = function() {
        fakeTweetModal.style.display = 'none';
        // 閉じた後にページを更新して、リストの「赤色表示」を反映させる
        location.reload();
    }
});