import { api, esc, statusBadge } from '../app.js';

function row(profile) {
  return `
  <tr>
    <td>${esc(profile.model_name)}<br><span class="muted small">${esc(profile.profile)}</span></td>
    <td>${esc(profile.quantization)}</td>
    <td>${esc(profile.recommended_layout)}</td>
    <td>${esc(profile.min_gpu_count)} × ${esc(profile.min_vram_per_gpu_gib)} GiB<br>
        <span class="muted small">实测权重 ${esc(profile.weight_gib)} GiB${contextMark(profile)}</span></td>
    <td>${esc(profile.vllm_image)}<br><span class="muted small">CUDA ${esc(profile.cuda_runtime)} / 驱动 ${esc(profile.min_driver)}</span></td>
    <td>${statusBadge(profile.validation_status)}</td>
    <td>${esc(profile.license)}${profile.license_id ? '<br><span class="muted small"><code>' + esc(profile.license_id) + '</code></span>' : ''}</td>
    <td>${originCell(profile)}</td>
  </tr>`;
}

/** 上下文右上角的星号:该值是官方模型卡标称(需打开 YaRN),不是 config 默认值。 */
function contextMark(row) {
  if (row.context_source !== 'card') {
    return ' / 上下文 ' + esc(row.context_k) + 'K';
  }
  return ' / 上下文 ' + esc(row.context_k) + 'K<sup title="官方模型卡标称值,需在 config.json 打开 YaRN 等扩展;仓库默认值更低">*</sup>';
}

/** 登记值是从哪个仓库的哪个 revision 核实来的。 */
function originCell(row) {
  if (!row.verified_repo) {
    return '<span class="muted small">未登记核实来源</span>';
  }
  return `<span class="small">${esc(row.verified_repo)}</span><br>
    <span class="muted small"><code>${esc((row.verified_revision || '').slice(0, 12))}</code> @ ${esc(row.verified_endpoint || '')}<br>核实于 ${esc(row.verified_at || '')}</span>`;
}

function familyRow(family) {
  return `
  <tr>
    <td>${esc(family.model_name)}</td>
    <td>${esc(family.organization)}</td>
    <td>${esc(family.total_params_b)}${family.active_params_b ? ' / ' + esc(family.active_params_b) + ' 激活' : ''}</td>
    <td>${esc(family.context_k)}K${family.context_source === 'card' ? '<sup title="官方模型卡标称值,需打开 YaRN 等扩展">*</sup>' : ''}</td>
    <td>${esc(family.modalities)}</td>
    <td>${esc(family.workloads)}</td>
    <td>${esc(family.license)}<br><span class="muted small">${esc(family.openness)}${family.license_id ? ' · ' + esc(family.license_id) : ''}</span></td>
    <td>${esc(family.vllm_status)}</td>
  </tr>`;
}

export async function render(container) {
  container.innerHTML = `
  <div class="card">
    <h2>模型目录</h2>
    <p class="muted small" style="margin-top:0">
      上层是可落地的部署档(带量化、显存门槛与锁定栈),下层是广覆盖的模型家族库。
      家族库只记录许可证、开放性与 vLLM 支持状态,未经验证的版本不会被写成可部署。
    </p>
    <div class="grid-3">
      <label class="field"><span>关键词</span><input type="text" id="q" placeholder="如 qwen / awq / 397B"></label>
      <label class="field"><span>组织(家族库)</span><select id="organization"><option value="">全部</option></select></label>
      <div class="field"><span>过滤</span>
        <div class="row small">
          <label><input type="checkbox" id="vllm_only"> 仅 vLLM 已支持</label>
          <label><input type="checkbox" id="multimodal"> 仅多模态</label>
          <label><input type="checkbox" id="permissive"> 仅宽松许可</label>
        </div>
      </div>
    </div>
  </div>
  <div id="tables"></div>`;

  const tables = container.querySelector('#tables');
  const organizationSelect = container.querySelector('#organization');

  const load = async () => {
    const params = new URLSearchParams();
    const keyword = container.querySelector('#q').value.trim();
    if (keyword) params.set('q', keyword);
    if (organizationSelect.value) params.set('organization', organizationSelect.value);
    if (container.querySelector('#vllm_only').checked) params.set('vllm_only', 'true');
    if (container.querySelector('#multimodal').checked) params.set('multimodal', 'true');
    if (container.querySelector('#permissive').checked) params.set('permissive', 'true');

    tables.innerHTML = '<div class="card"><p class="muted">加载中…</p></div>';
    try {
      const data = await api('/api/catalog?' + params.toString());
      if (organizationSelect.options.length <= 1) {
        data.organizations.forEach((name) => {
          const option = document.createElement('option');
          option.value = name;
          option.textContent = name;
          organizationSelect.appendChild(option);
        });
      }
      tables.innerHTML = `
      <div class="card">
        <h2>可部署档 ${data.model_count} / ${data.total_models}</h2>
        <div class="table-wrap"><table>
          <thead><tr><th>模型 / 部署档</th><th>量化</th><th>布局</th><th>最低硬件</th><th>部署栈</th><th>状态</th><th>许可证</th><th>登记值来源(实测)</th></tr></thead>
          <tbody>${data.models.map(row).join('') || '<tr><td colspan="8" class="muted">没有匹配项</td></tr>'}</tbody>
        </table></div>
        <p class="muted small">带 <sup>*</sup> 的上下文是官方模型卡标称的扩展上限(需在 config.json 打开 YaRN 等),
          其余上下文取自仓库 config.json。「登记值来源」是该行数值当初核实用的仓库与 revision,
          可点开仓库对照;实时漂移检查见每个部署档的详情。</p>
      </div>
      <div class="card">
        <h2>模型家族 ${data.family_count} / ${data.total_families}</h2>
        <div class="table-wrap"><table>
          <thead><tr><th>模型</th><th>组织</th><th>参数量(B)</th><th>上下文</th><th>模态</th><th>用途</th><th>许可/开放性</th><th>vLLM</th></tr></thead>
          <tbody>${data.families.map(familyRow).join('') || '<tr><td colspan="8" class="muted">没有匹配项</td></tr>'}</tbody>
        </table></div>
      </div>`;
    } catch (error) {
      tables.innerHTML = '<div class="card"><h2>加载失败</h2><p class="muted">' + esc(error.message) + '</p></div>';
    }
  };

  let timer = null;
  container.querySelector('#q').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(load, 220);
  });
  ['#organization', '#vllm_only', '#multimodal', '#permissive'].forEach((selector) => {
    container.querySelector(selector).addEventListener('change', load);
  });

  await load();
}
