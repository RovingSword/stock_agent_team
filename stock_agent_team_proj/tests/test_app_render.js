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
global.window = {};

const appModule = require(path.join(__dirname, '..', 'web', 'static', 'js', 'app.js'));
const {
    getAgentDiscussionCardId,
    getAgentPrimaryAnalysisText,
    buildAgentAnalysisCardHtml,
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

console.log('app render tests passed');
