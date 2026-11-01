let businesses = [];
let currentTables = {};
let testedCases = new Set();
let currentDataset = 'public_test';
let currentSampleQuestions = [];
let sampleOffset = 0;

const CHECKLIST_ITEMS = [
  { id: "VN-02", biz: "biz_099", q: "Tháng này mặt hàng nào bán chạy nhất?", desc: "Câu tự nhiên, chuẩn (Số lượng)", date: "2026-03-04" },
  { id: "VN-03", biz: "biz_099", q: "Anh/chị xem giúp em tháng này thuốc nào bán chạy nhất với.", desc: "Xưng hô và lịch sự", date: "2026-03-04" },
  { id: "CHAT-01", biz: "biz_099", q: "sp bán dc nhiều nhất tuần rồi là gì", desc: "Viết tắt, benchmark", date: "2026-03-04" },
  { id: "CHAT-06", biz: "biz_099", q: "thang nay mat hang nao ban chay nhat", desc: "Tiếng Việt không dấu", date: "2026-03-04" },
  { id: "CHAT-07", biz: "biz_099", q: "sp nào bán dc nhìu nhất tuần rùi z shop", desc: "Teencode, tiếng lóng", date: "2026-03-04" },
  { id: "DIA-04", biz: "biz_099", q: "Bữa giờ thuốc nào bán chạy nhất vậy?", desc: "Phương ngữ Nam, thời gian mơ hồ -> ABSTAIN", date: "2026-03-04" },
  { id: "DIA-06", biz: "biz_099", q: "Tháng ni thuốc mô bán chạy nhất rứa?", desc: "Phương ngữ Trung", date: "2026-03-04" },
  { id: "SEM-01", biz: "biz_fixture_probe", q: "Sản phẩm nào bán được nhiều nhất?", desc: "Số lượng (Sản phẩm A)", date: "2026-03-04" },
  { id: "SEM-02", biz: "biz_fixture_probe", q: "Sản phẩm nào thu về nhiều tiền nhất?", desc: "Doanh thu (Sản phẩm B)", date: "2026-03-04" },
  { id: "SEM-03", biz: "biz_fixture_probe", q: "Sản phẩm nào có lợi nhuận cao nhất?", desc: "Cần giá vốn -> UNANSWERABLE", date: "2026-03-04" },
  { id: "TIME-04", biz: "biz_099", q: "7 ngày gần đây bán được bao nhiêu?", desc: "Khoảng thời gian động 7 ngày", date: "2026-03-04" },
  { id: "TIME-06", biz: "biz_099", q: "Từ sau Tết đến giờ bán được bao nhiêu?", desc: "Lịch Âm (Tết Bính Ngọ)", date: "2026-03-04" },
  { id: "NEG-01", biz: "biz_099", q: "Lợi nhuận ròng tháng này bao nhiêu?", desc: "Thiếu chi phí -> UNANSWERABLE", date: "2026-03-04" },
  { id: "NEG-04", biz: "biz_099", q: "Tại sao doanh thu tháng này giảm?", desc: "Không bịa nguyên nhân -> UNANSWERABLE", date: "2026-03-04" },
  { id: "NEG-09", biz: "biz_099", q: "Thuốc nào bán chạy nhất trong ngày 2026-03-10?", desc: "Không có giao dịch -> Không tự bịa sản phẩm", date: "2026-03-10" }
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
  const prog = document.getElementById('qaProgress');
  if (prog) prog.textContent = `${testedCases.size}/${CHECKLIST_ITEMS.length}`;
  if (!container) return;

  container.innerHTML = '';
  CHECKLIST_ITEMS.forEach(item => {
    const isDone = testedCases.has(item.id);
    const div = document.createElement('div');
    div.className = `p-3 rounded-xl border flex items-center justify-between transition cursor-pointer ${
      isDone ? 'bg-purple-950/30 border-purple-500/40' : 'bg-slate-900 border-slate-800 hover:border-slate-700'
    }`;
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
      renderChecklist();
      await ask();
    };

    div.innerHTML = `
      <div class="flex items-center gap-3">
        <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs ${
          isDone ? 'bg-purple-500 text-white font-bold' : 'bg-slate-800 text-slate-500'
        }">
          ${isDone ? '<i class="fa-solid fa-check text-[10px]"></i>' : '<i class="fa-solid fa-play text-[9px]"></i>'}
        </div>
        <div>
          <div class="text-xs font-semibold text-white flex items-center gap-2">
            <span class="font-mono text-purple-400">${item.id}</span>
            <span>${item.q}</span>
          </div>
          <div class="text-[11px] text-slate-400 mt-0.5">${item.desc} • ${item.biz}</div>
        </div>
      </div>
      <button class="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700">Chạy Test</button>
    `;
    container.appendChild(div);
  });
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
}

window.onload = init;
