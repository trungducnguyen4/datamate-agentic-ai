let businesses = [];
let currentTables = {};

async function init() {
  await loadBusinesses();
  await loadSampleQuestions();
  setupEvents();
}

async function loadBusinesses() {
  const sel = document.getElementById('businessSelect');
  try {
    const res = await fetch('/api/businesses');
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
  try {
    const res = await fetch(`/api/business/${bizId}/tables`);
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

  html += `<h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Xem trước dữ liệu (Top 10 rows)</h4>
  <div class="overflow-x-auto border border-slate-800 rounded-xl">
    <table class="w-full text-left text-xs">
      <thead class="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
        <tr>`;
  t.preview_cols.forEach(c => {
    html += `<th class="px-3 py-2.5">${c}</th>`;
  });
  html += `</tr></thead><tbody class="divide-y divide-slate-800 text-slate-300">`;
  t.preview_rows.forEach(r => {
    html += `<tr class="hover:bg-slate-800/40">`;
    r.forEach(v => {
      html += `<td class="px-3 py-2 whitespace-nowrap">${v !== null ? v : '<span class="text-slate-600">NULL</span>'}</td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table></div>`;

  content.innerHTML = html;
  const modal = document.getElementById('tableModal');
  if (modal) modal.classList.remove('hidden');
}

async function loadSampleQuestions() {
  try {
    const res = await fetch('/api/sample-questions');
    if (!res.ok) return;
    const qList = await res.json();
    const pillsContainer = document.getElementById('samplePills');
    if (!pillsContainer) return;
    pillsContainer.innerHTML = '';
    qList.forEach(q => {
      const btn = document.createElement('button');
      btn.className = 'text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 px-2.5 py-1 rounded-lg transition';
      btn.textContent = q.question;
      btn.onclick = async () => {
        const sel = document.getElementById('businessSelect');
        if (sel) {
          sel.value = q.business_id;
          await onBusinessChange(q.business_id);
        }
        const qInput = document.getElementById('questionInput');
        if (qInput) qInput.value = q.question;
        const asOf = document.getElementById('asOfDate');
        if (asOf && q.as_of_date) {
          asOf.value = q.as_of_date;
        }
      };
      pillsContainer.appendChild(btn);
    });
  } catch (e) {
    console.error('Error loading sample questions:', e);
  }
}

function setupEvents() {
  const sel = document.getElementById('businessSelect');
  if (sel) sel.onchange = (e) => onBusinessChange(e.target.value);
  const closeBtn = document.getElementById('closeModalBtn');
  if (closeBtn) closeBtn.onclick = () => {
    const modal = document.getElementById('tableModal');
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
      body: JSON.stringify({ business_id: bizId, question: question, as_of_date: asOfDate })
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

  const tempDiv = document.getElementById('temporalInfo');
  if (tempDiv) {
    if (data.temporal) {
      const monthPart = data.temporal.target_month ? `<div><strong class="text-slate-400">Tháng:</strong> ${data.temporal.target_month}</div>` : '';
      tempDiv.innerHTML = `
        <div><strong class="text-slate-400">Từ ngày:</strong> ${data.temporal.start_date}</div>
        <div><strong class="text-slate-400">Đến ngày:</strong> ${data.temporal.end_date}</div>
        ${monthPart}
      `;
    } else {
      tempDiv.innerHTML = '<p class="text-slate-500 italic">Không có mốc thời gian cụ thể</p>';
    }
  }

  const planDiv = document.getElementById('planInfo');
  if (planDiv) {
    const unansReason = data.plan.unanswerable_reason ? `<div class="text-amber-400 text-[11px] mt-1"><i class="fa-solid fa-circle-info"></i> ${data.plan.unanswerable_reason}</div>` : '';
    planDiv.innerHTML = `
      <div><strong class="text-slate-400">Ý định (Intent):</strong> <span class="text-indigo-400 font-mono">${data.plan.intent}</span></div>
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
