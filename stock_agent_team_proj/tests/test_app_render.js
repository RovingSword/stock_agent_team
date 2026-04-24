const assert = require('assert');
const path = require('path');

function createStubElement(id) {
    return {
        id,
        value: '',
        innerHTML: '',
        textContent: '',
        scrollTop: 0,
        scrollHeight: 0,
        classList: {
            add() {},
            remove() {},
            toggle() {},
        },
        addEventListener() {},
        querySelector() {
            return {
                textContent: '',
                classList: {
                    add() {},
                    remove() {},
                    toggle() {},
                },
            };
        },
        insertAdjacentHTML(_position, html) {
            this.innerHTML += html;
        },
        scrollIntoView() {},
    };
}

const elementStore = new Map();
global.document = {
    getElementById(id) {
        if (!elementStore.has(id)) {
            elementStore.set(id, createStubElement(id));
        }
        return elementStore.get(id);
    },
    querySelector(selector) {
        if (selector === '.enhanced-agent-cards') {
            return this.getElementById('enhancedResultCards');
        }
        return null;
    },
    querySelectorAll() {
        return [];
    },
    addEventListener() {},
    createElement() {
        return {
            _text: '',
            innerHTML: '',
            set textContent(value) {
                this._text = value;
                this.innerHTML = String(value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/\"/g, '&quot;')
                    .replace(/'/g, '&#39;');
            },
            get textContent() {
                return this._text;
            },
        };
    },
};
global.window = {
    addEventListener() {},
};

const appModule = require(path.join(__dirname, '..', 'web', 'static', 'js', 'app.js'));
const {
    getAgentDiscussionCardId,
    getAgentPrimaryAnalysisText,
    buildAgentAnalysisCardHtml,
    renderMarkdown,
    renderEnhancedResult,
    enrichLlmResultWithPerAgentScores,
} = appModule;

const sampleData = {
    agent_role: 'technical',
    agent_name: '技术分析员',
    icon: '📈',
    score: 7.6,
    summary: '技术面偏强',
    analysis: '均线向上发散，量价配合良好。',
};

const pendingHtml = buildAgentAnalysisCardHtml(sampleData, true);
const finalHtml = buildAgentAnalysisCardHtml(sampleData, false);

assert.strictEqual(getAgentDiscussionCardId('technical'), 'agent-card-technical');
assert.ok(pendingHtml.includes('id="agent-card-technical"'));
assert.ok(finalHtml.includes('id="agent-card-technical"'));
assert.strictEqual(
    (pendingHtml.match(/id="([^"]+)"/) || [])[1],
    (finalHtml.match(/id="([^"]+)"/) || [])[1],
);
assert.strictEqual(
    getAgentPrimaryAnalysisText(sampleData),
    '均线向上发散，量价配合良好。',
);
assert.ok(finalHtml.includes('agent-analysis-summary'));
assert.ok(finalHtml.includes('均线向上发散，量价配合良好。'));

// 无 marked/DOMPurify 时降级为 HTML 转义，不应出现未转义的标签
const safe = renderMarkdown('<script>alert(1)</script>');
assert.ok(!safe.toLowerCase().includes('<script>'));

// 渲染 LLM 增强结果时，不应覆盖规则引擎结果区的既有节点
const legacyResult = global.document.getElementById('legacyResultContent');
legacyResult.innerHTML = '<div id="techScore"></div><div id="entryZone"></div>';
global.document.getElementById('enhancedResultSection').innerHTML = '';

renderEnhancedResult({
    final_action: 'buy',
    buy_reasons: ['趋势向上'],
    tech_score: 8.1,
    intel_score: 7.2,
    risk_score: 6.4,
    fund_score: 7.8,
});

assert.ok(legacyResult.innerHTML.includes('techScore'));
assert.ok(legacyResult.innerHTML.includes('entryZone'));
assert.ok(global.document.getElementById('enhancedResultSection').innerHTML.includes('最终交易决策'));
assert.ok(global.document.getElementById('reasonTags').innerHTML.includes('趋势向上'));

// SSE 终态仅有 agent_scores 时，应归一化出 tech_score 等字段供增强结果使用
const enriched = enrichLlmResultWithPerAgentScores({
    agent_scores: [
        { agent_role: 'technical', score: 8.1 },
        { agent_role: 'intelligence', score: 7.2 },
        { agent_role: 'risk', score: 6.4 },
        { agent_role: 'fundamental', score: 7.8 },
    ],
});
assert.strictEqual(enriched.tech_score, 8.1);
assert.strictEqual(enriched.intel_score, 7.2);
assert.strictEqual(enriched.risk_score, 6.4);
assert.strictEqual(enriched.fund_score, 7.8);

console.log('app render tests passed');
