import { api, esc, statusBadge, bindCopyButtons, verificationBlock, docSourceBlock } from '../app.js';

function launchBlock(lines) {
  const code = (lines || []).join('\n');
  return `
  <div class="row between">
    <h5 style="margin:0">启动命令</h5>
    <button class="tiny" data-copy="${esc(code)}">复制</button>
  </div>
  <pre class="code">${esc(code)}</pre>`;
}

/** 可公开核实的通用依据。一条都挂不上时如实降级,不拿别的引擎的文档凑数。 */
function publicBasisBlock(recipe) {
  const docs = recipe.authoritative_docs || [];
  if (!docs.length) {
    return `
  <div class="card">
    <h2>公开依据:暂无</h2>
    <p class="muted small" style="margin-top:0">
      来源台账 <code>deploy-portal/data/sources.json</code> 里还没有条目显式挂到这条方案上,
      所以它目前只有现场记录,没有可公开核实的通用依据。宁可留空,也不拿别的引擎的官方文档来凑数。
    </p>
  </div>`;
  }
  return docSourceBlock(docs, '可公开核实的通用依据',
    '这些就是「你凭什么这么说」的答案:引擎官方文档 / 官方配方 / 官方模型卡,任何人都能自己打开。');
}

function recipeCard(recipe) {
  const stack = recipe.stack || {};
  const docs = recipe.authoritative_docs || [];
  return `
  <div class="recipe-item">
    <header>
      <div>
        <h4>${esc(recipe.title)}</h4>
        <div class="row small" style="margin-top:6px">
          <span class="badge">${esc(recipe.environment)}</span>
          ${statusBadge(recipe.status)}
          <span class="badge">${esc(recipe.model)}</span>
        </div>
      </div>
      <a class="badge info" href="#/recipes/${esc(recipe.id)}">详情</a>
    </header>
    <dl class="kv">
      <dt>量化</dt><dd>${esc(recipe.quantization)}</dd>
      <dt>硬件</dt><dd>${esc((recipe.hardware || {}).summary)}</dd>
      <dt>布局</dt><dd>${esc((recipe.layout || {}).strategy)}:TP=${esc((recipe.layout || {}).tp)} · PP=${esc((recipe.layout || {}).pp)} · 副本 ${esc((recipe.layout || {}).replicas)}</dd>
      <dt>镜像</dt><dd>${esc(stack.image)}</dd>
      <dt>公开依据</dt><dd>${docs.length ? esc(docs.length) + ' 条(引擎官方文档 / 官方配方 / 官方模型卡)' : '暂无,只有现场记录'}</dd>
      <dt>验证情况</dt><dd>${esc(recipe.verified_on)}</dd>
    </dl>
  </div>`;
}

function recipeDetail(recipe) {
  const hardware = recipe.hardware || {};
  const stack = recipe.stack || {};
  const layout = recipe.layout || {};
  const sources = (recipe.sources || [])
    .map((path) => '<li><code class="small">' + esc(path) + '</code></li>')
    .join('');
  const steps = (recipe.steps || [])
    .map((step) => '<li><strong>' + esc(step.title) + '</strong>:' + esc(step.detail) + '</li>')
    .join('');
  // 验收清单是 recipes.json 里的 acceptance 数组;verification 是服务端算出的
  // 官方仓库核对对象,两者含义不同,不能共用一个键名(曾经因此整页报错)。
  const acceptance = (recipe.acceptance || [])
    .map((item) => '<li>' + esc(item) + '</li>')
    .join('');
  const pitfalls = (recipe.pitfalls || [])
    .map((item) => '<tr><td>' + esc(item.symptom) + '</td><td>' + esc(item.action) + '</td></tr>')
    .join('');

  return `
  <div class="card">
    <div class="row between">
      <div>
        <h2 style="margin:0">${esc(recipe.title)}</h2>
        <div class="row small" style="margin-top:8px">
          <span class="badge">${esc(recipe.environment)}</span>
          ${statusBadge(recipe.status)}
          <span class="badge">${esc(recipe.model)}</span>
          <span class="badge">${esc(recipe.quantization)}</span>
        </div>
      </div>
      <a class="badge" href="#/recipes">← 返回方案列表</a>
    </div>
    <p class="muted small" style="margin-bottom:0">验证情况:${esc(recipe.verified_on)}</p>
  </div>

  <div class="card">
    <h2>硬件与并行</h2>
    <dl class="kv">
      <dt>硬件</dt><dd>${esc(hardware.summary)}</dd>
      <dt>卡数 / 显存</dt><dd>${esc(hardware.gpu_count)} × ${esc(hardware.vram_per_gpu_gib)} GiB · ${esc(hardware.nodes)} 节点</dd>
      <dt>互联</dt><dd>${esc(hardware.interconnect)}</dd>
      <dt>驱动下限</dt><dd>${esc(hardware.min_driver)}</dd>
      <dt>主存 / 磁盘</dt><dd>≥ ${esc(hardware.min_host_ram_gib)} GiB / ≥ ${esc(hardware.min_disk_gib)} GiB</dd>
      <dt>并行布局</dt><dd>${esc(layout.strategy)}(TP=${esc(layout.tp)}, PP=${esc(layout.pp)}, 副本 ${esc(layout.replicas)})</dd>
      <dt>负载均衡</dt><dd>${esc(layout.lb)}</dd>
      <dt>要点</dt><dd>${esc(layout.notes)}</dd>
    </dl>
  </div>

  <div class="card">
    <h2>锁定栈</h2>
    <dl class="kv">
      <dt>镜像</dt><dd><code>${esc(stack.image)}</code></dd>
      <dt>镜像来源</dt><dd>${esc(stack.image_source)}</dd>
      <dt>vLLM</dt><dd>${esc(stack.vllm)}</dd>
      <dt>CUDA</dt><dd>${esc(stack.torch_cuda)}</dd>
      <dt>Ray</dt><dd>${esc(stack.ray)}</dd>
    </dl>
    ${launchBlock(recipe.launch)}
  </div>

  <div class="card">
    <h2>执行步骤</h2>
    <ol class="steps">${steps}</ol>
  </div>

  <div class="card">
    <h2>验收清单</h2>
    <ul class="steps">${acceptance}</ul>
  </div>

  <div class="card">
    <h2>常见问题</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>现象</th><th>处理</th></tr></thead>
      <tbody>${pitfalls}</tbody>
    </table></div>
  </div>

  ${verificationBlock(recipe.verification)}
  ${publicBasisBlock(recipe)}
  <div class="card">
    <h2>本工作区的现场记录(第三方打不开)</h2>
    <p class="muted small" style="margin-top:0">
      以下路径是这条方案在具体机器上落地时的记录(哪台机器、什么参数、踩过什么坑),只有本工作区能打开。
      它们是证据,但<b>不是通用依据</b>;只有「可公开核实的通用依据」那一栏才是不依赖本机的东西。
    </p>
    <ul class="steps">${sources}</ul>
  </div>`;
}

export async function render(container, params) {
  if (params && params.length) {
    const data = await api('/api/recipes');
    const recipe = data.recipes.find((item) => item.id === params[0]);
    if (!recipe) {
      container.innerHTML = '<div class="card"><h2>找不到方案</h2><p class="muted">' + esc(params[0]) + '</p></div>';
      return;
    }
    container.innerHTML = recipeDetail(recipe);
    bindCopyButtons(container);
    return;
  }

  const data = await api('/api/recipes');
  const byEnv = new Map();
  data.recipes.forEach((recipe) => {
    const key = recipe.environment || '未分组';
    if (!byEnv.has(key)) byEnv.set(key, []);
    byEnv.get(key).push(recipe);
  });

  container.innerHTML = `
  <div class="card">
    <h2>已验证部署方案</h2>
    <p class="muted small" style="margin-top:0">
      每条方案都分开给两类来源:可公开核实的通用依据(引擎官方文档 / 官方配方 / 官方模型卡,
      任何人都能打开)和本工作区的现场记录(具体机器上的落地文档与脚本,第三方打不开)。
      另外还包含锁定的镜像、启动参数、验收清单和已知坑;状态沿用模型目录的词汇,
      未验收的组合不会被标成已验证。${data.updated ? '更新时间:' + esc(data.updated) : ''}
    </p>
  </div>
  ${Array.from(byEnv.entries()).map(([environment, recipes]) => `
    <div class="card">
      <h2>${esc(environment)} · ${recipes.length} 条</h2>
      ${recipes.map(recipeCard).join('')}
    </div>`).join('')}`;
}
