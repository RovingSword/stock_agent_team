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
    dataMockBanner: document.getElementById('dataMockBanner'),
    dismissDataMock: document.getElementById('dismissDataMock'),
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
    if (elements.dismissDataMock) {
        elements.dismissDataMock.addEventListener('click', () => setDataMockBanner(false));
    }
});

/**
 * 展示或隐藏「模拟/兜底数据」顶栏
 */
function setDataMockBanner(visible) {
    if (!elements.dataMockBanner) return;
    elements.dataMockBanner.classList.toggle('hidden', !visible);
}

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
 * 更新分析按钮文本（图标通过 CSS + SVG 固定，按钮文字维持不变）
 */
function updateAnalyzeButton(_mode) {
    // 图标改用 SVG symbol，不再根据模式动态切换 emoji。
    // 保留函数以兼容现有监听器。
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

    // 从 file:// 打开时 fetch 会失败（浏览器对本地文件有跨域/安全限制）
    if (window.location.protocol === 'file:') {
        showError('请通过本机 Web 服务访问：在项目目录启动 uvicorn 后打开 http://127.0.0.1:8000/，不要双击用「文件」方式直接打开 index.html。');
        return;
    }
    setDataMockBanner(false);
    
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
            if (result.data && result.data.data_uses_mock) {
                setDataMockBanner(true);
            }
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
    elements.discussionSection.classList.add('discussion--glass');

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
        const msg = error && error.message ? error.message : String(error);
        showError(
            'SSE连接失败: ' + msg +
            '。请确认本机已启动 Web 服务，并用与接口相同的源访问（例如 http://127.0.0.1:8000/）。'
        );
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
                if (data.data && data.data.data_uses_mock) {
                    setDataMockBanner(true);
                }
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
                intelMsg.innerHTML = `<span class="msg-icon"><svg class="icon icon-sm" aria-hidden="true"><use href="#i-radio"/></svg></span> <strong>情报注入</strong>：${escapeHtml(cacheLabel)} · ${data.news_count || 0} 条新闻 · ${data.research_count || 0} 条研报 · ${data.sentiment_count || 0} 条舆情`;
                elements.discussionContent.appendChild(intelMsg);
                break;

            case 'round_start':
                renderDiscussionRoundStart(data);
                break;

            case 'agent_start':
                ensureDiscussionTimelineLayout();
                renderAgentStart(data);
                if (data.agent_role) {
                    elements.discussionStatus.textContent = `${getAgentLabel(data.agent_role)} 分析中…`;
                }
                break;

            case 'agent_analysis':
                ensureDiscussionTimelineLayout();
                renderAgentAnalysis(data);
                if (data.agent_role) {
                    elements.discussionStatus.textContent = `${getAgentLabel(data.agent_role)} 分析完成`;
                }
                break;

            case 'discussion':
                renderDiscussionRich(data);
                break;

            case 'discussion_focus':
                renderDiscussionFocusBanner(data);
                break;
                
            case 'final_decision':
                renderFinalDecision(data);
                break;

            case 'done': {
                const enriched = enrichLlmResultWithPerAgentScores(data);
                elements.discussionStatus.textContent = '分析完成';
                if (enriched.data_uses_mock) {
                    setDataMockBanner(true);
                }
                // 更新讨论区域标题文本（保留已有 SVG 图标）
                updateDiscussionHeaderText('LLM Agent Team 分析完成');
                removeLoadingIndicator();

                // 使用增强可视化结果（雷达图 + 置信度卡片 + 决策卡）
                renderEnhancedResult(enriched);
                updateChartAnnotations(enriched);

                elements.discussionSection.classList.remove('hidden');
                elements.discussionSection.classList.add('analysis-complete');
                break;
            }
                
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
 * 更新讨论区标题文本，保留已有的 SVG 图标节点。
 */
function updateDiscussionHeaderText(text) {
    const header = elements.discussionSection.querySelector('.discussion-header h3');
    if (!header) return;
    const iconSvg = header.querySelector('svg');
    header.textContent = '';
    if (iconSvg) header.appendChild(iconSvg);
    header.appendChild(document.createTextNode(' ' + text));
}

/**
 * 角色键规范化：把 agent_role / agent_type 统一映射到 4 类英文 role。
 */
function normalizeAgentRole(role) {
    if (!role) return 'unknown';
    const map = {
        'technical': 'technical',
        '技术分析员': 'technical',
        'tech': 'technical',
        'intelligence': 'intelligence',
        '情报员': 'intelligence',
        'intel': 'intelligence',
        'risk': 'risk',
        '风控官': 'risk',
        'fundamental': 'fundamental',
        '基本面分析师': 'fundamental',
        '基本面分析员': 'fundamental',
        'fund': 'fundamental',
        'leader': 'leader',
        '领队': 'leader',
    };
    return map[role] || 'unknown';
}

/**
 * SSE 终态里 per-agent 分数在 agent_scores 数组中；雷达图与增强卡片读取 tech_score 等平铺字段。
 * 将二者对齐，避免界面一直显示 0。
 */
function enrichLlmResultWithPerAgentScores(data) {
    if (!data) return data;
    const out = { ...data };
    const list = out.agent_scores;
    if (!Array.isArray(list) || list.length === 0) return out;
    for (const s of list) {
        const role = normalizeAgentRole(s.agent_role || s.agent_type);
        if (role === 'leader' || role === 'unknown') continue;
        const raw = s.score;
        const sc = typeof raw === 'number' && !Number.isNaN(raw)
            ? raw
            : (parseFloat(raw) || 0);
        if (role === 'technical') out.tech_score = sc;
        else if (role === 'intelligence') out.intel_score = sc;
        else if (role === 'risk') out.risk_score = sc;
        else if (role === 'fundamental') out.fund_score = sc;
    }
    return out;
}

/**
 * 角色对应的 SVG 图标 id。
 */
function getAgentIconId(role) {
    const map = {
        'technical': 'i-chart',
        'intelligence': 'i-radio',
        'risk': 'i-shield',
        'fundamental': 'i-book',
        'leader': 'i-sparkles',
    };
    return map[normalizeAgentRole(role)] || 'i-sparkles';
}

/**
 * 角色中文显示名。
 */
function getAgentLabel(role) {
    const map = {
        'technical': '技术分析员',
        'intelligence': '情报员',
        'risk': '风控官',
        'fundamental': '基本面分析师',
        'leader': '领队',
    };
    return map[normalizeAgentRole(role)] || (role || 'Agent');
}

function ensureDiscussionTimelineLayout() {
    const c = elements.discussionContent;
    if (!c.classList.contains('discussion-timeline')) {
        c.classList.add('discussion-timeline');
    }
    elements.discussionSection.classList.remove('hidden');
}

/**
 * 从文本中尝试解析 JSON 对象（兼容前后夹杂说明的情况）。
 */
function extractJsonObject(text) {
    const t = String(text || '').trim();
    const start = t.indexOf('{');
    const end = t.lastIndexOf('}');
    if (start === -1 || end <= start) return null;
    try {
        return JSON.parse(t.slice(start, end + 1));
    } catch {
        return null;
    }
}

function formatStructuredDiscussionHtml(obj) {
    const blocks = [];
    const meta = [];
    if (obj.stock_name || obj.ticker) {
        meta.push(
            `<div class="ds-title">${escapeHtml([obj.stock_name, obj.ticker].filter(Boolean).join(' · '))}</div>`
        );
    }
    if (obj.decision != null && obj.decision !== '') {
        meta.push(`<span class="ds-badge">${escapeHtml(String(obj.decision))}</span>`);
    }
    if (obj.confidence != null && obj.confidence !== '') {
        const c = obj.confidence;
        meta.push(
            `<span class="ds-meta">置信度 ${escapeHtml(typeof c === 'number' ? c.toFixed(2) : String(c))}</span>`
        );
    }
    if (meta.length) {
        blocks.push(`<div class="ds-head">${meta.join(' ')}</div>`);
    }

    const summary = obj.summary;
    if (summary && typeof summary === 'object' && !Array.isArray(summary)) {
        if (Array.isArray(summary.consensus) && summary.consensus.length) {
            const lis = summary.consensus
                .map((x) => `<li class="markdown-body">${renderMarkdown(String(x))}</li>`)
                .join('');
            blocks.push(`<div class="ds-section"><h4 class="ds-h">共识</h4><ul class="ds-list">${lis}</ul></div>`);
        }
        if (Array.isArray(summary.divergence) && summary.divergence.length) {
            const lis = summary.divergence
                .map((x) => `<li class="markdown-body">${renderMarkdown(String(x))}</li>`)
                .join('');
            blocks.push(`<div class="ds-section"><h4 class="ds-h">分歧</h4><ul class="ds-list">${lis}</ul></div>`);
        }
    } else if (typeof summary === 'string' && summary.trim()) {
        blocks.push(`<div class="ds-section markdown-body">${renderMarkdown(summary)}</div>`);
    }

    if (Array.isArray(obj.reasoning) && obj.reasoning.length) {
        const lis = obj.reasoning
            .map((x) => `<li class="markdown-body">${renderMarkdown(String(x))}</li>`)
            .join('');
        blocks.push(`<div class="ds-section"><h4 class="ds-h">推理链</h4><ul class="ds-list">${lis}</ul></div>`);
    }

    if (obj.agent_scores && typeof obj.agent_scores === 'object' && !Array.isArray(obj.agent_scores)) {
        const rows = Object.entries(obj.agent_scores)
            .map(
                ([k, v]) =>
                    `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(String(v))}</td></tr>`
            )
            .join('');
        blocks.push(
            `<div class="ds-section"><h4 class="ds-h">各维度评分</h4><table class="ds-table"><tbody>${rows}</tbody></table></div>`
        );
    }

    if (obj.data_quality && typeof obj.data_quality === 'object') {
        const dq = obj.data_quality;
        const miss = Array.isArray(dq.missing) ? dq.missing.join('、') : '';
        blocks.push(
            `<div class="ds-section ds-muted">数据完整度：${escapeHtml(String(dq.completeness ?? '—'))}` +
                (miss ? ` · 缺失：${escapeHtml(miss)}` : '') +
                `</div>`
        );
    }

    const analysisStr =
        typeof obj.analysis === 'string' && obj.analysis.trim() ? obj.analysis.trim() : '';
    if (analysisStr) {
        blocks.push(
            `<div class="ds-section"><h4 class="ds-h">补充说明</h4><div class="markdown-body">${renderMarkdown(analysisStr)}</div></div>`
        );
    }

    if (!blocks.length) {
        blocks.push(
            `<pre class="ds-fallback">${escapeHtml(JSON.stringify(obj, null, 2))}</pre>`
        );
    }

    return `<div class="discussion-structured">${blocks.join('\n')}</div>`;
}

function renderDiscussionRich(data) {
    ensureDiscussionTimelineLayout();
    const raw = data.content != null ? String(data.content) : '';
    const parsed = extractJsonObject(raw);
    const useStructured =
        parsed &&
        (parsed.decision != null ||
            (parsed.summary != null && typeof parsed.summary === 'object') ||
            (Array.isArray(parsed.reasoning) && parsed.reasoning.length));

    const inner = useStructured
        ? formatStructuredDiscussionHtml(parsed)
        : `<div class="message-content markdown-body">${renderMarkdown(raw)}</div>`;

    const msgType = ['opening', 'response', 'synthesis', 'message'].includes(data.type)
        ? data.type
        : 'message';
    const html = `
        <div class="discussion-message discussion-message--${msgType}">
            <div class="message-header">
                <span class="message-avatar">${getAvatarByRole(data.agent_role)}</span>
                <span class="message-name">${escapeHtml(data.agent_name || '')}</span>
                ${
                    msgType === 'synthesis'
                        ? '<span class="message-tag">讨论收束</span>'
                        : msgType === 'opening'
                          ? '<span class="message-tag">讨论开场</span>'
                          : ''
                }
            </div>
            ${inner}
        </div>
    `;
    elements.discussionContent.insertAdjacentHTML('beforeend', html);
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
    if (data.agent_role) {
        elements.discussionStatus.textContent = `${getAgentLabel(data.agent_role)} 讨论更新`;
    }
}

function renderDiscussionFocusBanner(meta) {
    removeLoadingIndicator();
    ensureDiscussionTimelineLayout();
    const html = `
        <div class="discussion-focus-banner" role="note">
            <span class="discussion-focus-icon" aria-hidden="true">⚖</span>
            <div class="discussion-focus-body">
                <strong>分歧焦点</strong>（程序提取）：
                ${escapeHtml(meta.high_agent || '')}（${escapeHtml(String(meta.high_score))} 分）
                与 ${escapeHtml(meta.low_agent || '')}（${escapeHtml(String(meta.low_score))} 分）
                相差 <strong>${escapeHtml(String(meta.spread))}</strong> 分
            </div>
        </div>
    `;
    elements.discussionContent.insertAdjacentHTML('beforeend', html);
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
    elements.discussionStatus.textContent = '讨论：对齐分歧焦点';
}

/**
 * 各轮次开始的时间线节点（不清空已有内容，避免冲掉情报注入与 loading 之外的节点）。
 */
function renderDiscussionRoundStart(data) {
    removeLoadingIndicator();
    ensureDiscussionTimelineLayout();
    const container = elements.discussionContent;
    const nodeHTML = `
        <div class="timeline-node stagger-in timeline-node--round">
            <div class="timeline-header">
                <div class="agent-avatar" data-role="leader">
                    <svg class="icon" aria-hidden="true"><use href="#i-sparkles"/></svg>
                </div>
                <div class="timeline-content">
                    <div class="timeline-title-row">
                        <span class="timeline-pill">Round ${escapeHtml(String(data.round || 1))}</span>
                        <span class="timeline-subtle">${escapeHtml(data.title || '分析轮次开始')}</span>
                    </div>
                </div>
            </div>
            <div class="typing-text">正在初始化本回合流程…</div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', nodeHTML);
    container.scrollTop = container.scrollHeight;
    elements.discussionStatus.textContent = data.title || `Round ${data.round || ''}`;
}

/**
 * 兼容旧入口：非 round 的杂项时间线（尽量少用）。
 */
function renderDiscussionTimeline(data) {
    if (data.round && !data.agent_role && !data.agent_type) {
        renderDiscussionRoundStart(data);
        return;
    }
    ensureDiscussionTimelineLayout();
    const role = normalizeAgentRole(data.agent_role || data.agent_type);
    const confidence = typeof data.confidence === 'number'
        ? Math.max(0, Math.min(100, Math.round(data.confidence * (data.confidence <= 1 ? 100 : 1))))
        : Math.floor(Math.random() * 25) + 75;
    const iconId = getAgentIconId(role);
    const agentLabel = escapeHtml(getAgentLabel(data.agent_role || data.agent_type));
    const body =
        data.message ||
        data.analysis_summary ||
        data.content ||
        data.summary ||
        data.analysis ||
        '正在进行深度分析…';
    const nodeHTML = `
        <div class="timeline-node stagger-in">
            <div class="timeline-header">
                <div class="agent-avatar" data-role="${role}">
                    <svg class="icon" aria-hidden="true"><use href="#${iconId}"/></svg>
                </div>
                <div class="timeline-content">
                    <div class="timeline-title-row">
                        <span class="agent-name">${agentLabel}</span>
                        <span class="confidence-ring" data-percent="${confidence}" style="--pct: ${confidence}%"></span>
                        <span class="timeline-pill pill-muted">${confidence}%</span>
                    </div>
                </div>
            </div>
            <div class="typing-text">${renderMarkdown(body)}</div>
        </div>
    `;
    elements.discussionContent.insertAdjacentHTML('beforeend', nodeHTML);
    elements.discussionContent.scrollTop = elements.discussionContent.scrollHeight;
    if (data.status) {
        elements.discussionStatus.textContent = data.status;
    } else if (data.agent_role) {
        elements.discussionStatus.textContent = `${getAgentLabel(data.agent_role)} 分析中…`;
    }
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
                <span class="decision-icon"><svg class="icon" aria-hidden="true"><use href="#i-target"/></svg></span>
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
 * 根据角色返回 SVG 头像片段（供讨论消息使用）。
 */
function getAvatarByRole(role) {
    const iconId = getAgentIconId(role);
    return `<svg class="icon icon-sm" aria-hidden="true"><use href="#${iconId}"/></svg>`;
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

function showLegacyResultView() {
    const legacy = document.getElementById('legacyResultContent');
    const enhanced = document.getElementById('enhancedResultSection');
    if (legacy) legacy.classList.remove('hidden');
    if (enhanced) enhanced.classList.add('hidden');
    elements.resultSection.classList.remove('hidden');
}

function showEnhancedResultView() {
    const legacy = document.getElementById('legacyResultContent');
    const enhanced = document.getElementById('enhancedResultSection');
    if (legacy) legacy.classList.add('hidden');
    if (enhanced) enhanced.classList.remove('hidden');
    elements.resultSection.classList.remove('hidden');
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
    showLegacyResultView();
    
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
    const roleToPrefix = {
        'technical': 'tech',
        'intelligence': 'intel',
        'risk': 'risk',
        'fundamental': 'fund'
    };
    const norm = normalizeAgentRole(score.agent_role || score.agent_type);
    const prefix = roleToPrefix[norm];
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

    const iconId = getAgentIconId(data.agent_role || data.agent_type);
    return `
        <div class="agent-analysis-card ${pending ? 'pending' : ''}" id="${getAgentDiscussionCardId(data.agent_role || data.agent_type)}">
            <div class="analysis-header">
                <span class="analysis-avatar" data-role="${normalizeAgentRole(data.agent_role || data.agent_type)}">
                    <svg class="icon icon-sm" aria-hidden="true"><use href="#${iconId}"/></svg>
                </span>
                <span class="analysis-name">${escapeHtml(data.agent_name || getAgentLabel(data.agent_role))}</span>
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
    showLegacyResultView();
    
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
                <td data-label="代码">${escapeHtml(record.stock_code)}</td>
                <td data-label="名称">${escapeHtml(record.stock_name)}</td>
                <td data-label="分析日期">${escapeHtml(record.buy_date)}</td>
                <td data-label="评分" class="num">${record.buy_score ? record.buy_score.toFixed(1) : '--'}</td>
                <td data-label="状态"><span class="status-badge ${statusClass}">${getStatusText(record.status)}</span></td>
                <td data-label="收益率" class="num ${scoreClass}">${formatReturnRate(record.return_rate)}</td>
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

    const upColor = '#DC2626';   // A 股：涨红
    const downColor = '#16A34A'; // A 股：跌绿
    const gridColor = '#E5E7EB';
    const axisColor = '#9CA3AF';
    const textColor = '#6B7280';

    const volumeColors = data.ohlc.map(item => (item[1] >= item[0]) ? upColor : downColor);

    const option = {
        animation: true,
        textStyle: { color: textColor, fontFamily: 'inherit' },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross', lineStyle: { color: axisColor } },
            backgroundColor: '#FFFFFF',
            borderColor: gridColor,
            borderWidth: 1,
            textStyle: { color: '#111827', fontSize: 12 },
            extraCssText: 'box-shadow: 0 4px 12px rgba(16,24,40,.08); border-radius: 8px;',
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                const date = params[0].axisValue;
                let html = `<div class="tooltip-date">${date}</div>`;
                for (const p of params) {
                    if (p.seriesType === 'candlestick') {
                        const d = p.data;
                        html += `开 ${d[1]} · 收 ${d[2]}<br>低 ${d[3]} · 高 ${d[4]}<br>`;
                    } else if (p.seriesType === 'bar') {
                        html += `成交量 ${Number(p.data).toLocaleString()}<br>`;
                    } else if (p.seriesName && p.data != null) {
                        html += `${p.seriesName} ${p.data}<br>`;
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
                axisLine: { lineStyle: { color: gridColor } },
                axisTick: { lineStyle: { color: gridColor } },
                axisLabel: { fontSize: 10, color: textColor },
                boundaryGap: true,
                axisPointer: { label: { show: true, backgroundColor: '#374151' } }
            },
            {
                type: 'category',
                data: data.dates,
                gridIndex: 1,
                axisLine: { lineStyle: { color: gridColor } },
                axisLabel: { show: false },
                boundaryGap: true
            }
        ],
        yAxis: [
            {
                scale: true,
                gridIndex: 0,
                splitLine: { lineStyle: { color: gridColor } },
                axisLine: { lineStyle: { color: gridColor } },
                axisLabel: { fontSize: 10, color: textColor }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                splitLine: { lineStyle: { color: gridColor } },
                axisLine: { lineStyle: { color: gridColor } },
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
                lineStyle: { width: 1.2, color: '#F59E0B' }
            },
            {
                name: 'MA10',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.2, color: '#2563EB' }
            },
            {
                name: 'MA20',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.2, color: '#7C3AED' }
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

    const SUPPORT_COLOR = '#16A34A';
    const RESIST_COLOR  = '#DC2626';

    if (supportLevels) {
        supportLevels.forEach((price, i) => {
            lines.push({
                yAxis: price,
                name: `支撑${i + 1}`,
                lineStyle: { color: SUPPORT_COLOR, type: 'dashed', width: 1.2 },
                label: {
                    formatter: `支撑 ${price}`,
                    position: 'insideStartBottom',
                    color: SUPPORT_COLOR,
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
                lineStyle: { color: RESIST_COLOR, type: 'dashed', width: 1.2 },
                label: {
                    formatter: `阻力 ${price}`,
                    position: 'insideStartTop',
                    color: RESIST_COLOR,
                    fontSize: 10
                }
            });
        });
    }

    return { data: lines, silent: true, animation: true };
}

/**
 * 将 Agent 团队分析结论叠加到 K 线图上（入场/止损/止盈标记）。
 * 颜色配合 A 股习惯：买入红、卖出绿。
 */
function updateChartAnnotations(analysisData) {
    if (!klineChartInstance || !klineDataCache) return;

    const BUY_COLOR = '#DC2626';   // 涨 / 买入
    const SELL_COLOR = '#16A34A';  // 跌 / 卖出
    const ENTRY_COLOR = '#1E40AF'; // 入场
    const TP_COLOR = '#2563EB';    // 止盈

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
            itemStyle: { color: BUY_COLOR },
            symbol: 'arrow',
            symbolSize: [20, 24],
            symbolRotate: 0,
            label: {
                show: true,
                formatter: '买入',
                color: '#fff',
                fontSize: 10,
                fontWeight: 'bold',
                backgroundColor: BUY_COLOR,
                padding: [3, 6],
                borderRadius: 4,
                offset: [0, -10]
            }
        });
    } else if (finalAction === 'sell' || finalAction === 'avoid') {
        markPoints.push({
            name: '卖出',
            coord: [lastDate, klineDataCache.ohlc[klineDataCache.ohlc.length - 1][4]],
            value: '卖',
            itemStyle: { color: SELL_COLOR },
            symbol: 'arrow',
            symbolSize: [20, 24],
            symbolRotate: 180,
            label: {
                show: true,
                formatter: finalAction === 'sell' ? '卖出' : '回避',
                color: '#fff',
                fontSize: 10,
                fontWeight: 'bold',
                backgroundColor: SELL_COLOR,
                padding: [3, 6],
                borderRadius: 4,
                offset: [0, 10]
            }
        });
    }

    if (stopLoss > 0) {
        markLines.push({
            yAxis: stopLoss,
            name: '止损',
            lineStyle: { color: SELL_COLOR, type: 'dotted', width: 1.5 },
            label: {
                formatter: `止损 ${stopLoss}`,
                position: 'insideEndTop',
                color: SELL_COLOR,
                fontSize: 10,
                fontWeight: 'bold'
            }
        });
    }

    if (takeProfit1 > 0) {
        markLines.push({
            yAxis: takeProfit1,
            name: '止盈1',
            lineStyle: { color: TP_COLOR, type: 'dotted', width: 1.3 },
            label: {
                formatter: `止盈1 ${takeProfit1}`,
                position: 'insideEndTop',
                color: TP_COLOR,
                fontSize: 10
            }
        });
    }

    if (takeProfit2 > 0) {
        markLines.push({
            yAxis: takeProfit2,
            name: '止盈2',
            lineStyle: { color: TP_COLOR, type: 'dotted', width: 1.3 },
            label: {
                formatter: `止盈2 ${takeProfit2}`,
                position: 'insideEndTop',
                color: TP_COLOR,
                fontSize: 10
            }
        });
    }

    if (entryZone.length >= 2) {
        markAreas.push([
            { yAxis: entryZone[0], itemStyle: { color: 'rgba(30, 64, 175, 0.08)' } },
            { yAxis: entryZone[entryZone.length - 1] }
        ]);
        markLines.push({
            yAxis: entryZone[0],
            name: '入场下沿',
            lineStyle: { color: ENTRY_COLOR, type: 'dashed', width: 1 },
            label: { formatter: `入场 ${entryZone[0]}`, position: 'insideStartBottom', color: ENTRY_COLOR, fontSize: 9 }
        });
        markLines.push({
            yAxis: entryZone[entryZone.length - 1],
            name: '入场上沿',
            lineStyle: { color: ENTRY_COLOR, type: 'dashed', width: 1 },
            label: { formatter: `入场 ${entryZone[entryZone.length - 1]}`, position: 'insideStartTop', color: ENTRY_COLOR, fontSize: 9 }
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

/**
 * 渲染 LLM 增强结果区（置信度卡片 + 雷达图 + 决策卡）。
 * 使用设计系统类名，无内联样式。
 */
function renderEnhancedResult(data) {
    const resultSection = document.getElementById('resultSection');
    const enhancedSection = document.getElementById('enhancedResultSection');
    if (!resultSection || !enhancedSection) return;

    const d = enrichLlmResultWithPerAgentScores(data);

    showEnhancedResultView();

    const finalAction = d.final_action || 'watch';
    const actionText = getActionText(finalAction);

    enhancedSection.innerHTML = `
        <div class="enhanced-agent-cards"></div>
        <div id="radarContainer" class="radar-panel"></div>
        <div class="decision-card">
            <div class="decision-title">最终交易决策</div>
            <div id="finalDecisionText" class="decision-text action-${escapeHtml(finalAction)}">${escapeHtml(actionText)}</div>
            <div class="tag-cloud" id="reasonTags"></div>
        </div>
    `;

    renderRadarChart(d);
    renderAgentConfidenceCards(d);

    const tagsEl = document.getElementById('reasonTags');
    if (tagsEl && Array.isArray(d.buy_reasons) && d.buy_reasons.length > 0) {
        tagsEl.innerHTML = d.buy_reasons
            .map(reason => `<span class="tag">${escapeHtml(String(reason))}</span>`)
            .join('');
    }

    enhancedSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * 雷达图：光色主题，单一品牌色。
 */
function renderRadarChart(data) {
    const container = document.getElementById('radarContainer');
    if (!container || typeof echarts === 'undefined') return;

    if (window.radarChartInstance) {
        try { window.radarChartInstance.dispose(); } catch (_) {}
    }

    const chart = echarts.init(container, null, { renderer: 'canvas' });

    const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        radar: {
            indicator: [
                { name: '技术分析', max: 10 },
                { name: '情报收集', max: 10 },
                { name: '风控评估', max: 10 },
                { name: '基本面', max: 10 }
            ],
            center: ['50%', '55%'],
            radius: '68%',
            splitNumber: 5,
            axisName: { color: '#6B7280', fontSize: 12 },
            splitLine: { lineStyle: { color: '#E5E7EB' } },
            axisLine: { lineStyle: { color: '#E5E7EB' } },
            splitArea: { areaStyle: { color: ['#FFFFFF', '#F9FAFB'] } }
        },
        series: [{
            type: 'radar',
            data: [{
                value: [
                    data.tech_score || 0,
                    data.intel_score || 0,
                    data.risk_score || 0,
                    data.fund_score || 0
                ],
                name: 'Agent 团队综合评分',
                areaStyle: { color: 'rgba(30, 64, 175, 0.18)' },
                lineStyle: { color: '#1E40AF', width: 2 },
                itemStyle: { color: '#1E40AF' },
                symbolSize: 6
            }]
        }]
    };

    chart.setOption(option);
    window.radarChartInstance = chart;

    const handler = () => chart.resize();
    window.addEventListener('resize', handler);
}

/**
 * LLM 四 Agent 置信度卡片。
 */
function renderAgentConfidenceCards(data) {
    const container = document.querySelector('.enhanced-agent-cards');
    if (!container) return;

    const agents = [
        { role: 'technical',    name: '技术分析员',  score: data.tech_score,  iconId: 'i-chart' },
        { role: 'intelligence', name: '情报员',      score: data.intel_score, iconId: 'i-radio' },
        { role: 'risk',         name: '风控官',      score: data.risk_score,  iconId: 'i-shield' },
        { role: 'fundamental',  name: '基本面分析师', score: data.fund_score,  iconId: 'i-book' }
    ];

    container.innerHTML = agents.map(agent => {
        const score = (typeof agent.score === 'number' ? agent.score : 0).toFixed(1);
        return `
            <div class="enhanced-card">
                <div class="agent-mark" data-role="${agent.role}">
                    <svg class="icon icon-lg" aria-hidden="true"><use href="#${agent.iconId}"/></svg>
                </div>
                <div class="agent-name">${agent.name}</div>
                <div class="agent-score">${score}</div>
                <div class="agent-sublabel">置信度</div>
            </div>
        `;
    }).join('');
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
        renderEnhancedResult,
        enrichLlmResultWithPerAgentScores,
    };
}
