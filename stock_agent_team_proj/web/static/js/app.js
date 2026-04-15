/**
 * 股票Agent分析系统 - 前端逻辑
 */

// API基础地址
const API_BASE = '';

// DOM元素
const elements = {
    stockCode: document.getElementById('stockCode'),
    stockName: document.getElementById('stockName'),
    analyzeBtn: document.getElementById('analyzeBtn'),
    loadingSection: document.getElementById('loadingSection'),
    resultSection: document.getElementById('resultSection'),
    errorSection: document.getElementById('errorSection'),
    historySection: document.getElementById('historySection'),
    refreshHistory: document.getElementById('refreshHistory'),
};

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
}

/**
 * 处理分析请求
 */
async function handleAnalyze() {
    const stockCode = elements.stockCode.value.trim();
    
    if (!stockCode) {
        showError('请输入股票代码');
        return;
    }
    
    // 显示加载状态
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
 * 显示分析结果
 */
function displayResult(data) {
    // 隐藏错误区域
    elements.errorSection.classList.add('hidden');
    
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
