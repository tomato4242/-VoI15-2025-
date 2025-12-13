// static/script.js - 拡張機能版

let processedPunishments = new Set();

document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('addTaskModal');
    const openModalBtn = document.getElementById('openModalBtn');
    const fakeTweetModal = document.getElementById('fakeTweetModal');

    // モーダル制御
    if (openModalBtn) {
        openModalBtn.addEventListener('click', function() {
            modal.style.display = 'block';
        });
    }

    // 背景クリックで閉じる
    window.addEventListener('click', function(event) {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(m => {
            if (event.target === m) {
                m.style.display = 'none';
            }
        });
    });

    // 初期化
    renderTaskList();
    updateStats();
    loadRankings();
    loadBadges();

    // 定期更新
    setInterval(checkForPunishments, 3000);
    setInterval(updateStats, 5000);
    setInterval(refreshTaskList, 10000);
    setInterval(loadRankings, 15000);
});

// ===== タブ切り替え =====
function switchTab(tabName) {
    // すべてのタブを非表示
    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));
    
    // すべてのボタンを非アクティブ化
    const buttons = document.querySelectorAll('.tab-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    
    // 選択されたタブを表示
    document.getElementById(tabName + '-tab').classList.add('active');
    event.target.classList.add('active');
}

// ===== タスク管理 =====
function renderTaskList() {
    const taskList = document.getElementById('taskList');
    
    fetch('/api/tasks')
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(tasks => {
            if (!Array.isArray(tasks) || tasks.length === 0) {
                taskList.innerHTML = '<li class="no-task">現在、タスクはありません。</li>';
                return;
            }

            taskList.innerHTML = tasks.map(task => {
                const now = new Date();
                const deadline = task.deadline ? new Date(task.deadline) : null;
                const isExpired = deadline && deadline < now && !task.is_completed;
                const isPunished = task.is_punished;

                let statusClass = '';
                let statusIcon = '';
                if (isPunished) {
                    statusClass = 'expired';
                    statusIcon = '💀 処刑済み';
                } else if (isExpired) {
                    statusClass = 'expired';
                    statusIcon = '⏰ 期限超過';
                }

                const deadlineStr = deadline ? 
                    deadline.toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : 
                    '期限なし';

                return `
                    <li class="task-item ${statusClass}">
                        <div class="task-info">
                            <span class="task-name">${escapeHtml(task.title)}</span>
                            <div class="task-meta">
                                <span class="deadline">⏳ ${deadlineStr}</span>
                                <span class="penalty">💣 ${escapeHtml(task.penalty_text)}</span>
                            </div>
                            ${statusIcon ? `<div class="punished-msg">${statusIcon}</div>` : ''}
                        </div>
                        <form method="post" action="/delete/${task.id}" style="margin: 0;">
                            <button type="submit" class="delete-btn" onclick="return confirmDelete('${escapeHtml(task.title)}')">
                                解除（完了）
                            </button>
                        </form>
                    </li>
                `;
            }).join('');
        })
        .catch(error => {
            console.error('タスク読み込みエラー:', error);
            taskList.innerHTML = '<li class="no-task">タスクの読み込みに失敗しました。</li>';
        });
}

function checkForPunishments() {
    fetch('/check_punishments')
        .then(response => response.json())
        .then(punishedTasks => {
            if (punishedTasks && punishedTasks.length > 0) {
                const newPunishments = punishedTasks.filter(task => 
                    !processedPunishments.has(task.id)
                );

                newPunishments.forEach(task => {
                    processedPunishments.add(task.id);
                    showFakeTweet(task);
                });
            }
        })
        .catch(error => console.error('チェックエラー:', error));
}

function showFakeTweet(task) {
    const tweetTextDisplay = document.getElementById('tweetTextDisplay');
    const fakeTweetModal = document.getElementById('fakeTweetModal');

    const tweetContent = `
        <b>【自動投稿】</b><br>
        私は怠惰な学生です。期限を守れませんでした。<br>
        <br>
        <strong style="font-size: 1.1em;">${escapeHtml(task.penalty_text)}</strong><br>
        <br>
        <span style="color:#1da1f2">#怠惰是正アプリ #SocialGuillotine</span>
    `;

    tweetTextDisplay.innerHTML = tweetContent;
    fakeTweetModal.style.display = 'block';
    playWarningSound();
}

function closeTweetModal() {
    document.getElementById('fakeTweetModal').style.display = 'none';
    setTimeout(() => {
        location.reload();
    }, 500);
}

function updateStats() {
    fetch('/api/stats')
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(stats => {
            if (stats && typeof stats === 'object') {
                document.getElementById('lazynessScore').textContent = 
                    (stats.laziness_score || 0).toFixed(1) + '%';
                document.getElementById('completedCount').textContent = 
                    stats.completed_tasks || 0;
                document.getElementById('streakCount').textContent = 
                    (stats.current_streak || 0) + '日';
                document.getElementById('punishedCount').textContent = 
                    stats.punished_tasks || 0;
            }
        })
        .catch(error => console.error('統計更新エラー:', error));
}

function refreshTaskList() {
    renderTaskList();
}

// ===== ランキング =====
function loadRankings() {
    fetch('/api/rankings')
        .then(response => response.json())
        .then(rankings => {
            const tbody = document.getElementById('rankingBody');
            if (!rankings || rankings.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">ランキングデータがありません</td></tr>';
                return;
            }

            tbody.innerHTML = rankings.map(r => `
                <tr>
                    <td class="rank">${r.rank}</td>
                    <td>${escapeHtml(r.username)}</td>
                    <td class="score">${r.laziness_score.toFixed(1)}%</td>
                    <td>${r.completed_tasks}</td>
                    <td>${r.punished_tasks}</td>
                </tr>
            `).join('');
        })
        .catch(error => console.error('ランキング読み込みエラー:', error));
}

// ===== バッジ =====
function loadBadges() {
    fetch('/api/badges')
        .then(response => response.json())
        .then(badges => {
            const grid = document.getElementById('badgesGrid');
            if (!badges || badges.length === 0) {
                grid.innerHTML = '<p style="text-align:center; color: #aaa;">まだバッジを獲得していません</p>';
                return;
            }

            grid.innerHTML = badges.map(badge => `
                <div class="badge-card">
                    <div class="badge-icon">${badge.icon}</div>
                    <div class="badge-name">${escapeHtml(badge.name)}</div>
                    <div class="badge-date">${new Date(badge.unlocked_at).toLocaleDateString('ja-JP')}</div>
                </div>
            `).join('');
        })
        .catch(error => console.error('バッジ読み込みエラー:', error));
}

// ===== グループ =====
function showGroupCreateForm() {
    const form = document.getElementById('groupCreateForm');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

function showGroupJoinForm() {
    const form = document.getElementById('groupJoinForm');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

// ===== ユーティリティ =====
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

function confirmDelete(taskTitle) {
    return confirm(`「${taskTitle}」を完了しますか？`);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function playWarningSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (e) {
        console.log('音声再生エラー:', e);
    }
}