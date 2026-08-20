const question = document.querySelector('#question');
const askBtn = document.querySelector('#askBtn');
const runMeta = document.querySelector('.run-meta');
const answerHeading = document.querySelector('.answer-panel h2');
const answerText = document.querySelector('.answer-text');
const confidence = document.querySelector('.confidence');
const evidenceCount = document.querySelector('.evidence-card .count');
const evidenceList = document.querySelector('.evidence-list');
const planList = document.querySelector('#plan-list');
const toolCallList = document.querySelector('#tool-call-list');
const executionState = document.querySelector('#execution-state');

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
}

function renderEvidence(run) {
  if (!evidenceList) return;
  const sources = [];
  (run.tool_results || []).forEach(item => {
    const result = item.result || {};
    if (result._source) sources.push({source: result._source, tool: item.tool || 'tool'});
    (result.evidence || []).forEach(evidence => {
      if (evidence.source) sources.push({source: evidence.source, tool: item.tool || 'evidence'});
    });
  });
  const unique = [...new Map(sources.map(item => [item.source, item])).values()];
  if (!unique.length) {
    evidenceList.innerHTML = '<span class="audit-empty">本次运行未返回证据</span>';
    return;
  }
  evidenceList.innerHTML = unique.slice(0, 12).map(item => `<div class="evidence-row"><span class="source-icon table">▤</span><div><b>${escapeHtml(item.tool)}</b><p>${escapeHtml(item.source)}</p></div><span class="source-tag">可审计来源</span></div>`).join('');
}

function renderAudit(run) {
  const plan = run.plan || [];
  if (planList) planList.innerHTML = plan.length
    ? plan.map(item => `<span class="audit-step"><b>${escapeHtml(item.step)}.</b>${escapeHtml(item.tool)}</span>`).join('')
    : '<span class="audit-empty">本次运行未生成计划</span>';
  const calls = run.tool_calls || [];
  if (toolCallList) toolCallList.innerHTML = calls.length
    ? calls.slice(0, 12).map(call => `<span class="audit-step"><b>${escapeHtml(call.function?.name || 'tool')}</b></span>`).join('')
    : '<span class="audit-empty">本次运行未调用工具</span>';
  if (executionState) {
    const graph = (run.tool_results || []).map(item => item.result || {}).find(result => result.backend);
    const risk = (run.tool_results || []).map(item => item.result || {}).find(result => result.policy_version && result.risk_code);
    const selfEval = run.self_evaluation?.repair?.actions || [];
    executionState.innerHTML = `<span>图谱：${escapeHtml(graph?.backend || '未调用')}</span><span>策略：${escapeHtml(risk?.policy_version || 'risk-policy-v1')}</span><span>自检：${selfEval.length ? '已修复引用' : '通过'}</span>`;
  }
}

function renderRun(run) {
  const answer = run.answer || {};
  if (answerHeading && answer['结论']) answerHeading.textContent = answer['结论'];
  if (answerText && answer['证据']) {
    answerText.textContent = `已完成可审计分析，绑定 ${answer['证据'].length} 条来源。`;
  }
  if (confidence && answer['置信度']) {
    confidence.textContent = `${answer['置信度']} 置信度`;
    confidence.className = `confidence ${answer['置信度'] === 'high' ? 'high' : 'medium'}`;
  }
  if (evidenceCount) evidenceCount.textContent = String((run.evidence_sources || []).length);
  renderEvidence(run);
  renderAudit(run);
  const verification = run.verification || {};
  const coverage = answer['证据']?.length && !verification.unsupported_citations?.length ? '证据完整' : '证据待核验';
  const tokens = run.token_usage?.total_tokens || 0;
  const elapsed = run.elapsed_ms ? `${Math.round(run.elapsed_ms)}ms` : '耗时未知';
  runMeta.innerHTML = `<span class="running"><i></i> Agent 已完成分析</span><span>${(run.tool_calls || []).length} 个工具调用 · ${(run.evidence_sources || []).length} 条证据</span><span>${coverage}</span><span>${elapsed} · ${tokens} tokens</span>`;
}

async function analyzeQuestion() {
  const original = askBtn.innerHTML;
  askBtn.innerHTML = '分析中…';
  askBtn.disabled = true;
  runMeta.innerHTML = '<span class="running"><i></i> 正在检索证据与构建上下文</span><span>查询财务报表 · 股东关系 · 历史记忆</span>';
  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: question?.value || ''}),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error?.message || '分析服务不可用');
    renderRun(payload.run);
  } catch (error) {
    // Keep the static demonstration visible while making the backend state explicit.
    runMeta.innerHTML = `<span class="running">后端暂不可用</span><span>${error.message}</span><span>当前显示演示数据</span>`;
  } finally {
    askBtn.innerHTML = original;
    askBtn.disabled = false;
  }
}

askBtn?.addEventListener('click', analyzeQuestion);
document.querySelectorAll('.nav-item').forEach(item => item.addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  item.classList.add('active');
}));
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
}));
question?.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') askBtn.click(); });
