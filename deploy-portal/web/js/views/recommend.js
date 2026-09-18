import { api, esc, num, state, toast, copyText, download, verificationBlock, docSourceBlock,
  isCudaGpu as isCuda, computeLabel as computeText, stackLabel as stackLineOf } from '../app.js';

const STORAGE_KEY = 'deploy-portal.hardware';
const WORKLOADS = ['agent', 'coding', 'reasoning', 'general', 'english'];
const PLAN_CHOICES = [3, 4, 5];

const DEFAULTS = {
  gpu_id: '',
  gpu_count: 8,
  nodes: 1,
  driver_version: '',
  host_ram_gib: 512,
  disk_free_gib: 1000,
  context_k: 32,
  workload: 'agent,coding,reasoning',
  require_multimodal: false,
  require_permissive_license: false,
};

function verifiedGpus() {
  return (state.gpus || []).filter((gpu) => gpu.verification && gpu.verification.status === 'ok');
}

function loadHardware() {
  const gpus = verifiedGpus();
  const fallback = gpus.length ? gpus[0].id : '';
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const saved = { ...DEFAULTS, ...JSON.parse(raw) };
      if (!gpus.some((gpu) => gpu.id === saved.gpu_id)) saved.gpu_id = fallback;
      return saved;
    }
  } catch (error) {
    /* 忽略损坏的本地缓存 */
  }
  return { ...DEFAULTS, gpu_id: fallback };
}

function saveHardware(hardware) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(hardware));
  } catch (error) {
    /* 隐私模式下写不进去,忽略 */
  }
}

function workloadSet(value) {
  return String(value || '')
    .split(/[,;，；]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function gpuById(id) {
  return (state.gpus || []).find((gpu) => gpu.id === id) || null;
}

function gpuOptionLabel(gpu) {
  const status = gpu.verification && gpu.verification.status === 'ok' ? '' : '(核实失败)';
  return gpu.name + ' · ' + num(gpu.vram_gib) + 'GB · ' + computeText(gpu) + status;
}

// 厂商分组。昇腾与 NVIDIA 的部署栈完全不通用,混在一个下拉里会让人以为
// 同一套 CUDA 镜像能直接搬到昇腾卡上。
const VENDOR_GROUPS = [
  { vendor: 'nvidia', label: 'NVIDIA(CUDA 生态)' },
  { vendor: 'huawei', label: '华为昇腾(CANN 生态)' },
];

function gpuSpecHtml(gpu) {
  if (!gpu) return '<p class="muted small">没有可用的 GPU 目录数据。</p>';
  const check = gpu.verification || {};
  const link = '<a href="' + esc(gpu.source_url) + '" target="_blank" rel="noreferrer">厂商官方页</a>';
  // 只有 NVIDIA 卡的算力能对官方算力表核实;昇腾没有 sm 等级,不能挂那个链接,
  // 否则等于拿 NVIDIA 的标度冒充昇腾的核实依据。
  const cc = isCuda(gpu)
    ? '<a href="' + esc((state.gpuMeta && state.gpuMeta.cc_source && state.gpuMeta.cc_source.url) || '#') +
      '" target="_blank" rel="noreferrer">官方算力表</a>'
    : '官方产品页(该生态无 CUDA 算力等级)';
  const basis = gpu.vram_basis ? '<br><span class="muted">显存口径:' + esc(gpu.vram_basis) + '</span>' : '';
  const ccBasis = gpu.compute_capability_basis
    ? '<br><span class="muted">算力口径:' + esc(gpu.compute_capability_basis) + '</span>' : '';
  const fp8Basis = gpu.fp8_basis ? '<br><span class="muted">FP8 口径:' + esc(gpu.fp8_basis) + '</span>' : '';
  const arch = gpu.architecture
    ? esc(gpu.architecture)
    : '<span class="muted">架构:' + esc(gpu.architecture_basis || '厂商页未标注') + '</span>';
  return '<p class="muted small" style="margin:8px 0 0">' +
    arch + ' · ' + esc(gpu.form_factor) + ' · ' + esc(gpu.memory_type) +
    ' · ' + esc(computeText(gpu)) +
    (gpu.fp8_supported ? ' · 支持 FP8' : ' · 不支持 FP8') + '<br>' +
    '显存/算力核实:' + link + ' + ' + cc + ',核实于 ' + esc((check.checked_at || '').slice(0, 10)) +
    basis + ccBasis + fp8Basis + '</p>';
}

function gpuOptionHtml(gpu, selectedId) {
  return '<option value="' + esc(gpu.id) + '"' + (gpu.id === selectedId ? ' selected' : '') + '>' +
    esc(gpuOptionLabel(gpu)) + '</option>';
}

function gpuOptionsHtml(gpus, selectedId) {
  const known = new Set(VENDOR_GROUPS.map((group) => group.vendor));
  const groups = VENDOR_GROUPS.map((group) => {
    const items = gpus.filter((gpu) => (gpu.vendor || 'nvidia') === group.vendor);
    if (!items.length) return '';
    return '<optgroup label="' + esc(group.label) + '">' +
      items.map((gpu) => gpuOptionHtml(gpu, selectedId)).join('') + '</optgroup>';
  });
  // 目录里出现未登记的厂商时也要列出来,不能因为分组写死就把卡藏起来。
  const other = gpus.filter((gpu) => !known.has(gpu.vendor || 'nvidia'));
  if (other.length) {
    groups.push('<optgroup label="其他厂商">' +
      other.map((gpu) => gpuOptionHtml(gpu, selectedId)).join('') + '</optgroup>');
  }
  return groups.join('');
}

function ecosystemNoteHtml(gpu) {
  if (isCuda(gpu)) return '';
  return '<p class="muted small" style="margin:8px 0 0">' +
    '所选卡属于 ' + esc(String((gpu && gpu.ecosystem) || '').toUpperCase()) +
    ' 生态:没有 CUDA 算力等级,登记表里的 NVIDIA 驱动下限与 CUDA/vLLM 镜像对它不适用,' +
    '所以驱动输入框已停用;CANN 版本与镜像要求按下方部署方法文档核对。</p>';
}

/** 换卡时同步「哪些控件对这个生态有效」,不留一个改了没反应的空控件。 */
function syncEcosystemUi(container) {
  const select = container.querySelector('#gpu_id');
  if (!select) return;
  const gpu = gpuById(select.value);
  const driverInput = container.querySelector('#driver_version');
  if (driverInput) driverInput.disabled = !isCuda(gpu);
  const host = container.querySelector('#ecosystem-note');
  if (host) host.innerHTML = ecosystemNoteHtml(gpu);
}

function formHtml(hardware) {
  const gpus = verifiedGpus();
  const options = gpuOptionsHtml(gpus, hardware.gpu_id);
  const selectedGpu = gpuById(hardware.gpu_id);
  const workloads = WORKLOADS.map((item) => {
    const checked = workloadSet(hardware.workload).includes(item) ? ' checked' : '';
    return '<label class="small"><input type="checkbox" name="workload" value="' + item + '"' + checked + '> ' + esc(item) + '</label>';
  }).join('');
  const plans = PLAN_CHOICES.map((count) =>
    '<option value="' + count + '">' + count + ' 个方案</option>').join('');
  return `
  <div class="stack-16">
    <div class="card">
      <h2>硬件资源</h2>
      ${gpus.length ? `
      <label class="field"><span>GPU 型号(来自已核实的 GPU 目录)</span>
        <select id="gpu_id">${options}</select>
      </label>
      <div id="gpu-spec">${gpuSpecHtml(selectedGpu)}</div>
      <div id="ecosystem-note">${ecosystemNoteHtml(selectedGpu)}</div>` :
      '<p class="muted">GPU 目录为空:先运行 <code>python deploy-portal/tools/sync_gpus.py</code> 核实 GPU 规格。</p>'}
      <div class="grid-2" style="margin-top:12px">
        <label class="field"><span>GPU 数量</span><input type="number" min="1" id="gpu_count" value="${esc(hardware.gpu_count)}"></label>
        <label class="field"><span>节点数</span><input type="number" min="1" id="nodes" value="${esc(hardware.nodes)}"></label>
        <label class="field"><span>驱动版本(NVIDIA)</span><input type="text" id="driver_version" value="${esc(hardware.driver_version)}"${isCuda(selectedGpu) ? '' : ' disabled'}></label>
        <label class="field"><span>需要的上下文 K</span><input type="number" min="1" id="context_k" value="${esc(hardware.context_k)}"></label>
        <label class="field"><span>主存 GiB</span><input type="number" id="host_ram_gib" value="${esc(hardware.host_ram_gib)}"></label>
        <label class="field"><span>可用磁盘 GiB</span><input type="number" id="disk_free_gib" value="${esc(hardware.disk_free_gib)}"></label>
      </div>
      <label class="field"><span>用途(逗号分隔)</span><input type="text" id="workload" value="${esc(hardware.workload)}"></label>
      <div class="row small">
        <span class="muted">常用:</span>${workloads}
      </div>
      <div class="row" style="margin-top:10px">
        <label class="small"><input type="checkbox" id="require_multimodal"${hardware.require_multimodal ? ' checked' : ''}> 需要多模态</label>
        <label class="small"><input type="checkbox" id="require_permissive_license"${hardware.require_permissive_license ? ' checked' : ''}> 仅限宽松许可</label>
      </div>
    </div>
    <div class="card">
      <h2>偏好</h2>
      <label class="field"><span>排序偏好</span>
        <select id="preference">
          <option value="balanced">balanced 综合</option>
          <option value="quality">quality 能力优先</option>
          <option value="throughput">throughput 吞吐优先</option>
        </select>
      </label>
      <label class="field"><span>展示条数</span>
        <select id="top">${plans.replace('value="' + (hardware.top || 5) + '"', 'value="' + (hardware.top || 5) + '" selected')}</select>
      </label>
      <div class="row">
        <button class="primary" id="run">开始推荐</button>
        <button class="ghost" id="reset">恢复默认</button>
      </div>
      <p class="muted small" style="margin-bottom:0">推荐按实测权重与算出的 KV cache 匹配,只做部署预筛选;上线前仍要按方案文档做实机验收。</p>
    </div>
  </div>`;
}

function readForm(root) {
  const value = (id) => root.querySelector('#' + id).value.trim();
  const checked = (id) => root.querySelector('#' + id).checked;
  const workloads = Array.from(root.querySelectorAll('input[name="workload"]:checked')).map((node) => node.value);
  const merged = new Set([...workloadSet(value('workload')), ...workloads]);
  return {
    gpu_id: value('gpu_id'),
    gpu_count: Number(value('gpu_count')),
    nodes: Number(value('nodes')),
    driver_version: value('driver_version'),
    host_ram_gib: Number(value('host_ram_gib')),
    disk_free_gib: Number(value('disk_free_gib')),
    context_k: Number(value('context_k')),
    workload: Array.from(merged).join(','),
    require_multimodal: checked('require_multimodal'),
    require_permissive_license: checked('require_permissive_license'),
  };
}

function verifySummary(verification) {
  if (!verification || !verification.repos || !verification.repos.length) {
    return '<p class="muted small" style="margin-top:8px">该部署档没有对应的官方仓库抓取记录,未做核对。</p>';
  }
  const reference = verification.repos.find((repo) => repo.is_reference) || verification.repos[0];
  const weightCheck = (reference.checks || []).find((check) => check.field === '权重大小');
  const KIND = { match: 'ok', close: 'warn', differ: 'bad' };
  const parts = [
    '<a href="' + esc(reference.source_url || '#') + '" target="_blank" rel="noreferrer">' + esc(reference.repo) + '</a>',
    '<code class="small">' + esc((reference.revision || '').slice(0, 10)) + '</code>',
    esc(reference.license || '未声明'),
  ];
  if (weightCheck) {
    // 登记值已按实测订正过,所以这里比的是「当初核实的值 vs 上游当前值」,不是声明 vs 事实。
    parts.push('上游当前权重 ' + esc(weightCheck.upstream || weightCheck.real) +
      ' <span class="badge ' + (KIND[weightCheck.level] || 'info') + '">登记 ' +
      esc(weightCheck.recorded || weightCheck.declared) + ' / ' +
      (weightCheck.delta_pct > 0 ? '+' : '') + esc(num(weightCheck.delta_pct, 1)) + '%</span>');
  }
  const note = reference.is_reference ? '' : ' <span class="badge warn">未找到同档位官方仓库</span>';
  return '<p class="small muted" style="margin:8px 0 0">官方仓库核对:' + parts.join(' · ') + note + '</p>';
}

function memoryHtml(memory) {
  if (!memory) return '';
  const usedPct = memory.utilization === null ? '—' : num(memory.utilization * 100, 0) + '%';
  // 反算的上下文上限。算不出时必须说清为什么,不给一个看着精确的数。
  const maxContext = memory.max_context_k === null || memory.max_context_k === undefined
    ? '<span class="badge warn">无法反算</span>' +
      (memory.max_context_note ? '<br><span class="muted small">' + esc(memory.max_context_note) + '</span>' : '')
    : '约 ' + esc(memory.max_context_k) + 'K ' +
      (memory.max_context_limit === 'model'
        ? '<span class="badge info">受该档标称上下文限制</span>'
        : '<span class="badge info">显存反算上限</span>') +
      (memory.max_context_note ? '<br><span class="muted small">' + esc(memory.max_context_note) + '</span>' : '');
  const kv = memory.kv_gib === null
    ? '<span class="badge warn">KV 结构无法核实,只按权重下界核算</span>' +
      (memory.kv_note ? '<br><span class="muted small">' + esc(memory.kv_note) + '</span>' : '')
    : esc(memory.kv_gib) + ' GiB(按 ' + esc(memory.kv_context_k) + 'K 上下文)';
  const kind = memory.attention_kind ? '<span class="badge info">' + esc(memory.attention_kind) + '</span>' : '';
  return `
    <dl class="kv">
      <dt>实测权重</dt><dd>${esc(memory.weight_gib)} GiB</dd>
      <dt>KV cache ${kind}</dt><dd>${kv}</dd>
      <dt>运行时余量</dt><dd>${num(memory.runtime_overhead_ratio * 100, 0)}%(工程预留,非实测)</dd>
      <dt>合计需求</dt><dd>${esc(memory.needed_gib)} GiB</dd>
      <dt>单卡需求</dt><dd>${esc(memory.per_card_gib)} GiB(TP=${esc(memory.tp)})</dd>
      <dt>显存占用</dt><dd>${usedPct} 已用(按并行组 ${esc(memory.tp)} 张卡共 ${esc(memory.engaged_vram_gib)} GiB)</dd>
      <dt>空闲显存</dt><dd>${esc(memory.waste_gib)} GiB${memory.replicas > 1 ? '(当前卡数可放 ' + esc(memory.replicas) + ' 个副本)' : ''}</dd>
      <dt>最长上下文</dt><dd>${maxContext}</dd>
    </dl>
    ${memory.kv_basis ? '<p class="muted small" style="margin:0">KV 口径:' + esc(memory.kv_basis) + '</p>' : ''}`;
}

function rankCard(item, index, gpu) {
  const profile = item.profile;
  const cuda = isCuda(gpu);
  const recipeLinks = (item.recipes || [])
    .map((id) => '<a class="badge info" href="#/recipes/' + esc(id) + '">查看部署方案</a>')
    .join(' ');
  // 跨生态的方案不能被悄悄丢掉,也不能装成能直接用:如实说明它在别的生态下。
  const foreign = Array.from(new Set((item.recipes_other_ecosystem || [])
    .map((entry) => entry.ecosystem)));
  const foreignNote = foreign.length
    ? '<p class="muted small" style="margin:6px 0 0">另有 ' + foreign.length + ' 套 <code>' +
      esc(foreign.join('/')) + '</code> 生态的部署方法属于同名模型,但那是另一套栈的实现,' +
      '不能直接搬到你选的这张卡上。</p>'
    : '';
  const warnings = (item.warnings || [])
    .map((text) => '<li>' + esc(text) + '</li>')
    .join('');
  const verify = verifySummary(item.verification);
  return `
  <div class="rank-card${index === 0 ? ' first' : ''}">
    <div class="row between">
      <h4>${index === 0 ? '首选 · ' : '#' + (index + 1) + ' · '}${esc(profile.model_name)}</h4>
      <span class="score">${num(item.score, 1)} 分</span>
    </div>
    <div class="row small">
      <span class="badge">${esc(profile.quantization)}</span>
      <span class="badge">${esc(profile.recommended_layout)}</span>
      ${recipeLinks || '<span class="muted small">暂无写好的部署方案</span>'}
    </div>
    ${foreignNote}
    ${memoryHtml(item.memory)}
    <dl class="kv">
      ${cuda ? `
      <dt>部署栈</dt><dd>CUDA ${esc(profile.cuda_runtime)} · ${esc(profile.vllm_image)}</dd>
      <dt>驱动下限</dt><dd>${esc(profile.min_driver)}</dd>` : `
      <dt>部署栈</dt><dd><span class="badge warn">CUDA 栈登记档</span>
        <br><span class="muted small">此档登记的是 CUDA 栈实现(CUDA ${esc(profile.cuda_runtime)} ·
        ${esc(profile.vllm_image)}),昇腾要用对应生态的实现,版本需另行核实。</span></dd>
      <dt>驱动下限</dt><dd><span class="muted">不适用(该档的 NVIDIA 驱动下限  ${esc(profile.min_driver)}
        与昇腾无关,判定时已跳过)</span></dd>`}
      <dt>许可证</dt><dd>${esc(profile.license)} <code class="small">${esc(profile.license_id)}</code></dd>
      <dt>上下文</dt><dd>${esc(profile.context_k)}K <code class="small">${esc(profile.context_source)}</code></dd>
      <dt>用途</dt><dd>${esc(profile.workloads)}</dd>
    </dl>
    ${verify}
    ${warnings ? '<ul class="warn-list">' + warnings + '</ul>' : ''}
  </div>`;
}

function officialMatrixHtml(official) {
  if (!official) return '';
  const src = official.source || {};
  const links = [];
  if (src.matrix_page) links.push('<a href="' + esc(src.matrix_page) + '" target="_blank" rel="noopener">打开官方支持矩阵页</a>');
  if (src.project_url) links.push('<a href="' + esc(src.project_url) + '" target="_blank" rel="noopener">项目仓库</a>');
  const head = `
    <div class="card">
      <h2>官方支持矩阵(公开来源)</h2>
      <p class="muted small" style="margin-top:0">
        这张卡能跑哪些模型,以官方文档为准:${esc(src.project || '')}
        ${src.doc_version ? '<code>' + esc(src.doc_version) + '</code>' : ''}
        ${src.doc_channel ? '(' + esc(src.doc_channel) + ' 版)' : ''}
        ${links.join(' · ')}
        ${src.generated_at ? '<br>抓取于 ' + esc(src.generated_at) + ';' : ''}
        ${esc(src.policy || '')}
      </p>`;
  if (!official.available) {
    return head + '<p class="muted small">' + esc(official.reason || '还没有抓取官方支持矩阵。') + '</p></div>';
  }
  if (!official.family) {
    return head +
      '<p class="small" style="color:var(--warn,#a60)">' + esc(official.reason || '') + '</p>' +
      '<p class="muted small">官方矩阵在列的硬件族:' + (official.families || []).map(esc).join('、') + '</p>' +
      '</div>';
  }

  const models = official.models || [];
  // `Support` 不在 capabilities 里(它和 Model/Note 一起单列),所以这一列取 item.support。
  const columns = [
    ['BF16', 'BF16'], ['W8A8', 'W8A8'],
    ['Tensor Parallel', 'Tensor Parallel'], ['Expert Parallel', 'Expert Parallel'],
    ['max-model-len', 'max-model-len'],
  ];
  const rows = models.map((item) => {
    const caps = item.capabilities || {};
    const doc = (item.tutorial && item.tutorial.url)
      ? '<a href="' + esc(item.tutorial.url) + '" target="_blank" rel="noopener">官方教程</a>'
      : '<span class="muted">官方未给教程</span>';
    return '<tr>' +
      '<td>' + esc(item.model) +
        (item.note ? '<br><span class="muted small">' + esc(item.note) + '</span>' : '') + '</td>' +
      '<td>' + esc(item.support || '—') + '</td>' +
      columns.map((key) => '<td>' + esc(caps[key[0]] || '—') + '</td>').join('') +
      '<td>' + doc + '</td></tr>';
  }).join('');

  const withCommands = models.filter((item) => ((item.tutorial || {}).blocks || []).length);
  const commands = withCommands.map((item) => {
    const blocks = item.tutorial.blocks.map((block) =>
      '<p class="muted small" style="margin:10px 0 4px">' + esc(block.section) +
      (block.tab ? ' · ' + esc(block.tab) : '') + ' · ' + esc(block.language) + '</p>' +
      '<pre class="code">' + esc(block.code) + '</pre>').join('');
    return '<details style="margin:10px 0"><summary>' + esc(item.model) + ' · 官方启动命令' +
      '(教程共 ' + esc(item.tutorial.block_total) + ' 个代码块,这里取部署相关小节 ' +
      esc(item.tutorial.blocks.length) + ' 个)</summary>' + blocks +
      '<p class="muted small">命令逐字来自 <a href="' + esc(item.tutorial.url) +
      '" target="_blank" rel="noopener">' + esc(item.tutorial.title || item.tutorial.key) +
      '</a>,本平台不改写。</p></details>';
  }).join('');

  return head +
    '<p class="small" style="margin:8px 0 0">这张卡的卡名里逐字出现了官方硬件族 <b>' +
    esc(official.family) + '</b>,所以按官方口径给出该族在列的 ' + esc(models.length) +
    ' 个模型行(其中生成式 ' + esc(official.generative_total) + ' 个)。' +
    '<br><span class="muted">匹配规则:' + esc(official.basis || '') + '</span></p>' +
    (models.length
      ? '<div class="table-wrap"><table><thead><tr><th>官方模型</th>' +
        '<th>官方支持</th>' +
        columns.map((key) => '<th>' + esc(key[1]) + '</th>').join('') +
        '<th>官方文档</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
      : '<p class="muted small">官方矩阵里这张卡没有任何模型行。</p>') +
    (commands ? '<h3 style="margin:16px 0 0">官方部署方法(逐字照搬)</h3>' + commands : '') +
    '</div>';
}
function renderResult(target, data) {
  const totals = data.totals;
  const gpu = gpuById(data.hardware.gpu_id);
  // 昇腾没有 NVIDIA 驱动下限这回事,写「驱动 未填」会让人以为缺了个必填项。
  const stackLine = esc(stackLineOf(gpu, data.hardware));
  const parts = [];
  parts.push(`
  <div class="card">
    <div class="row between">
      <h2 style="margin:0">推荐结果</h2>
      <div class="row">
        <button class="tiny" id="copy-md">复制 Markdown 报告</button>
        <button class="tiny" id="export-json">导出 JSON</button>
      </div>
    </div>
    <p class="muted small" style="margin:8px 0 0">
      硬件:${esc(totals.gpu_count)} × ${esc(data.hardware.gpu_name)}(单卡 ${num(totals.vram_per_gpu_gib)} GiB,
      合计约 ${num(totals.total_vram_gib)} GiB),${esc(computeText(gpu))},
      ${stackLine};按 ${esc(data.hardware.context_k)}K 上下文核算;
      偏好 ${esc(data.preference)}。实际匹配出 ${esc(data.plans_total)} 个可行方案,未通过 ${esc(data.rejected_total)} 个。
    </p>
    ${gpu ? gpuSpecHtml(gpu) : ''}
    ${data.ecosystem_note ? '<p class="muted small" style="margin:8px 0 0">' + esc(data.ecosystem_note) + '</p>' : ''}
    ${data.stack_note ? '<p class="small" style="margin:8px 0 0;color:var(--warn,#a60)">' + esc(data.stack_note) + '</p>' : ''}
    <p class="muted small" style="margin:8px 0 0">${esc(data.scoring_note || '')}</p>
  </div>`);

  parts.push(officialMatrixHtml(data.official_matrix));

  if (data.plans.length) {
    parts.push('<div class="card"><h2>匹配到的部署方案</h2>' +
      data.plans.map((item, index) => rankCard(item, index, gpu)).join('') + '</div>');
  } else {
    parts.push('<div class="card"><h2>匹配到的部署方案</h2><p class="muted">没有部署档满足全部硬约束。看下面的缺口清单,或放宽上下文、卡数、多模态等需求。</p></div>');
  }

  if (data.rejected.length) {
    parts.push(`
    <div class="card">
      <h2>接近但未通过</h2>
      <p class="muted small" style="margin-top:0">这里只列前 ${esc(data.rejected.length)} 个,缺口按实测核算给出。</p>
      <div class="table-wrap"><table>
        <thead><tr><th>模型 / 量化</th><th>主要缺口</th></tr></thead>
        <tbody>${data.rejected.map((item) => `
          <tr>
            <td>${esc(item.profile.model_name)}<br><span class="muted small">${esc(item.profile.quantization)}</span></td>
            <td><ul class="fail-list">${item.failures.map((text) => '<li>' + esc(text) + '</li>').join('')}</ul></td>
          </tr>`).join('')}
        </tbody>
      </table></div>
    </div>`);
  }

  const top = data.plans[0];
  if (top) {
    parts.push(verificationBlock(top.verification, { lead: true }));
    if (top.verification && top.verification.docs && top.verification.docs.length) {
      parts.push(docSourceBlock(top.verification.docs, '首选方案的权威来源'));
    }
  }

  target.innerHTML = '<div class="stack-16">' + parts.join('') + '</div>';

  target.querySelector('#export-json').addEventListener('click', () => {
    download('recommendation.json', JSON.stringify(data, null, 2));
    toast('已导出 JSON');
  });
  target.querySelector('#copy-md').addEventListener('click', () => copyText(toMarkdown(data), '已复制 Markdown'));
}

function toMarkdown(data) {
  const totals = data.totals;
  const lines = [];
  lines.push('# 大模型部署推荐报告', '');
  lines.push('- 硬件:' + totals.gpu_count + ' × ' + data.hardware.gpu_name +
    '(单卡 ' + totals.vram_per_gpu_gib + ' GiB,合计约 ' + totals.total_vram_gib + ' GiB)');
  lines.push('- 计算能力:' + computeText(gpuById(data.hardware.gpu_id)));
  lines.push('- ' + stackLineOf(gpuById(data.hardware.gpu_id), data.hardware) +
    ' · 核算上下文:' + data.hardware.context_k + 'K · 偏好:' + data.preference, '');
  if (data.ecosystem_note) lines.push('> ' + data.ecosystem_note, '');
  lines.push('## 匹配到的部署方案', '');
  lines.push('| 排名 | 模型 | 量化 | 布局 | 实测权重GiB | KV GiB | 合计GiB | 单卡GiB | 占用率 | 最长上下文K | 得分 |');
  lines.push('|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|');
  data.plans.forEach((item, index) => {
    const p = item.profile;
    const m = item.memory || {};
    lines.push('| ' + (index + 1) + ' | ' + p.model_name + ' | ' + p.quantization +
      ' | ' + p.recommended_layout + ' | ' + m.weight_gib + ' | ' + (m.kv_gib === null ? '无法核实' : m.kv_gib) +
      ' | ' + m.needed_gib + ' | ' + m.per_card_gib + ' | ' + Math.round((m.utilization || 0) * 100) + '%' +
      ' | ' + (m.max_context_k === null || m.max_context_k === undefined ? '无法反算' : m.max_context_k) +
      ' | ' + item.score + ' |');
  });
  lines.push('', '## 风险提示', '');
  data.plans.forEach((item) => {
    if (item.warnings.length) {
      lines.push('- ' + item.profile.model_name + ':' + item.warnings.join(';'));
    }
  });
  if (data.rejected.length) {
    lines.push('', '## 接近但未通过', '');
    data.rejected.forEach((item) => {
      lines.push('- ' + item.profile.model_name + ' · ' + item.profile.quantization + ':' + item.failures.join(';'));
    });
  }
  lines.push('', '> 权重为 artifact 实测值,KV cache 由真实 config 的 attention 结构算出;');
  lines.push('> 结果只做部署预筛选,不替代实机验收。');
  return lines.join('\n');
}

export async function render(container) {
  const hardware = loadHardware();
  container.innerHTML = `
  <div class="layout">
    ${formHtml(hardware)}
    <div id="result"><div class="card"><h2>推荐结果</h2><p class="muted">选好 GPU 型号与卡数后点“开始推荐”。</p></div></div>
  </div>`;

  const run = async () => {
    const payload = readForm(container);
    saveHardware({ ...payload, top: Number(container.querySelector('#top').value) });
    const result = container.querySelector('#result');
    result.innerHTML = '<div class="card"><p class="muted">计算中…</p></div>';
    try {
      const data = await api('/api/recommend', {
        method: 'POST',
        body: JSON.stringify({
          hardware: payload,
          preference: container.querySelector('#preference').value,
          top: Number(container.querySelector('#top').value) || 5,
        }),
      });
      renderResult(result, data);
    } catch (error) {
      result.innerHTML = '<div class="card"><h2>计算失败</h2><p class="muted">' + esc(error.message) + '</p></div>';
    }
  };

  const runButton = container.querySelector('#run');
  if (runButton) runButton.addEventListener('click', run);
  container.querySelector('#reset').addEventListener('click', () => {
    localStorage.removeItem(STORAGE_KEY);
    render(container);
  });
  const gpuSelect = container.querySelector('#gpu_id');
  if (gpuSelect) {
    gpuSelect.addEventListener('change', () => {
      container.querySelector('#gpu-spec').innerHTML = gpuSpecHtml(gpuById(gpuSelect.value));
      syncEcosystemUi(container);
    });
  }

  if ((state.gpus || []).length) await run();
}
