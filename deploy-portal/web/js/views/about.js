import { api, esc, num, computeLabel } from '../app.js';

export async function render(container) {
  const [meta, recipeData, gpuData] = await Promise.all([
    api('/api/meta'), api('/api/recipes'), api('/api/gpus')]);
  const gpus = gpuData.gpus || [];
  const gpuMeta = gpuData.meta || {};
  const ccSource = gpuMeta.cc_source || {};
  const mirrors = recipeData.mirrors || { entries: [] };
  const catalog = meta.catalog;

  container.innerHTML = `
  <div class="card">
    <h2>这套系统怎么来的</h2>
    <p>
      推荐规则只有一份实现:model-selector 的命令行工具与这个网站都调用同一个
      <code>recommend.py</code>。因此两边给出的排序、硬约束和风险提示必然一致,
      不会出现“网站说能跑、脚本说不能跑”的情况。
    </p>
    <dl class="kv">
      <dt>部署档目录</dt><dd>${esc(catalog.models_csv)}(${catalog.model_count} 条)</dd>
      <dt>家族库</dt><dd>${esc(catalog.families_csv)}(${catalog.family_count} 条)</dd>
      <dt>部署方案</dt><dd>${esc(meta.recipes_json)}(${(recipeData.count || 0)} 条已记录方案)</dd>
      <dt>环境台账</dt><dd>${esc(meta.deployments_json)}</dd>
    </dl>
  </div>

  <div class="card">
    <h2>国内镜像策略</h2>
    <p class="muted small" style="margin-top:0">${esc(mirrors.policy || '')}</p>
    <div class="table-wrap"><table>
      <thead><tr><th>用途</th><th>来源</th><th>固定版本/摘要</th><th>说明</th></tr></thead>
      <tbody>${(mirrors.entries || []).map((entry) => `
        <tr>
          <td>${esc(entry.kind)}</td>
          <td>${esc(entry.endpoint)}</td>
          <td><code class="small">${esc(entry.usage)}</code></td>
          <td class="small">${esc(entry.notes)}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>
  </div>

  <div class="card">
    <h2>字段含义</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>字段</th><th>作用</th></tr></thead>
      <tbody>
        <tr><td>单卡显存 / 总显存</td><td>决定能否加载;总显存不能只等于权重,还要留运行时与 KV Cache</td></tr>
        <tr><td>计算能力</td><td>FP8、稀疏注意力、FlashAttention 等内核只支持特定架构,显存够也可能跑不了</td></tr>
        <tr><td>TP / PP / 副本数</td><td>决定卡间通信、单请求速度、吞吐与故障域</td></tr>
        <tr><td>NVLink / PCIe / 跨机网络</td><td>大 TP 依赖高速互联;跨机 TP 不应放在普通 10GbE 上</td></tr>
        <tr><td>驱动 / 容器 CUDA / vLLM</td><td>它们是一个锁定组合;nvidia-smi 显示的 CUDA 不是宿主 Toolkit 版本</td></tr>
        <tr><td>模型 revision / 量化实现 / parser</td><td>同名模型的不同权重可能需要不同内核,工具调用与思考 parser 也会变化</td></tr>
        <tr><td>验证状态</td><td>区分已验证镜像、工作区规划与仅容量估算的候选</td></tr>
      </tbody>
    </table></div>
  </div>

  <div class="card">
    <h2>硬件从哪来:已核实的 GPU 目录</h2>
    <p>
      硬件不需要手填型号:可选的 GPU 来自核实过的目录(当前 ${gpus.length} 张卡)。
      单卡显存与算力由服务端按目录填入,推荐接口不接受调用方自带显存数值——
      否则等于让用户填数字绕过判定。
    </p>
    <dl class="kv">
      <dt>核实口径</dt><dd>显存容量/类型/互联逐字命中厂商产品页正文;NVIDIA 卡的算力另外要求命中 NVIDIA 官方 CUDA-Enabled GPUs 算力表,昇腾等非 CUDA 生态不做 sm 映射</dd>
      <dt>目录文件</dt><dd>${esc(gpuMeta.path || '')}</dd>
      <dt>算力表来源</dt><dd><a href="${esc(ccSource.url || '#')}" target="_blank" rel="noreferrer">${esc(ccSource.url || '')}</a>${ccSource.verified_at ? '(核实于 ' + esc(ccSource.verified_at.slice(0, 10)) + ')' : ''}<br><span class="muted small">该表只用于 NVIDIA 卡:昇腾没有 sm_xx,拿 NVIDIA 标度去套是伪核实。</span></dd>
      <dt>核实结果</dt><dd>${num(gpuMeta.verified_count)} / ${num(gpuMeta.gpu_count)} 张卡通过</dd>
    </dl>
    <p class="muted small">${esc(gpuMeta.source_policy || '')}</p>
    <div class="table-wrap"><table>
      <thead><tr><th>卡</th><th>厂商 / 生态</th><th>架构</th><th>单卡显存</th><th>显存类型</th><th>互联</th><th>算力</th><th>核实</th></tr></thead>
      <tbody>${gpus.map((gpu) => `
        <tr>
          <td><a href="${esc(gpu.source_url)}" target="_blank" rel="noreferrer">${esc(gpu.name)}</a></td>
          <td class="small">${esc(gpu.vendor || 'nvidia')} / <code>${esc(gpu.ecosystem || 'cuda')}</code></td>
          <td class="small">${gpu.architecture ? esc(gpu.architecture) : '<span class="muted">' + esc(gpu.architecture_basis || '厂商页未标注') + '</span>'}</td>
          <td>${num(gpu.vram_gib)} GiB</td>
          <td class="small">${esc(gpu.memory_type)}</td>
          <td class="small">${esc(gpu.interconnect)}</td>
          <td class="small">${esc(computeLabel(gpu))}${gpu.fp8_supported ? ' · FP8' : ''}</td>
          <td class="small">${gpu.verification && gpu.verification.status === 'ok' ? '<span class="badge ok">已核实</span>' : '<span class="badge bad">核实失败</span>'}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>
    <p class="muted small">
      两条都对不上就不收录:产品页已下线的旧卡(A800 / H800 / L20 / A10 / A30 / V100)不在目录内,
      工作区里真实存在的这类机器只能走台账的「现场登记(未核实)」路径,页面上会明确标出,
      绝不填记忆值。
    </p>
    <h5 class="small" style="color:var(--muted)">华为昇腾:同一套页面上,口径不同</h5>
    <ul class="steps small">
      <li>目录里的昇腾条目带 <code>vendor: huawei</code> / <code>ecosystem: cann</code>,与 CUDA 卡分开分组,不混在一个下拉里。</li>
      <li><strong>不做 sm 映射</strong>:sm_xx 是 NVIDIA 专有标度,昇腾的 <code>compute_capability</code> 留空并写明口径,不编一个等级出来。</li>
      <li><strong>FP8 看厂商页标称</strong>:不再由算力推导。Atlas 350 官方页写明支持 HiF8/mxFP8/mxFP4,按厂商页记为支持;Atlas 300I Duo 官方页未标注,记为不支持。</li>
      <li><strong>不套用 NVIDIA 的门槛</strong>:登记表里的算力下限与驱动下限只对 CUDA 栈成立,昇腾卡不参与这两项判定。</li>
      <li><strong>KV cache 只按下界核算</strong>:昇腾走 <code>--quantization ascend</code> 的专有量化,没有可核实的公开公式,因此不套 CUDA 的 2 字节口径,页面显示「KV 结构无法核实,只按权重下界核算」。</li>
      <li><strong>部署方法不跨生态关联</strong>:工作区现有的部署方案都是 CUDA 栈,昇腾卡只关联同生态方案;同名模型若存在别的生态方案,会单独说明「不能直接搬过来」。</li>
      <li>官方产品页只写卡型号、没写芯片型号的条目(如 Atlas 300I Duo),架构字段留空并注明原因,不填记忆值。</li>
      <li>Atlas 300I Duo 官方页把 96GB 与 48GB 两种出货配置写在同一行,因此<strong>两个容量各列一条</strong>,不合并成一个数。</li>
    </ul>
    <p class="muted small">
      未收录的昇腾型号:官方产品页已换代到 950 系列,<code>910B</code> / <code>310P</code> 在各官方页正文里
      逐字核不到(0 命中),工作区自述的「64 GiB/卡」不是厂商页证据,因此这次不收录——
      宁可少一张卡,也不填一个核不到的数字。
    </p>
  </div>

  <div class="card">
    <h2>显存怎么算的</h2>
    <p>
      「放得下吗」不能只看参数量。权重取 artifact 实测字节数,KV cache 按模型真实的
      attention 结构算,两者之和再乘运行时余量:
    </p>
    <pre class="small">权重 GiB = artifact 里 .safetensors 的实际字节数(实测)
KV GiB   = 元素数/token/层 × 层数 × 上下文 token × 2 字节 / 1024³
合计 GiB = (权重 + KV) × 1.10          # 运行时余量,工程预留
单卡 GiB = 合计 ÷ TP
判定     = 单卡 GiB ≤ 单卡显存 × 0.92   # 单卡可用比例
占用率   = 合计 ÷ (TP × 单卡显存)</pre>
    <p>
      其中 <code>2 字节</code> / <code>1.10</code> / <code>0.92</code> 三个系数是工程假设,
      <strong>不是实测值</strong>,推荐结果里逐条标注为「工程预留,非实测」。
    </p>
    <h5 class="small" style="color:var(--muted)">KV cache 的三种口径(不能用一个公式套所有模型)</h5>
    <div class="table-wrap"><table>
      <thead><tr><th>口径</th><th>元素数/token/层</th><th>适用</th></tr></thead>
      <tbody>
        <tr><td><code>mla</code></td><td class="small">kv_lora_rank + qk_rope_head_dim,各头共享<strong>不乘 2</strong></td><td class="small">DeepSeek 系、GLM-5.2、Kimi-K2.6</td></tr>
        <tr><td><code>hybrid-linear</code></td><td class="small">只算 full_attention 的层,2 × kv_heads × head_dim</td><td class="small">Qwen3.5 系</td></tr>
        <tr><td><code>gqa</code></td><td class="small">2 × kv_heads × head_dim × 层数</td><td class="small">其余(含 MiniMax-M2.7、Qwen3 系)</td></tr>
      </tbody>
    </table></div>
    <p class="muted small">
      把混合线性注意力按全层算会把 Qwen3.5 的 KV 高估约 4 倍;把 MLA 当 GQA(乘 2)会把
      DeepSeek 系高估一倍。两者都会直接改变「这些卡放得下吗」的结论。
      结构拿不到的档(如官方仓库 gated)会留空并注明「只按权重下界核算」,不套公式顶数。
    </p>
    <h5 class="small" style="color:var(--muted)">排序不再偏袒工作区试过的方案</h5>
    <p class="muted small">
      早期版本会给「本机验证过」的档加分,于是 kty5l / xt / zc5s 用过的方案天然排在前面,
      等于把「我们试过」当成「更适合你的硬件」。现在 <code>validation_status</code> 完全不参与排序,
      唯一保留的是「有没有可执行部署方法」(+3),并且新增显存利用率项:
      占用低于 45% 扣分(该换更大的档,或把卡拿去跑更多副本),高于 90% 扣分(没给长上下文和并发留余量)。
    </p>
  </div>

  <div class="card">
    <h2>维护规则与边界</h2>
    <ul class="steps">
      <li>新增部署档前,先在联网机核实国内镜像确实含目标 revision/artifact,失败才回退海外源并告知用户。</li>
      <li>把模型 revision、量化仓库、镜像 tag+digest、驱动下限与启动参数视为一个锁定单元一起记录。</li>
      <li>实机验收通过后,把状态从 candidate/provisional-local 提升为 verified-local,并回填实测值。</li>
      <li>容量估算不是承诺:家族库里的估算项不会覆盖精确部署档,也不会被标成生产可用。</li>
      <li>工具调用类部署,验收必须发送带 tools 与 tool_choice=auto 的真实请求;纯文本生成不算通过。</li>
    </ul>
    <p class="muted small">
      本页所有结论都是部署预筛选,不替代实机验收。许可证最终仍应由法务按具体模型 revision 复核。
      当前工作区:${esc(meta.workspace)}
    </p>
  </div>`;
}
