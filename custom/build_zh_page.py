# -*- coding: utf-8 -*-
"""
Token Meter 页面深度中文化生成器
读取官方原版 page.html，输出防冲突、防覆盖的独立 page_zh.html
"""

import os
import re

SOURCE_HTML = os.path.join(os.path.dirname(__file__), "..", "page.html")
TARGET_HTML = os.path.join(os.path.dirname(__file__), "..", "page_zh.html")

# 静态替换映射表（只匹配完整的标签内文本和特定属性）
STATIC_REPLACEMENTS = [
    # 语言和标题
    (r'<html\s+lang=en>', '<html lang="zh-CN">'),
    (r'<title>Token Meter</title>', '<title>Token Meter · AI Token 与开销监控看板</title>'),

    # 导航栏选项
    (r'<span class=tabLabel>Sessions</span>', '<span class=tabLabel>运行会话</span>'),
    (r'<span class=tabLabel>Spend</span>', '<span class=tabLabel>消费统计</span>'),
    (r'<span class=tabLabel>Models</span>', '<span class=tabLabel>模型分析</span>'),
    (r'<span class=tabLabel>Efficiency</span>', '<span class=tabLabel>效率洞察</span>'),
    (r'<span class=tabLabel>Git</span>', '<span class=tabLabel>Git 交付</span>'),
    (r'<span class=tabLabel>Performance</span>', '<span class=tabLabel>性能报告</span>'),
    (r'<span class=tabLabel>Read</span>', '<span class=tabLabel>阅读文档</span>'),
    (r'<span class=tabLabel>Learn</span>', '<span class=tabLabel>快速上手</span>'),
    (r'<span class=tabLabel>Tools</span>', '<span class=tabLabel>工具能力</span>'),
    (r'<span class=tabLabel>Settings</span>', '<span class=tabLabel>系统设置</span>'),

    # 导航属性
    (r'data-label=Sessions', 'data-label="运行会话"'),
    (r'aria-label=Sessions', 'aria-label="运行会话"'),
    (r'title=Sessions', 'title="运行会话"'),
    (r'data-label=Spend', 'data-label="消费统计"'),
    (r'aria-label=Spend', 'aria-label="消费统计"'),
    (r'title=Spend', 'title="消费统计"'),
    (r'data-label=Models', 'data-label="模型分析"'),
    (r'aria-label=Models', 'aria-label="模型分析"'),
    (r'title=Models', 'title="模型分析"'),
    (r'data-label=Efficiency', 'data-label="效率洞察"'),
    (r'aria-label=Efficiency', 'aria-label="效率洞察"'),
    (r'title=Efficiency', 'title="效率洞察"'),
    (r'data-label=Git', 'data-label="Git 交付"'),
    (r'aria-label=Git', 'aria-label="Git 交付"'),
    (r'title=Git', 'title="Git 交付"'),
    (r'data-label=Performance', 'data-label="性能报告"'),
    (r'aria-label=Performance', 'aria-label="性能报告"'),
    (r'title=Performance', 'title="性能报告"'),
    (r'data-label=Tools', 'data-label="工具能力"'),
    (r'aria-label=Tools', 'aria-label="工具能力"'),
    (r'data-label=Settings', 'data-label="系统设置"'),
    (r'aria-label=Settings', 'aria-label="系统设置"'),

    # 快捷按钮
    (r'<option value="">All projects</option>', '<option value="">全部项目 (All projects)</option>'),
    (r'>Other local sessions<', '>其它本地会话<'),
    (r'>All projects<', '>全部项目<'),
    (r'function projectFilterValue\(project\)\{return project&&\(project\.startsWith', 'function projectFilterValue(project){if(typeof project==="string"){project=project.replace(/\\\\/g,"/");if(/^[a-zA-Z]:\\//.test(project)){project=project.charAt(0).toUpperCase()+project.slice(1);}else if(/^[a-zA-Z]\\//.test(project)){project=project.charAt(0).toUpperCase()+":/"+project.slice(2);}}return project&&(project.startsWith'),
    (r'>Current sessions<', '>当前活跃会话<'),
    (r'>All sessions<', '>全部会话记录<'),
    (r'>Spend today<', '>今日消费<'),
    (r'>Sessions today<', '>今日会话数<'),
    (r'>Vs yesterday<', '>对比昨日<'),
    (r'>View month spend<', '>查看本月消费<'),
    (r'>Live local traces · last 30 minutes.<', '>实时本地会话 · 最近 30 分钟<'),
    (r'>Waiting for evidence<', '>等待数据产生<'),
    (r'>Waiting for activity<', '>等待会话活动<'),
    (r'>Waiting for comparison<', '>等待对比数据<'),
    (r'>Waiting for dated cost evidence<', '>等待日期费用数据<'),
    (r'>First five minutes<', '>新手快速入门<'),
    (r'>Getting started<', '>使用指引<'),
    (r'>Understand this run<', '>解析本次会话<'),
    (r'>Check cost, context, wait, and the latest execution.<', '>查看开销、上下文使用、等待耗时及最新执行。<'),
    (r'>Review Run<', '>查看运行<'),

    # 会话看板卡片
    (r'>Session cost<', '>当前会话开销<'),
    (r'>Started<', '>开始时间<'),
    (r'>Last activity<', '>最近活跃<'),
    (r'>local time<', '>本地时间<'),
    (r'>pinned log - frozen view<', '>已固定会话 - 静态视图<'),
    (r'>Input<', '>输入 Tokens<'),
    (r'>Output<', '>输出 Tokens<'),
    (r'>Wait time<', '>等待耗时<'),
    (r'>Context in use<', '>当前上下文使用<'),
    (r'>Efficiency<', '>效率洞察<'),
    (r'>This run<', '>本次运行<'),
    (r'>Output / \$<', '>产出 / 美元<'),
    (r'>Reasoning ratio<', '>推理输出占比<'),
    (r'>Session budget<', '>会话预算上限<'),
    (r'>Usage details<', '>使用明细<'),
    (r'>cache, tools, efficiency, and execution profile<', '>缓存、工具调用、效率指标与执行画像<'),
    (r'>Execution Profile<', '>单步执行画像<'),
    (r'>per execution or request<', '>单次模型调用/请求画像<'),
    (r'>Tokens<', '>Token 数<'),
    (r'>Cost<', '>费用<'),
    (r'>Context<', '>上下文<'),
    (r'>Steps<', '>执行步骤<'),
    (r'>Wait<', '>等待时长<'),
    (r'>Linear<', '>线性尺度<'),
    (r'>Cumulative<', '>累计尺度<'),
    (r'>Prompt-load evidence<', '>提示词预载分析<'),
    (r'>Tool-result tokens<', '>工具返回 Token<'),
    (r'>estimated returned text<', '>工具结果估算文本<'),
    (r'>input served from cache<', '>命中缓存输入<'),
    (r'>estimated avoided spend<', '>预估节约开销<'),
    (r'>Burn / minute<', '>每分钟消耗速度<'),
    (r'>while the run is active<', '>在会话活跃执行期间<'),

    # 筛选条与工具栏
    (r'>Status<', '>运行状态<'),
    (r'>All<', '>全部<'),
    (r'>Working<', '>执行中<'),
    (r'>Recent<', '>最近活跃<'),
    (r'>Waiting<', '>等待交互<'),
    (r'>Recent activity<', '>最近动态<'),
    (r'>Search<', '>搜索<'),
    (r'>All apps<', '>全部应用<'),
    (r'>Projects<', '>所属项目<'),
    (r'>All projects<', '>全部项目<'),
    (r'>Time range<', '>时间范围<'),
    (r'>Any time<', '>不限时间<'),
    (r'>Last 24 hours<', '>最近 24 小时<'),
    (r'>Last 7 days<', '>最近 7 天<'),
    (r'>Last 30 days<', '>最近 30 天<'),
    (r'>Last 90 days<', '>最近 90 天<'),
    (r'>Today<', '>今天<'),
    (r'>Yesterday<', '>昨天<'),
    (r'>All history<', '>全部历史<'),
    (r'>Clear filters<', '>清空筛选<'),
    (r'>Sort<', '>排序<'),
    (r'>Execs<', '>轮次<'),
    (r'>Filtered cost<', '>筛选开销<'),
    (r'>Input tokens<', '>输入 Token<'),
    (r'>Output tokens<', '>输出 Token<'),
    (r'>By model<', '>按模型<'),
    (r'>Add model<', '>添加模型<'),
    (r'>Open in Codex<', '>在 Codex 中打开<'),
    (r'>Delete session<', '>删除会话<'),
    (r'>No user message captured.<', '>未捕获到用户输入消息。<'),

    # 模型视图
    (r'>Observed output pace<', '>观测输出速率<'),
    (r'>waiting for timing evidence<', '>等待耗时样本<'),
    (r'>Matched pace<', '>匹配速率<'),
    (r'>Typical wait<', '>典型等待耗时<'),
    (r'>Timing unavailable<', '>无耗时记录<'),
    (r'>Cost unavailable<', '>无费用记录<'),
    (r'>0 executions<', '>0 次调用<'),
    (r'>Model trends<', '>模型趋势分析<'),
    (r'>Output pace<', '>输出速率<'),
    (r'>Output wait<', '>响应等待<'),
    (r'>Avg input<', '>平均输入<'),
    (r'>Avg output<', '>平均输出<'),
    (r'>Model runtime<', '>模型宿主工具<'),
    (r'>Logs \(all\)<', '>全部会话记录<'),
    (r'>Typical workload<', '>典型任务负载<'),

    # 消费视图
    (r'>Estimated agent spend over time.<', '>AI 编程助手历史消费趋势。<'),
    (r'>7 days<', '>7 天<'),
    (r'>30 days<', '>30 天<'),
    (r'>Month<', '>自然月<'),
    (r'>Custom<', '>自定义范围<'),
    (r'>From<', '>起始日期<'),
    (r'>To<', '>截止日期<'),
    (r'>Selected-period spend<', '>选定时段总消费<'),
    (r'>Daily average<', '>日均消费<'),
    (r'>Top platform<', '>主要支出平台<'),
    (r'>Highest day<', '>单日最高消费<'),
    (r'>Spend trend<', '>消费走势<'),
    (r'>Daily spend by platform · line shows average.<', '>各平台每日支出分布 · 折线为均值<'),
    (r'>Highest-cost logs<', '>最高开销会话排行<'),
    (r'>Platform split<', '>各平台占比<'),
    (r'>Session economics<', '>会话经济学分布<'),
    (r'>Concentration, typical sessions, and outliers.<', '>集中度、常规会话与大额异常点分析<'),
    (r'>Spend concentration<', '>消费集中度<'),
    (r'>Top 10% of cost-covered sessions.<', '>前 10% 高成本会话分析<'),
    (r'>Top decile<', '>前 10% 分位<'),
    (r'>Remaining sessions<', '>其余 90% 会话<'),
    (r'>Session shape<', '>会话形态分布<'),
    (r'>Period cost · other measures are full-session totals.<', '>周期内开销 · 其他统计为会话全量值<'),
    (r'>Cost and input by active time<', '>活跃耗时与成本/输入分布<'),

    # 效率视图
    (r'>Local token efficiency.<', '>本地 Token 使用效率分析。<'),
    (r'>No comparable prior period<', '>无同期对比数据<'),
    (r'>Context load<', '>上下文负载率<'),
    (r'>input tokens per output token<', '>每产出 1 个输出 Token 所需输入的 Token 数<'),
    (r'>Output / execution<', '>单次交互产出量<'),
    (r'>token-covered executions<', '>包含 Token 记录的交互轮次<'),
    (r'>Reasoning effort<', '>推理开销占比<'),
    (r'>Reasoning<', '>深度思考/推理<'),
    (r'>Output / exec<', '>单轮产出<'),

    # Git 交付视图
    (r'>Pushed code &times; covered spend.<', '>推送代码量 &times; Token 消费关联洞察<'),
    (r'>Last 12 months<', '>最近 12 个月<'),
    (r'>Local Git<', '>本地 Git<'),
    (r'>Scanning local Git<', '>正在检索本地 Git 记录<'),
    (r'>Pushed lines<', '>推送代码行数<'),
    (r'>added<', '>新增<'),
    (r'>deleted<', '>删除<'),
    (r'>Spend / 1K<', '>每千行开销<'),
    (r'>Push yield<', '>代码推送产出率<'),
    (r'>Spend coverage<', '>统计覆盖率<'),
    (r'>Push days<', '>推送天数<'),
    (r'>Commits<', '>提交次数<'),
    (r'>Repositories<', '>关联仓库数<'),
    (r'>Code pushed by day<', '>每日代码推送统计<'),
    (r'>Added<', '>新增行<'),
    (r'>Deleted<', '>删除行<'),
    (r'>Selected day<', '>选定日期<'),
    (r'>&larr; Previous<', '>&larr; 前一天<'),
    (r'>Next &rarr;<', '>后一天 &rarr;<'),
    (r'>Delivery economics<', '>交付成本模型<'),
    (r'>Cost by pushed lines<', '>按推送代码行数划分的成本分布<'),
    (r'>Clear Git evidence<', '>清除 Git 历史缓存<'),

    # 工具能力视图
    (r'>Tools, MCP servers, and skills.<', '>工具、MCP 服务与扩展技能分析。<'),
    (r'>MCP servers<', '>MCP 服务<'),
    (r'>Skills<', '>扩展技能<'),
    (r'>All capabilities<', '>全部能力<'),
    (r'>Tools, MCP servers, skills, evidence, and state<', '>工具、MCP 服务、扩展技能调用统计与状态<'),
    (r'>Runtime<', '>运行环境<'),
    (r'>All runtimes<', '>全部运行环境<'),
    (r'>Sort by<', '>排序方式<'),
    (r'>Name A–Z<', '>按名称 A–Z<'),
    (r'>Name Z–A<', '>按名称 Z–A<'),
    (r'>Most observed<', '>调用频次最高<'),
    (r'>Least observed<', '>调用频次最低<'),
    (r'>Recently observed<', '>最近活跃<'),
    (r'>Oldest observed<', '>最早记录<'),
    (r'>Capability<', '>功能名称<'),
    (r'>Runtime / source<', '>宿主工具 / 来源<'),
    (r'>Configuration<', '>配置类型<'),
    (r'>Last observed<', '>最近调用时间<'),
    (r'>Control<', '>管理操作<'),
    (r'>No use observed<', '>暂无调用记录<'),
    (r'>Observed<', '>已记录调用<'),

    # 系统设置视图
    (r'>Budgets, connections, pricing, and updates.<', '>预算配额、助手连接、模型定价与版本更新。<'),
    (r'>Sections<', '>配置分区<'),
    (r'>Model pricing<', '>模型定价设置<'),
    (r'>Language signals<', '>交互语言信号<'),
    (r'>Git evidence history<', '>Git 提交记录缓存<'),
    (r'>Software updates<', '>软件版本与更新<'),
    (r'>Not configured<', '>未配置<'),
    (r'>Set budget<', '>设定预算<'),
    (r'>Spent this month<', '>本月已花费<'),
    (r'>Calculated budget<', '>测算建议预算<'),
    (r'>Not set<', '>未设置<'),
    (r'>Remaining<', '>剩余可用<'),
    (r'>Projected month<', '>预估本月总消费<'),
    (r'>Monthly spend<', '>月度消费监控<'),
    (r'>Set budgets<', '>保存预算<'),
    (r'>Alerts at<', '>预警提醒阈值<'),
    (r'>Session defaults<', '>会话默认配置<'),
    (r'>Default session budget \(USD\)<', '>默认单次会话预算 (USD)<'),
    (r'>Runtime budgets · current spend<', '>各运行工具预算与当前支出<'),
    (r'>Budget \(USD\)<', '>预算上限 (USD)<'),
    (r'>Save budgets<', '>保存预算配置<'),
    (r'>Saved machine-wide<', '>已保存并在本机全局生效<'),
    (r'>Connect supported local agents.<', '>连接受支持的本地 AI 编程工具。<'),
    (r'>Loading connection status<', '>正在检测连接状态...<'),
    (r'>Cost estimates<', '>成本估算模型<'),
    (r'>Loading prices<', '>正在载入模型定价...<'),
    (r'>Apply to selected models<', '>应用到所选模型<'),
    (r'>From now<', '>从现在起<'),
    (r'>From date<', '>指定生效日期<'),
    (r'>Effective from<', '>生效时间<'),
    (r'>No models selected<', '>尚未选择模型<'),
    (r'>Provider<', '>供应商<'),
    (r'>Model id<', '>模型标识 (ID)<'),
    (r'>Cache write<', '>缓存写入 (/1M)<'),
    (r'>Cached input<', '>缓存读取 (/1M)<'),
    (r'>Save models<', '>保存模型定价<'),
    (r'>Save and recalculate<', '>保存并重新计算历史数据<'),
    (r'>Restore defaults<', '>恢复默认费率<'),
    (r'>Saved locally<', '>已保存在本地<'),
    (r'>Check for updates every 10 minutes<', '>每 10 分钟自动检查一次更新<'),
    (r'>Off also disables auto-install.<', '>关闭后同时停用自动安装。<'),
    (r'>Automatically install available updates<', '>发现可用更新时自动安装<'),
    (r'>Checks continue when off.<', '>关闭自动安装时仍会继续检测新版本。<'),
    (r'>Check now<', '>立即检查更新<'),
    (r'>Confirm<', '>确认<'),
    (r'>Cancel<', '>取消<'),
    (r'>Move to Trash<', '>移至回收站<'),
    (r'>Assign model to this session<', '>为此会话指定模型<'),
    (r'>Clear assignment<', '>清除指定模型<'),
    (r'>Save model<', '>保存模型设置<'),
    (r'>New update available<', '>发现新版本可用<'),
]

# 动态运行时的本地化 JS 代码块
ZH_RUNTIME_SCRIPT = """
<!-- ================================================================= -->
<!-- Token Meter 简体中文本地化增强模块 (防覆盖独立运行层)           -->
<!-- ================================================================= -->
<script>
(function() {
  console.log('[Token Meter ZH] 简体中文本地化引擎已启动');

  // 全局精确短语翻译表
  const zhDict = {
    'Sessions': '运行会话',
    'Spend': '消费统计',
    'Models': '模型分析',
    'Efficiency': '效率洞察',
    'Git': 'Git 交付',
    'Performance': '性能报告',
    'Tools': '工具能力',
    'Read': '阅读文档',
    'Learn': '快速上手',
    'Settings': '系统设置',
    'Active': '活跃',
    'Working': '执行中',
    'Listening': '监听中',
    'Waiting': '等待中',
    'Live': '运行中',
    'Recent': '最近活跃',
    'All': '全部',
    'Today': '今天',
    'Yesterday': '昨天',
    'Last 7 days': '最近 7 天',
    'Last 30 days': '最近 30 天',
    'Last 90 days': '最近 90 天',
    'All history': '全部历史',
    'Any time': '不限时间',
    'Clear filters': '清空筛选',
    'All projects': '全部项目',
    'Other local sessions': '其它本地会话',
    'No project': '未关联项目',
    'All models': '全部模型',
    'All apps': '全部应用',
    'All runtimes': '全部运行工具',
    'Session cost': '会话开销',
    'Input': '输入 Tokens',
    'Output': '输出 Tokens',
    'Wait time': '等待耗时',
    'Context in use': '当前上下文使用',
    'Output / $': '产出 / 美元',
    'Reasoning ratio': '推理占比',
    'Session budget': '会话预算',
    'Usage details': '使用明细',
    'Execution Profile': '执行画像',
    'Prompt-load impact': '提示词预载占比',
    'Search local session history.': '搜索本地会话历史...',
    'Filters are still active. Matching live sessions will appear here automatically.': '筛选条件生效中。符合条件的实时会话将自动展示在这里。',
    'Start a supported agent. Its live card appears here.': '启动受支持的 AI 编程助手（Claude / Codex / Trae / WorkBuddy / Antigravity），其实时会话卡片将自动在此展示。',
    'Waiting for evidence': '等待数据产生',
    'Waiting for activity': '等待会话活动',
    'Waiting for comparison': '等待对比数据',
    'Waiting for dated cost evidence': '等待日期费用数据',
    'No sessions recorded yet': '暂未记录到会话数据',
    'No candidate requires a decision': '当前没有待处理的候选项目',
    'No capabilities match these filters.': '没有符合当前筛选条件的能力组件。',
    'No daily evidence': '暂无每日统计数据',
    'No model activity in this window': '此时间段内暂无模型活动',
    'No model history in this window': '此时间段内暂无模型记录',
    'No use observed': '暂无调用记录',
    'Observed use': '已观测调用',
    'Active time': '活跃时间',
    'Daily total': '单日总计',
    'Pushed lines': '推送代码行',
    'Commits': '提交次数',
    'Coverage': '覆盖率',
    'Covered spend': '统计消费',
    'Setting': '设置项',
    'Budget': '预算上限',
    'P10': '前 10% 分位',
    'Median': '中位数',
    'Mean': '均值',
    'P90': '前 90% 分位',
    'Speed': '生成速率',
    'Cost': '费用',
    'Tokens': 'Token 数量',
    'Steps': '步骤数',
    'Wait': '等待耗时',
    'Linear': '线性',
    'Cumulative': '累计',
    'added': '新增',
    'deleted': '删除',
    'Added': '新增代码',
    'Deleted': '删除代码',
    'Repositories': '关联仓库',
    'Push days': '推送天数',
    'Save': '保存',
    'Cancel': '取消',
    'Confirm': '确认',
    'Reset': '重置',
    'Refresh': '刷新',
    'Export CSV': '导出 CSV',
    'Delete': '删除'
  };

  function translateNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const txt = node.nodeValue.trim();
      if (txt && zhDict[txt]) {
        node.nodeValue = node.nodeValue.replace(txt, zhDict[txt]);
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      // 占位符和 title
      if (node.placeholder && zhDict[node.placeholder]) {
        node.placeholder = zhDict[node.placeholder];
      }
      if (node.title && zhDict[node.title]) {
        node.title = zhDict[node.title];
      }
      // 子节点递归
      for (let i = 0; i < node.childNodes.length; i++) {
        translateNode(node.childNodes[i]);
      }
    }
  }

  // 页面初始加载时执行一次翻译
  function translatePage() {
    translateNode(document.body);
  }

  // 使用 MutationObserver 监听动态插入的内容进行实时汉化
  const observer = new MutationObserver(function(mutations) {
    for (const m of mutations) {
      for (const added of m.addedNodes) {
        translateNode(added);
      }
      if (m.type === 'characterData' && m.target) {
        const txt = m.target.nodeValue.trim();
        if (txt && zhDict[txt]) {
          m.target.nodeValue = m.target.nodeValue.replace(txt, zhDict[txt]);
        }
      }
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      translatePage();
      observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    });
  } else {
    translatePage();
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  // 定时每秒低开销复查一次关键标题与按钮
  setInterval(translatePage, 1500);
})();
</script>
"""

def main():
    if not os.path.exists(SOURCE_HTML):
        print(f"Error: {SOURCE_HTML} not found.")
        return 1

    with open(SOURCE_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Read source HTML: {len(content)} bytes")

    # 执行静态正则替换
    replaced_count = 0
    for pattern, replacement in STATIC_REPLACEMENTS:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            content = re.sub(pattern, replacement, content)
            replaced_count += matches

    print(f"Performed {replaced_count} static UI text replacements.")

    # 注入运行时汉化增强脚本（放置在 </body> 前）
    if "</body>" in content:
        content = content.replace("</body>", f"{ZH_RUNTIME_SCRIPT}\n</body>")
    else:
        content += f"\n{ZH_RUNTIME_SCRIPT}"

    with open(TARGET_HTML, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully generated Chinese page: {TARGET_HTML} ({len(content)} bytes)")
    return 0

if __name__ == "__main__":
    exit(main())
