/**
 * 股票Agent分析系统 - 前端逻辑
 * 支持规则引擎和LLM Agent两种分析模式
 */

// API基础地址
const API_BASE = '';

// DOM元素
const elements = {
    stockCode: document.getElementById('stockCode'),
    stockName: document.getElementById('stockName'),
    analyzeBtn: document.getElementById('analyzeBtn'),
    loadingSection: document.getElementById('loadingSection'),
    discussionSection: document.getElementById('discussionSection'),
    discussionContent: document.getElementById('discussionContent'),
    discussionStatus: document.getElementById('discussionStatus'),
    resultSection: document.getElementById('resultSection'),
    errorSection: document.getElementById('errorSection'),
    historySection: document.getElementById('historySection'),
    refreshHistory: document.getElementById('refreshHistory'),
    klineSection: document.getElementById('klineSection'),
    klineChart: document.getElementById('klineChart'),
    klineStatus: document.getElementById('klineStatus'),
};

// SSE连接
let eventSource = null;

// K线图 ECharts 实例与缓存数据
let klineChartInstance = null;
let klineDataCache = null;

let markedMarkdownConfigured = false;

function ensureMarkedConfigured() {
    if (markedMarkdownConfigured) return;
    if (typeof marked !== 'undefined' && typeof marked.use === 'function') {
        marked.use({ gfm: true, breaks: true });
    }
    markedMarkdownConfigured = true;
}

/**
 * 将 Markdown 转为可安全插入 DOM 的 HTML（依赖 marked + DOMPurify）
 */
function renderMarkdown(text) {
    if (text == null || text === '') return '';
    const raw = String(text);
    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        return escapeHtml(raw);
    }
    ensureMarkedConfigured();
    const html = marked.parse(raw);
    return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadHistory();
});

/**
 * 初始化事件监听
 */
function initEventListeners() {
    // 分析按钮
    elements.analyzeBtn.addEventListener('click', handleAnalyze);
    
    // 回车键触发分析
    elements.stockCode.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleAnalyze();
    });
    
    // 刷新历史记录
    elements.refreshHistory.addEventListener('click', loadHistory);
    
    // 模式切换
    document.querySelectorAll('input[name="analyzeMode"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            updateAnalyzeButton(e.target.value);
        });
    });
}

/**
 * 更新分析按钮文本
 */
function updateAnalyzeButton(mode) {
    const btnIcon = elements.analyzeBtn.querySelector('.btn-icon');
    if (mode === 'llm') {
        btnIcon.textContent = '🤖';
    } else {
        btnIcon.textContent = '🔍';
    }
}

/**
 * 获取当前选择的分析模式
 */
function getAnalyzeMode() {
    const selected = document.querySelector('input[name="analyzeMode"]:checked');
    return selected ? selected.value : 'rule';
}

/**
 * 处理分析请求
 */
async function handleAnalyze() {
    const stockCode = elements.stockCode.value.trim();
    const mode = getAnalyzeMode();
    
    if (!stockCode) {
        showError('请输入股票代码');
        return;
    }
    
    // 关闭之前的SSE连接
    closeEventSource();
    
    if (mode === 'llm') {
        // LLM模式：使用SSE
        handleLLMAnalyze(stockCode);
    } else {
        // 规则引擎模式
        handleRuleAnalyze(stockCode);
    }
}

/**
 * 规则引擎分析
 */
async function handleRuleAnalyze(stockCode) {
    showLoading();
    
    loadKlineChart(stockCode);
    
    try {
        const response = await fetch(`${API_BASE}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                stock_code: stockCode,
                stock_name: elements.stockName.value.trim() || undefined,
                user_request: '分析是否适合中短线买入'
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            displayResult(result.data);
            updateChartAnnotations(result.data);
            loadHistory();
        } else {
            showError(result.message || '分析失败');
        }
    } catch (error) {
        console.error('分析请求失败:', error);
        showError('网络错误，请检查服务是否启动');
    } finally {
        hideLoading();
    }
}

/**
 * LLM Agent分析（使用SSE）
 */
async function handleLLMAnalyze(stockCode) {
    // 显示讨论区域
    elements.loadingSection.classList.add('hidden');
    elements.resultSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
    elements.discussionSection.classList.remove('hidden');
    elements.discussionSection.classList.remove('analysis-complete');

    // 并行加载K线图
    loadKlineChart(stockCode);

    // 清空讨论内容
    elements.discussionContent.innerHTML = '';
    elements.discussionStatus.textContent = '准备中';
    
    // 禁用按钮
    elements.analyzeBtn.disabled = true;
    
    // 添加初始加载动画
    addLoadingIndicator();
    
    try {
        // 使用fetch + ReadableStream实现SSE（因为EventSource不支持POST）
        const stockName = elements.stockName.value.trim() || stockCode;
        const url = `${API_BASE}/api/analyze_llm`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                stock_code: stockCode,
                stock_name: elements.stockName.value.trim() || undefined,
                user_request: '分析是否适合中短线买入',
                force_refresh: document.getElementById('forceRefreshIntel')?.checked || false
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // 处理SSE数据
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            let currentEventType = 'message';
            for (const line of lines) {
                if (line.startsWith('event:')) {
                    currentEventType = line.slice(6).trim();
                    continue;
                }
                if (line.startsWith('data:')) {
                    const data = line.slice(5).trim();
                    handleSSEMessage(currentEventType, data);
                    currentEventType = 'message';  // 重置，避免影响下一个事件
                }
            }
        }
        
    } catch (error) {
        console.error('SSE连接失败:', error);
        showError('SSE连接失败: ' + error.message);
        elements.discussionSection.classList.add('hidden');
    } finally {
        elements.analyzeBtn.disabled = false;
    }
}

/**
 * 处理SSE消息
 */
function handleSSEMessage(eventType, dataStr) {
    try {
        const data = JSON.parse(dataStr);
        
        switch (eventType) {
            case 'start':
                elements.discussionStatus.textContent = '初始化中...';
                break;
                
            case 'status':
                // 状态更新事件
                if (data.message) {
                    elements.discussionStatus.textContent = data.message;
                }
                break;

            case 'rule_analysis':
                elements.discussionStatus.textContent = '规则引擎分析完成';
                break;
                
            case 'intel_injected':
                // 情报注入事件
                const cacheStatus = data.cache_status || 'unknown';
                const cacheLabel = cacheStatus === 'fresh' ? '新鲜缓存' :
                                  cacheStatus === 'stale' ? '缓存过时' :
                                  cacheStatus === 'expired' ? '缓存已过期' : '全新搜索';
                elements.discussionStatus.textContent = `情报已注入 (${cacheLabel}: ${data.news_count || 0}条新闻, ${data.research_count || 0}条研报)`;
                // 在讨论区显示情报注入消息
                const intelMsg = document.createElement('div');
                intelMsg.className = 'discussion-msg system-msg';
                intelMsg.innerHTML = `<span class="msg-icon">📡</span> <strong>情报注入</strong>: ${cacheLabel} | ${data.news_count || 0}条新闻, ${data.research_count || 0}条研报, ${data.sentiment_count || 0}条舆情`;
                elements.discussionContent.appendChild(intelMsg);
                break;

            case 'round_start':
                renderRoundStart(data);
                break;
                
            case 'agent_start':
                renderAgentStart(data);
                break;
                
            case 'agent_analysis':
                renderAgentAnalysis(data);
                break;
                
            case 'discussion':
                renderDiscussion(data);
                break;
                
            case 'final_decision':
                renderFinalDecision(data);
                break;
                
            case 'done':
                elements.discussionStatus.textContent = '分析完成 ✓';
                // 更新讨论区域标题
                const discussionHeader = elements.discussionSection.querySelector('.discussion-header h3');
                if (discussionHeader) {
                    discussionHeader.textContent = '🤖 LLM Agent Team 分析完成';
                }
                removeLoadingIndicator();
                displayLLMResult(data);
                // 保持讨论区域可见，不隐藏，并展开显示所有内容
                elements.discussionSection.classList.remove('hidden');
                elements.discussionSection.classList.add('analysis-complete');
                break;
                
            case 'error':
                console.error('SSE错误:', data);
                elements.discussionStatus.textContent = '发生错误';
                showError(data.error || '分析过程出错');
                removeLoadingIndicator();
                break;
        }
    } catch (e) {
        console.error('解析SSE数据失败:', e);
    }
}

/**
 * 渲染讨论轮次开始
 */
function renderRoundStart(data) {
    const round = data.round;
    const title = data.title;
    
    const roundHtml = `
        <div class="discussion-round round-${round}">
            <div class="round-header">
                <span class="round-title">${title}</span>
            </div>
            <div class="round-content" id="round-${round}-content">
            </div>
        </div>
    `;
    
    elements.discussionContent.insertAdjacentHTML('beforeend', roundHtml);
    elements.discussionStatus.textContent = `第${round}轮进行中...`;
    
    // 滚动到底部
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
}

/**
 * 渲染Agent开始分析
 */
function renderAgentStart(data) {
    const round = data.round;
    const container = document.getElementById(`round-${round}-content`) || elements.discussionContent;

    const cardId = getAgentDiscussionCardId(data.agent_role);
    if (!document.getElementById(cardId)) {
        container.insertAdjacentHTML('beforeend', buildAgentAnalysisCardHtml(data, true));
    }
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
}

/**
 * 渲染Agent分析完成
 */
function renderAgentAnalysis(data) {
    const container = document.getElementById(`round-${data.round || 1}-content`) || elements.discussionContent;
    let card = document.getElementById(getAgentDiscussionCardId(data.agent_role));
    
    if (card) {
        card.classList.remove('pending');
        const summaryElement = card.querySelector('.agent-analysis-summary');
        const analysisElement = card.querySelector('.agent-analysis-text');

        const summaryText = getAgentSummaryText(data);
        summaryElement.classList.toggle('hidden', !summaryText);
        summaryElement.classList.add('markdown-body');
        summaryElement.innerHTML = summaryText ? renderMarkdown(summaryText) : '';
        analysisElement.classList.add('markdown-body');
        analysisElement.innerHTML = renderMarkdown(getAgentPrimaryAnalysisText(data));
        card.querySelector('.agent-score-value').textContent = (data.score || 0).toFixed(1);
    } else {
        container.insertAdjacentHTML('beforeend', buildAgentAnalysisCardHtml(data, false));
    }
    
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
}

/**
 * 渲染讨论消息
 */
function renderDiscussion(data) {
    const container = document.getElementById(`round-${data.round || 2}-content`) || elements.discussionContent;

    const html = `
        <div class="discussion-message ${data.type || 'message'}">
            <div class="message-header">
                <span class="message-avatar">${getAvatarByRole(data.agent_role)}</span>
                <span class="message-name">${data.agent_name}</span>
            </div>
            <div class="message-content markdown-body">${renderMarkdown(data.content)}</div>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', html);
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
}

/**
 * 渲染最终决策
 */
function renderFinalDecision(data) {
    const action = data.final_action || 'watch';
    const shortLabel = getActionText(action);
    const rawAdvice = (data.action_text || '').trim();
    const showAdviceDetail =
        rawAdvice &&
        rawAdvice.replace(/\s/g, '') !== String(shortLabel).replace(/\s/g, '');
    const adviceBlock = showAdviceDetail
        ? `<div class="decision-action-detail markdown-body">${renderMarkdown(rawAdvice)}</div>`
        : '';
    const scoreVal = (data.composite_score || 0).toFixed(1);
    const html = `
        <div class="final-decision-card">
            <div class="decision-header">
                <span class="decision-icon">🎯</span>
                <span class="decision-title">最终决策</span>
            </div>
            <div class="decision-content">
                <div class="decision-action-row">
                    <span class="decision-action ${action}">${escapeHtml(shortLabel)}</span>
                </div>
                ${adviceBlock}
                <div class="decision-score" aria-label="综合评分 ${scoreVal} 分">
                    <span class="decision-score-label">综合评分</span>
                    <span class="decision-score-main">
                        <span class="decision-score-number">${scoreVal}</span><span class="decision-score-denom">/10</span>
                    </span>
                </div>
                <div class="decision-summary markdown-body">${renderMarkdown(data.summary || data.analysis || '综合分析完成')}</div>
            </div>
        </div>
    `;
    
    elements.discussionContent.insertAdjacentHTML('beforeend', html);
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
}

/**
 * 根据角色获取头像
 */
function getAvatarByRole(role) {
    const avatars = {
        'leader': '👔',
        'technical': '🔧',
        'intelligence': '📡',
        'risk': '🛡️',
        'fundamental': '📈'
    };
    return avatars[role] || '🤖';
}

/**
 * 添加加载指示器
 */
function addLoadingIndicator() {
    const html = `
        <div class="discussion-loading" id="discussionLoading">
            <div class="loading-dots">
                <span></span><span></span><span></span><span></span>
            </div>
            <p>正在连接LLM Agent团队...</p>
        </div>
    `;
    elements.discussionContent.insertAdjacentHTML('beforeend', html);
}

/**
 * 移除加载指示器
 */
function removeLoadingIndicator() {
    const loader = document.getElementById('discussionLoading');
    if (loader) {
        loader.remove();
    }
}

/**
 * 关闭SSE连接
 */
function closeEventSource() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

/**
 * 显示分析结果（从SSE数据）
 */
function displayLLMResult(data) {
    // 不再隐藏讨论区域，让用户可以看到分析过程
    elements.resultSection.classList.remove('hidden');
    
    // 叠加 Agent 分析标注到 K 线图
    updateChartAnnotations(data);
    
    // Agent评分
    const agentScores = data.agent_scores || [];
    agentScores.forEach(score => {
        updateAgentCardFromLLM(score);
    });
    
    // 交易建议
    const entryZone = data.entry_zone;
    document.getElementById('entryZone').textContent =
        entryZone && entryZone.length > 0
            ? `${entryZone[0]} - ${entryZone[entryZone.length - 1]}`
            : '--';
    document.getElementById('stopLoss').textContent = 
        data.stop_loss ? (typeof data.stop_loss === 'number' ? data.stop_loss.toFixed(2) : data.stop_loss) : '--';
    document.getElementById('takeProfit1').textContent =
        data.take_profit_1 ? (typeof data.take_profit_1 === 'number' ? data.take_profit_1.toFixed(2) : data.take_profit_1) : '--';
    document.getElementById('takeProfit2').textContent =
        data.take_profit_2 ? (typeof data.take_profit_2 === 'number' ? data.take_profit_2.toFixed(2) : data.take_profit_2) : '--';
    document.getElementById('positionSize').textContent =
        data.position_size ? `${(data.position_size * 100).toFixed(0)}%` : '--';
    
    // 买入理由
    const buyReasons = data.buy_reasons || [];
    const buyReasonsList = document.getElementById('buyReasons');
    if (buyReasons.length > 0) {
        buyReasonsList.innerHTML = buyReasons.map(r => `<li><div class="markdown-body">${renderMarkdown(r)}</div></li>`).join('');
    } else {
        buyReasonsList.innerHTML = '<li>暂无</li>';
    }
    
    // 风险提示
    const riskWarnings = data.risk_warnings || [];
    const riskWarningsList = document.getElementById('riskWarnings');
    if (riskWarnings.length > 0) {
        riskWarningsList.innerHTML = riskWarnings.map(r => `<li><div class="markdown-body">${renderMarkdown(r)}</div></li>`).join('');
    } else {
        riskWarningsList.innerHTML = '<li>暂无</li>';
    }

    // 滚动到结果区域
    elements.resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * 更新Agent卡片（从LLM数据）
 */
function updateAgentCardFromLLM(score) {
    const roleMap = {
        'technical': 'tech',
        'intelligence': 'intel',
        'risk': 'risk',
        'fundamental': 'fund'
    };
    
    const prefix = roleMap[score.agent_role];
    if (!prefix) return;
    
    document.getElementById(`${prefix}Score`).textContent = 
        (score.score || 0).toFixed(1);
    document.getElementById(`${prefix}Weight`).textContent =
        typeof score.weight === 'number' ? `${(score.weight * 100).toFixed(0)}%` : '--';
    const commentEl = document.getElementById(`${prefix}Comment`);
    commentEl.classList.add('markdown-body');
    commentEl.innerHTML = renderMarkdown(getAgentPrimaryAnalysisText(score));
}

function getAgentDiscussionCardId(agentRole) {
    return `agent-card-${agentRole}`;
}

function getAgentSummaryText(data) {
    return data.summary || '';
}

function getAgentPrimaryAnalysisText(data) {
    return data.analysis || data.summary || '分析完成';
}

function buildAgentAnalysisCardHtml(data, pending = false) {
    const summaryText = getAgentSummaryText(data);
    const analysisText = pending ? '正在分析...' : getAgentPrimaryAnalysisText(data);

    const summaryBlock = `<div class="agent-analysis-summary markdown-body ${summaryText ? '' : 'hidden'}">${summaryText ? renderMarkdown(summaryText) : ''}</div>`;
    const analysisBlock = pending
        ? `<div class="agent-analysis-text">${escapeHtml(analysisText)}</div>`
        : `<div class="agent-analysis-text markdown-body">${renderMarkdown(analysisText)}</div>`;

    return `
        <div class="agent-analysis-card ${pending ? 'pending' : ''}" id="${getAgentDiscussionCardId(data.agent_role)}">
            <div class="analysis-header">
                <span class="analysis-avatar">${data.icon || '🤖'}</span>
                <span class="analysis-name">${data.agent_name}</span>
                <span class="analysis-score ${pending ? 'hidden' : ''}">
                    评分: <span class="agent-score-value">${(data.score || 0).toFixed(1)}</span>/10
                </span>
                ${pending ? `
                <span class="thinking-dots">
                    <span></span><span></span><span></span>
                </span>
                ` : ''}
            </div>
            ${summaryBlock}
            ${analysisBlock}
        </div>
    `;
}

/**
 * 显示分析结果
 */
function displayResult(data) {
    // 隐藏错误区域和讨论区域
    elements.errorSection.classList.add('hidden');
    elements.discussionSection.classList.add('hidden');
    
    // 显示结果区域
    elements.resultSection.classList.remove('hidden');
    
    // Agent评分
    const agentScores = data.agent_scores || [];
    updateAgentCard('tech', agentScores.find(s => s.agent_type === 'technical'));
    updateAgentCard('intel', agentScores.find(s => s.agent_type === 'intelligence'));
    updateAgentCard('risk', agentScores.find(s => s.agent_type === 'risk'));
    updateAgentCard('fund', agentScores.find(s => s.agent_type === 'fundamental'));
    
    // 交易建议
    const execution = data.execution || {};
    document.getElementById('entryZone').textContent = 
        execution.entry_zone && execution.entry_zone.length > 0 
            ? `${execution.entry_zone[0]} - ${execution.entry_zone[execution.entry_zone.length - 1]}` 
            : '--';
    document.getElementById('stopLoss').textContent = 
        execution.stop_loss ? execution.stop_loss.toFixed(2) : '--';
    document.getElementById('takeProfit1').textContent = 
        execution.take_profit_1 ? execution.take_profit_1.toFixed(2) : '--';
    document.getElementById('takeProfit2').textContent = 
        execution.take_profit_2 ? execution.take_profit_2.toFixed(2) : '--';
    document.getElementById('positionSize').textContent = 
        execution.position_size ? `${(execution.position_size * 100).toFixed(0)}%` : '--';
    
    // 买入理由
    const buyReasons = data.rationale?.buy_reasons || [];
    const buyReasonsList = document.getElementById('buyReasons');
    if (buyReasons.length > 0) {
        buyReasonsList.innerHTML = buyReasons.map(r => `<li><div class="markdown-body">${renderMarkdown(r)}</div></li>`).join('');
    } else {
        buyReasonsList.innerHTML = '<li>暂无</li>';
    }
    
    // 风险提示
    const riskWarnings = data.rationale?.risk_warnings || [];
    const riskWarningsList = document.getElementById('riskWarnings');
    if (riskWarnings.length > 0) {
        riskWarningsList.innerHTML = riskWarnings.map(r => `<li><div class="markdown-body">${renderMarkdown(r)}</div></li>`).join('');
    } else {
        riskWarningsList.innerHTML = '<li>暂无</li>';
    }
}

/**
 * 更新Agent卡片
 */
function updateAgentCard(prefix, agentData) {
    if (!agentData) return;
    
    document.getElementById(`${prefix}Score`).textContent = 
        agentData.score ? agentData.score.toFixed(1) : '0.0';
    document.getElementById(`${prefix}Weight`).textContent = 
        agentData.weight ? `${(agentData.weight * 100).toFixed(0)}%` : '--';
    const commentEl = document.getElementById(`${prefix}Comment`);
    commentEl.classList.add('markdown-body');
    commentEl.innerHTML = renderMarkdown(agentData.comment || '暂无评价');
}

/**
 * 加载历史记录
 */
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/history?limit=10`);
        const result = await response.json();
        
        if (result.success) {
            displayHistory(result.data || []);
        }
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

/**
 * 显示历史记录
 */
function displayHistory(records) {
    const tbody = document.getElementById('historyTableBody');
    
    if (records.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">暂无历史记录</td></tr>';
        return;
    }
    
    tbody.innerHTML = records.map(record => {
        const statusClass = record.status || 'holding';
        const scoreClass = record.return_rate > 0 ? 'profit-positive' : 
                          record.return_rate < 0 ? 'profit-negative' : '';
        
        return `
            <tr>
                <td>${escapeHtml(record.stock_code)}</td>
                <td>${escapeHtml(record.stock_name)}</td>
                <td>${escapeHtml(record.buy_date)}</td>
                <td>${record.buy_score ? record.buy_score.toFixed(1) : '--'}</td>
                <td><span class="status-badge ${statusClass}">${getStatusText(record.status)}</span></td>
                <td class="${scoreClass}">${formatReturnRate(record.return_rate)}</td>
            </tr>
        `;
    }).join('');
}

/**
 * 显示加载状态
 */
function showLoading() {
    elements.analyzeBtn.disabled = true;
    elements.loadingSection.classList.remove('hidden');
    elements.resultSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
    elements.discussionSection.classList.add('hidden');
}

/**
 * 隐藏加载状态
 */
function hideLoading() {
    elements.analyzeBtn.disabled = false;
    elements.loadingSection.classList.add('hidden');
}

/**
 * 显示错误
 */
function showError(message) {
    elements.errorSection.classList.remove('hidden');
    elements.resultSection.classList.add('hidden');
    elements.discussionSection.classList.add('hidden');
    document.getElementById('errorMessage').textContent = message;
    // K线图保持可见（如果已加载），方便用户参考
}

/**
 * 获取动作文本
 */
function getActionText(action) {
    const actionMap = {
        'buy': '建议买入',
        'strong_buy': '强烈买入',
        'sell': '建议卖出',
        'watch': '观望',
        'hold': '持有',
        'avoid': '回避'
    };
    return actionMap[action] || action || '--';
}

/**
 * 获取置信度文本
 */
function getConfidenceText(confidence) {
    if (typeof confidence === 'number') {
        if (confidence >= 0.8) return '高';
        if (confidence >= 0.5) return '中';
        return '低';
    }
    const confidenceMap = {
        'high': '高',
        'medium': '中',
        'low': '低'
    };
    return confidenceMap[confidence] || confidence || '--';
}

/**
 * 获取状态文本
 */
function getStatusText(status) {
    const statusMap = {
        'holding': '持仓中',
        'closed': '已平仓',
        'cancelled': '已取消',
        'pending': '待执行'
    };
    return statusMap[status] || status || '--';
}

/**
 * 格式化收益率
 */
function formatReturnRate(rate) {
    if (rate === null || rate === undefined) return '--';
    const sign = rate > 0 ? '+' : '';
    return `${sign}${rate.toFixed(2)}%`;
}

/**
 * HTML转义
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// K线图相关功能
// ============================================================

async function fetchKlineData(stockCode) {
    const resp = await fetch(`${API_BASE}/api/kline/${encodeURIComponent(stockCode)}?days=60`);
    if (!resp.ok) throw new Error(`K线数据请求失败: HTTP ${resp.status}`);
    return resp.json();
}

function showKlineSection() {
    elements.klineSection.classList.remove('hidden');
    elements.klineStatus.textContent = '加载中...';
}

function hideKlineSection() {
    elements.klineSection.classList.add('hidden');
}

function initKlineChart() {
    if (klineChartInstance) {
        klineChartInstance.dispose();
    }
    klineChartInstance = echarts.init(elements.klineChart);
    window.addEventListener('resize', () => {
        if (klineChartInstance) klineChartInstance.resize();
    });
}

function renderKlineChart(data) {
    klineDataCache = data;
    if (!klineChartInstance) initKlineChart();

    const upColor = '#ef5350';
    const downColor = '#26a69a';

    const volumeColors = data.ohlc.map(item => (item[1] >= item[0]) ? upColor : downColor);

    const option = {
        animation: true,
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                const date = params[0].axisValue;
                let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`;
                for (const p of params) {
                    if (p.seriesType === 'candlestick') {
                        const d = p.data;
                        html += `开: ${d[1]}<br>收: ${d[2]}<br>低: ${d[3]}<br>高: ${d[4]}<br>`;
                    } else if (p.seriesType === 'bar') {
                        html += `成交量: ${Number(p.data).toLocaleString()}<br>`;
                    } else if (p.seriesName && p.data != null) {
                        html += `${p.seriesName}: ${p.data}<br>`;
                    }
                }
                return html;
            }
        },
        grid: [
            { left: '8%', right: '3%', top: '6%', height: '58%' },
            { left: '8%', right: '3%', top: '70%', height: '20%' }
        ],
        xAxis: [
            {
                type: 'category',
                data: data.dates,
                gridIndex: 0,
                axisLine: { lineStyle: { color: '#8392A5' } },
                axisLabel: { fontSize: 10 },
                boundaryGap: true,
                axisPointer: { label: { show: true } }
            },
            {
                type: 'category',
                data: data.dates,
                gridIndex: 1,
                axisLine: { lineStyle: { color: '#8392A5' } },
                axisLabel: { show: false },
                boundaryGap: true
            }
        ],
        yAxis: [
            {
                scale: true,
                gridIndex: 0,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLine: { lineStyle: { color: '#8392A5' } },
                axisLabel: { fontSize: 10 }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLine: { lineStyle: { color: '#8392A5' } },
                axisLabel: { show: false }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: 0,
                end: 100
            },
            {
                type: 'slider',
                xAxisIndex: [0, 1],
                bottom: '2%',
                height: 20,
                start: 0,
                end: 100
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.ohlc,
                itemStyle: {
                    color: upColor,
                    color0: downColor,
                    borderColor: upColor,
                    borderColor0: downColor
                },
                markLine: buildSupportResistanceMarkLines(data.support_levels, data.resistance_levels),
            },
            {
                name: 'MA5',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.ma5,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.2, color: '#ff9800' }
            },
            {
                name: 'MA10',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.2, color: '#2196f3' }
            },
            {
                name: 'MA20',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.2, color: '#9c27b0' }
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: data.volumes,
                itemStyle: {
                    color: function (params) {
                        return volumeColors[params.dataIndex] || '#999';
                    }
                }
            }
        ]
    };

    klineChartInstance.setOption(option, true);
    elements.klineStatus.textContent = `近${data.dates.length}个交易日`;
}

function buildSupportResistanceMarkLines(supportLevels, resistanceLevels) {
    const lines = [];

    if (supportLevels) {
        supportLevels.forEach((price, i) => {
            lines.push({
                yAxis: price,
                name: `支撑${i + 1}`,
                lineStyle: { color: '#4caf50', type: 'dashed', width: 1.5 },
                label: {
                    formatter: `支撑 ${price}`,
                    position: 'insideStartBottom',
                    color: '#4caf50',
                    fontSize: 10
                }
            });
        });
    }

    if (resistanceLevels) {
        resistanceLevels.forEach((price, i) => {
            lines.push({
                yAxis: price,
                name: `阻力${i + 1}`,
                lineStyle: { color: '#f44336', type: 'dashed', width: 1.5 },
                label: {
                    formatter: `阻力 ${price}`,
                    position: 'insideStartTop',
                    color: '#f44336',
                    fontSize: 10
                }
            });
        });
    }

    return { data: lines, silent: true, animation: true };
}

function updateChartAnnotations(analysisData) {
    if (!klineChartInstance || !klineDataCache) return;

    const lastDate = klineDataCache.dates[klineDataCache.dates.length - 1];
    const markPoints = [];
    const markLines = [];
    const markAreas = [];

    const entryZone = analysisData.entry_zone || (analysisData.execution && analysisData.execution.entry_zone) || [];
    const stopLoss = analysisData.stop_loss || (analysisData.execution && analysisData.execution.stop_loss) || 0;
    const takeProfit1 = analysisData.take_profit_1 || (analysisData.execution && analysisData.execution.take_profit_1) || 0;
    const takeProfit2 = analysisData.take_profit_2 || (analysisData.execution && analysisData.execution.take_profit_2) || 0;
    const finalAction = analysisData.final_action || '';

    if (finalAction === 'buy' || finalAction === 'strong_buy') {
        markPoints.push({
            name: '买入',
            coord: [lastDate, klineDataCache.ohlc[klineDataCache.ohlc.length - 1][2]],
            value: '买',
            itemStyle: { color: '#4caf50' },
            symbol: 'arrow',
            symbolSize: [24, 28],
            symbolRotate: 0,
            label: {
                show: true,
                formatter: '买入',
                color: '#fff',
                fontSize: 10,
                fontWeight: 'bold',
                backgroundColor: '#4caf50',
                padding: [3, 6],
                borderRadius: 3,
                offset: [0, -10]
            }
        });
    } else if (finalAction === 'sell' || finalAction === 'avoid') {
        markPoints.push({
            name: '卖出',
            coord: [lastDate, klineDataCache.ohlc[klineDataCache.ohlc.length - 1][4]],
            value: '卖',
            itemStyle: { color: '#f44336' },
            symbol: 'arrow',
            symbolSize: [24, 28],
            symbolRotate: 180,
            label: {
                show: true,
                formatter: finalAction === 'sell' ? '卖出' : '回避',
                color: '#fff',
                fontSize: 10,
                fontWeight: 'bold',
                backgroundColor: '#f44336',
                padding: [3, 6],
                borderRadius: 3,
                offset: [0, 10]
            }
        });
    }

    if (stopLoss > 0) {
        markLines.push({
            yAxis: stopLoss,
            name: '止损',
            lineStyle: { color: '#f44336', type: 'dotted', width: 2 },
            label: {
                formatter: `止损 ${stopLoss}`,
                position: 'insideEndTop',
                color: '#f44336',
                fontSize: 10,
                fontWeight: 'bold'
            }
        });
    }

    if (takeProfit1 > 0) {
        markLines.push({
            yAxis: takeProfit1,
            name: '止盈1',
            lineStyle: { color: '#2196f3', type: 'dotted', width: 1.5 },
            label: {
                formatter: `止盈1 ${takeProfit1}`,
                position: 'insideEndTop',
                color: '#2196f3',
                fontSize: 10
            }
        });
    }

    if (takeProfit2 > 0) {
        markLines.push({
            yAxis: takeProfit2,
            name: '止盈2',
            lineStyle: { color: '#1565c0', type: 'dotted', width: 1.5 },
            label: {
                formatter: `止盈2 ${takeProfit2}`,
                position: 'insideEndTop',
                color: '#1565c0',
                fontSize: 10
            }
        });
    }

    if (entryZone.length >= 2) {
        markAreas.push([
            { yAxis: entryZone[0], itemStyle: { color: 'rgba(33,150,243,0.08)' } },
            { yAxis: entryZone[entryZone.length - 1] }
        ]);
        markLines.push({
            yAxis: entryZone[0],
            name: '入场下沿',
            lineStyle: { color: '#2196f3', type: 'dashed', width: 1 },
            label: { formatter: `入场 ${entryZone[0]}`, position: 'insideStartBottom', color: '#2196f3', fontSize: 9 }
        });
        markLines.push({
            yAxis: entryZone[entryZone.length - 1],
            name: '入场上沿',
            lineStyle: { color: '#2196f3', type: 'dashed', width: 1 },
            label: { formatter: `入场 ${entryZone[entryZone.length - 1]}`, position: 'insideStartTop', color: '#2196f3', fontSize: 9 }
        });
    }

    const existingLines = (klineChartInstance.getOption().series[0].markLine || {}).data || [];

    klineChartInstance.setOption({
        series: [{
            name: 'K线',
            markPoint: { data: markPoints, animation: true, animationDuration: 600 },
            markLine: { data: [...existingLines, ...markLines], silent: true, animation: true, animationDuration: 600 },
            markArea: { data: markAreas, silent: true, animation: true, animationDuration: 600 }
        }]
    });
}

async function loadKlineChart(stockCode) {
    try {
        showKlineSection();
        if (typeof echarts === 'undefined') {
            elements.klineStatus.textContent = 'ECharts 未加载';
            return;
        }
        initKlineChart();
        const data = await fetchKlineData(stockCode);
        renderKlineChart(data);
    } catch (err) {
        console.error('K线图加载失败:', err);
        elements.klineStatus.textContent = 'K线数据加载失败';
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getAgentDiscussionCardId,
        getAgentSummaryText,
        getAgentPrimaryAnalysisText,
        buildAgentAnalysisCardHtml,
        renderMarkdown,
    };
}
