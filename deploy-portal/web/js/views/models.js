import { api, esc, num, copyText, bindCopyButtons, toast } from '../app.js';

function provenance(summary) {
  if (!summary.available) {
    return '<div class="card"><h2>还没有抓取快照</h2><p class="muted">' + esc(summary.hint || '') + '</p>' +
      '<pre class="code">python deploy-portal/tools/sync_hf.py</pre></div>';
  }
  const counts = summary.counts || {};
  const docs = summary.docs || {};
  const errors = summary.errors || [];
  const errorRows = errors.map((item) => `
    <tr><td>${esc(item.scope)}</td><td>${esc(item.stage || item.sort || '')}</td><td class="small">${esc(item.error)}</td></tr>
  `).join('');
  return `
  <div class="card">
    <h2>数据来源与抓取时间</h2>
    <dl class="kv">
      <dt>使用端点</dt><dd><code>${esc(summary.endpoint_used)}</code> <span class="badge ${summary.endpoint_kind === 'domestic-mirror' ? 'ok' : 'info'}">${esc(summary.endpoint_kind)}</span></dd>
      <dt>抓取时间</dt><dd>${esc(summary.fetched_at)} (UTC)</dd>
      <dt>索引规模</dt><dd>${esc(counts.index)} 个模型 / ${esc(counts.organizations)} 个组织,每组织上限 ${esc(summary.per_org_limit)}</dd>
      <dt>重点仓库</dt><dd>${esc(counts.details)} 个(含 revision、许可证、参数量、权重大小、上下文长度)</dd>
      <dt>权威文档</dt><dd>${docs.available ? esc((docs.counts || {}).ok) + ' / ' + esc((docs.counts || {}).checked) + ' 个可达,抓取于 ' + esc(docs.fetched_at) : '未验证'}</dd>
      <dt>抓取错误</dt><dd>${errors.length ? errors.length + ' 条(见下表,未被隐藏)' : '无'}</dd>
    </dl>
    <p class="muted small">${esc(summary.endpoint_note || '')}</p>
    ${errors.length ? '<div class="table-wrap"><table><thead><tr><th>范围</th><th>阶段</th><th>错误</th></tr></thead><tbody>' + errorRows + '</tbody></table></div>' : ''}
  </div>`;
}

function modelRow(model) {
  const shortSha = (model.sha || '').slice(0, 10);
  return `
  <tr data-repo="${esc(model.id)}">
    <td><a href="#/models/${esc(model.id)}">${esc(model.id)}</a></td>
    <td class="small">${esc(model.organization_name || model.organization)}</td>
    <td class="small">${esc(model.pipeline_tag || '—')}</td>
    <td class="small">${esc(model.license || '—')}</td>
    <td class="small">${model.downloads === null || model.downloads === undefined ? '—' : num(model.downloads)}</td>
    <td class="small">${esc((model.last_modified || '').slice(0, 10))}</td>
    <td><code class="small">${esc(shortSha)}</code></td>
  </tr>`;
}

function detailPanel(detail) {
  const gguf = (detail.gguf_dirs || []).map((item) => `
    <tr><td><code class="small">${esc(item.dir)}</code></td><td>${esc(item.files)}</td><td>${esc(item.gib)} GiB</td></tr>
  `).join('');
  const quant = detail.quantization_config
    ? '<pre class="code">' + esc(JSON.stringify(detail.quantization_config, null, 2)) + '</pre>'
    : '<span class="muted small">config.json 未声明量化配置</span>';
  const verification = detail.verification;
  let verifyBlock = '';
  if (verification && verification.repos.length) {
    const rows = verification.repos.map((repo) => `
      <tr>
        <td>${repo.is_reference ? '<span class="badge ok">对照档</span> ' : ''}${esc(repo.repo)}<br><span class="muted small">${esc(repo.role)}</span></td>
        <td class="small">${esc(repo.quant)}</td>
        <td class="small">${repo.weight_gib ? esc(repo.weight_gib) + ' GiB' : '—'}</td>
        <td class="small">${repo.total_params_b ? esc(repo.total_params_b) + ' B' : '—'}</td>
      </tr>`).join('');
    verifyBlock = `
    <h5 class="small" style="color:var(--muted)">同档位仓库核对</h5>
    <p class="muted small" style="margin-top:0">目标量化档位:${esc(verification.target_quant || '未识别')}。只有档位一致的仓库才用于权重对比;
      目录登记值已按实测订正,逐项漂移检查见对应部署档详情。</p>
    <div class="table-wrap"><table>
      <thead><tr><th>仓库</th><th>档位</th><th>实测权重</th><th>实测参数</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  }

  return `
  <div class="card">
    <div class="row between">
      <h2 style="margin:0">${esc(detail.repo)}</h2>
      <a class="badge" href="#/models">← 返回模型库</a>
    </div>
    <div class="row small" style="margin-top:8px">
      <span class="badge info">${esc(detail.role || '重点仓库')}</span>
      <span class="badge">档位 ${esc(detail.quant || '未标注')}</span>
      <span class="badge">许可证 ${esc(detail.license || '未声明')}</span>
    </div>
    <dl class="kv">
      <dt>revision</dt><dd><code>${esc(detail.revision || '未知')}</code></dd>
      <dt>官方地址</dt><dd>${detail.source_url ? '<a href="' + esc(detail.source_url) + '" target="_blank" rel="noreferrer">' + esc(detail.source_url) + '</a>' : '—'}</dd>
      <dt>参数量</dt><dd>${detail.total_params_b ? esc(detail.total_params_b) + ' B' : '未提供 safetensors 索引'}</dd>
      <dt>权重</dt><dd>${detail.weight_gib ? esc(detail.weight_gib) + ' GiB(' + esc(detail.weight_shards) + ' 个分片)' : '—'}
        ${detail.gguf_gib ? '<br>GGUF 合计 ' + esc(detail.gguf_gib) + ' GiB / ' + esc(detail.gguf_file_count) + ' 个文件' : ''}</dd>
      <dt>上下文</dt><dd>${detail.context_k
        ? esc(detail.context_k) + ' K(max_position_embeddings ' + esc(detail.max_position_embeddings) + ')'
        : (detail.config_missing === true
          ? '<span class="muted">仓库不含 config.json(GGUF 类仓库属正常)</span>'
          : '<span class="muted">config.json 未取到(受限仓库或镜像超时),上下文需人工核对</span>')}</dd>
      <dt>架构</dt><dd>${esc((detail.architectures || []).join(', ') || detail.model_type || '—')}</dd>
      <dt>专家数</dt><dd>${detail.num_experts ? esc(detail.num_experts) + '(每 token 激活 ' + esc(detail.num_experts_per_tok) + ')' : '非 MoE 或未声明'}</dd>
      <dt>权重精度</dt><dd>${esc(detail.torch_dtype || '—')}</dd>
      <dt>下载 / 点赞</dt><dd>${num(detail.downloads)} / ${num(detail.likes)}</dd>
      <dt>最后更新</dt><dd>${esc(detail.last_modified)}</dd>
      <dt>标签</dt><dd class="small">${esc((detail.tags || []).join(', '))}</dd>
    </dl>
    <div class="row between" style="margin-top:10px">
      <h5 class="small" style="color:var(--muted);margin:0">config.json 中的量化配置</h5>
      <button class="tiny" data-copy="${esc(JSON.stringify(detail.quantization_config || {}, null, 2))}">复制</button>
    </div>
    ${quant}
    ${gguf ? '<h5 class="small" style="color:var(--muted)">GGUF 量化档分布</h5><div class="table-wrap"><table><thead><tr><th>目录</th><th>文件数</th><th>合计</th></tr></thead><tbody>' + gguf + '</tbody></table></div>' : ''}
    ${verifyBlock}
  </div>`;
}

export async function render(container, params) {
  if (params && params.length) {
    const repo = params.join('/');
    const detail = await api('/api/hf-detail?repo=' + encodeURIComponent(repo));
    container.innerHTML = detailPanel(detail);
    bindCopyButtons(container);
    return;
  }

  container.innerHTML = `
  <div id="summary"><div class="card"><p class="muted">加载中…</p></div></div>
  <div class="card">
    <h2>官方与社区来源索引</h2>
    <p class="muted small" style="margin-top:0">
      直接从 HF 兼容 API 抓取的真实结果,不是手工整理的清单。每条都带 revision、许可证与最后更新时间,
      点进详情可看到实测参数量、权重大小和上下文长度。
    </p>
    <div class="grid-3">
      <label class="field"><span>关键词</span><input type="text" id="q" placeholder="如 qwen3 / awq / gguf"></label>
      <label class="field"><span>组织</span><select id="organization"><option value="">全部</option></select></label>
      <label class="field"><span>任务类型</span><select id="task"><option value="">全部</option></select></label>
      <label class="field"><span>许可证</span><select id="license"><option value="">全部</option></select></label>
      <label class="field"><span>排序</span>
        <select id="sort">
          <option value="downloads">下载量</option>
          <option value="last_modified">最后更新</option>
          <option value="likes">点赞数</option>
          <option value="id">名称</option>
        </select>
      </label>
    </div>
    <div class="row"><button class="primary" id="search">查询</button>
      <button class="ghost" id="prev" disabled>上一页</button>
      <button class="ghost" id="next" disabled>下一页</button>
      <span class="muted small" id="hint"></span></div>
  </div>
  <div id="results"></div>`;

  const results = container.querySelector('#results');
  const summaryBox = container.querySelector('#summary');
  // 全库两万多条,没有翻页就只能永远看前 PAGE_SIZE 条,那个「显示前 N 个」提示等于骗人。
  const PAGE_SIZE = 50;
  let offset = 0;

  const load = async () => {
    const query = new URLSearchParams();
    const keyword = container.querySelector('#q').value.trim();
    if (keyword) query.set('q', keyword);
    ['organization', 'task', 'license', 'sort'].forEach((id) => {
      const value = container.querySelector('#' + id).value;
      if (value) query.set(id === 'license' ? 'license' : id, value);
    });
    query.set('limit', String(PAGE_SIZE));
    query.set('offset', String(offset));
    results.innerHTML = '<div class="card"><p class="muted">加载中…</p></div>';
    try {
      const data = await api('/api/hf-catalog?' + query.toString());
      if (!summaryBox.dataset.filled) {
        summaryBox.innerHTML = provenance(data.summary);
        summaryBox.dataset.filled = '1';
        if (data.summary.available) {
          const facets = data.page.facets;
          const fill = (id, values) => {
            const select = container.querySelector('#' + id);
            values.forEach((value) => {
              const option = document.createElement('option');
              option.value = value;
              option.textContent = value;
              select.appendChild(option);
            });
          };
          fill('organization', facets.organizations);
          fill('task', facets.tasks);
          fill('license', facets.licenses);
        }
      }
      if (!data.summary.available) {
        results.innerHTML = '';
        return;
      }
      const page = data.page;
      const from = page.total ? page.offset + 1 : 0;
      const to = page.offset + page.models.length;
      container.querySelector('#hint').textContent =
        '匹配 ' + page.total + ' 个,当前 ' + from + '-' + to + ' 条(全库 ' + page.grand_total + ')';
      const prev = container.querySelector('#prev');
      const next = container.querySelector('#next');
      prev.disabled = page.offset <= 0;
      next.disabled = to >= page.total;
      results.innerHTML = `
      <div class="card">
        <div class="table-wrap"><table>
          <thead><tr><th>仓库</th><th>组织</th><th>任务</th><th>许可证</th><th>下载</th><th>更新</th><th>revision</th></tr></thead>
          <tbody>${page.models.map(modelRow).join('') || '<tr><td colspan="7" class="muted">没有匹配项</td></tr>'}</tbody>
        </table></div>
      </div>`;
    } catch (error) {
      results.innerHTML = '<div class="card"><h2>加载失败</h2><p class="muted">' + esc(error.message) + '</p></div>';
    }
  };

  // 条件变了必须回到第一页,否则会出现「匹配 3 条却显示 51-53」这种空页。
  const reload = () => {
    offset = 0;
    return load();
  };

  container.querySelector('#search').addEventListener('click', reload);
  container.querySelector('#prev').addEventListener('click', () => {
    offset = Math.max(0, offset - PAGE_SIZE);
    load();
  });
  container.querySelector('#next').addEventListener('click', () => {
    offset += PAGE_SIZE;
    load();
  });
  let timer = null;
  container.querySelector('#q').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(reload, 300);
  });
  ['organization', 'task', 'license', 'sort'].forEach((id) => {
    container.querySelector('#' + id).addEventListener('change', reload);
  });

  await load();
}
