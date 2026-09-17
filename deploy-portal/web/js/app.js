import { render as recommend } from './views/recommend.js';
import { render as catalog } from './views/catalog.js';
import { render as models } from './views/models.js';
import { render as recipes } from './views/recipes.js';
import { render as ledger } from './views/ledger.js';
import { render as about } from './views/about.js';

const routes = { recommend, catalog, models, recipes, ledger, about };

export const state = { meta: null, gpus: null, gpuMeta: null };

export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch (error) {
    throw new Error('返回内容不是 JSON: ' + text.slice(0, 200));
  }
  if (!response.ok) {
    throw new Error((payload && payload.error) || ('请求失败 ' + response.status));
  }
  return payload;
}

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function esc(value) {
  return String(value === undefined || value === null ? '' : value)
    .replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

export function num(value, digits = 0) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return esc(value);
  return parsed.toFixed(digits).replace(/\.0+$/, '');
}

const STATUS_STYLE = {
  'verified-local': ['ok', '本地已验证'],
  'validated-user-workspace': ['ok', '用户态已验证'],
  'provisional-local': ['warn', '规划/临时'],
  'candidate': ['info', '候选'],
};

export function statusBadge(status) {
  const [kind, label] = STATUS_STYLE[status] || ['info', status || '未知'];
  return '<span class="badge ' + kind + '">' + esc(label) + '</span>';
}

export function yesNo(value) {
  return String(value).toLowerCase() === 'true' ? '是' : '否';
}

/**
 * 计算能力数值 -> sm 标签,如 8 -> sm_80、8.6 -> sm_86、9 -> sm_90。
 *
 * 非 CUDA 生态(华为昇腾等)没有 sm 等级,目录里该字段为 null。这种情况必须
 * 显示占位符:早先直接拼字符串会渲染出 sm_null,看着像一张算力叫 null 的卡。
 */
export function smLabel(value) {
  if (value === null || value === undefined || value === '') return '—';
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 'sm_' + esc(value);
  return 'sm_' + parsed.toFixed(1).replace('.', '');
}

/**
 * 这张卡是不是 CUDA 生态。目录里 NVIDIA 卡是 ecosystem=cuda;没有该字段时按 cuda
 * 处理,这样台账里现场登记的 NVIDIA 机器继续按原来的逻辑显示。
 */
export function isCudaGpu(gpu) {
  return !gpu || (gpu.ecosystem || 'cuda') === 'cuda';
}

/**
 * 算力标签。非 CUDA 生态(华为昇腾等)没有 sm_xx,显示生态名而不是编一个 sm 号。
 * 三个视图共用这一个函数,否则同一张卡在不同页面会显示成不同说法。
 */
export function computeLabel(gpu) {
  if (!gpu) return '—';
  if (!isCudaGpu(gpu)) return String(gpu.ecosystem || '').toUpperCase() + ' 生态';
  return smLabel(gpu.compute_capability);
}

/**
 * 驱动/栈这一行。昇腾没有 NVIDIA 驱动下限这回事,写「驱动 未填」会让人以为
 * 缺了个必填项。HTML 页面与 Markdown 报告共用,避免两处说法不一致。
 */
export function stackLabel(gpu, hardware) {
  // 不要在句子里重复「CANN 生态」:调用方通常紧挨着 computeLabel 显示生态名,
  // 两处都说一遍会读成「CANN 生态,CANN 生态,不适用 NVIDIA 驱动下限」。
  if (!isCudaGpu(gpu)) return '驱动下限不适用(NVIDIA 驱动下限与昇腾无关)';
  return '驱动 ' + ((hardware && hardware.driver_version) || '未填');
}

const CHECK_LEVELS = {
  match: ['ok', '一致'],
  close: ['warn', '接近'],
  differ: ['bad', '有差异'],
};

/** 把「登记值 vs 上游当前值」的漂移检查渲染成表格。 */
export function verificationBlock(verification, options = {}) {
  if (!verification || !verification.repos || !verification.repos.length) {
    return '';
  }
  const repos = verification.repos;
  const reference = repos.filter((repo) => repo.is_reference);
  const others = repos.filter((repo) => !repo.is_reference);
  const checkRows = reference.flatMap((repo) => (repo.checks || []).map((check) => {
    const [kind, label] = CHECK_LEVELS[check.level] || ['info', check.level];
    return `
    <tr>
      <td>${esc(check.field)}</td>
      <td>${esc(check.declared)}</td>
      <td>${esc(check.real)}</td>
      <td><span class="badge ${kind}">${esc(label)}</span> ${check.delta_pct > 0 ? '+' : ''}${esc(num(check.delta_pct, 1))}%</td>
    </tr>`;
  })).join('');
  const repoRows = repos.map((repo) => `
    <tr>
      <td>${repo.is_reference ? '<span class="badge ok">对照档</span> ' : ''}
        ${repo.source_url ? '<a href="' + esc(repo.source_url) + '" target="_blank" rel="noreferrer">' + esc(repo.repo) + '</a>' : esc(repo.repo)}
        <br><span class="muted small">${esc(repo.role || '')}</span></td>
      <td><code class="small">${esc((repo.revision || '').slice(0, 12))}</code></td>
      <td class="small">${esc(repo.license || '未声明')}</td>
      <td class="small">${repo.weight_gib ? esc(repo.weight_gib) + ' GiB' : (repo.gguf_gib ? 'GGUF ' + esc(repo.gguf_gib) + ' GiB' : '—')}</td>
      <td class="small">${repo.total_params_b ? esc(repo.total_params_b) + ' B' : '—'}</td>
    </tr>`).join('');
  const noReference = !reference.length
    ? '<p class="warn-list" style="padding-left:18px">没有与声明量化档位一致的官方仓库,因此不做权重对比。这可能意味着该部署档所用权重来自本轮未追踪的仓库。</p>'
    : '';
  // 官方配方 = 经过社区验证的部署方法,单独提到最上面,不和文档清单混在一起。
  const officialRecipes = (verification.docs || []).filter((doc) => (doc.kind || '').indexOf('official-recipe') === 0);
  const recipeLine = officialRecipes.length
    ? '<p class="small" style="margin:10px 0 0">官方部署配方:' +
      officialRecipes.map((doc) => '<a href="' + esc(doc.url) + '" target="_blank" rel="noreferrer">' + esc(doc.title || doc.id) + '</a>').join(' · ') +
      '</p>'
    : '<p class="muted small" style="margin:10px 0 0">vLLM 官方 recipes 仓库截至本次同步未收录该模型的专用配方(目录列表已逐个核对)。</p>';

  // 登记值是从哪个仓库的哪个 revision 来的,必须能看到,否则「实测」二字无从查证。
  const origin = verification.provenance || {};
  const originLine = origin.repo
    ? '<p class="small" style="margin:10px 0 0">本档登记值的来源:' +
      (origin.repo ? '<code>' + esc(origin.repo) + '</code> ' : '') +
      (origin.revision ? '@ <code>' + esc(origin.revision.slice(0, 12)) + '</code> ' : '') +
      (origin.endpoint ? '(' + esc(origin.endpoint) + ')' : '') +
      (origin.verified_at ? ',核实于 ' + esc(origin.verified_at) : '') + '</p>'
    : '';

  return `
  <div class="card">
    <h2>与官方仓库的核对</h2>
    <p class="muted small" style="margin-top:0">
      目录里的权重与上下文已按实测订正,所以下表是<b>漂移检查</b>:拿当初核实的值去比上游当前值,
      上游改了权重或 config 会在这里露出来。目标量化档位:${esc(verification.target_quant || '未识别')};
      只有档位一致的仓库才用于权重对比,否则 BF16 基座和 INT4 量化档比较会得出无意义的偏差。
    </p>
    ${originLine}
    ${recipeLine}
    <div class="table-wrap"><table>
      <thead><tr><th>仓库</th><th>revision</th><th>许可证</th><th>实测权重</th><th>实测参数</th></tr></thead>
      <tbody>${repoRows}</tbody>
    </table></div>
    ${checkRows ? '<h5 class="small" style="color:var(--muted)">登记值 vs 上游当前值</h5><div class="table-wrap"><table><thead><tr><th>字段</th><th>目录登记</th><th>上游当前</th><th>结论</th></tr></thead><tbody>' + checkRows + '</tbody></table></div>' : ''}
    ${noReference}
    ${others.length && reference.length ? '<p class="muted small">另有 ' + others.length + ' 个同模型的其它档位仓库(如原始精度基座),它们的权重不代表本部署档。</p>' : ''}
  </div>`;
}

/** 权威文档来源列表。 */
export function docSourceBlock(sources, title = '权威来源') {
  if (!sources || !sources.length) {
    return '';
  }
  const rows = sources.map((item) => `
    <tr>
      <td><a href="${esc(item.url)}" target="_blank" rel="noreferrer">${esc(item.title || item.id)}</a>
        <br><span class="muted small">${esc(item.url)}</span></td>
      <td class="small">${esc(item.kind)}</td>
      <td class="small">${item.status === 200 ? '<span class="badge ok">已验证可达</span>' : '<span class="badge bad">' + esc(item.status || item.error) + '</span>'}</td>
      <td class="small">${esc((item.checked_at || '').replace('T', ' ').replace('Z', ''))}</td>
    </tr>`).join('');
  return `
  <div class="card">
    <h2>${esc(title)}</h2>
    <p class="muted small" style="margin-top:0">
      这些链接由 <code>tools/sync_docs.py</code> 实际请求验证过,记录当时的 HTTP 状态与内容指纹,不是凭记忆写的地址。
    </p>
    <div class="table-wrap"><table>
      <thead><tr><th>来源</th><th>类型</th><th>状态</th><th>验证时间</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

let toastTimer = null;
export function toast(message) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 2200);
}

export async function copyText(text, label = '已复制') {
  try {
    await navigator.clipboard.writeText(text);
    toast(label);
  } catch (error) {
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
    toast(label);
  }
}

export function download(filename, text) {
  const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function bindCopyButtons(root) {
  root.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', () => copyText(button.dataset.copy, '已复制到剪贴板'));
  });
}

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const parts = raw.split('/').filter(Boolean);
  return { name: parts[0] || 'recommend', params: parts.slice(1) };
}

function setActiveNav(name) {
  document.querySelectorAll('#nav a').forEach((link) => {
    link.classList.toggle('active', link.dataset.view === name);
  });
}

async function route() {
  const { name, params } = parseHash();
  const view = routes[name] || routes.recommend;
  const container = document.getElementById('view');
  setActiveNav(routes[name] ? name : 'recommend');
  container.innerHTML = '<p class="muted">加载中…</p>';
  if (location.hash !== '#/' + name && name === 'recommend') {
    history.replaceState(null, '', '#/recommend');
  }
  try {
    await view(container, params);
  } catch (error) {
    container.innerHTML =
      '<div class="card"><h2>加载失败</h2><p class="muted">' + esc(error.message) + '</p></div>';
  }
}

async function boot() {
  try {
    state.meta = await api('/api/meta');
    const gpus = await api('/api/gpus');
    state.gpus = gpus.gpus || [];
    state.gpuMeta = gpus.meta || null;
    const catalog = state.meta.catalog;
    document.getElementById('brand-sub').textContent =
      '按硬件资源推荐可部署模型,并给出已验证的部署方法';
    document.getElementById('meta-line').textContent =
      '目录:' + catalog.models_csv + ' · 部署档 ' + catalog.model_count + ' 条 · 模型家族 ' +
      catalog.family_count + ' 条';
  } catch (error) {
    document.getElementById('meta-line').textContent = '无法读取元数据:' + error.message;
  }
  window.addEventListener('hashchange', route);
  route();
}

boot();
