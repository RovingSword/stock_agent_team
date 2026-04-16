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
};

// SSE连接
let eventSource = null;

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
            // 刷新历史记录
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
                user_request: '分析是否适合中短线买入'
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

        summaryElement.textContent = getAgentSummaryText(data);
        summaryElement.classList.toggle('hidden', !getAgentSummaryText(data));
        analysisElement.textContent = getAgentPrimaryAnalysisText(data);
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
            <div class="message-content">${escapeHtml(data.content)}</div>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', html);
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
}

/**
 * 渲染最终决策
 */
function renderFinalDecision(data) {
    const html = `
        <div class="final-decision-card">
            <div class="decision-header">
                <span class="decision-icon">🎯</span>
                <span class="decision-title">最终决策</span>
            </div>
            <div class="decision-content">
                <div class="decision-action ${data.final_action || 'watch'}">${data.action_text || getActionText(data.final_action)}</div>
                <div class="decision-score">
                    综合评分: <strong>${(data.composite_score || 0).toFixed(1)}</strong>/10
                </div>
                <div class="decision-summary">${escapeHtml(data.summary || data.analysis || '综合分析完成')}</div>
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
    
    // 基本信息
    document.getElementById('stockTitle').textContent = 
        `${data.stock_name || '--'}(${data.stock_code || '--'})`;

    // 动作徽章
    const actionBadge = document.getElementById('actionBadge');
    actionBadge.textContent = data.action_text || getActionText(data.final_action);
    actionBadge.className = `action-badge ${data.final_action || 'watch'}`;

    // 综合评分
    const compositeScore = data.composite_score || 0;
    document.getElementById('compositeScore').textContent = compositeScore.toFixed(1);

    // 置信度
    document.getElementById('confidenceText').textContent = 
        getConfidenceText(data.confidence);
    
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
        buyReasonsList.innerHTML = buyReasons.map(r => `<li>${escapeHtml(r)}</li>`).join('');
    } else {
        buyReasonsList.innerHTML = '<li>暂无</li>';
    }
    
    // 风险提示
    const riskWarnings = data.risk_warnings || [];
    const riskWarningsList = document.getElementById('riskWarnings');
    if (riskWarnings.length > 0) {
        riskWarningsList.innerHTML = riskWarnings.map(r => `<li>${escapeHtml(r)}</li>`).join('');
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
    document.getElementById(`${prefix}Comment`).textContent = 
        getAgentPrimaryAnalysisText(score);
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
            <div class="agent-analysis-summary ${summaryText ? '' : 'hidden'}">${escapeHtml(summaryText)}</div>
            <div class="agent-analysis-text">${escapeHtml(analysisText)}</div>
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
    
    // 基本信息
    document.getElementById('stockTitle').textContent = 
        `${data.stock_name}(${data.stock_code})`;
    
    // 动作徽章
    const actionBadge = document.getElementById('actionBadge');
    actionBadge.textContent = getActionText(data.final_action);
    actionBadge.className = `action-badge ${data.final_action}`;
    
    // 综合评分
    document.getElementById('compositeScore').textContent = 
        data.composite_score.toFixed(1);
    
    // 置信度
    document.getElementById('confidenceText').textContent = 
        getConfidenceText(data.confidence);
    
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
        buyReasonsList.innerHTML = buyReasons.map(r => `<li>${escapeHtml(r)}</li>`).join('');
    } else {
        buyReasonsList.innerHTML = '<li>暂无</li>';
    }
    
    // 风险提示
    const riskWarnings = data.rationale?.risk_warnings || [];
    const riskWarningsList = document.getElementById('riskWarnings');
    if (riskWarnings.length > 0) {
        riskWarningsList.innerHTML = riskWarnings.map(r => `<li>${escapeHtml(r)}</li>`).join('');
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
    document.getElementById(`${prefix}Comment`).textContent = 
        agentData.comment || '暂无评价';
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

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getAgentDiscussionCardId,
        getAgentSummaryText,
        getAgentPrimaryAnalysisText,
        buildAgentAnalysisCardHtml,
    };
}
