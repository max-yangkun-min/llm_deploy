import { api, esc, num, statusBadge, toast, computeLabel, stackLabel } from '../app.js';

function checkTable(rows) {
  const unverified = rows.filter((row) => row.hardware_verified === false);
  const caveat = unverified.length
    ? '<p class="muted small" style="margin:0 0 8px">该环境用的是现场登记规格(' +
      esc(unverified[0].hardware_gpu_name || '') +
      '),厂商产品页没有这个型号,单卡显存/算力未经官方页核实。</p>'
    : '';
  // 「通过」不能吞掉核算口径的差别:KV 没核实到的档只算了权重下界,
  // 直接写「通过」会把一个下界结论读成完整判定。
  const verdict = (row) => {
    if (!row.pass) return '<span class="badge bad">不满足</span>';
    const lowerBound = row.memory && row.memory.kv_verified === false;
    return lowerBound
      ? '<span class="badge warn">下界通过</span><br><span class="muted small">KV 未计入</span>'
      : '<span class="badge ok">通过</span>';
  };
  return `
  ${caveat}
  <div class="table-wrap"><table>
    <thead><tr><th>部署档</th><th>结果</th><th>缺口 / 风险</th></tr></thead>
    <tbody>${rows.map((row) => `
      <tr>
        <td>${esc(row.profile.model_name)}<br><span class="muted small">${esc(row.profile.profile)}</span></td>
        <td>${verdict(row)}</td>
        <td>
          ${row.failures.length ? '<ul class="fail-list">' + row.failures.map((text) => '<li>' + esc(text) + '</li>').join('') + '</ul>' : ''}
          ${row.warnings.length ? '<ul class="warn-list">' + row.warnings.map((text) => '<li>' + esc(text) + '</li>').join('') + '</ul>' : ''}
          ${!row.failures.length && !row.warnings.length ? '<span class="muted small">硬约束全部满足</span>' : ''}
        </td>
      </tr>`).join('')}
    </tbody>
  </table></div>`;
}

function envCard(environment) {
  const hardware = environment.hardware || {};
  const recipeLinks = (environment.recipes || [])
    .map((id) => '<a class="badge info" href="#/recipes/' + esc(id) + '">' + esc(id) + '</a>')
    .join(' ');
  const docs = (environment.docs || [])
    .map((path) => '<li><code class="small">' + esc(path) + '</code></li>')
    .join('');
  const constraints = (environment.constraints || [])
    .map((item) => '<li>' + esc(item) + '</li>')
    .join('');
  return `
  <div class="card" data-env="${esc(environment.id)}">
    <div class="row between">
      <div>
        <h2 style="margin:0">${esc(environment.name)}</h2>
        <p class="muted small" style="margin:4px 0 0">${esc(environment.headline)}</p>
      </div>
      ${statusBadge(environment.status)}
    </div>
    <dl class="kv">
      <dt>GPU</dt><dd>${esc(hardware.gpu_count)} × ${esc(hardware.gpu_name)}(${esc(hardware.vram_per_gpu_gib)} GiB/卡 · 合计 ${num(Number(hardware.gpu_count) * Number(hardware.vram_per_gpu_gib))} GiB)</dd>
      ${hardware.gpu_id ? '<dt>GPU 目录</dt><dd><code>' + esc(hardware.gpu_id) + '</code> <span class="badge ok">显存/算力已对厂商页核实</span></dd>' : ''}
      ${hardware.verification_note ? '<dt>规格来源</dt><dd><span class="badge warn">未经厂商页核实</span> ' + esc(hardware.verification_note) + '</dd>' : ''}
      <dt>计算能力</dt><dd>${esc(computeLabel(hardware))} · ${esc(stackLabel(hardware, hardware))}</dd>
      <dt>拓扑</dt><dd>${esc(hardware.nodes)} 节点 · ${esc(hardware.interconnect)}</dd>
      <dt>主存 / 磁盘</dt><dd>${esc(hardware.host_ram_gib)} GiB / ${esc(hardware.disk_free_gib)} GiB 可用</dd>
      <dt>选定档</dt><dd><code>${esc(environment.selected_profile)}</code></dd>
      <dt>离线包</dt><dd><code>${esc(environment.offline_package)}</code></dd>
      <dt>状态说明</dt><dd>${esc(environment.status_note)}</dd>
    </dl>
    <h5 class="small" style="color:var(--muted)">相关方案</h5>
    <div class="row small">${recipeLinks}</div>
    <h5 class="small" style="color:var(--muted)">硬件红线</h5>
    <ul class="steps small">${constraints}</ul>
    <h5 class="small" style="color:var(--muted)">文档</h5>
    <ul class="steps small">${docs}</ul>
    <div class="row" style="margin-top:10px">
      <button class="tiny" data-check="${esc(environment.id)}">按本机硬件做达标检查</button>
    </div>
    <div data-result="${esc(environment.id)}"></div>
  </div>`;
}

export async function render(container) {
  const [data, recipeData] = await Promise.all([api('/api/deployments'), api('/api/recipes')]);
  container.innerHTML = `
  <div class="card">
    <h2>部署台账</h2>
    <p class="muted small" style="margin-top:0">
      每个环境一条记录:硬件、选定部署档、离线包路径、硬件红线与当前验证状态。
      达标检查会用该环境自己的硬件参数调用同一个推荐引擎,列出每个方案的缺口。
      ${data.updated ? '更新时间:' + esc(data.updated) : ''}
    </p>
  </div>
  ${data.environments.map(envCard).join('')}`;

  container.querySelectorAll('[data-check]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = button.dataset.check;
      const environment = data.environments.find((item) => item.id === id);
      const target = container.querySelector('[data-result="' + id + '"]');
      const profileIds = Array.from(new Set(
        (environment.recipes || [])
          .map((recipeId) => {
            const recipe = recipeData.recipes.find((item) => item.id === recipeId);
            return recipe && recipe.profile_id ? recipe.profile_id : null;
          })
          .filter(Boolean)
          .concat(environment.selected_profile ? [environment.selected_profile] : [])
      ));
      target.innerHTML = '<p class="muted small">检查中…</p>';
      try {
        const rows = await Promise.all(profileIds.map((profileId) => api('/api/check', {
          method: 'POST',
          body: JSON.stringify({ hardware: environment.hardware, profile_id: profileId }),
        })));
        target.innerHTML = '<h5 class="small" style="color:var(--muted)">达标检查结果</h5>' + checkTable(rows);
      } catch (error) {
        target.innerHTML = '<p class="muted small">检查失败:' + esc(error.message) + '</p>';
      }
    });
  });
  toast('已加载 ' + data.environments.length + ' 个环境');
}
