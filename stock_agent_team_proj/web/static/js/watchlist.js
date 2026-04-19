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

// 渲染观察池表格
function renderWatchlistTable(candidates) {
    const tbody = document.getElementById('wlTableBody');
    
    if (!candidates || candidates.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="10">暂无候选股票</td></tr>';
        return;
    }
    
    tbody.innerHTML = candidates.map(c => `
        <tr class="candidate-row" data-code="${c.code}">
            <td>${c.code}</td>
            <td>${c.name}</td>
            <td>${getSourceLabel(c.source)}</td>
            <td>${c.score.toFixed(1)}</td>
            <td>${c.composite_score ? c.composite_score.toFixed(1) : '--'}</td>
            <td><span class="status-badge status-${c.status}">${getStatusLabel(c.status)}</span></td>
            <td>${c.is_buy_recommended ? '✅' : '❌'}</td>
            <td>${formatDate(c.add_date)}</td>
            <td>${formatDate(c.last_analysis_date)}</td>
            <td>
                <button class="btn-tiny btn-analyze" onclick="handleAnalyzeOne('${c.code}')">🤖 LLM分析</button>
                <button class="btn-tiny btn-danger" onclick="handleRemoveStock('${c.code}')">移除</button>
            </td>
        </tr>
    `).join('');
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

// 追踪情报
async function handleTrackIntel(forceRefresh = false) {
    // 防御：确保 forceRefresh 是布尔值（addEventListener 可能传入 Event 对象）
    forceRefresh = forceRefresh === true;
    const code = document.getElementById('intelStockCode').value.trim();
    
    if (!code) {
        alert('请输入股票代码');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/intel/track`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: code,
                force_refresh: forceRefresh
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

            // 构建缓存状态标签
            let cacheLabel = '';
            if (meta.is_fresh) {
                cacheLabel = `<span class="cache-badge cache-fresh">✅ 新鲜缓存(${meta.age_days}天前)</span>`;
            } else if (meta.is_stale) {
                cacheLabel = `<span class="cache-badge cache-stale">⚠️ 缓存过时(${meta.age_days}天前)</span> <button class="btn-tiny btn-secondary" onclick="handleTrackIntel(true)">🔄 强制刷新</button>`;
            } else if (meta.is_expired) {
                cacheLabel = `<span class="cache-badge cache-expired">❌ 缓存已过期</span>`;
            } else {
                cacheLabel = `<span class="cache-badge cache-new">🔍 全新搜索</span>`;
            }

            // 构建情报展示
            let html = `
                <div class="intel-item"><strong>股票:</strong> ${data.stock_name}(${data.stock_code})</div>
                <div class="intel-item"><strong>追踪时间:</strong> ${data.tracked_at}</div>
                <div class="intel-item"><strong>搜索引擎:</strong> ${data.search_stats?.search_provider || '未配置'}</div>
                <div class="intel-item"><strong>缓存状态:</strong> ${cacheLabel}</div>
            `;

            // 新闻列表
            if (data.news && data.news.length > 0) {
                html += '<div class="intel-category"><strong>📰 新闻 (' + data.news.length + '条)</strong></div>';
                data.news.forEach(n => {
                    html += `<div class="intel-news-item">
                        <a href="${n.url || '#'}" target="_blank">${n.title}</a>
                        <span class="intel-snippet">${n.summary || ''}</span>
                    </div>`;
                });
            } else {
                html += '<div class="intel-category"><strong>📰 新闻</strong> 暂无</div>';
            }

            // 研报列表
            if (data.research && data.research.length > 0) {
                html += '<div class="intel-category"><strong>📋 研报 (' + data.research.length + '条)</strong></div>';
                data.research.forEach(r => {
                    html += `<div class="intel-news-item">
                        <a href="${r.url || '#'}" target="_blank">${r.title}</a>
                        <span class="intel-snippet">${r.summary || ''}</span>
                    </div>`;
                });
            } else {
                html += '<div class="intel-category"><strong>📋 研报</strong> 暂无</div>';
            }

            // 舆情列表
            if (data.sentiment && data.sentiment.length > 0) {
                html += '<div class="intel-category"><strong>💬 舆情 (' + data.sentiment.length + '条)</strong></div>';
                data.sentiment.forEach(s => {
                    html += `<div class="intel-news-item">
                        <a href="${s.url || '#'}" target="_blank">${s.title}</a>
                        <span class="intel-snippet">${s.summary || ''}</span>
                    </div>`;
                });
            } else {
                html += '<div class="intel-category"><strong>💬 舆情</strong> 暂无</div>';
            }

            document.getElementById('intelBriefContent').innerHTML = html;
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('追踪情报失败:', error);
        alert('追踪失败，请重试');
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

// 加载定时任务状态
async function loadSchedulerStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/scheduler/status`);
        const result = await response.json();
        
        if (result.success) {
            const statusDiv = document.getElementById('schedulerStatus');
            const tasksDiv = document.getElementById('schedulerTasks');
            
            statusDiv.innerHTML = `
                <p>调度器状态: <span class="${result.data.scheduler_running ? 'text-success' : 'text-muted'}">
                    ${result.data.scheduler_running ? '运行中' : '已停止'}
                </span></p>
                <p>最后检查: ${result.data.last_check}</p>
            `;
            
            // 渲染任务列表
            const tasks = result.data.predefined_tasks || {};
            tasksDiv.innerHTML = Object.values(tasks).map(task => `
                <div class="task-item">
                    <div class="task-info">
                        <strong>${task.display_name}</strong>
                        <p>${task.description}</p>
                        <p class="task-schedule">执行时间: ${task.default_time}</p>
                    </div>
                    <button class="btn-tiny btn-secondary" onclick="handleRunTask('${task.name}')">执行</button>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('加载定时任务状态失败:', error);
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
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} ({d}%)'
        },
        legend: {
            orient: 'vertical',
            left: 'left'
        },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 10,
                borderColor: '#fff',
                borderWidth: 2
            },
            label: {
                show: true,
                formatter: '{b}\n{d}%'
            },
            data: [
                { value: Math.round(winRate * 100), name: '盈利', itemStyle: { color: '#38a169' } },
                { value: Math.round((1 - winRate) * 100), name: '亏损', itemStyle: { color: '#e53e3e' } }
            ]
        }]
    };
    
    perfPieChartInstance.setOption(option);
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
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                const p = params[0];
                return `${p.axisValue}<br/>累计收益: ${p.value.toFixed(2)}%`;
            }
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false
        },
        yAxis: {
            type: 'value',
            axisLabel: {
                formatter: '{value}%'
            }
        },
        series: [{
            type: 'line',
            data: values,
            smooth: true,
            lineStyle: {
                width: 3
            },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(56, 161, 105, 0.3)' },
                        { offset: 1, color: 'rgba(56, 161, 105, 0.05)' }
                    ]
                }
            },
            itemStyle: {
                color: '#38a169'
            }
        }],
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        }
    };
    
    perfLineChartInstance.setOption(option);
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

// 渲染持仓表格
function renderPositionsTable(positions) {
    const tbody = document.getElementById('positionsTableBody');
    
    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="9">暂无持仓记录</td></tr>';
        return;
    }
    
    tbody.innerHTML = positions.map(p => `
        <tr>
            <td>${p.stock_code}</td>
            <td>${p.stock_name}</td>
            <td>¥${p.entry_price.toFixed(2)}</td>
            <td>${p.shares}</td>
            <td>${p.entry_date}</td>
            <td>${p.holding_days}天</td>
            <td class="${p.profit_rate >= 0 ? 'text-success' : 'text-danger'}">
                ${p.profit_rate >= 0 ? '+' : ''}¥${(p.profit_loss || 0).toFixed(2)}
            </td>
            <td class="${p.profit_rate >= 0 ? 'text-success' : 'text-danger'}">
                ${p.profit_rate >= 0 ? '+' : ''}${(p.profit_rate * 100).toFixed(2)}%
            </td>
            <td>
                <button class="btn-tiny btn-danger" onclick="handleClosePosition('${p.stock_code}')">平仓</button>
            </td>
        </tr>
    `).join('');
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

// 渲染信号表格
function renderSignalsTable(signals) {
    const tbody = document.getElementById('signalsTableBody');
    
    if (!signals || signals.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="10">暂无历史信号</td></tr>';
        return;
    }
    
    tbody.innerHTML = signals.map(s => `
        <tr>
            <td>${s.stock_code}</td>
            <td>${s.stock_name}</td>
            <td>${s.signal_type}</td>
            <td>¥${s.entry_price.toFixed(2)}</td>
            <td>${s.exit_price ? '¥' + s.exit_price.toFixed(2) : '--'}</td>
            <td>${s.signal_date}</td>
            <td>${s.close_date || '--'}</td>
            <td>${s.holding_days || '--'}</td>
            <td class="${s.profit_rate >= 0 ? 'text-success' : 'text-danger'}">
                ${s.profit_rate >= 0 ? '+' : ''}${(s.profit_rate * 100).toFixed(2)}%
            </td>
            <td><span class="status-badge status-${s.status}">${s.status}</span></td>
        </tr>
    `).join('');
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
