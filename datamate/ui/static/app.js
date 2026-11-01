let businesses = [];
let currentTables = {};
let testedCases = new Set();
let currentDataset = 'public_test';
let currentSampleQuestions = [];
let sampleOffset = 0;
let qaTestResults = null;

const CHECKLIST_ITEMS = [
  { id: "VN-02", biz: "biz_099", q: "Tháng này mặt hàng nào bán chạy nhất?", desc: "Câu tự nhiên, chuẩn (Số lượng)", date: "2026-03-04", expected_type: "string", expected_answer: "Panadol Extra đỏ vỉ" },
  { id: "VN-03", biz: "biz_099", q: "Anh/chị xem giúp em tháng này thuốc nào bán chạy nhất với.", desc: "Xưng hô và lịch sự", date: "2026-03-04", expected_type: "string", expected_answer: "Panadol Extra đỏ vỉ" },
  { id: "CHAT-01", biz: "biz_099", q: "sp bán dc nhiều nhất tuần rồi là gì", desc: "Viết tắt, benchmark", date: "2026-03-04", expected_type: "string", expected_answer: "Panadol Extra đỏ vỉ" },
  { id: "CHAT-06", biz: "biz_099", q: "thang nay mat hang nao ban chay nhat", desc: "Tiếng Việt không dấu", date: "2026-03-04", expected_type: "string", expected_answer: "Panadol Extra đỏ vỉ" },
  { id: "CHAT-07", biz: "biz_099", q: "sp nào bán dc nhìu nhất tuần rùi z shop", desc: "Teencode, tiếng lóng", date: "2026-03-04", expected_type: "string", expected_answer: "Panadol Extra đỏ vỉ" },
  { id: "DIA-04", biz: "biz_099", q: "Bữa giờ thuốc nào bán chạy nhất vậy?", desc: "Phương ngữ Nam, thời gian mơ hồ -> ABSTAIN", date: "2026-03-04", expected_type: "abstain", expected_answer: null },
  { id: "DIA-06", biz: "biz_099", q: "Tháng ni thuốc mô bán chạy nhất rứa?", desc: "Phương ngữ Trung", date: "2026-03-04", expected_type: "string", expected_answer: "Panadol Extra đỏ vỉ" },
  { id: "SEM-01", biz: "biz_fixture_probe", q: "Sản phẩm nào bán được nhiều nhất?", desc: "Số lượng (Sản phẩm A)", date: "2026-03-04", expected_type: "string", expected_answer: "Sản phẩm A" },
  { id: "SEM-02", biz: "biz_fixture_probe", q: "Sản phẩm nào thu về nhiều tiền nhất?", desc: "Doanh thu (Sản phẩm B)", date: "2026-03-04", expected_type: "string", expected_answer: "Sản phẩm B" },
  { id: "SEM-03", biz: "biz_fixture_probe", q: "Sản phẩm nào có lợi nhuận cao nhất?", desc: "Cần giá vốn -> UNANSWERABLE", date: "2026-03-04", expected_type: "unanswerable", expected_answer: null },
  { id: "SEM-04", biz: "biz_099", q: "Panadol đỏ còn hạn sử dụng đến khi nào?", desc: "Cần HSD -> UNANSWERABLE", date: "2026-03-04", expected_type: "unanswerable", expected_answer: null },
  { id: "NEG-04", biz: "biz_099", q: "Tại sao tuần rồi doanh số giảm?", desc: "Câu hỏi Why/Nguyên nhân -> UNANSWERABLE", date: "2026-03-04", expected_type: "unanswerable", expected_answer: null },
  { id: "NEG-05", biz: "biz_099", q: "Tháng sau dự đoán bán được bao nhiêu cái nhiệt kế?", desc: "Dự đoán tương lai -> UNANSWERABLE", date: "2026-03-04", expected_type: "unanswerable", expected_answer: null },
  { id: "LUNAR-01", biz: "biz_099", q: "Từ sau Tết đến giờ bán được bao nhiêu tiền?", desc: "Lịch âm (Sau Tết Bính Ngọ)", date: "2026-03-04", expected_type: "number", expected_answer: 6425000 },
  { id: "EMPTY-01", biz: "biz_empty_sales", q: "Mặt hàng nào bán chạy nhất tháng này?", desc: "Tiệm mới mở 0 đơn -> ABSTAIN", date: "2026-03-04", expected_type: "abstain", expected_answer: null }
];

async function init() {
  await loadBusinesses();
  await loadSampleQuestions();
  setupEvents();
  renderChecklist();
}

async function loadBusinesses() {
  const sel = document.getElementById('businessSelect');
  try {
    const res = await fetch('/api/businesses?dataset=' + currentDataset);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    businesses = await res.json();
    sel.innerHTML = '';
    businesses.forEach((b) => {
      const opt = document.createElement('option');
      opt.value = b.id;
      const title = b.readme ? b.readme.split('\n')[0].replace(/#/g, '').trim() : 'Doanh nghiệp';
      opt.textContent = `${b.id} — ${title}`;
      sel.appendChild(opt);
    });
    if (businesses.length > 0) {
      sel.value = businesses[0].id;
      await onBusinessChange(businesses[0].id);
    }
  } catch (e) {
    console.error('Error loading businesses:', e);
    if (sel) {
      sel.innerHTML = '<option value="" disabled selected>Lỗi tải doanh nghiệp: ' + e.message + '</option>';
    }
  }
}

async function onBusinessChange(bizId) {
  const b = businesses.find(x => x.id === bizId);
  const readmeEl = document.getElementById('bizReadme');
  if (b && readmeEl) {
    readmeEl.textContent = b.readme || 'Không có mô tả';
  }
  await loadSampleQuestions(bizId);
  try {
    const res = await fetch(`/api/business/${bizId}/tables?dataset=` + currentDataset);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    currentTables = await res.json();
    renderTables(currentTables);
  } catch (e) {
    console.error('Error loading tables:', e);
  }
}

function renderTables(tables) {
  const container = document.getElementById('tablesContainer');
  const badge = document.getElementById('tableCountBadge');
  const keys = Object.keys(tables || {});
  if (badge) badge.textContent = `${keys.length} bảng`;
  if (!container) return;
  if (keys.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 italic text-center py-8">Không có bảng nào</p>';
    return;
  }
  container.innerHTML = '';
  keys.forEach(tName => {
    const t = tables[tName];
    const card = document.createElement('div');
    card.className = 'bg-slate-900/90 border border-slate-700/60 hover:border-blue-500/40 p-3 rounded-xl transition cursor-pointer flex items-center justify-between';
    card.onclick = () => openTableModal(tName, t);
    card.innerHTML = `
      <div>
        <div class="font-semibold text-xs text-blue-400 flex items-center gap-1.5">
          <i class="fa-solid fa-table text-[10px]"></i> ${tName}
        </div>
        <div class="text-[11px] text-slate-400 mt-0.5">
          ${t.columns.length} cột • ${t.row_count} dòng
        </div>
      </div>
      <span class="text-slate-500 text-xs hover:text-white"><i class="fa-solid fa-eye"></i></span>
    `;
    container.appendChild(card);
  });
}

function openTableModal(tName, t) {
  const title = document.getElementById('modalTableTitle');
  if (title) title.innerHTML = `<i class="fa-solid fa-table text-blue-400"></i> Bảng: ${tName} (${t.row_count} dòng)`;
  const content = document.getElementById('modalTableContent');
  if (!content) return;
  
  let html = `<div class="mb-4">
    <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Các cột & Vai trò ngữ nghĩa (Semantic Roles)</h4>
    <div class="flex flex-wrap gap-2">`;
  t.columns.forEach(c => {
    const roleBadge = c.semantic_role 
      ? `<span class="bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded text-[10px]">${c.semantic_role}</span>`
      : `<span class="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-[10px]">default</span>`;
    html += `<div class="bg-slate-800/80 border border-slate-700/60 px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-2">
      <span class="font-mono text-slate-200">${c.name}</span>
      ${roleBadge}
    </div>`;
  });
  html += `</div></div>`;

  if (t.preview_rows && t.preview_rows.length > 0) {
    html += `<div>
      <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Dữ liệu xem trước (Preview ${t.preview_rows.length} dòng)</h4>
      <div class="overflow-x-auto border border-slate-800 rounded-xl">
        <table class="w-full text-xs text-left text-slate-300">
          <thead class="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
            <tr>${t.preview_cols.map(c => `<th class="px-3 py-2.5">${c}</th>`).join('')}</tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            ${t.preview_rows.map(r => `<tr class="hover:bg-slate-800/40">${r.map(v => `<td class="px-3 py-2 font-mono text-[11px]">${v !== null ? v : '<span class=\"text-slate-600\">null</span>'}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
  }
  content.innerHTML = html;
  const modal = document.getElementById('tableModal');
  if (modal) modal.classList.remove('hidden');
}

async function loadSampleQuestions(bizId = '') {
  try {
    const sel = document.getElementById('businessSelect');
    const targetBiz = bizId || (sel ? sel.value : '');
    const url = `/api/sample-questions?dataset=${currentDataset}${targetBiz ? '&business_id=' + targetBiz : ''}`;
    const res = await fetch(url);
    if (!res.ok) return;
    currentSampleQuestions = await res.json();
    sampleOffset = 0;
    renderSamplePills();
  } catch (e) {
    console.error('Error loading sample questions:', e);
  }
}

function renderSamplePills() {
  const pillsContainer = document.getElementById('samplePills');
  if (!pillsContainer) return;
  pillsContainer.innerHTML = '';

  if (!currentSampleQuestions || currentSampleQuestions.length === 0) {
    pillsContainer.innerHTML = '<span class="text-xs text-slate-500 italic">Không có gợi ý nào cho doanh nghiệp này</span>';
    return;
  }

  // Display at most 3-4 clean, compact questions
  const PAGE_SIZE = 3;
  const start = sampleOffset % currentSampleQuestions.length;
  let slice = currentSampleQuestions.slice(start, start + PAGE_SIZE);
  if (slice.length < PAGE_SIZE && currentSampleQuestions.length >= PAGE_SIZE) {
    slice = slice.concat(currentSampleQuestions.slice(0, PAGE_SIZE - slice.length));
  }

  slice.forEach(q => {
    const btn = document.createElement('button');
    btn.className = 'text-[11px] bg-slate-800 hover:bg-slate-700 hover:border-blue-500/40 text-slate-300 border border-slate-700/60 px-3 py-1.5 rounded-lg transition text-left truncate max-w-[280px] sm:max-w-[360px] shadow-sm flex items-center gap-1.5';
    btn.title = q.question;
    btn.innerHTML = `<i class="fa-solid fa-arrow-turn-down-right text-blue-400 text-[9px]"></i> <span class="truncate">${q.question}</span>`;
    btn.onclick = () => {
      const qInput = document.getElementById('questionInput');
      if (qInput) qInput.value = q.question;
      const asOf = document.getElementById('asOfDate');
      if (asOf && q.as_of_date) {
        asOf.value = q.as_of_date;
      }
    };
    pillsContainer.appendChild(btn);
  });
}

function renderChecklist() {
  const container = document.getElementById('checklistContainer');
  if (!container) return;

  const items = qaTestResults ? qaTestResults.results : CHECKLIST_ITEMS;
  const prog = document.getElementById('qaProgress');
  if (prog) {
    if (qaTestResults) {
      prog.textContent = `${qaTestResults.summary.passed}/${qaTestResults.summary.total} PASS`;
    } else {
      prog.textContent = `${testedCases.size}/${CHECKLIST_ITEMS.length}`;
    }
  }

  container.innerHTML = '';
  items.forEach(item => {
    const status = item.status || (testedCases.has(item.id) ? 'TESTED' : 'PENDING');

    let statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-800 text-slate-400">PENDING</span>';
    let cardBorder = 'border-slate-800 hover:border-slate-700 bg-slate-900/60';

    if (status === 'PASS') {
      statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">PASS (+1)</span>';
      cardBorder = 'border-emerald-500/30 bg-emerald-950/10 hover:border-emerald-500/50';
    } else if (status === 'FAIL') {
      statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-red-500/10 border border-red-500/30 text-red-400">FAIL (-1)</span>';
      cardBorder = 'border-red-500/30 bg-red-950/10 hover:border-red-500/50';
    } else if (status === 'ABSTAIN') {
      statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/10 border border-amber-500/30 text-amber-400">ABSTAIN (0)</span>';
      cardBorder = 'border-amber-500/30 bg-amber-950/10 hover:border-amber-500/50';
    }

    const div = document.createElement('div');
    div.className = `p-3.5 rounded-xl border flex flex-col gap-2 transition cursor-pointer ${cardBorder}`;

    div.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <span class="font-mono text-xs font-bold text-purple-400 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-500/20">${item.id}</span>
          <span class="text-xs font-medium text-white">${item.q}</span>
        </div>
        <div class="flex items-center gap-2">
          ${item.latency_ms ? `<span class="text-[10px] font-mono text-slate-400"><i class="fa-solid fa-bolt text-amber-400"></i> ${item.latency_ms}ms</span>` : ''}
          ${statusBadge}
        </div>
      </div>
      <div class="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/60 pt-2">
        <div><i class="fa-solid fa-tag text-slate-500"></i> ${item.desc} • <span class="font-mono text-purple-300">${item.biz}</span></div>
        <div class="flex items-center gap-3">
          <div><span class="text-slate-500">Exp:</span> <span class="font-mono text-slate-300 font-semibold">${item.expected_type}: ${item.expected_answer !== null && item.expected_answer !== undefined ? item.expected_answer : 'null'}</span></div>
          ${item.actual_type ? `<div><span class="text-slate-500">Act:</span> <span class="font-mono text-emerald-300 font-semibold">${item.actual_type}: ${item.actual_answer !== null && item.actual_answer !== undefined ? item.actual_answer : 'null'}</span></div>` : ''}
        </div>
      </div>
    `;

    div.onclick = async () => {
      const sel = document.getElementById('businessSelect');
      if (sel) {
        sel.value = item.biz;
        await onBusinessChange(item.biz);
      }
      const qInput = document.getElementById('questionInput');
      if (qInput) qInput.value = item.q;
      const asOf = document.getElementById('asOfDate');
      if (asOf) asOf.value = item.date;

      const modal = document.getElementById('checklistModal');
      if (modal) modal.classList.add('hidden');

      testedCases.add(item.id);
      await ask();
    };

    container.appendChild(div);
  });
}

async function runAllQATests() {
  const runBtn = document.getElementById('runAllTestsBtn');
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running Tests...';
  }

  try {
    const res = await fetch('/api/run-all-tests', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to run QA tests');
    const data = await res.json();
    qaTestResults = data;
    updateQAScorecard(data.summary);
    renderChecklist();
  } catch (err) {
    console.error(err);
    alert('Lỗi khi chạy QA tests: ' + err.message);
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run All 15 Tests';
    }
  }
}

function updateQAScorecard(summary) {
  if (!summary) return;
  const accEl = document.getElementById('qaScoreAccuracy');
  if (accEl) accEl.textContent = `${summary.accuracy_pct}%`;

  const scoreEl = document.getElementById('qaScorePenalized');
  if (scoreEl) scoreEl.textContent = `+${summary.penalized_score} / ${summary.total}`;

  const countsEl = document.getElementById('qaScoreCounts');
  if (countsEl) countsEl.textContent = `${summary.passed} PASS / ${summary.failed} FAIL`;

  const latEl = document.getElementById('qaScoreLatency');
  if (latEl) latEl.textContent = `${summary.avg_latency_ms} ms`;

  const prog = document.getElementById('qaProgress');
  if (prog) prog.textContent = `${summary.passed}/${summary.total}`;
}

function setupEvents() {
  const dsSel = document.getElementById('datasetSelect');
  if (dsSel) {
    currentDataset = dsSel.value;
    dsSel.onchange = async () => {
      currentDataset = dsSel.value;
      await loadBusinesses();
      await loadSampleQuestions();
    };
  }

  const sel = document.getElementById('businessSelect');
  if (sel) sel.onchange = (e) => onBusinessChange(e.target.value);

  const refreshBtn = document.getElementById('refreshSamplesBtn');
  if (refreshBtn) {
    refreshBtn.onclick = () => {
      if (currentSampleQuestions && currentSampleQuestions.length > 0) {
        sampleOffset += 3;
        renderSamplePills();
      }
    };
  }

  const closeBtn = document.getElementById('closeModalBtn');
  if (closeBtn) closeBtn.onclick = () => {
    const modal = document.getElementById('tableModal');
    if (modal) modal.classList.add('hidden');
  };

  const chkBtn = document.getElementById('qaChecklistBtn');
  if (chkBtn) chkBtn.onclick = () => {
    const modal = document.getElementById('checklistModal');
    if (modal) modal.classList.remove('hidden');
  };

  const runAllBtn = document.getElementById('runAllTestsBtn');
  if (runAllBtn) runAllBtn.onclick = runAllQATests;

  const closeChkBtn = document.getElementById('closeChecklistBtn');
  if (closeChkBtn) closeChkBtn.onclick = () => {
    const modal = document.getElementById('checklistModal');
    if (modal) modal.classList.add('hidden');
  };

  const askBtn = document.getElementById('askBtn');
  if (askBtn) askBtn.onclick = ask;

  const qInput = document.getElementById('questionInput');
  if (qInput) {
    qInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        ask();
      }
    });
  }

  const copyBtn = document.getElementById('copySqlBtn');
  if (copyBtn) {
    copyBtn.onclick = () => {
      const sqlEl = document.getElementById('sqlCode');
      if (sqlEl) {
        navigator.clipboard.writeText(sqlEl.textContent);
        alert('Đã sao chép câu lệnh SQL!');
      }
    };
  }

  // Activity Diagram View Switchers
  const btnVisual = document.getElementById('btnViewVisual');
  if (btnVisual) btnVisual.onclick = () => switchFlowView('visual');

  const btnMermaid = document.getElementById('btnViewMermaid');
  if (btnMermaid) btnMermaid.onclick = () => switchFlowView('mermaid');

  const copyMermaidBtn = document.getElementById('copyMermaidBtn');
  if (copyMermaidBtn) {
    copyMermaidBtn.onclick = () => {
      navigator.clipboard.writeText(MERMAID_DIAGRAM_DEFINITION);
      alert('Đã sao chép mã Mermaid Activity Diagram!');
    };
  }
}

const MERMAID_DIAGRAM_DEFINITION = `stateDiagram-v2
    [*] --> InitialState: 1. Nhận câu hỏi & as_of_date
    InitialState --> NLU: 2. Vietnamese NLU & Text Normalization
    NLU --> Temporal: 3. Temporal Engine (Âm/Dương lịch)
    Temporal --> IntentSchema: 4. Intent & Multi-table Schema Mapping
    
    state "Kiểm định Bằng chứng (PA Guard)" as Decision <<choice>>
    IntentSchema --> Decision
    
    Decision --> PAGuardAbstain: [Mơ hồ / Thiếu dữ liệu / Causal]
    Decision --> SafeSQLExecution: [Hợp lệ & Đầy đủ bằng chứng]
    
    state "Nhánh An Toàn (0đ)" as PAGuardAbstain {
        TuChoi: 5A. Quyết định ABSTAIN hoặc UNANSWERABLE
        BaoToanDiem: Bảo toàn 0đ (Tránh bị phạt -1đ)
        TuChoi --> BaoToanDiem
    }
    
    state "Nhánh Thực Thi (+1đ)" as SafeSQLExecution {
        SinhSQL: 5B. Parameterized SQL Compilation
        ThucThiSafe: 6. Safe SQL Executor (Query-Only, Opcode Limit)
        DinhDang: 7. Format 9 Kiểu Output chuẩn BTC
        SinhSQL --> ThucThiSafe
        ThucThiSafe --> DinhDang
    }
    
    BaoToanDiem --> [*]: Kết thúc luồng (0đ)
    DinhDang --> [*]: Kết thúc luồng (+1đ)
`;

let mermaidRendered = false;

async function renderMermaidDiagram() {
  if (mermaidRendered || !window.mermaid) return;
  const chartEl = document.getElementById('mermaidChart');
  if (!chartEl) return;
  try {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });
    const { svg } = await mermaid.render('mermaidSvgId', MERMAID_DIAGRAM_DEFINITION);
    chartEl.innerHTML = svg;
    mermaidRendered = true;
  } catch (err) {
    console.error('Mermaid render error:', err);
    chartEl.innerHTML = `<div class="text-rose-400 p-4">Lỗi hiển thị Mermaid: ${err.message}</div>`;
  }
}

function switchFlowView(view) {
  const visCont = document.getElementById('viewVisualContainer');
  const merCont = document.getElementById('viewMermaidContainer');
  const btnVis = document.getElementById('btnViewVisual');
  const btnMer = document.getElementById('btnViewMermaid');
  
  if (view === 'visual') {
    if (visCont) visCont.classList.remove('hidden');
    if (merCont) merCont.classList.add('hidden');
    if (btnVis) {
      btnVis.className = 'px-2.5 py-1 rounded-lg bg-blue-600 text-white font-medium shadow transition text-[11px]';
    }
    if (btnMer) {
      btnMer.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white transition text-[11px]';
    }
  } else {
    if (visCont) visCont.classList.add('hidden');
    if (merCont) merCont.classList.remove('hidden');
    if (btnMer) {
      btnMer.className = 'px-2.5 py-1 rounded-lg bg-blue-600 text-white font-medium shadow transition text-[11px]';
    }
    if (btnVis) {
      btnVis.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white transition text-[11px]';
    }
    renderMermaidDiagram();
  }
}

function updateActivityDiagram(data) {
  const sub = data.submission;
  const badge = document.getElementById('flowStatusBadge');
  
  // 1. Update NLU Detail
  const nluDetail = document.getElementById('actNluDetail');
  if (nluDetail && data.nlp) {
    nluDetail.innerHTML = `Clean: <span class="text-white font-semibold">"${data.nlp.clean_query}"</span>`;
  }
  
  // 2. Update Temporal Detail
  const tempDetail = document.getElementById('actTempDetail');
  if (tempDetail) {
    if (data.temporal) {
      tempDetail.innerHTML = `Range: <span class="text-white font-semibold">${data.temporal.start_date || '?'} &rarr; ${data.temporal.end_date || '?'}</span>`;
    } else {
      tempDetail.innerHTML = `<span class="text-slate-500">Mặc định (Không có mốc ngày)</span>`;
    }
  }
  
  // 3. Update Intent Detail
  const intentDetail = document.getElementById('actIntentDetail');
  if (intentDetail && data.plan) {
    intentDetail.innerHTML = `Intent: <span class="text-white font-semibold">${data.plan.intent}</span> | Conf: <span class="text-indigo-400">${(data.plan.confidence * 100).toFixed(0)}%</span>`;
  }
  
  // 4. Update Decision & Branches
  const brAbstain = document.getElementById('branchAbstain');
  const brSuccess = document.getElementById('branchSuccess');
  const decisionNode = document.getElementById('flowNodeDecision');
  
  if (sub.type === 'abstain' || sub.type === 'unanswerable') {
    if (badge) {
      badge.className = 'px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 font-mono text-[11px] flex items-center gap-1.5';
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span> PA GUARD: ${sub.type.toUpperCase()} (0đ)`;
    }
    if (brAbstain) {
      brAbstain.classList.add('flow-node-abstain');
      brAbstain.classList.remove('opacity-40');
    }
    if (brSuccess) {
      brSuccess.classList.remove('flow-node-success');
      brSuccess.classList.add('opacity-40');
    }
    if (decisionNode) {
      decisionNode.classList.add('flow-node-abstain');
      decisionNode.classList.remove('flow-node-success');
    }
  } else {
    if (badge) {
      badge.className = 'px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono text-[11px] flex items-center gap-1.5';
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> EXECUTED: ${sub.type.toUpperCase()} (+1đ)`;
    }
    if (brSuccess) {
      brSuccess.classList.add('flow-node-success');
      brSuccess.classList.remove('opacity-40');
    }
    if (brAbstain) {
      brAbstain.classList.remove('flow-node-abstain');
      brAbstain.classList.add('opacity-40');
    }
    if (decisionNode) {
      decisionNode.classList.add('flow-node-success');
      decisionNode.classList.remove('flow-node-abstain');
    }
  }
}

async function ask() {
  const sel = document.getElementById('businessSelect');
  const bizId = sel ? sel.value : '';
  const qInput = document.getElementById('questionInput');
  const question = qInput ? qInput.value.trim() : '';
  const asOfEl = document.getElementById('asOfDate');
  const asOfDate = asOfEl ? asOfEl.value : '2026-03-04';

  if (!bizId) {
    alert('Vui lòng chọn một doanh nghiệp!');
    return;
  }
  if (!question) {
    alert('Vui lòng nhập câu hỏi!');
    return;
  }

  const btn = document.getElementById('askBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i> Đang xử lý...';
  }

  const flowBadge = document.getElementById('flowStatusBadge');
  if (flowBadge) {
    flowBadge.className = 'px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40 font-mono text-[11px] flex items-center gap-1.5';
    flowBadge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping"></span> RUNNING (Đang suy luận...)';
  }

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ business_id: bizId, question: question, as_of_date: asOfDate, dataset: currentDataset })
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }
    const data = await res.json();
    renderResult(data);
  } catch (e) {
    alert('Lỗi truy vấn: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>Hỏi Agent</span><i class="fa-solid fa-paper-plane text-[10px]"></i>';
    }
  }
}

function renderResult(data) {
  const latencyTag = document.getElementById('latencyTag');
  if (latencyTag) latencyTag.textContent = `Thời gian xử lý: ${data.latency_ms} ms`;
  const sub = data.submission;
  const typeBadge = document.getElementById('answerTypeBadge');
  if (typeBadge) typeBadge.textContent = sub.type.toUpperCase();

  const ansVal = document.getElementById('answerValue');
  if (ansVal) {
    if (sub.type === 'unanswerable') {
      if (typeBadge) typeBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono';
      ansVal.innerHTML = `<span class="text-amber-400"><i class="fa-solid fa-triangle-exclamation mr-2"></i>UNANSWERABLE</span> <span class="text-sm font-normal text-slate-400 block mt-1">Dữ liệu hiện tại không đủ để trả lời câu hỏi này.</span>`;
    } else if (sub.type === 'abstain') {
      if (typeBadge) typeBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-slate-500/20 text-slate-400 border border-slate-500/30 font-mono';
      ansVal.innerHTML = `<span class="text-slate-400"><i class="fa-solid fa-hand mr-2"></i>ABSTAIN</span> <span class="text-sm font-normal text-slate-400 block mt-1">Agent chủ động từ chối trả lời để bảo vệ điểm số (0 điểm thay vì mạo hiểm bị -1).</span>`;
    } else {
      if (typeBadge) typeBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono';
      let displayVal = sub.answer;
      if (typeof sub.answer === 'number') {
        displayVal = Number(sub.answer).toLocaleString('vi-VN');
        if (sub.type === 'percent') displayVal += ' %';
        else if (sub.type === 'number' && sub.answer >= 1000) displayVal += ' VNĐ';
      } else if (Array.isArray(sub.answer)) {
        displayVal = `<ul class="list-disc list-inside text-sm font-medium mt-1">` + sub.answer.map(x => `<li>${x}</li>`).join('') + `</ul>`;
      }
      ansVal.innerHTML = `<span class="text-emerald-400">${displayVal}</span>`;
    }
  }

  // Vietnamese NLU Preprocessing Info
  const nlpDiv = document.getElementById('nlpInfo');
  if (nlpDiv && data.nlp) {
    const flags = [];
    if (data.nlp.is_quantity_query) flags.push('<span class="bg-blue-500/20 text-blue-300 px-1 py-0.5 rounded text-[10px]">Quantity</span>');
    if (data.nlp.is_revenue_query) flags.push('<span class="bg-emerald-500/20 text-emerald-300 px-1 py-0.5 rounded text-[10px]">Revenue</span>');
    if (data.nlp.is_profit_cost_query) flags.push('<span class="bg-amber-500/20 text-amber-300 px-1 py-0.5 rounded text-[10px]">Profit/Cost</span>');
    if (data.nlp.is_expiration_query) flags.push('<span class="bg-rose-500/20 text-rose-300 px-1 py-0.5 rounded text-[10px]">Expiry</span>');
    if (data.nlp.is_stock_query) flags.push('<span class="bg-indigo-500/20 text-indigo-300 px-1 py-0.5 rounded text-[10px]">Stock</span>');
    if (data.nlp.is_why_causal) flags.push('<span class="bg-red-500/20 text-red-300 px-1 py-0.5 rounded text-[10px]">Why/Causal</span>');
    if (data.nlp.is_future) flags.push('<span class="bg-purple-500/20 text-purple-300 px-1 py-0.5 rounded text-[10px]">Future</span>');
    if (data.nlp.is_ambiguous_time) flags.push('<span class="bg-slate-500/20 text-slate-300 px-1 py-0.5 rounded text-[10px]">Ambiguous Time</span>');

    nlpDiv.innerHTML = `
      <div><strong class="text-slate-400">Chuẩn hóa:</strong> <span class="text-teal-300">"${data.nlp.clean_query}"</span></div>
      <div class="mt-1 flex flex-wrap gap-1">${flags.join(' ') || '<span class="text-slate-500">Mặc định</span>'}</div>
    `;
  }

  const tempDiv = document.getElementById('temporalInfo');
  if (tempDiv) {
    if (data.temporal) {
      const monthPart = data.temporal.target_month ? `<div><strong class="text-slate-400">Tháng:</strong> ${data.temporal.target_month}</div>` : '';
      const ambPart = data.temporal.is_ambiguous ? `<div class="text-amber-400 text-[11px]"><i class="fa-solid fa-triangle-exclamation"></i> Thời gian mơ hồ (bữa giờ)</div>` : '';
      tempDiv.innerHTML = `
        <div><strong class="text-slate-400">Từ ngày:</strong> ${data.temporal.start_date || '--'}</div>
        <div><strong class="text-slate-400">Đến ngày:</strong> ${data.temporal.end_date || '--'}</div>
        ${monthPart}
        ${ambPart}
      `;
    } else {
      tempDiv.innerHTML = '<p class="text-slate-500 italic">Không có mốc thời gian cụ thể</p>';
    }
  }

  const planDiv = document.getElementById('planInfo');
  if (planDiv) {
    const unansReason = data.plan.unanswerable_reason ? `<div class="text-amber-400 text-[11px] mt-1"><i class="fa-solid fa-circle-info"></i> ${data.plan.unanswerable_reason}</div>` : '';
    planDiv.innerHTML = `
      <div><strong class="text-slate-400">Ý định:</strong> <span class="text-indigo-400 font-mono">${data.plan.intent}</span></div>
      <div><strong class="text-slate-400">Độ tin cậy:</strong> ${(data.plan.confidence * 100).toFixed(0)}%</div>
      ${unansReason}
    `;
  }

  const sqlEl = document.getElementById('sqlCode');
  if (sqlEl) {
    sqlEl.textContent = data.plan.sql || '-- Không có câu lệnh SQL (Truy vấn được xử lý đặc biệt hoặc từ chối)';
  }

  // Update Activity Diagram flow
  updateActivityDiagram(data);
}

window.onload = init;
