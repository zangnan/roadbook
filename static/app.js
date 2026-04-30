/**
 * 路书 RoadBook - Web 界面 JavaScript
 */

(function() {
    'use strict';

    // DOM 元素
    const elements = {
        photoDirSelect: document.getElementById('photo-dir-select'),
        photoDirInput: document.getElementById('photo-dir-input'),
        distanceThreshold: document.getElementById('distance-threshold'),
        timeThreshold: document.getElementById('time-threshold'),
        thumbnailWidth: document.getElementById('thumbnail-width'),
        thumbnailHeight: document.getElementById('thumbnail-height'),
        imageQuality: document.getElementById('image-quality'),
        cacheType: document.getElementById('cache-type'),
        singleHtml: document.getElementById('single-html'),
        htmlOnly: document.getElementById('html-only'),
        btnRun: document.getElementById('btn-run'),
        progressSection: document.getElementById('progress-section'),
        progressStatus: document.getElementById('progress-status'),
        progressPhotoDir: document.getElementById('progress-photo-dir'),
        logContainer: document.getElementById('log-container'),
        logOutput: document.getElementById('log-output'),
        generateSection: document.getElementById('generate-section')
    };

    let currentTaskId = null;
    let pollInterval = null;
    let currentPhotoDir = null;  // 当前生成的目录名

    /**
     * 安全设置元素的 disabled 属性
     */
    function safeSetDisabled(element, value) {
        if (element) {
            element.disabled = value;
        }
    }

    /**
     * 获取照片目录（从下拉框或输入框）
     */
    function getPhotoDir() {
        const selected = elements.photoDirSelect.value;
        const input = elements.photoDirInput.value.trim();
        return selected || input;
    }

    /**
     * 获取表单参数
     */
    function getFormParams() {
        return {
            photo_dir: getPhotoDir(),
            distance_threshold: parseInt(elements.distanceThreshold.value) || 1000,
            time_threshold: parseInt(elements.timeThreshold.value) || 7200,
            html_only: elements.htmlOnly.checked
        };
    }

    /**
     * 添加日志行
     */
    function addLogLine(time, text, level) {
        level = level || 'info';

        // 根据日志内容判断级别
        if (text.includes('错误') || text.includes('失败') || text.includes('Error')) {
            level = 'error';
        } else if (text.includes('警告') || text.includes('Warning')) {
            level = 'warning';
        } else if (text.includes('完成') || text.includes('成功') || text.includes('生成')) {
            level = 'success';
        }

        const line = document.createElement('p');
        line.className = `log-line ${level}`;
        line.innerHTML = `<span class="time">${time}</span>${escapeHtml(text)}`;
        elements.logOutput.appendChild(line);

        // 滚动到底部
        elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
    }

    /**
     * HTML 转义
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 清空日志
     */
    function clearLog() {
        elements.logOutput.innerHTML = '';
    }

    /**
     * 显示/隐藏进度区域
     */
    function showProgress(show) {
        elements.progressSection.style.display = show ? 'block' : 'none';
        if (show) {
            elements.generateSection.style.display = 'none';
        } else {
            elements.generateSection.style.display = 'block';
        }
    }

    /**
     * 轮询任务状态
     */
    function pollStatus() {
        if (!currentTaskId) return;

        fetch(`/api/status/${currentTaskId}`)
            .then(res => res.json())
            .then(data => {
                // 更新日志
                if (data.output && data.output.length > 0) {
                    data.output.forEach(item => {
                        addLogLine(item.time, item.text);
                    });
                }

                // 更新状态
                elements.progressStatus.textContent = getStatusText(data.status);
                if (data.photo_dir) {
                    elements.progressPhotoDir.textContent = data.photo_dir;
                }

                // 任务完成
                if (data.status === 'completed') {
                    stopPolling();
                    safeSetDisabled(elements.btnRun, false);
                    addLogLine('系统', '生成完成！', 'success');
                    // 刷新历史记录
                    refreshHistory();
                } else if (data.status === 'failed') {
                    stopPolling();
                    safeSetDisabled(elements.btnRun, false);
                    addLogLine('系统', `生成失败！请检查错误信息。`, 'error');
                }
            })
            .catch(err => {
                console.error('轮询错误:', err);
            });
    }

    /**
     * 开始轮询
     */
    function startPolling(taskId) {
        currentTaskId = taskId;
        safeSetDisabled(elements.btnRun, true);
        clearLog();
        showProgress(true);
        pollInterval = setInterval(pollStatus, 1000);
        pollStatus(); // 立即执行一次
    }

    /**
     * 停止轮询
     */
    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    /**
     * 获取状态文本
     */
    function getStatusText(status) {
        const statusMap = {
            'pending': '准备中...',
            'running': '生成中...',
            'completed': '已完成',
            'failed': '失败'
        };
        return statusMap[status] || status;
    }

    /**
     * 刷新历史记录
     */
    function refreshHistory() {
        fetch('/api/outputs')
            .then(res => res.json())
            .then(data => {
                updateHistoryTable(data);
            })
            .catch(err => {
                console.error('刷新历史记录失败:', err);
            });
    }

    /**
     * 更新历史记录表格
     */
    function updateHistoryTable(dirs) {
        const historyList = document.getElementById('history-list');
        if (!historyList) return;

        if (!dirs || dirs.length === 0) {
            historyList.innerHTML = '<p class="empty">暂无生成记录</p>';
            return;
        }

        let html = `
            <table class="history-table">
                <thead>
                    <tr>
                        <th>目录</th>
                        <th>生成时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
        `;

        dirs.forEach(item => {
            const isCurrentDir = item.name === currentPhotoDir;
            const rowClass = isCurrentDir ? ' class="current-row"' : '';
            html += `<tr${rowClass} data-dir="${item.name}">`;
            html += `<td>${escapeHtml(item.name)}</td>`;
            html += `<td>${escapeHtml(item.mtime)}</td>`;
            html += `<td>`;
            if (item.has_output) {
                html += `<a href="/output/${item.name}/track_output.html" class="btn-link btn-track">轨迹地图</a>`;
            }
            if (item.has_timeline) {
                html += `<a href="/output/${item.name}/timeline.html" class="btn-link btn-timeline">时间轴</a>`;
            }
            html += `</td></tr>`;
        });

        html += '</tbody></table>';
        historyList.innerHTML = html;
        // 为新添加的链接绑定点击事件
        setupLinks();
    }

    /**
     * 执行生成
     */
    function runGeneration() {
        const params = getFormParams();

        if (!params.photo_dir) {
            alert('请选择或输入照片目录');
            return;
        }

        currentPhotoDir = params.photo_dir;
        elements.progressPhotoDir.textContent = params.photo_dir;
        elements.progressStatus.textContent = '准备中...';

        fetch('/api/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }
            startPolling(data.task_id);
        })
        .catch(err => {
            console.error('请求错误:', err);
            alert('请求失败: ' + err.message);
        });
    }

    /**
     * 同步下拉框和输入框
     */
    function syncDirInputs() {
        elements.photoDirInput.value = elements.photoDirSelect.value;
    }

    // 事件绑定
    elements.photoDirSelect.addEventListener('change', syncDirInputs);
    elements.btnRun.addEventListener('click', runGeneration);

    // 初始化链接点击处理（桌面模式）
    function setupLinks() {
        document.querySelectorAll('a.btn-link').forEach(function(link) {
            link.onclick = function(e) {
                e.preventDefault();
                var href = this.getAttribute('href');
                if (href && href.indexOf('desktop=') === -1) {
                    href = href + (href.indexOf('?') !== -1 ? '&' : '?') + 'desktop=1';
                }
                showPageLoading();
                window.location.href = href;
            };
        });
    }

    // 显示页面跳转 loading
    function showPageLoading() {
        var loading = document.getElementById('page-loading');
        if (!loading) {
            loading = document.createElement('div');
            loading.id = 'page-loading';
            loading.innerHTML = '<div class="loading-spinner"></div><p>正在跳转...</p>';
            loading.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(15,23,42,0.85);display:flex;justify-content:center;align-items:center;flex-direction:column;z-index:99999;';
            var spinner = loading.querySelector('.loading-spinner');
            spinner.style.cssText = 'width:44px;height:44px;border:4px solid rgba(255,255,255,0.2);border-top-color:#00d4ff;border-radius:50%;animation:spin 0.8s linear infinite;';
            var text = loading.querySelector('p');
            text.style.cssText = 'color:#fff;margin-top:16px;font-size:14px;';
            var style = document.createElement('style');
            style.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
            document.head.appendChild(style);
            document.body.appendChild(loading);
        }
        loading.style.display = 'flex';
    }

    // DOMContentLoaded 时直接设置链接处理
    document.addEventListener('DOMContentLoaded', setupLinks);

    // 初始化
    console.log('路书 RoadBook Web 界面已加载');

})();

// 全屏预览功能（挂载到全局）
window.openPreview = function(imgElement) {
    const modal = document.getElementById('previewModal');
    const previewImage = document.getElementById('previewImage');
    if (modal && previewImage) {
        previewImage.src = imgElement.src;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
};

window.closePreview = function() {
    const modal = document.getElementById('previewModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
};
