/**
 * 观察池和表现统计 - 前端逻辑
 */

// ========== 全局变量 ==========

let wlChartInstance = null;
let perfPieChartInstance = null;
let perfLineChartInstance = null;

// ========== Tab切换 ==========

document.addEventListener('DOMContentLoaded', () => {
    initTabNav();
    initWatchlistEvents();
    initPerformanceEvents();
    loadWatchlistStatus();
    loadSchedulerStatus();
    loadPerformanceStats();
});

// Tab导航初始化
function initTabNav() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            // 切换按钮状态
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 切换面板
            tabPanels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `tab-${tabId}`) {
                    panel.classList.add('active');
                }
            });
            
            // 加载对应Tab的数据
            if (tabId === 'watchlist') {
                loadWatchlistStatus();
                loadWatchlistList();
                loadSchedulerStatus();
            } else if (tabId === 'performance') {
                loadPerformanceStats();
                loadPositions();
                loadSignals();
            }
        });
    });
}

// ========== 观察池功能 ==========

function initWatchlistEvents() {
    // 添加股票
    document.getElementById('wlAddBtn').addEventListener('click', handleAddStock);
    
    // 分析所有
    document.getElementById('wlAnalyzeAllBtn').addEventListener('click', handleAnalyzeAll);
    
    // 刷新列表
    document.getElementById('wlRefreshBtn').addEventListener('click', () => {
        loadWatchlistStatus();
        loadWatchlistList();
    });
    
    // 采集情报
    document.getElementById('wlCollectIntelBtn').addEventListener('click', handleCollectIntel);
    
    // 启动定时任务
    document.getElementById('wlRunSchedulerBtn').addEventListener('click', handleRunScheduler);
    
    // 追踪情报
    document.getElementById('intelTrackBtn').addEventListener('click', () => handleTrackIntel(false));

    // 刷新定时任务状态
    document.getElementById('refreshSchedulerBtn').addEventListener('click', loadSchedulerStatus);
    
    // 状态筛选
    document.getElementById('wlStatusFilter').addEventListener('change', loadWatchlistList);
    
    // 回车键添加股票
    document.getElementById('wlStockCode').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleAddStock();
    });
}

// 加载观察池状态
async function loadWatchlistStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/watchlist/status`);
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            document.getElementById('wlTotalCount').textContent = data.total || 0;
            
            // 计算各状态数量
            const byStatus = data.by_status || {};
            document.getElementById('wlBuyRecCount').textContent = data.buy_recommended || 0;
            document.getElementById('wlPendingCount').textContent = byStatus.pending || 0;
            document.getElementById('wlWatchingCount').textContent = byStatus.watching || 0;
        }
    } catch (error) {
        console.error('加载观察池状态失败:', error);
    }
}

// 加载观察池列表
async function loadWatchlistList() {
    try {
        const statusFilter = document.getElementById('wlStatusFilter').value;
        const url = statusFilter 
            ? `${API_BASE}/api/watchlist/list?status=${statusFilter}`
            : `${API_BASE}/api/watchlist/list`;
        
        const response = await fetch(url);
        const result = await response.json();
        
        if (result.success) {
            renderWatchlistTable(result.data.candidates || []);
        }
    } catch (error) {
        console.error('加载观察池列表失败:', error);
    }
}

// 渲染观察池表格（7 列，次要列通过 tooltip / title 承载）
function renderWatchlistTable(candidates) {
    const tbody = document.getElementById('wlTableBody');

    if (!candidates || candidates.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">暂无候选股票</td></tr>';
        return;
    }

    tbody.innerHTML = candidates.map(c => {
        const sourceLabel = getSourceLabel(c.source);
        const addDate = formatDate(c.add_date);
        const lastDate = formatDate(c.last_analysis_date);
        const rowTitle = `来源：${sourceLabel} · 添加：${addDate} · 最后分析：${lastDate}`;
        const recBadge = c.is_buy_recommended
            ? '<span class="badge badge-success">推荐</span>'
            : '<span class="badge">-</span>';
        return `
            <tr class="candidate-row" data-code="${c.code}" title="${rowTitle}">
                <td data-label="代码">${c.code}</td>
                <td data-label="名称">${c.name}</td>
                <td data-label="评分" class="num">${c.score.toFixed(1)}</td>
                <td data-label="综合" class="num">${c.composite_score ? c.composite_score.toFixed(1) : '--'}</td>
                <td data-label="状态"><span class="status-badge status-${c.status}">${getStatusLabel(c.status)}</span></td>
                <td data-label="推荐">${recBadge}</td>
                <td data-label="操作">
                    <button class="btn-tiny btn-analyze" onclick="handleAnalyzeOne('${c.code}')">LLM 分析</button>
                    <button class="btn-tiny btn-danger" onclick="handleRemoveStock('${c.code}')">移除</button>
                </td>
            </tr>
        `;
    }).join('');
}

// 添加股票
async function handleAddStock() {
    const code = document.getElementById('wlStockCode').value.trim();
    const name = document.getElementById('wlStockName').value.trim();
    const reason = document.getElementById('wlAddReason').value.trim();
    
    if (!code) {
        alert('请输入股票代码');
        return;
    }
    
    if (!name) {
        alert('请输入股票名称');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/watchlist/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: code,
                stock_name: name,
                source: 'manual',
                score: 0,
                reason: reason || '手动添加'
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            document.getElementById('wlStockCode').value = '';
            document.getElementById('wlStockName').value = '';
            document.getElementById('wlAddReason').value = '';
            loadWatchlistStatus();
            loadWatchlistList();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('添加股票失败:', error);
        alert('添加失败，请重试');
    }
}

// 移除股票
async function handleRemoveStock(code) {
    if (!confirm(`确定要从观察池移除 ${code}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/watchlist/remove`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: code,
                reason: '用户手动移除'
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            loadWatchlistStatus();
            loadWatchlistList();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('移除股票失败:', error);
        alert('移除失败，请重试');
    }
}

// 分析单只股票
async function handleAnalyzeOne(code) {
    // 读取分析模式，默认使用LLM
    const modeRadio = document.querySelector('input[name="wlAnalyzeMode"]:checked');
    const mode = modeRadio ? modeRadio.value : 'llm';

    if (mode === 'llm' && !confirm(`将使用LLM Agent深度分析 ${code}（含网络情报），可能需要较长时间，继续吗？`)) return;

    // 读取是否强制刷新情报
    const forceRefreshEl = document.getElementById('wlForceRefresh');
    const forceRefresh = forceRefreshEl ? forceRefreshEl.checked : false;

    try {
        const response = await fetch(`${API_BASE}/api/watchlist/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: code,
                mode: mode,
                with_intel: true,
                force_refresh: forceRefresh
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            alert(`分析失败: ${errorData.detail ? JSON.stringify(errorData.detail) : '服务器错误 (' + response.status + ')'}`);
            return;
        }

        const result = await response.json();
        
        if (result.success) {
            let msg = result.message;
            // LLM模式显示详细结果
            if (mode === 'llm' && result.data && result.data.analyzed) {
                const analyzed = result.data.analyzed[0];
                if (analyzed) {
                    const intelSource = analyzed.intel_source || 'none';
                    const intelLabel = intelSource === 'none' ? '无' :
                                     intelSource.startsWith('cached') ? `缓存(${intelSource})` :
                                     intelSource === 'fresh_search' ? '全新搜索' :
                                     intelSource.startsWith('stale') ? `过时缓存(${intelSource})` : intelSource;
                    msg = `分析完成!\n模式: LLM Agent\n动作: ${analyzed.action || '--'}\n综合评分: ${analyzed.composite_score || '--'}\n置信度: ${analyzed.confidence || '--'}\n是否买入: ${analyzed.is_buy ? '是' : '否'}\n情报注入: ${analyzed.with_intel ? '是' : '否'}\n情报来源: ${intelLabel}`;
                }
            }
            alert(msg);
            loadWatchlistStatus();
            loadWatchlistList();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('分析失败:', error);
        alert('分析失败，请重试');
    }
}

// 分析所有待分析股票
async function handleAnalyzeAll() {
    // 读取分析模式，默认使用LLM
    const modeRadio = document.querySelector('input[name="wlAnalyzeMode"]:checked');
    const mode = modeRadio ? modeRadio.value : 'llm';

    if (mode === 'llm') {
        if (!confirm('将使用LLM Agent深度分析所有待分析股票，可能需要较长时间，继续吗？')) return;
    } else {
        if (!confirm('确定要分析所有待分析的股票吗?')) return;
    }

    // 读取是否强制刷新情报
    const forceRefreshEl = document.getElementById('wlForceRefresh');
    const forceRefresh = forceRefreshEl ? forceRefreshEl.checked : false;

    try {
        const response = await fetch(`${API_BASE}/api/watchlist/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: mode,
                with_intel: true,
                force_refresh: forceRefresh
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            alert(`分析失败: ${errorData.detail ? JSON.stringify(errorData.detail) : '服务器错误 (' + response.status + ')'}`);
            return;
        }

        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            loadWatchlistStatus();
            loadWatchlistList();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('批量分析失败:', error);
        alert('分析失败，请重试');
    }
}

// 采集情报
async function handleCollectIntel() {
    if (!confirm('确定要采集最新情报数据吗?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/intel/collect`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`情报采集完成!\n龙虎榜: ${result.data.dragon_rank.count}条\n热门板块: ${result.data.hot_sectors.count}条\n机构调研: ${result.data.research.count}条`);
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('采集情报失败:', error);
        alert('采集失败，请重试');
    }
}

/** 防止「追踪情报」重复提交（含 LLM 解读） */
let _intelTrackInFlight = false;

function _setIntelTrackUiLocked(locked) {
    const form = document.querySelector('.intel-form');
    const trackBtn = document.getElementById('intelTrackBtn');
    const refreshBtn = document.getElementById('intelRefreshBtn');
    const codeInput = document.getElementById('intelStockCode');
    const llmChk = document.getElementById('intelLlmInterpret');
    if (form) {
        form.classList.toggle('intel-form--busy', locked);
        form.setAttribute('aria-busy', locked ? 'true' : 'false');
    }
    if (codeInput) {
        codeInput.disabled = locked;
    }
    if (trackBtn) {
        trackBtn.disabled = locked;
        if (locked) {
            if (!trackBtn.dataset.defaultHtml) {
                trackBtn.dataset.defaultHtml = trackBtn.innerHTML;
            }
            trackBtn.innerHTML = '<svg class="icon icon-sm" aria-hidden="true"><use href="#i-search"/></svg> 分析中…';
        } else if (trackBtn.dataset.defaultHtml) {
            trackBtn.innerHTML = trackBtn.dataset.defaultHtml;
        }
    }
    if (refreshBtn) {
        refreshBtn.disabled = locked;
    }
    if (llmChk) {
        llmChk.disabled = locked;
    }
}

// 追踪情报
async function handleTrackIntel(forceRefresh = false) {
    // 防御：确保 forceRefresh 是布尔值（addEventListener 可能传入 Event 对象）
    forceRefresh = forceRefresh === true;
    const code = document.getElementById('intelStockCode').value.trim();
    
    if (!code) {
        alert('请输入股票代码');
        return;
    }

    if (_intelTrackInFlight) {
        return;
    }
    
    _intelTrackInFlight = true;
    _setIntelTrackUiLocked(true);
    try {
        const llmChk = document.getElementById('intelLlmInterpret');
        const withLlm = llmChk ? llmChk.checked : true;
        const response = await fetch(`${API_BASE}/api/intel/track`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: code,
                force_refresh: forceRefresh,
                with_llm_interpretation: withLlm
            })
        });
        
        // 检查HTTP状态码
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.detail
                ? (Array.isArray(errorData.detail)
                    ? errorData.detail.map(d => d.msg || d).join('; ')
                    : JSON.stringify(errorData.detail))
                : `请求失败 (${response.status})`;
            alert(`追踪情报失败: ${errorMsg}`);
            return;
        }

        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            const meta = result.cache_meta || {};
            document.getElementById('intelBriefSection').classList.remove('hidden');

            // 缓存状态徽标
            let cacheLabel = '';
            if (meta.is_fresh) {
                cacheLabel = `<span class="badge badge-success">新鲜缓存 · ${meta.age_days} 天前</span>`;
            } else if (meta.is_stale) {
                cacheLabel = `<span class="badge badge-warn">缓存过时 · ${meta.age_days} 天前</span>
                    <button class="btn-tiny btn-secondary" onclick="handleTrackIntel(true)">强制刷新</button>`;
            } else if (meta.is_expired) {
                cacheLabel = `<span class="badge badge-danger">缓存已过期</span>`;
            } else {
                cacheLabel = `<span class="badge badge-brand">全新搜索</span>`;
            }

            // 顶部元信息
            const metaHtml = `
                <div class="intel-meta">
                    <div><span class="label">股票</span> <strong>${data.stock_name}</strong> (${data.stock_code})</div>
                    <div><span class="label">追踪时间</span> ${data.tracked_at || '--'}</div>
                    <div><span class="label">搜索引擎</span> ${data.search_stats?.search_provider || '未配置'}</div>
                    <div><span class="label">缓存状态</span> ${cacheLabel}</div>
                </div>
            `;

            const renderGroup = (iconId, title, items) => {
                const count = items && items.length ? items.length : 0;
                const header = `
                    <h5>
                        <svg class="icon icon-sm" aria-hidden="true"><use href="#${iconId}"/></svg>
                        ${title}
                        <span class="badge">${count}</span>
                    </h5>
                `;
                if (!count) {
                    return `<div class="intel-group">${header}<p class="intel-empty">暂无数据</p></div>`;
                }
                const listItems = items.map(it => `
                    <li>
                        <a href="${it.url || '#'}" target="_blank" rel="noopener">${it.title || '(无标题)'}</a>
                        ${it.summary ? `<div class="intel-snippet">${it.summary}</div>` : ''}
                    </li>
                `).join('');
                return `<div class="intel-group">${header}<ul class="intel-list">${listItems}</ul></div>`;
            };

            const bre = result.intel_brief;
            const llm = result.llm_interpretation;

            const esc = (t) => (typeof escapeHtml === 'function' ? escapeHtml(String(t)) : String(t));
            const renderRuleBrief = (brief) => {
                if (!brief || !brief.core_thesis) {
                    return '';
                }
                const sent = brief.overall_sentiment || '—';
                const cats = (brief.catalysts || []).slice(0, 6);
                const risks = (brief.risk_flags || []).slice(0, 5);
                const oq = (brief.open_questions || []).slice(0, 3);
                const catHtml = cats.length
                    ? `<ul class="intel-list intel-list--compact">${cats.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`
                    : '';
                const riskHtml = risks.length
                    ? `<ul class="intel-list intel-list--compact">${risks.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`
                    : '';
                const oqHtml = oq.length
                    ? `<ul class="intel-list intel-list--compact">${oq.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`
                    : '';
                return `
                <div class="intel-summary-card">
                    <h5>
                        <svg class="icon icon-sm" aria-hidden="true"><use href="#i-chart"/></svg>
                        规则型情报摘要
                        <span class="badge badge-brand">${esc(String(sent))}</span>
                    </h5>
                    <p class="intel-summary-thesis intel-snippet">${esc(String(brief.core_thesis || ''))}</p>
                    ${cats.length ? `<div class="intel-subblock"><span class="label">催化剂 / 热点</span>${catHtml}</div>` : ''}
                    ${risks.length ? `<div class="intel-subblock"><span class="label">风险标记</span>${riskHtml}</div>` : ''}
                    ${oq.length ? `<div class="intel-subblock"><span class="label">待澄清</span>${oqHtml}</div>` : ''}
                </div>`;
            };

            const stanceClass = (stance) => {
                if (!stance) return 'badge-brand';
                if (stance.includes('偏多')) return 'badge-success';
                if (stance.includes('偏空')) return 'badge-danger';
                if (stance.includes('观望') || stance.includes('信息不足')) return 'badge-warn';
                return 'badge-brand';
            };

            const renderLlm = (x) => {
                if (!x || !x.summary_text) return '';
                const st = String(x.stance || '');
                const src = x.source === 'llm_v1' ? '模型生成' : (x.source === 'rule_fallback' ? '规则整理' : '—');
                const conf = typeof x.confidence === 'number' ? x.confidence.toFixed(2) : '—';
                const bl = Array.isArray(x.bullets) ? x.bullets : [];
                const bullets = bl.length
                    ? `<ul class="intel-list intel-list--compact">${bl.map(b => `<li>${esc(String(b))}</li>`).join('')}</ul>`
                    : '';
                return `
                <div class="intel-interpret">
                    <h5>
                        <svg class="icon icon-sm" aria-hidden="true"><use href="#i-radio"/></svg>
                        情报员 · 简要解读
                        <span class="badge ${stanceClass(st)}">${esc(st || '—')}</span>
                        <span class="intel-interpret-meta">置信 ${esc(String(conf))} · ${esc(src)}</span>
                    </h5>
                    <p class="intel-interpret-body intel-snippet">${esc(String(x.summary_text))}</p>
                    ${bullets}
                    <p class="intel-interpret-disclaimer">${esc(String(x.disclaimer || '本解读基于当前抓取与规则摘要，不构成投资建议。'))}</p>
                </div>`;
            };

            const groupsHtml =
                renderGroup('i-news', '新闻', data.news) +
                renderGroup('i-book', '研报', data.research) +
                renderGroup('i-msg',  '舆情', data.sentiment);

            document.getElementById('intelBriefContent').innerHTML =
                metaHtml + renderRuleBrief(bre) + renderLlm(llm) + groupsHtml;
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('追踪情报失败:', error);
        alert('追踪失败，请重试');
    } finally {
        _intelTrackInFlight = false;
        _setIntelTrackUiLocked(false);
    }
}

// 启动定时任务
async function handleRunScheduler() {
    if (!confirm('确定要启动定时任务吗?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/scheduler/start`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            loadSchedulerStatus();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('启动定时任务失败:', error);
        alert('启动失败，请重试');
    }
}

/** 在定时任务区域展示最近一次手动执行的返回 data（JSON，安全文本） */
function renderSchedulerLastRun(data) {
    const el = document.getElementById('schedulerLastRun');
    if (!el || data == null) return;
    el.classList.remove('hidden');
    el.innerHTML = '<h4 class="scheduler-run-heading">最近一次执行结果</h4>';
    const pre = document.createElement('pre');
    pre.className = 'scheduler-run-json';
    pre.textContent = JSON.stringify(data, null, 2);
    el.appendChild(pre);
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// 加载定时任务状态
async function loadSchedulerStatus() {
    const statusDiv = document.getElementById('schedulerStatus');
    const tasksDiv = document.getElementById('schedulerTasks');
    try {
        const response = await fetch(`${API_BASE}/api/scheduler/status`);
        const result = await response.json();
        
        if (result.success) {
            const running = result.data.scheduler_running;
            const nextRuns = result.data.next_runs || [];
            const nextRunsHtml = nextRuns.length
                ? `<div class="scheduler-next-runs">
                    <p class="timeline-subtle">计划下次运行（进程内调度器）</p>
                    <ul>${nextRuns.map(
                        (n) =>
                            `<li><strong>${n.task_name}</strong> · ${n.next_run}</li>`
                    ).join('')}</ul>
                </div>`
                : '';

            statusDiv.innerHTML = `
                <p>调度器：<span class="badge ${running ? 'badge-success' : ''}">${running ? '运行中' : '已停止'}</span>
                <span class="timeline-subtle">最后检查 ${result.data.last_check || '--'}</span></p>
                ${nextRunsHtml}
            `;

            const tasks = result.data.predefined_tasks || {};
            tasksDiv.innerHTML = Object.values(tasks).map(task => `
                <div class="task-item">
                    <h5>${task.display_name}</h5>
                    <p>${task.description}</p>
                    <p class="timeline-subtle">执行时间 ${task.default_time}</p>
                    <button class="btn-tiny" onclick="handleRunTask('${task.name}')">立即执行</button>
                </div>
            `).join('');
        } else {
            statusDiv.innerHTML = `<p class="timeline-subtle">${result.message || '无法获取调度状态'}</p>`;
        }
    } catch (error) {
        console.error('加载定时任务状态失败:', error);
        if (statusDiv) {
            statusDiv.innerHTML = '<p class="timeline-subtle">加载定时任务状态失败</p>';
        }
    }
}

// 执行任务
async function handleRunTask(taskName) {
    if (!confirm(`确定要执行 ${taskName} 任务吗?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/scheduler/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_name: taskName })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            if (result.data) {
                renderSchedulerLastRun(result.data);
            }
            loadSchedulerStatus();
            if (taskName === 'weekly_analysis' || taskName === 'daily_update') {
                loadWatchlistList();
                loadWatchlistStatus();
            }
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('执行任务失败:', error);
        alert('执行失败，请重试');
    }
}

// ========== 表现统计功能 ==========

function initPerformanceEvents() {
    document.getElementById('refreshPositionsBtn').addEventListener('click', loadPositions);
    document.getElementById('refreshSignalsBtn').addEventListener('click', loadSignals);
    document.getElementById('genWeeklyReportBtn').addEventListener('click', generateWeeklyReport);
    document.getElementById('genMonthlyReportBtn').addEventListener('click', generateMonthlyReport);
}

// 加载表现统计
async function loadPerformanceStats() {
    try {
        const response = await fetch(`${API_BASE}/api/performance/stats`);
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            document.getElementById('perfTotalSignals').textContent = data.total_signals || 0;
            document.getElementById('perfWinRate').textContent = `${(data.win_rate * 100).toFixed(1)}%`;
            document.getElementById('perfTotalProfit').textContent = `${(data.total_profit_rate * 100).toFixed(2)}%`;
            document.getElementById('perfAvgDays').textContent = data.avg_holding_days || 0;
            
            // 渲染胜率饼图
            renderPerfPieChart(data.win_rate || 0);
        }
        
        // 加载图表数据
        loadPerfChartData();
    } catch (error) {
        console.error('加载表现统计失败:', error);
    }
}

// 加载表现图表数据
async function loadPerfChartData() {
    try {
        const response = await fetch(`${API_BASE}/api/performance/chart-data`);
        const result = await response.json();
        
        if (result.success) {
            renderPerfLineChart(result.data.cumulative_curve || []);
        }
    } catch (error) {
        console.error('加载图表数据失败:', error);
    }
}

// 渲染胜率饼图
function renderPerfPieChart(winRate) {
    const chartDom = document.getElementById('perfPieChart');
    
    if (!chartDom) return;
    
    if (!perfPieChartInstance) {
        perfPieChartInstance = echarts.init(chartDom);
    }
    
    const option = {
        textStyle: { color: '#6B7280', fontFamily: 'inherit' },
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} ({d}%)',
            backgroundColor: '#FFFFFF',
            borderColor: '#E5E7EB',
            borderWidth: 1,
            textStyle: { color: '#111827' },
            extraCssText: 'box-shadow: 0 4px 12px rgba(16,24,40,.08); border-radius: 8px;'
        },
        legend: {
            orient: 'vertical',
            left: 'left',
            textStyle: { color: '#6B7280' }
        },
        series: [{
            type: 'pie',
            radius: ['52%', '72%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 6,
                borderColor: '#FFFFFF',
                borderWidth: 2
            },
            label: {
                show: true,
                formatter: '{b}\n{d}%',
                color: '#374151'
            },
            data: [
                { value: Math.round(winRate * 100),       name: '盈利', itemStyle: { color: '#DC2626' } },
                { value: Math.round((1 - winRate) * 100), name: '亏损', itemStyle: { color: '#16A34A' } }
            ]
        }]
    };

    perfPieChartInstance.setOption(option);
    window.addEventListener('resize', () => perfPieChartInstance && perfPieChartInstance.resize());
}

// 渲染累计收益曲线
function renderPerfLineChart(cumulativeData) {
    const chartDom = document.getElementById('perfLineChart');
    
    if (!chartDom) return;
    
    if (!perfLineChartInstance) {
        perfLineChartInstance = echarts.init(chartDom);
    }
    
    const dates = cumulativeData.map(d => d.date);
    const values = cumulativeData.map(d => d.value * 100); // 转换为百分比
    
    const option = {
        textStyle: { color: '#6B7280', fontFamily: 'inherit' },
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#FFFFFF',
            borderColor: '#E5E7EB',
            borderWidth: 1,
            textStyle: { color: '#111827' },
            extraCssText: 'box-shadow: 0 4px 12px rgba(16,24,40,.08); border-radius: 8px;',
            formatter: function(params) {
                const p = params[0];
                return `${p.axisValue}<br/>累计收益 ${p.value.toFixed(2)}%`;
            }
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: { lineStyle: { color: '#E5E7EB' } },
            axisTick: { show: false },
            axisLabel: { color: '#6B7280' }
        },
        yAxis: {
            type: 'value',
            axisLabel: { formatter: '{value}%', color: '#6B7280' },
            axisLine: { show: false },
            splitLine: { lineStyle: { color: '#E5E7EB' } }
        },
        series: [{
            type: 'line',
            data: values,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 2, color: '#1E40AF' },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(30, 64, 175, 0.20)' },
                        { offset: 1, color: 'rgba(30, 64, 175, 0.02)' }
                    ]
                }
            },
            itemStyle: { color: '#1E40AF' }
        }],
        grid: {
            left: '3%',
            right: '4%',
            bottom: '8%',
            top: '8%',
            containLabel: true
        }
    };

    perfLineChartInstance.setOption(option);
    window.addEventListener('resize', () => perfLineChartInstance && perfLineChartInstance.resize());
}

// 加载持仓记录
async function loadPositions() {
    try {
        const response = await fetch(`${API_BASE}/api/performance/positions`);
        const result = await response.json();
        
        if (result.success) {
            renderPositionsTable(result.data.positions || []);
        }
    } catch (error) {
        console.error('加载持仓记录失败:', error);
    }
}

// 渲染持仓表格（7 列：代码/名称/入场价/股数/持仓天数/收益率/操作）
function renderPositionsTable(positions) {
    const tbody = document.getElementById('positionsTableBody');

    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">暂无持仓记录</td></tr>';
        return;
    }

    tbody.innerHTML = positions.map(p => {
        const isProfit = p.profit_rate >= 0;
        const profitClass = isProfit ? 'profit-positive' : 'profit-negative';
        const profitSign = isProfit ? '+' : '';
        const rowTitle = `入场日期：${p.entry_date || '--'} · 盈亏金额：${profitSign}¥${(p.profit_loss || 0).toFixed(2)}`;
        return `
            <tr title="${rowTitle}">
                <td data-label="代码">${p.stock_code}</td>
                <td data-label="名称">${p.stock_name}</td>
                <td data-label="入场价" class="num">¥${p.entry_price.toFixed(2)}</td>
                <td data-label="股数" class="num">${p.shares}</td>
                <td data-label="持仓天数" class="num">${p.holding_days} 天</td>
                <td data-label="收益率" class="num ${profitClass}">
                    ${profitSign}${(p.profit_rate * 100).toFixed(2)}%
                </td>
                <td data-label="操作">
                    <button class="btn-tiny btn-danger" onclick="handleClosePosition('${p.stock_code}')">平仓</button>
                </td>
            </tr>
        `;
    }).join('');
}

// 平仓
async function handleClosePosition(code) {
    const reason = prompt('请输入平仓原因:', '用户手动平仓');
    if (reason === null) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/performance/close`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: code,
                reason: reason
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            loadPositions();
            loadPerformanceStats();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('平仓失败:', error);
        alert('平仓失败，请重试');
    }
}

// 加载历史信号
async function loadSignals() {
    try {
        const response = await fetch(`${API_BASE}/api/performance/history?limit=50`);
        const result = await response.json();
        
        if (result.success) {
            renderSignalsTable(result.data.signals || []);
        }
    } catch (error) {
        console.error('加载历史信号失败:', error);
    }
}

// 渲染信号表格（7 列：代码/名称/类型/入场价/出场价/持仓天数/收益率）
function renderSignalsTable(signals) {
    const tbody = document.getElementById('signalsTableBody');

    if (!signals || signals.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">暂无历史信号</td></tr>';
        return;
    }

    tbody.innerHTML = signals.map(s => {
        const isProfit = s.profit_rate >= 0;
        const profitClass = isProfit ? 'profit-positive' : 'profit-negative';
        const profitSign = isProfit ? '+' : '';
        const rowTitle = `信号日期：${s.signal_date || '--'} · 平仓日期：${s.close_date || '--'} · 状态：${s.status || '--'}`;
        return `
            <tr title="${rowTitle}">
                <td data-label="代码">${s.stock_code}</td>
                <td data-label="名称">${s.stock_name}</td>
                <td data-label="类型"><span class="badge">${s.signal_type}</span></td>
                <td data-label="入场价" class="num">¥${s.entry_price.toFixed(2)}</td>
                <td data-label="出场价" class="num">${s.exit_price ? '¥' + s.exit_price.toFixed(2) : '--'}</td>
                <td data-label="持仓天数" class="num">${s.holding_days || '--'}</td>
                <td data-label="收益率" class="num ${profitClass}">
                    ${profitSign}${(s.profit_rate * 100).toFixed(2)}%
                </td>
            </tr>
        `;
    }).join('');
}

// 生成周报
async function generateWeeklyReport() {
    try {
        const response = await fetch(`${API_BASE}/api/performance/weekly`);
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('reportContent').classList.remove('hidden');
            document.getElementById('reportText').textContent = JSON.stringify(result.data, null, 2);
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('生成周报失败:', error);
        alert('生成周报失败，请重试');
    }
}

// 生成月报
async function generateMonthlyReport() {
    try {
        const response = await fetch(`${API_BASE}/api/performance/monthly`);
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('reportContent').classList.remove('hidden');
            document.getElementById('reportText').textContent = JSON.stringify(result.data, null, 2);
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('生成月报失败:', error);
        alert('生成月报失败，请重试');
    }
}

// ========== 辅助函数 ==========

function getSourceLabel(source) {
    const labels = {
        'dragon_rank': '龙虎榜',
        'hot_sector': '热门板块',
        'research': '机构调研',
        'manual': '手动'
    };
    return labels[source] || source;
}

function getStatusLabel(status) {
    const labels = {
        'pending': '待分析',
        'watching': '观察中',
        'archived': '已归档',
        'removed': '已移除'
    };
    return labels[status] || status;
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('zh-CN');
    } catch {
        return dateStr;
    }
}
