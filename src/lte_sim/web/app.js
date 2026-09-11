const $ = (selector) => document.querySelector(selector);

const el = {
  attachButton: $("#attachButton"),
  detachButton: $("#detachButton"),
  stopAttachButton: $("#stopAttachButton"),
  resetButton: $("#resetButton"),
  openCustomFaultButton: $("#openCustomFaultButton"),
  toolbarFaultState: $("#toolbarFaultState"),
  commandForm: $("#commandForm"),
  commandInput: $("#commandInput"),
  commandFeedback: $("#commandFeedback"),
  showAtHistoryButton: $("#showAtHistoryButton"),
  quickActions: $("#quickActions"),
  scenarioSelect: $("#scenarioSelect"),
  scenarioDescription: $("#scenarioDescription"),
  httpHealth: $("#httpHealth"),
  apHealth: $("#apHealth"),
  enbHealth: $("#enbHealth"),
  eventDot: $("#eventDot"),
  versionChip: $("#versionChip"),
  httpPort: $("#httpPort"),
  apPort: $("#apPort"),
  enbPort: $("#enbPort"),
  runModeValue: $("#runModeValue"),
  openSettingsButton: $("#openSettingsButton"),
  settingsDialog: $("#settingsDialog"),
  settingsCloseButton: $("#settingsCloseButton"),
  settingsDoneButton: $("#settingsDoneButton"),
  exitModeButton: $("#settingsExitModeButton"),
  settingsCurrentMode: $("#settingsCurrentMode"),
  settingsModeHint: $("#settingsModeHint"),
  settingsRunsPath: $("#settingsRunsPath"),
  settingsOpenRunsButton: $("#settingsOpenRunsButton"),
  settingsExportRunButton: $("#settingsExportRunButton"),
  settingsRunsHint: $("#settingsRunsHint"),
  uiScaleDown: $("#settingsScaleDown"),
  uiScaleUp: $("#settingsScaleUp"),
  uiScaleValue: $("#settingsScaleValue"),
  uiScaleRange: $("#settingsScaleRange"),
  uiScaleReset: $("#settingsScaleReset"),
  managementPort: $("#managementPort"),
  lanGuidePanel: $("#lanGuidePanel"),
  lanTestButton: $("#lanTestButton"),
  lanControllerIp: $("#lanControllerIp"),
  lanModemIp: $("#lanModemIp"),
  lanAgentStatus: $("#lanAgentStatus"),
  lanApStatus: $("#lanApStatus"),
  lanEnbStatus: $("#lanEnbStatus"),
  lanManagementStatus: $("#lanManagementStatus"),
  lanHeartbeat: $("#lanHeartbeat"),
  lanExternalWeb: $("#lanExternalWeb"),
  lanLastError: $("#lanLastError"),
  apPortInline: $("#apPortInline"),
  enbPortInline: $("#enbPortInline"),
  transactionId: $("#transactionId"),
  attachStatus: $("#attachStatus"),
  attachHint: $("#attachHint"),
  flowProgress: $("#flowProgress"),
  durationValue: $("#durationValue"),
  cellValue: $("#cellValue"),
  plmnValue: $("#plmnValue"),
  metricSuccess: $("#metricSuccess"),
  metricFailures: $("#metricFailures"),
  runStatsCard: $("#runStatsCard"),
  flowStateText: $("#flowStateText"),
  currentFaultParamChips: $("#currentFaultParamChips"),
  showFaultParametersButton: $("#showFaultParametersButton"),
  showFlowGuideButton: $("#showFlowGuideButton"),
  cfunBadge: $("#cfunBadge"),
  mibBandwidth: $("#mibBandwidth"),
  mibSfn: $("#mibSfn"),
  mibPhich: $("#mibPhich"),
  sibBarred: $("#sibBarred"),
  sibQrx: $("#sibQrx"),
  sibPlmn: $("#sibPlmn"),
  sibTac: $("#sibTac"),
  lastError: $("#lastError"),
  lastErrorTitle: $("#lastErrorTitle"),
  lastErrorText: $("#lastErrorText"),
  lastErrorAction: $("#lastErrorAction"),
  flowSteps: $("#flowSteps"),
  logTableBody: $("#logTableBody"),
  logCount: $("#logCount"),
  emptyLogs: $("#emptyLogs"),
  logSearch: $("#logSearch"),
  logTypeFilter: $("#logTypeFilter"),
  pauseLogsButton: $("#pauseLogsButton"),
  exportLogsButton: $("#exportLogsButton"),
  exportTraceButton: $("#exportTraceButton"),
  clearLogsButton: $("#clearLogsButton"),
  toast: $("#toast"),
  securityStatusBadge: $("#securityStatusBadge"),
  securityBackendValue: $("#securityBackendValue"),
  securityLibsrtpValue: $("#securityLibsrtpValue"),
  securityProtocolImpl: $("#securityProtocolImpl"),
  securityTestBoundary: $("#securityTestBoundary"),
  securityBindingVersion: $("#securityBindingVersion"),
  securityProfileValue: $("#securityProfileValue"),
  securityIntegrationSummary: $("#securityIntegrationSummary"),
  securitySessionStatus: $("#securitySessionStatus"),
  nasCipherValue: $("#nasCipherValue"),
  nasIntegrityValue: $("#nasIntegrityValue"),
  nasNegotiatedValue: $("#nasNegotiatedValue"),
  srtpCipherValue: $("#srtpCipherValue"),
  srtpAuthValue: $("#srtpAuthValue"),
  securityKeyId: $("#securityKeyId"),
  securityPacketCount: $("#securityPacketCount"),
  nasByteProtectionStatus: $("#nasByteProtectionStatus"),
  nasByteAlgorithms: $("#nasByteAlgorithms"),
  nasUeCount: $("#nasUeCount"),
  nasMmeCount: $("#nasMmeCount"),
  nasLastSecurityEvent: $("#nasLastSecurityEvent"),
  nasLastSecurityMeta: $("#nasLastSecurityMeta"),
  securityVectorValidation: $("#securityVectorValidation"),
  securityCoreValidation: $("#securityCoreValidation"),
  securityReferenceValidation: $("#securityReferenceValidation"),
  securityUdpValidation: $("#securityUdpValidation"),
  securityPlaintext: $("#securityPlaintext"),
  securityProtectButton: $("#securityProtectButton"),
  securitySelfTestButton: $("#securitySelfTestButton"),
  securityPcapButton: $("#securityPcapButton"),
  srtpScenarioActions: $("#srtpScenarioActions"),
  securityPipeline: $("#securityPipeline"),
  securityPipelineSummary: $("#securityPipelineSummary"),
  securitySelfTestNav: $("#securitySelfTestNav"),
  securitySelfTestDetails: $("#securitySelfTestDetails"),
  securityResult: $("#securityResult"),
  srtpScenarioSelect: $("#srtpScenarioSelect"),
  securityScenarioRunButton: $("#securityScenarioRunButton"),
  securityScenarioExpectation: $("#securityScenarioExpectation"),
  securityStandaloneDemoButton: $("#securityStandaloneDemoButton"),
  securityStandaloneResult: $("#securityStandaloneResult"),
  securityPacketDetail: $("#securityPacketDetail"),
  securityDetailTitle: $("#securityDetailTitle"),
  securityDetailHint: $("#securityDetailHint"),
  taskRuntimeCards: $("#taskRuntimeCards"),
  apCommandCount: $("#apCommandCount"),
  apLastCommand: $("#apLastCommand"),
  apCommandErrors: $("#apCommandErrors"),
  enbSocketCount: $("#enbSocketCount"),
  enbSocketRtt: $("#enbSocketRtt"),
  enbSocketErrors: $("#enbSocketErrors"),
  primitiveTraceBody: $("#primitiveTraceBody"),
  emptyPrimitiveTrace: $("#emptyPrimitiveTrace"),
  timerCards: $("#timerCards"),
  diagnosisCode: $("#diagnosisCode"),
  diagnosisBody: $("#diagnosisBody"),
  runSystemCheckButton: $("#runSystemCheckButton"),
  runBlindDiagnosisButton: $("#runBlindDiagnosisButton"),
  runtimeReplay: $("#runtimeReplay"),
  blindDiagnosisPanel: $("#blindDiagnosisPanel"),
  exportDiagnosisButton: $("#exportDiagnosisButton"),
  systemCheckSummary: $("#systemCheckSummary"),
  systemCheckGrid: $("#systemCheckGrid"),
  packetTraceBody: $("#packetTraceBody"),
  emptyPacketTrace: $("#emptyPacketTrace"),
  runProgressFill: $("#runProgressFill"),
  runProgressLabel: $("#runProgressLabel"),
  shortcutHint: $("#shortcutHint"),
  customFaultForm: $("#customFaultForm"),
  faultStageInput: $("#faultStageInput"),
  faultActionInput: $("#faultActionInput"),
  faultMessageInput: $("#faultMessageInput"),
  faultFieldInput: $("#faultFieldInput"),
  faultFieldSuggestions: $("#faultFieldSuggestions"),
  faultFieldMeta: $("#faultFieldMeta"),
  faultFieldCount: $("#faultFieldCount"),
  faultValueHint: $("#faultValueHint"),
  faultValueChoices: $("#faultValueChoices"),
  faultCapabilityNote: $("#faultCapabilityNote"),
  faultModifyWorkspace: $("#faultModifyWorkspace"),
  faultTimingWorkspace: $("#faultTimingWorkspace"),
  faultTimingHint: $("#faultTimingHint"),
  faultDelayInput: $("#faultDelayInput"),
  customFaultError: $("#customFaultError"),
  customFaultApplyButton: $("#customFaultApplyButton"),
  customFaultDialog: $("#customFaultDialog"),
  customFaultCloseButton: $("#customFaultCloseButton"),
  customFaultCancelButton: $("#customFaultCancelButton"),
  customFaultDisableButton: $("#customFaultDisableButton"),
  faultConfigPreview: $("#faultConfigPreview"),
  filterFaultOnly: $("#filterFaultOnly"),
  traceDetailStatus: $("#traceDetailStatus"),
  traceDetailEmpty: $("#traceDetailEmpty"),
  traceDetailPanel: $("#traceDetailPanel"),
  diagnosisEvidence: $("#diagnosisEvidence"),
  showDiagnosisHistoryButton: $("#showDiagnosisHistoryButton"),
  apSignalToken: $("#apSignalToken"),
  enbSignalToken: $("#enbSignalToken"),
  topologyLiveSummary: $("#topologyLiveSummary"),
  liveStageValue: $("#liveStageValue"),
  liveTaskValue: $("#liveTaskValue"),
  liveQueueValue: $("#liveQueueValue"),
  livePrimitiveValue: $("#livePrimitiveValue"),
  liveTimerValue: $("#liveTimerValue"),
  liveRttValue: $("#liveRttValue"),
  liveDecisionValue: $("#liveDecisionValue"),
  traceViewMode: $("#traceViewMode"),
  faultDialog: $("#faultDialog"),
  faultSeverity: $("#faultSeverity"),
  faultTitle: $("#faultTitle"),
  faultSummary: $("#faultSummary"),
  faultScenarioNote: $("#faultScenarioNote"),
  faultImpact: $("#faultImpact"),
  faultCauses: $("#faultCauses"),
  faultChecks: $("#faultChecks"),
  faultSuggestions: $("#faultSuggestions"),
  faultTechnical: $("#faultTechnical"),
  faultInjectionFacts: $("#faultInjectionFacts"),
  faultInjectionParameters: $("#faultInjectionParameters"),
  faultCloseButton: $("#faultCloseButton"),
  faultCopyButton: $("#faultCopyButton"),
  faultDebugButton: $("#faultDebugButton"),
  faultTargetButton: $("#faultTargetButton"),
  infoDialog: $("#infoDialog"),
  infoDialogEyebrow: $("#infoDialogEyebrow"),
  infoDialogTitle: $("#infoDialogTitle"),
  infoDialogIntro: $("#infoDialogIntro"),
  infoDialogBody: $("#infoDialogBody"),
  infoDialogCloseButton: $("#infoDialogCloseButton"),
  infoDialogConfirmButton: $("#infoDialogConfirmButton"),
};

let state = null;
let logsPaused = false;
let pausedLogs = [];
let eventSource = null;
const renderSignatures = new Map();
const previousText = new WeakMap();
let sseErrorShown = false;
let sseFailureTimer = null;
let lastDiagnosisId = null;
let activeFaultReport = null;
let lastTerminalArchiveRefresh = null;
let lastSecurityRunId = null;
let lastRenderedTraceRows = [];
let selectedTraceItem = null;
let traceFocusCorrelation = "";
let selectedSecurityPacket = null;
let selectedSecurityStage = null;
let lastSecurityResult = null;

const SECURITY_SCENARIO_GUIDE = {
  NORMAL: ["正常链路", "单个 RTP 包应完成 SRTP 保护、真实 UDP 传输并被接收端接受；连续多包由“连续多包”场景单独验证。"],
  TAMPER_TAG: ["篡改认证 Tag", "接收端应该在认证阶段拒绝该包；Rejected 才表示认证保护生效。"],
  TAMPER_CIPHERTEXT: ["篡改密文", "密文被修改后 Authentication Tag 不再匹配，接收端应该拒绝，不允许恢复明文。"],
  WRONG_KEY: ["接收端错误 Key", "发送端和接收端使用不同 Key 时，认证应失败并拒绝该包。"],
  REPLAY: ["Replay 重放", "同一已接收的 SRTP 包再次到达时，应被 Replay Window 识别并拒绝。"],
  OUT_OF_ORDER: ["乱序", "合理范围内的乱序包仍应被接受，证明 Replay Window 不会把正常乱序误判为重放。"],
  ROLLOVER: ["Sequence 回绕", "RTP Sequence 从 65535 回到 0 时仍应正确维护 Packet Index / ROC 并完成验证。"],
  MULTI_PACKET: ["连续多包", "连续多包应分别生成正确 Sequence、SRTP 保护结果，并全部完成接收端验证。"],
  HEADER_VARIANTS: ["RTP Header 组合", "使用 CSRC、Header Extension 与 RTP Padding 三种头部组合走完整 protect → UDP → unprotect 链路，验证 Header 长度与认证输入处理。"],
};

function renderSecurityScenarioExpectation() {
  if (!el.securityScenarioExpectation || !el.srtpScenarioSelect) return;
  const [title, detail] = SECURITY_SCENARIO_GUIDE[el.srtpScenarioSelect.value] || ["异常场景", "运行后比较预期行为与实际 Receiver 结果。"];
  el.securityScenarioExpectation.innerHTML = `<strong>${escapeHtml(title)} · 预期行为</strong><span>${escapeHtml(detail)}</span>`;
}

const FLOW_GUIDE = {
  cfun_enable: {
    title: "1. 启用无线功能",
    task: "AP → Modem",
    purpose: "AP 发送 AT+CFUN=1，触发 Modem 从关闭无线功能进入附着准备状态。",
    evidence: "AT History、AP-Modem Socket、Modem CFUN 状态。",
    faults: "这一层主要关注 AT/Socket 可达性；当前不人为设置协议故障模板。",
  },
  nas_attach_req: {
    title: "2. NAS 发起 Attach",
    task: "NAS",
    purpose: "NAS Task 创建附着事务并启动后续广播信息、RRC 和 NAS 过程。",
    evidence: "NAS_ATTACH_REQ、流程关联 ID、TaskBus 生命周期。",
    faults: "若前置状态不合法会停止；当前不为了凑场景而增加虚构故障。",
  },
  mib_sib_read: {
    title: "3. 读取 MIB/SIB",
    task: "RRC / L1",
    purpose: "读取简化的 MIB/SIB 广播信息，为驻留和系统信息校验提供输入。",
    evidence: "MIB/SIB 面板、相关 Primitive、G_SYSTEM_INFO 工程保护计时器。",
    faults: "可以通过系统信息响应异常、Delay/Drop 等真实路径影响后续校验。",
  },
  system_info_validate: {
    title: "4. 系统信息校验",
    task: "RRC / NAS",
    purpose: "检查 Cell Barred、PLMN、TAC 等关键字段是否满足当前附着条件。",
    evidence: "Primitive 参数 Before/After、Expected/Actual、Diagnosis Evidence。",
    faults: "Cell Barred、PLMN mismatch、TAC/系统信息格式异常通常在这里暴露。",
  },
  random_access: {
    title: "5. 随机接入",
    task: "RRC / L2 / L1",
    purpose: "模拟 RA Preamble 与 Random Access Response，使 UE 获得建立 RRC 的前置接入条件。",
    evidence: "RA Primitive、Task Trace、G_RANDOM_ACCESS。",
    faults: "RA Reject、响应丢失、延迟等会在本步骤终止。",
  },
  rrc_connection: {
    title: "6. 建立 RRC 连接",
    task: "RRC",
    purpose: "执行 RRC Connection Request / Setup / SetupComplete 的简化建链过程。",
    evidence: "RRC Primitive、T300、Modem-eNB Socket Trace。",
    faults: "RRC Reject、RRC 响应 Drop/Delay 或 T300 到期。",
  },
  nas_attach_request: {
    title: "7. 发送 Attach Request",
    task: "NAS",
    purpose: "在 RRC 已建立的基础上，将 NAS Attach Request 送入网络侧 Stub。",
    evidence: "NAS Attach Request Primitive、Socket TX/RX、G_ATTACH_REQUEST。",
    faults: "Primitive/Socket 的修改、丢弃或延迟会在此形成可追踪证据。",
  },
  authentication: {
    title: "8. 鉴权",
    task: "NAS",
    purpose: "处理 Authentication Request / Response，并根据真实收到的参数决定是否继续。",
    evidence: "AUTH_RESPONSE_IND、Expected/Actual、G_AUTHENTICATION、Socket Evidence。",
    faults: "网络明确 Reject、参数异常、Primitive Missing、Socket Drop/Timeout 都会被区分诊断。",
  },
  security_mode: {
    title: "9. NAS 安全模式",
    task: "NAS",
    purpose: "模拟 Security Mode Command / Complete 协商流程，并更新 NAS Cipher/Integrity 状态。",
    evidence: "Security Mode Primitive、T3460 过程语义、G_SECURITY_MODE。",
    faults: "参数异常、消息缺失或 Socket 异常会在本步骤形成独立根因。",
  },
  attach_accept: {
    title: "10. 网络接受 Attach",
    task: "NAS / Network Stub",
    purpose: "网络侧返回 Attach Accept，表示核心注册流程被接受。",
    evidence: "Attach Accept Socket/Primitive 以及状态机迁移。",
    faults: "当前版本不为这一节点人为增加无真实工程意义的独立故障模板。",
  },
  attach_complete: {
    title: "11. Attach 完成",
    task: "NAS",
    purpose: "发送 Attach Complete，最终状态进入 ATTACHED。",
    evidence: "Attach Complete Primitive、G_ATTACH_COMPLETE、最终状态。",
    faults: "Primitive/Socket 丢失、延迟或参数错误会阻止最终 ATTACHED。",
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(iso) {
  if (!iso) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  }).format(new Date(iso));
}

function signatureChanged(key, value) {
  const next = JSON.stringify(value);
  if (renderSignatures.get(key) === next) return false;
  renderSignatures.set(key, next);
  return true;
}

function flashValue(node, value) {
  if (!node) return;
  const text = String(value);
  const previous = previousText.get(node);
  node.textContent = text;
  if (previous !== undefined && previous !== text) {
    node.classList.remove("value-changed");
    void node.offsetWidth;
    node.classList.add("value-changed");
  }
  previousText.set(node, text);
}

function lastSignature(rows, extra = "") {
  const list = rows || [];
  const last = list[list.length - 1] || {};
  return [
    list.length,
    last.time || last.finishedAt || "",
    last.event || last.type || last.command || "",
    extra,
  ];
}

function toast(message, kind = "info") {
  el.toast.textContent = message;
  el.toast.dataset.kind = kind;
  el.toast.classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(
    () => el.toast.classList.remove("visible"),
    kind === "error" ? 3200 : 1800,
  );
}

function listHtml(node, items) {
  if (!node) return;
  node.innerHTML =
    (items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") ||
    "<li>暂无更多信息</li>";
}

function shortFlowId(value) {
  const text = String(value || "").trim();
  if (!text) return "--";
  if (text.length <= 16) return text;
  return `${text.slice(0, 7)}…${text.slice(-6)}`;
}

function diagnosisText(report) {
  if (!report) return "";
  return [
    `${report.title || report.code || "仿真异常"} [${report.code || "UNCLASSIFIED"}]`,
    report.summary || "",
    report.impact ? `影响：${report.impact}` : "",
    report.scenarioNote || "",
    "",
    "可能原因：",
    ...(report.likelyCauses || []).map((x) => `- ${x}`),
    "",
    "检查项：",
    ...(report.checks || []).map((x) => `- ${x}`),
    "",
    "建议操作：",
    ...(report.suggestions || []).map((x) => `- ${x}`),
    "",
    `Step: ${report.failedStep || "--"}`,
    `Scenario: ${report.scenario || "--"}`,
    `Transaction: ${report.transactionId || "--"}`,
    report.message ? `原始错误: ${report.message}` : "",
    report.learnTopic ? `建议学习: ${report.learnTopic}` : "",
  ]
    .filter((x) => x !== null && x !== undefined)
    .join("\n");
}

function faultRuntimeEvidence(report = null) {
  const corr = report?.correlation_id || report?.correlationId || "";
  if (corr) {
    const matched = [...(state?.faultEvidence || [])].reverse().find((item) => item.correlation_id === corr);
    if (matched) return matched;
  }
  return [...(state?.faultEvidence || [])].reverse()[0] || null;
}

function faultFactRows(report = null) {
  const cfg = state?.faultConfig || {};
  const evidence = faultRuntimeEvidence(report) || {};
  const active = Boolean(cfg.enabled || evidence.fault_type || report?.fault_type);
  if (!active) return [];
  const stageKey = evidence.target_step || cfg.stage || report?.failedStep;
  const stage = faultCatalog?.stages?.[stageKey];
  const faultType = evidence.fault_label || report?.fault_label || cfg.fault_type || "--";
  const layer = evidence.layer || cfg.layer || "--";
  const primitive = evidence.primitive || report?.primitive || cfg.primitive || "--";
  const task = evidence.target_task || cfg.task || "--";
  const field = report?.field || evidence.field || cfg.field || "--";
  const before = report?.before ?? evidence.before;
  const after = report?.after ?? evidence.after;
  const expected = report?.expected ?? evidence.expected;
  const actual = report?.actual ?? evidence.actual;
  return [
    ["注入阶段", stage?.label || evidence.target_step_label || stageKey || "--"],
    ["注入层", layer === "socket" ? "Socket 发送路径" : "Primitive 交付路径"],
    ["故障动作", faultType],
    ["目标 Task", task],
    ["Primitive / Message", primitive],
    ["字段", field],
    ["Before", valueText(before)],
    ["After", valueText(after)],
    ["Expected", valueText(expected)],
    ["Actual", valueText(actual)],
    ["Delay", evidence.delay_ms ?? cfg.delay_ms ? `${evidence.delay_ms ?? cfg.delay_ms} ms` : "--"],
    ["Timeout", evidence.timer_limit ?? cfg.timeout_ms ? `${evidence.timer_limit ?? cfg.timeout_ms} ms` : "--"],
    ["相关计时器", report?.timer_label || evidence.timer_label || evidence.related_timer || "--"],
    ["流程关联 ID", shortFlowId(report?.correlation_id || evidence.correlation_id)],
    ["Fault ID", report?.fault_id || evidence.fault_id || cfg.fault_id || "--"],
  ];
}

function renderFaultInjectionFacts(report = null) {
  if (!el.faultInjectionFacts || !el.faultInjectionParameters) return;
  const rows = faultFactRows(report);
  el.faultInjectionParameters.hidden = rows.length === 0;
  el.faultInjectionFacts.innerHTML = rows.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
}

function openFaultParametersDialog() {
  const report = state?.diagnosis?.lastReport || null;
  const rows = faultFactRows(report);
  const html = rows.length
    ? `<dl class="dialog-fault-facts">${rows.map(([label,value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>`
    : `<div class="dialog-empty"><strong>当前没有启用故障注入</strong><p>运行条件为 NORMAL，Primitive / Socket 不会被 Fault Injector 修改。</p></div>`;
  openInfoDialog({
    eyebrow: "故障注入",
    title: rows.length ? "当前故障注入参数" : "正常网络",
    intro: rows.length ? "以下为当前 FaultConfig 以及本次运行已记录的注入参数。" : "当前 Attach 使用正常网络条件。",
    html,
  });
}

function showFaultDialog(report) {
  if (!report || !el.faultDialog) return;
  activeFaultReport = report;
  el.faultSeverity.textContent = report.severity || "ERROR";
  el.faultTitle.textContent = report.title || "仿真异常";
  el.faultSummary.textContent =
    report.summary || report.message || "当前操作未成功完成。";
  el.faultScenarioNote.textContent = report.scenarioNote || "";
  renderFaultInjectionFacts(report);
  el.faultImpact.textContent = report.impact || "当前操作未生效。";
  listHtml(el.faultCauses, report.likelyCauses || []);
  listHtml(el.faultChecks, report.checks || []);
  listHtml(el.faultSuggestions, report.suggestions || []);
  el.faultTechnical.textContent = JSON.stringify(report, null, 2);
  /* Legacy technical layout removed: `Code: ${report.code || "OPERATION_ERROR"}\nStep: ${report.failedStep || "--"}\nScenario: ${report.scenario || "--"}\nTransaction: ${report.transactionId || "--"}\nTime: ${report.time || new Date().toISOString()}\nRaw: ${report.message || "--"}\nLearn: ${report.learnTopic || "--"}`; */
  const target = report.targetView || "debug";
  el.faultTargetButton.textContent =
    target === "security"
      ? "打开 Security"
      : target === "at"
        ? "查看 AT / Socket"
        : target === "tasks"
          ? "查看原语 Trace"
          : target === "overview"
            ? "返回 Attach 页面"
            : "打开相关页面";
  if (typeof el.faultDialog.showModal === "function") {
    if (!el.faultDialog.open) el.faultDialog.showModal();
  } else {
    el.faultDialog.setAttribute("open", "");
  }
}

function closeFaultDialog() {
  if (!el.faultDialog) return;
  if (typeof el.faultDialog.close === "function" && el.faultDialog.open)
    el.faultDialog.close();
  else el.faultDialog.removeAttribute("open");
}

function operationErrorReport(
  title,
  error,
  {
    impact = "本次操作没有成功生效。",
    checks = [],
    suggestions = [],
    targetView = "debug",
  } = {},
) {
  return {
    id: `ui-${Date.now()}`,
    time: new Date().toISOString(),
    severity: "ERROR",
    code: "UI_OPERATION_FAILED",
    title,
    summary: error?.message || String(error || "未知错误"),
    impact,
    likelyCauses: ["后端服务未就绪或连接中断", "请求参数与当前状态不兼容"],
    checks: checks.length
      ? checks
      : [
          "确认仿真服务仍在运行",
          "检查顶部 Socket 状态",
          "查看诊断/日志中的最近错误",
        ],
    suggestions: suggestions.length
      ? suggestions
      : ["恢复服务或修正状态后重试", "若问题持续，导出状态与日志用于定位"],
    targetView,
    message: error?.message || String(error || ""),
    scenario: state?.scenario?.id || "--",
    transactionId: state?.flow?.transactionId || "--",
    failedStep: state?.flow?.currentStep || "--",
    scenarioNote: "这是界面/接口操作错误，不一定代表 LTE Attach 协议本身失败。",
    learnTopic: "错误处理、Socket/HTTP 状态与控制面调试方法",
  };
}

function openDialog(dialog) {
  if (!dialog) return;
  if (typeof dialog.showModal === "function") {
    if (!dialog.open) dialog.showModal();
  } else dialog.setAttribute("open", "");
}

function closeDialog(dialog) {
  if (!dialog) return;
  if (typeof dialog.close === "function" && dialog.open) dialog.close();
  else dialog.removeAttribute("open");
}

function openInfoDialog({ eyebrow = "说明", title = "信息", intro = "", html = "" } = {}) {
  if (!el.infoDialog) return;
  if (el.infoDialogEyebrow) el.infoDialogEyebrow.textContent = eyebrow;
  if (el.infoDialogTitle) el.infoDialogTitle.textContent = title;
  if (el.infoDialogIntro) el.infoDialogIntro.textContent = intro;
  if (el.infoDialogBody) el.infoDialogBody.innerHTML = html;
  openDialog(el.infoDialog);
}

function historyTable(headers, rows, emptyText = "暂无记录") {
  if (!rows.length) return `<div class="dialog-empty">${escapeHtml(emptyText)}</div>`;
  const head = headers.map((item) => `<th>${escapeHtml(item)}</th>`).join("");
  const body = rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("");
  return `<div class="history-modal-table-wrap"><table class="history-modal-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function openRunHistoryDialog() {
  const history = [...(state?.runHistory || [])].slice(-20).reverse();
  const rows = history.map((item) => [
    formatTime(item.finishedAt),
    item.transactionId || "--",
    item.scenario || "--",
    item.result || "--",
    item.durationMs == null ? "--" : `${item.durationMs} ms`,
    item.failedStep || "--",
  ]);
  openInfoDialog({
    eyebrow: "History",
    title: "运行记录",
    intro: "记录最近 20 次 Attach 的结果。顶部“本次会话”计数在重置后归零，但历史记录保留用于排障回看。",
    html: historyTable(["时间", "事务", "场景", "结果", "耗时", "失败步骤"], rows, "当前还没有运行记录。"),
  });
}

function openAtHistoryDialog() {
  const history = [...(state?.atHistory || [])].slice(-40).reverse();
  const rows = history.map((item) => [
    formatTime(item.time),
    item.command || "--",
    item.ok ? "OK" : "ERROR",
    item.durationMs == null ? "--" : `${item.durationMs} ms`,
    String(item.response || "").replace(/\s+/g, " ").slice(0, 80) || "--",
  ]);
  openInfoDialog({
    eyebrow: "AT History",
    title: "AT 指令历史",
    intro: "用于回看 AP→Modem 指令是否成功、响应时延以及最近返回内容。",
    html: historyTable(["时间", "指令", "结果", "耗时", "响应摘要"], rows, "当前还没有 AT 指令历史。"),
  });
}

function openFlowGuideDialog() {
  const steps = (state?.flow?.steps || []).map((step, index) => `
    <article class="guide-step-card"><strong>${index + 1}. ${escapeHtml(step.name || step.key)}</strong><p>${escapeHtml(step.detail || "")}</p></article>`).join("");
  openInfoDialog({
    eyebrow: "Attach Guide",
    title: "Attach 流程讲解",
    intro: "本页面展示的是从 AP 触发到网络附着完成的一条精简控制面链路。每一步失败后，都可以在 Task / Trace 和诊断页继续定位。",
    html: `<div class="guide-card-grid">${steps}</div>`,
  });
}

function openFlowStepDialog(stepKey) {
  const step = (state?.flow?.steps || []).find((item) => item.key === stepKey);
  const guide = FLOW_GUIDE[stepKey] || {};
  if (!step && !guide.title) return;
  const completed = new Set(state?.flow?.completed || []);
  const status = state?.flow?.failedStep === stepKey
    ? "失败"
    : completed.has(stepKey)
      ? "已完成"
      : state?.flow?.currentStep === stepKey && state?.flow?.running
        ? "执行中"
        : "未执行";
  const report = state?.diagnosis?.lastReport;
  const failure = state?.flow?.failedStep === stepKey && report
    ? `<article class="guide-step-card guide-failure"><strong>本次失败根因</strong><p>${escapeHtml(report.title || report.root_cause || report.code || "运行失败")}</p><small>${escapeHtml(report.summary || "")}</small></article>`
    : "";
  openInfoDialog({
    eyebrow: "Attach Step",
    title: guide.title || step?.name || stepKey,
    intro: `当前状态：${status}。${step?.detail || ""}`,
    html: `<div class="guide-card-grid">
      <article class="guide-step-card"><strong>这一步做什么</strong><p>${escapeHtml(guide.purpose || step?.detail || "")}</p></article>
      <article class="guide-step-card"><strong>涉及模块</strong><p>${escapeHtml(guide.task || "--")}</p></article>
      <article class="guide-step-card"><strong>到哪里看证据</strong><p>${escapeHtml(guide.evidence || "Task / Trace 与诊断页")}</p></article>
      <article class="guide-step-card"><strong>可能异常</strong><p>${escapeHtml(guide.faults || "查看诊断和相关 Primitive/Timer/Socket Evidence")}</p></article>
      ${failure}
    </div>`,
  });
}

function openDiagnosisHistoryDialog() {
  const history = [...(state?.diagnosis?.history || [])].slice(-20).reverse();
  const rows = history.map((item) => [
    formatTime(item.time),
    item.title || item.root_cause || item.code || "--",
    item.failedStep || "--",
    item.severity || "ERROR",
    item.summary || "--",
  ]);
  openInfoDialog({
    eyebrow: "Diagnosis",
    title: "诊断历史",
    intro: "保存最近 20 条失败诊断摘要，便于回看异常根因和失败步骤。",
    html: historyTable(["时间", "根因", "失败步骤", "级别", "摘要"], rows, "当前还没有诊断历史。"),
  });
}

function presentOperationError(title, error, options = {}) {
  toast(error?.message || String(error), "error");
  showFaultDialog(operationErrorReport(title, error, options));
}

function setHealth(node, socketState) {
  const status = socketState?.status || "UNKNOWN";
  const connections = socketState?.connections || 0;
  node.classList.toggle("online", ["LISTENING", "REMOTE"].includes(status));
  node.title = `${status} · 活跃连接 ${connections}`;
}

function setBusy(running) {
  document.body.classList.toggle("is-running", Boolean(running));
  el.attachButton.disabled = running;
  el.attachButton.textContent = running ? "Attach 执行中…" : "开始 Attach";
  if (el.stopAttachButton) el.stopAttachButton.disabled = !running;
  el.scenarioSelect.disabled = running;
  if (el.customFaultApplyButton) el.customFaultApplyButton.disabled = running;
  if (el.openCustomFaultButton) el.openCustomFaultButton.disabled = running;
  el.resetButton.disabled = false;
}

function animateSignal(node, reverse = false) {
  if (!node || window.matchMedia("(prefers-reduced-motion: reduce)").matches)
    return;
  node.classList.remove("pulse-forward", "pulse-reverse");
  void node.offsetWidth;
  node.classList.add(reverse ? "pulse-reverse" : "pulse-forward");
}

function renderTopologyActivity(flow) {
  const step = flow.currentStep;
  const networkSteps = new Set([
    "mib_sib_read",
    "random_access",
    "rrc_connection",
    "nas_attach_request",
    "authentication",
    "security_mode",
    "attach_accept",
    "attach_complete",
  ]);
  animateSignal(el.apSignalToken, false);
  if (networkSteps.has(step)) animateSignal(el.enbSignalToken, false);
  if (el.topologyLiveSummary) {
    el.topologyLiveSummary.textContent = flow.running
      ? `正在执行 ${step || "Attach"}；光点由真实步骤状态变化触发。`
      : flow.failedStep
        ? `流程在 ${flow.failedStep} 失败；请在诊断页查看原因。`
        : (flow.completed || []).length
          ? "本次 Attach 已结束；流程和 Trace 已保留。"
          : "等待 Attach；动画只在真实消息或步骤变化时触发。";
  }
}

function renderScenarioOptions(nextState) {
  if (el.scenarioSelect.options.length === 0 && nextState.scenarioOptions) {
    nextState.scenarioOptions.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name;
      option.title = `${item.id} · ${item.description || ""}`;
      option.dataset.description = item.description;
      el.scenarioSelect.appendChild(option);
    });
  }
  const runtimeCustom = el.scenarioSelect.querySelector("[data-runtime-custom]");
  if (nextState.scenario.id === "CUSTOM") {
    const option = runtimeCustom || document.createElement("option");
    option.value = "CUSTOM";
    option.textContent = "当前：自定义故障（选择预设可退出）";
    option.dataset.runtimeCustom = "true";
    option.dataset.description = nextState.scenario.description;
    option.disabled = true;
    if (!runtimeCustom) el.scenarioSelect.prepend(option);
  } else if (runtimeCustom) {
    runtimeCustom.remove();
  }
  el.scenarioSelect.value = nextState.scenario.id;
  const option = el.scenarioSelect.selectedOptions[0];
  el.scenarioDescription.textContent =
    option?.dataset.description || nextState.scenario.description;
  el.scenarioDescription.title = el.scenarioDescription.textContent;
}

function renderFlow(flow) {
  const completed = new Set(flow.completed || []);
  const steps = flow.steps || [];
  const timings = flow.stepTimingMs || {};
  const sig = [
    steps.map((x) => x.key),
    [...completed],
    flow.currentStep,
    flow.failedStep,
    flow.running,
    timings,
  ];
  if (signatureChanged("flow", sig)) {
    renderTopologyActivity(flow);
    el.flowSteps.innerHTML = steps
      .map((step, idx) => {
        let status = "pending";
        if (completed.has(step.key)) status = "done";
        if (
          flow.currentStep === step.key &&
          flow.running &&
          !completed.has(step.key)
        )
          status = "active";
        if (flow.failedStep === step.key) status = "failed";
        const timing = timings[step.key];
        const statusText =
          status === "done"
            ? `DONE${timing != null ? ` · ${timing}ms` : ""}`
            : status === "active"
              ? "RUN"
              : status === "failed"
                ? "FAIL"
                : "";
        return `<li class="${status}" data-step-key="${escapeHtml(step.key)}" role="button" tabindex="0" ${status==="failed"?'data-failure-step="true"':""}>
        <div class="step-marker">${status === "done" ? "✓" : idx + 1}</div>
        <div class="step-copy"><strong>${escapeHtml(step.name)}</strong><span title="${escapeHtml(step.detail)}">${escapeHtml(step.detail)}</span></div>
        <span class="step-status">${statusText}</span>
      </li>`;
      })
      .join("");
  }
  const total = steps.length || 11;
  const percent = Math.round((completed.size / total) * 100);
  el.flowProgress.textContent = `${completed.size} / ${total}`;
  el.flowStateText.textContent = flow.running
    ? flow.currentStep || "Running"
    : flow.failedStep
      ? `Failed · ${flow.failedStep}`
      : "Idle";
  el.transactionId.textContent = flow.transactionId || "--";
  el.durationValue.textContent =
    flow.durationMs != null ? `${flow.durationMs} ms` : "--";
  if (el.runProgressFill) el.runProgressFill.style.width = `${percent}%`;
  if (el.runProgressLabel) el.runProgressLabel.textContent = `${percent}%`;
}

let faultCatalog = null;
function fillOptions(node, values, selected, labels = {}) {
  if (!node) return;
  node.replaceChildren(...values.map(value => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labels[value] || value;
    return option;
  }));
  if (values.includes(selected)) node.value = selected;
}
function nestedValue(object, field) {
  const parts = String(field || "").split(".").filter(Boolean);
  let value = object;
  for (const part of parts) value = value && typeof value === "object" ? value[part] : undefined;
  return value;
}
function faultExpectedValue(stage, field, layer = "primitive") {
  const spec = faultCatalog?.stages?.[stage] || {};
  const source = layer === "socket" ? (spec.socket_example || spec.socket_expected || {}) : (spec.primitive_example || spec.expected || {});
  const value = nestedValue(source, field);
  if (value !== undefined) return value;
  return nestedValue(layer === "socket" ? (spec.socket_expected || {}) : (spec.expected || {}), field);
}
function expectedFaultRoot(action, layer) {
  if (action === "MODIFY_FIELD") return layer === "socket" ? "NETWORK_REJECT / PARAMETER_INVALID" : "PRIMITIVE_PARAMETER_INVALID";
  if (action === "DROP") return "PRIMITIVE_MISSING";
  if (action === "TIMER_TIMEOUT" || action === "DELAY") return "TIMER_EXPIRED（超过等待上限时）";
  if (action === "DUPLICATE") return "DUPLICATE_PRIMITIVE";
  if (action === "SOCKET_DROP") return "SOCKET_DROP";
  if (action === "SOCKET_DELAY") return "SOCKET_TIMEOUT / TIMER_EXPIRED（超过等待上限时）";
  return "按运行证据判定";
}

function syncFaultPreview() {
  if (!el.faultConfigPreview || !faultCatalog) return;
  const stage = el.faultStageInput?.value;
  const spec = faultCatalog.stages?.[stage];
  const layer = $("#faultLayerInput")?.value || "primitive";
  const action = el.faultActionInput?.value || "MODIFY_FIELD";
  const primitive = $("#faultPrimitiveInput")?.value || spec?.primitive || "--";
  const field = $("#faultFieldInput")?.value || "--";
  let detail = "";
  if (action === "MODIFY_FIELD") {
    let after = el.faultMessageInput?.value ?? "";
    try { after = JSON.parse(after); } catch (_) {}
    const before = faultExpectedValue(stage, field, layer);
    detail = `${field}: ${JSON.stringify(before)} → ${JSON.stringify(after)}`;
  } else if (["DELAY", "SOCKET_DELAY"].includes(action)) {
    detail = `实际延迟 ${Number(el.faultDelayInput?.value || 0)} ms；等待上限 ${Number($("#faultTimeoutInput")?.value || 0)} ms`;
  } else if (action === "DUPLICATE") {
    detail = "同一原语真实交付 2 次，由目标 Task 的去重/状态检查发现异常";
  } else if (["DROP", "SOCKET_DROP", "TIMER_TIMEOUT"].includes(action)) {
    detail = `目标消息不交付；等待上限 ${Number($("#faultTimeoutInput")?.value || 0)} ms`;
  }
  const actionText = action === "MODIFY_FIELD" ? "修改消息字段" : ({DELAY:"延迟原语交付",DROP:"不交付该原语",DUPLICATE:"重复交付原语",TIMER_TIMEOUT:"等待计时器到期",SOCKET_DELAY:"延迟 Socket 发送",SOCKET_DROP:"抑制 Socket 发送"}[action] || action);
  el.faultConfigPreview.innerHTML = `<div><b>注入位置</b><strong>${escapeHtml(spec?.label || stage || "--")}</strong><span>${escapeHtml(layer === "socket" ? "Socket 发送前" : "原语交付前")} · ${escapeHtml(primitive)}</span></div><div><b>本次动作</b><strong>${escapeHtml(actionText)}</strong><span>${escapeHtml(detail)}</span></div><div><b>运行观察点</b><strong>${escapeHtml(expectedFaultRoot(action, layer))}</strong><span>运行后检查消费者实收值、网络侧决策、Timer/Socket 与 Runtime Evidence。</span></div>`;
}
function renderFaultFieldSuggestions(fields, spec, socket) {
  if (!el.faultFieldSuggestions) return;
  const help = socket ? (spec.socket_field_help || {}) : (spec.field_help || {});
  const types = socket ? (spec.socket_fields || {}) : (spec.fields || {});
  const example = socket ? (spec.socket_example || {}) : (spec.primitive_example || {});
  const suggestions = socket ? (spec.socket_suggestions || {}) : (spec.suggestions || {});
  if (el.faultFieldCount) el.faultFieldCount.textContent = `${fields.length} 项`;
  el.faultFieldSuggestions.replaceChildren(...fields.map(field => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "fault-field-option";
    const before = nestedValue(example, field);
    const suggested = suggestions[field];
    button.innerHTML = `<strong>${escapeHtml(field)}</strong><span>${escapeHtml(help[field] || "当前消息字段")}</span><small>类型 ${escapeHtml(types[field] || "--")} · 原值 ${escapeHtml(valueText(before))}${suggested !== undefined && suggested !== null ? ` · 示例 ${escapeHtml(valueText(suggested))}` : ""}</small>`;
    button.title = `选择字段 ${field}`;
    button.addEventListener("click", () => {
      el.faultFieldInput.value = field;
      if (suggested !== undefined && suggested !== null) {
        el.faultMessageInput.value = typeof suggested === "string" ? suggested : JSON.stringify(suggested);
      }
      syncFaultFieldMeta();
      syncFaultPreview();
      el.faultMessageInput.focus();
    });
    return button;
  }));
}
function faultFieldTypeName() {
  const stage = el.faultStageInput?.value;
  const spec = faultCatalog?.stages?.[stage] || {};
  const socket = $("#faultLayerInput")?.value === "socket";
  const field = String(el.faultFieldInput?.value || "").trim();
  return (socket ? spec.socket_fields : spec.fields)?.[field] || "未知";
}
function syncFaultFieldMeta() {
  if (!faultCatalog || !el.faultStageInput) return;
  const spec = faultCatalog.stages?.[el.faultStageInput.value] || {};
  const socket = $("#faultLayerInput")?.value === "socket";
  const field = String(el.faultFieldInput?.value || "").trim();
  const typeName = (socket ? spec.socket_fields : spec.fields)?.[field] || "未知";
  const help = (socket ? spec.socket_field_help : spec.field_help)?.[field] || "请输入当前消息白名单中的字段路径。";
  const before = faultExpectedValue(el.faultStageInput.value, field, socket ? "socket" : "primitive");
  if (el.faultFieldMeta) {
    el.faultFieldMeta.innerHTML = `<strong>${escapeHtml(field || "未选择字段")}</strong><span>${escapeHtml(help)}</span><small>字段类型：${escapeHtml(typeName)} · 当前原值：${escapeHtml(valueText(before))}</small>`;
  }
  if (el.faultValueHint) {
    const tips = {
      str: "字符串：直接输入文字，不需要加引号。例如 INVALID_RES、REJECT、001-01。",
      int: "整数：只输入整数，例如 42、999、-120。",
      bool: "布尔值：只使用 true 或 false。",
      dict: "对象：请输入合法 JSON 对象，例如 {\"cellBarred\":true}；结构必须与当前字段语义相符。",
    };
    el.faultValueHint.textContent = tips[typeName] || "字段必须属于当前消息白名单；后端会严格校验类型。";
  }
  if (el.faultValueChoices) {
    el.faultValueChoices.replaceChildren();
    const suggested = socket ? spec.socket_suggestions?.[field] : spec.suggestions?.[field];
    const values = [];
    if (typeName === "bool") values.push(true, false);
    if (suggested !== undefined && suggested !== null && !values.some(item => item === suggested)) values.push(suggested);
    for (const value of values.slice(0, 3)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "fault-value-chip";
      button.textContent = `填入 ${valueText(value)}`;
      button.addEventListener("click", () => {
        el.faultMessageInput.value = typeof value === "string" ? value : JSON.stringify(value);
        syncFaultPreview();
      });
      el.faultValueChoices.append(button);
    }
  }
  el.faultFieldSuggestions?.querySelectorAll(".fault-field-option").forEach(node => {
    node.classList.toggle("selected", node.querySelector("strong")?.textContent === field);
  });
}
function parseFaultValue(raw, typeName) {
  const value = String(raw ?? "").trim();
  if (typeName === "str") return value;
  if (typeName === "int") {
    if (!/^-?\d+$/.test(value)) throw new Error("该字段是整数，请输入 42、999、-120 这类整数");
    return Number(value);
  }
  if (typeName === "bool") {
    if (value === "true") return true;
    if (value === "false") return false;
    throw new Error("该字段是布尔值，请输入 true 或 false");
  }
  if (typeName === "dict") {
    let parsed;
    try { parsed = JSON.parse(value); } catch (_) { throw new Error("该字段是对象，请输入合法 JSON 对象"); }
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("该字段是对象，请输入 JSON 对象而不是字符串/数组");
    return parsed;
  }
  try { return JSON.parse(value); } catch (_) { return value; }
}
function syncFaultFields() {
  if (!faultCatalog || !el.faultStageInput) return;
  const spec = faultCatalog.stages[el.faultStageInput.value];
  if (!spec) return;
  const socket = $("#faultLayerInput").value === "socket";
  const taskValue = socket ? "eNB/MME Stub" : spec.task;
  const primitiveValue = socket ? spec.message : spec.primitive;
  $("#faultTaskInput").value = spec.task;
  $("#faultPrimitiveInput").value = primitiveValue;
  $("#faultTaskDisplay").textContent = taskValue;
  $("#faultPrimitiveDisplay").textContent = primitiveValue;
  const types = socket ? ["MODIFY_FIELD", "SOCKET_DELAY", "SOCKET_DROP"] : ["MODIFY_FIELD", "DELAY", "DROP", "DUPLICATE", "TIMER_TIMEOUT"];
  const typeLabels = {MODIFY_FIELD:"修改字段",DELAY:"延迟原语",DROP:"丢弃原语",DUPLICATE:"重复原语",TIMER_TIMEOUT:"强制等待超时",SOCKET_DELAY:"延迟 Socket 消息",SOCKET_DROP:"丢弃 Socket 消息"};
  fillOptions(el.faultActionInput, types, types.includes(el.faultActionInput.value) ? el.faultActionInput.value : types[0], typeLabels);
  const fields = Object.keys(socket ? (spec.socket_fields || {}) : (spec.fields || {}));
  const current = String(el.faultFieldInput?.value || "").trim();
  renderFaultFieldSuggestions(fields, spec, socket);
  if (!current || !fields.includes(current)) el.faultFieldInput.value = fields[0] || "";
  const action = el.faultActionInput.value;
  const modify = action === "MODIFY_FIELD";
  const delayed = ["DELAY", "SOCKET_DELAY"].includes(action);
  const waits = delayed || ["DROP", "SOCKET_DROP", "TIMER_TIMEOUT"].includes(action);
  if (el.faultModifyWorkspace) el.faultModifyWorkspace.hidden = !modify;
  if (el.faultTimingWorkspace) el.faultTimingWorkspace.hidden = !(delayed || waits);
  $("#faultFieldGroup").hidden = !modify;
  $("#faultValueGroup").hidden = !modify;
  $("#faultDelayGroup").hidden = !delayed;
  $("#faultTimeoutGroup").hidden = !waits;
  el.faultFieldInput.disabled = !modify;
  el.faultMessageInput.disabled = !modify;
  el.faultDelayInput.disabled = !delayed;
  $("#faultTimeoutInput").disabled = !waits;
  if (el.faultFieldSuggestions) el.faultFieldSuggestions.hidden = !modify;
  if (el.faultTimingHint) {
    const timingHints = {
      DELAY: "真实延迟目标 Primitive 的交付；超过等待上限时由计时器判定超时。",
      DROP: "目标 Primitive 不交付；目标 Task 不会收到该对象，等待计时器继续运行。",
      TIMER_TIMEOUT: "不修改任何字段，直接保留等待过程直到工程保护计时器真实到期。",
      SOCKET_DELAY: "在 socket.send/request 前加入真实延迟，并记录 TX/RX/Timer 运行证据。",
      SOCKET_DROP: "在 Socket 发送前抑制消息；对端不会产生对应 Peer RX。",
    };
    el.faultTimingHint.textContent = timingHints[action] || "该动作不修改消息字段，只影响真实交付/等待时序。";
  }
  if (modify) {
    const field = el.faultFieldInput.value;
    const suggested = socket ? spec.socket_suggestions?.[field] : spec.suggestions?.[field];
    if (suggested !== undefined && suggested !== null && document.activeElement !== el.faultMessageInput) {
      el.faultMessageInput.placeholder = `示例：${typeof suggested === "string" ? suggested : JSON.stringify(suggested)}`;
    }
    if (el.faultCapabilityNote) el.faultCapabilityNote.textContent = `当前 ${socket ? "Socket 消息" : "Primitive"} 有 ${fields.length} 个后端白名单字段可修改；点击左侧字段即可看到原值、类型和建议测试值。`;
    syncFaultFieldMeta();
  } else if (el.faultCapabilityNote) {
    const actionNames = {DELAY:"延迟交付",DROP:"丢弃原语",DUPLICATE:"重复交付",TIMER_TIMEOUT:"等待超时",SOCKET_DELAY:"Socket 延迟",SOCKET_DROP:"Socket 丢弃"};
    el.faultCapabilityNote.textContent = `当前动作：${actionNames[action] || action}。该动作不修改消息字段，因此不会显示“可修改字段”列表；运行后以实际 Timer / Socket / Task 消费证据为准。`;
  }
  syncFaultPreview();
}
api('/api/fault-catalog').then(catalog => {
  faultCatalog = catalog;
  const stageLabels = {};
  Object.entries(catalog.stages || {}).forEach(([key, spec]) => { stageLabels[key] = spec.label || key; });
  fillOptions(el.faultStageInput, Object.keys(catalog.stages), 'authentication', stageLabels);
  syncFaultFields();
  if (state) renderCustomFault(state);
}).catch(error => toast(error.message, 'error'));

function renderCustomFault(nextState) {
  const fault = nextState.faultConfig || {};
  const enabled = Boolean(fault.enabled);
  const stageLabel = faultCatalog?.stages?.[fault.stage]?.label || fault.stage || "--";
  const actionLabels = {MODIFY_FIELD:"修改字段",DELAY:"延迟原语",DROP:"丢弃原语",DUPLICATE:"重复原语",TIMER_TIMEOUT:"等待超时",SOCKET_DELAY:"Socket 延迟",SOCKET_DROP:"Socket 丢包"};
  const actionLabel = actionLabels[fault.fault_type] || fault.fault_type || "--";
  const expected = enabled && fault.fault_type === "MODIFY_FIELD" ? faultExpectedValue(fault.stage, fault.field, fault.layer || "primitive") : undefined;
  const layerLabel = fault.layer === "socket" ? "Socket" : "Primitive";
  const isCustomScenario = (nextState?.scenario?.id || "") === "CUSTOM";
  const summary = !enabled
    ? "本轮不注入故障"
    : isCustomScenario
      ? `自定义故障已启用 · ${stageLabel} / ${layerLabel} / ${actionLabel}`
      : "已启用预设场景；请运行流程后结合 Trace / Diagnosis 定位实际影响。";
  $("#currentFaultStatus").textContent = enabled ? "故障注入已启用" : "正常网络";
  $("#currentFaultSummary").textContent = summary;
  if (el.showFaultParametersButton) el.showFaultParametersButton.hidden = !enabled;
  if (el.currentFaultParamChips) {
    const chips = enabled && isCustomScenario ? [
      ["阶段", stageLabel], ["层", layerLabel], ["动作", actionLabel],
      ["对象", fault.primitive || "--"],
      ...(fault.fault_type === "MODIFY_FIELD" ? [["字段", fault.field || "--"], ["参数", `${valueText(expected)} → ${valueText(fault.value)}`]] : []),
      ...(["DELAY","SOCKET_DELAY"].includes(fault.fault_type) ? [["延迟", `${fault.delay_ms} ms`]] : []),
      ...(["DROP","TIMER_TIMEOUT"].includes(fault.fault_type) ? [["等待上限", `${fault.timeout_ms} ms`]] : []),
    ] : [];
    el.currentFaultParamChips.hidden = chips.length === 0;
    el.currentFaultParamChips.innerHTML = chips.map(([k,v]) => `<span><b>${escapeHtml(k)}</b>${escapeHtml(v)}</span>`).join("");
  }
  if (el.toolbarFaultState) {
    el.toolbarFaultState.dataset.active = String(enabled);
    el.toolbarFaultState.querySelector("strong").textContent = enabled ? "故障注入" : "正常网络";
    el.toolbarFaultState.querySelector("small").textContent = enabled ? summary : "未启用故障注入";
  }
  const report = nextState.diagnosis?.lastReport;
  $("#failureLinks").hidden = !report;
  $("#failureRootSummary").textContent = report ? `${report.failedStep || "--"} · ${report.root_cause || report.code}` : "";
  if (!faultCatalog || document.activeElement?.closest?.('#customFaultForm')) return;
  el.faultStageInput.value = fault.stage || 'authentication';
  $("#faultLayerInput").value = fault.layer || 'primitive';
  syncFaultFields();
  if ([...el.faultActionInput.options].some(o => o.value === (fault.fault_type || 'MODIFY_FIELD'))) el.faultActionInput.value = fault.fault_type || 'MODIFY_FIELD';
  syncFaultFields();
  if (el.faultFieldInput) el.faultFieldInput.value = fault.field || el.faultFieldInput.value || 'auth_result';
  el.faultMessageInput.value = typeof fault.value === 'string' ? fault.value : JSON.stringify(fault.value);
  el.faultDelayInput.value = String(fault.delay_ms || 0);
  $("#faultTimeoutInput").value = String(fault.timeout_ms || 3000);
  syncFaultPreview();
}

function renderLogs(logs) {
  const sourceLogs = logsPaused ? pausedLogs : logs;
  const query = el.logSearch.value.trim().toLowerCase();
  const typeFilter = el.logTypeFilter.value;
  if (
    !signatureChanged(
      "logs",
      lastSignature(sourceLogs, `${query}|${typeFilter}|${logsPaused}`),
    )
  )
    return;
  const filtered = sourceLogs
    .filter((log) => {
      const hay =
        `${log.source} ${log.target} ${log.type} ${log.message} ${log.transactionId || ""}`.toLowerCase();
      const type = String(log.type || "").toUpperCase();
      const typeOk = typeFilter === "ALL" || type.includes(typeFilter);
      return typeOk && (!query || hay.includes(query));
    })
    .slice(-250)
    .reverse();

  el.logCount.textContent = `${filtered.length} / ${sourceLogs.length} 条`;
  el.emptyLogs.hidden = filtered.length > 0;
  el.logTableBody.innerHTML = filtered
    .map((log) => {
      const type = String(log.type || "INFO");
      const cls = type.toLowerCase().replaceAll("_", "-");
      const detailTitle = log.detail
        ? escapeHtml(JSON.stringify(log.detail))
        : "";
      return `<tr>
      <td class="time-cell">${formatTime(log.time)}</td>
      <td><strong>${escapeHtml(log.source)}</strong><span class="arrow">→</span>${escapeHtml(log.target)}</td>
      <td><span class="type-pill ${cls}">${escapeHtml(type)}</span></td>
      <td title="${detailTitle}">${escapeHtml(log.message)}</td>
      <td class="tx-cell">${escapeHtml(log.transactionId || "--")}</td>
    </tr>`;
    })
    .join("");
}

function renderRuntime(nextState) {
  const tasks = nextState.taskRuntime || {};
  if (!signatureChanged("runtime", tasks)) return;
  const order = ["NAS", "RRC", "L2", "L1"];
  el.taskRuntimeCards.innerHTML = order
    .map((name) => {
      const task = tasks[name] || {};
      const status = task.lifecycleStatus || task.status || "IDLE";
      const statusLabels = {IDLE:"待机", CREATED:"已创建", QUEUED:"排队", ENQUEUED:"入队", RUNNING:"处理中", PROCESSING:"处理中", SUCCESS:"完成", COMPLETED:"完成", FAILED:"失败", ERROR:"失败", TIMEOUT:"超时", STOPPED:"停止"};
      const latency = task.lastProcessingMs == null ? "--" : `${task.lastProcessingMs} ms`;
      return `<article class="task-runtime-card" data-status="${escapeHtml(status)}">
      <div><span>${name}</span><b>${escapeHtml(statusLabels[status] || status)}</b></div>
      <strong>${escapeHtml(task.lastPrimitive || "等待原语")}</strong>
      <small>队列 ${Number(task.queueDepth || 0)} · 已处理 ${Number(task.processed || 0)}</small>
      <small>最近处理 ${latency} · 错误 ${Number(task.errors || 0)} · 超时 ${Number(task.timeouts || 0)}</small>
    </article>`;
    })
    .join("");

  const transport = nextState.transportMetrics || {};
  const ap = transport.apModem || {};
  const enb = transport.modemEnb || {};
  el.apCommandCount.textContent = `${Number(ap.commands || 0)} cmd / ${Number(ap.responses || 0)} rsp`;
  el.apLastCommand.textContent = `last: ${ap.lastCommand || "--"} · ${ap.lastResponseMs == null ? "--" : `${ap.lastResponseMs} ms`}`;
  el.apCommandErrors.textContent = `errors ${Number(ap.errors || 0)}`;
  el.enbSocketCount.textContent = `${Number(enb.tx || 0)} tx / ${Number(enb.rx || 0)} rx`;
  el.enbSocketRtt.textContent = `RTT ${enb.lastRttMs == null ? "--" : `${enb.lastRttMs} ms`} · req ${enb.lastRequestId || "--"}`;
  el.enbSocketErrors.textContent = `errors ${Number(enb.errors || 0)} · ${enb.lastMessageType || "--"}`;
}

function renderControlObservability(nextState) {
  if (!el.liveStageValue) return;
  const flow = nextState?.flow || {};
  const steps = flow.steps || [];
  const currentStep = steps.find((step) => step.id === flow.currentStep) || steps.find((step) => step.key === flow.currentStep) || null;
  const taskRuntime = nextState?.taskRuntime || {};
  const runningTask = Object.entries(taskRuntime).find(([, item]) => ["RUNNING", "PROCESSING", "QUEUED", "ENQUEUED"].includes(String(item?.lifecycleStatus || item?.status || "").toUpperCase()));
  const trace = nextState?.taskEvents || nextState?.primitiveTrace || [];
  const lastPrimitive = [...trace].reverse().find((item) => item?.primitive);
  const queueDepth = Object.values(taskRuntime).reduce((sum, item) => sum + Number(item?.queueDepth || 0), 0);
  const activeTimers = Object.values(nextState?.timers || {}).filter((item) => item?.status === "RUNNING").length;
  const lastRtt = nextState?.transportMetrics?.modemEnb?.lastRttMs;
  const networkDecision = [...(nextState?.runtimeEvents || [])].reverse().find((item) => ["NETWORK_AUTH_DECISION", "NETWORK_CONTROL_DECISION", "UE_SYSTEM_INFO_DECISION", "CONTROL_PLANE_DELIVERY_DECISION"].includes(item?.event));
  const completed = Array.isArray(flow.completed) ? flow.completed.length : 0;
  const stageText = flow.running
    ? (currentStep?.label || currentStep?.name || flow.currentStep || `运行中 ${completed}/11`)
    : (nextState?.modem?.attachStatus === "ATTACHED" ? "Attach 已完成" : (flow.failedStep ? `失败：${flow.failedStep}` : "等待启动"));
  el.liveStageValue.textContent = stageText;
  el.liveTaskValue.textContent = runningTask?.[0] || lastPrimitive?.task || lastPrimitive?.target_task || "--";
  el.liveQueueValue.textContent = String(queueDepth);
  el.livePrimitiveValue.textContent = lastPrimitive?.primitive || "--";
  el.liveTimerValue.textContent = String(activeTimers);
  el.liveRttValue.textContent = lastRtt == null ? "--" : `${lastRtt} ms`;
  if (el.liveDecisionValue) el.liveDecisionValue.textContent = networkDecision
    ? `${networkDecision.decisionType || "网络侧"} · ${networkDecision.decision || "--"}`
    : "--";
}

function traceCorrelation(item) {
  return item?.correlationId || item?.correlation_id || "";
}

function isFaultRelated(item) {
  const corr = traceCorrelation(item);
  return Boolean(
    item?.fault_type || item?.root_cause || item?.error ||
    (state?.faultEvidence || []).some((row) => row.correlation_id === corr) ||
    (state?.diagnosis?.lastReport?.correlation_id && state.diagnosis.lastReport.correlation_id === corr)
  );
}

function isKeyTraceEvent(row) {
  const phase = String(row?.phase || row?.status || "").toUpperCase();
  const primitive = String(row?.primitive || "").toUpperCase();
  if (isFaultRelated(row)) return true;
  if (["COMPLETED", "ERROR", "TIMEOUT", "WAITING_RESPONSE", "QUEUE_FULL"].includes(phase)) return true;
  return /ATTACH|AUTH|SECURITY|RRC|SYSTEM_INFO|RANDOM_ACCESS|MIB|SIB/.test(primitive);
}

function traceViewAccepts(row) {
  const mode = el.traceViewMode?.value || "key";
  if (mode === "all") return true;
  if (mode === "diagnostic") {
    return isFaultRelated(row) || ["ERROR", "TIMEOUT", "QUEUE_FULL"].includes(String(row?.phase || row?.status || "").toUpperCase());
  }
  return isKeyTraceEvent(row);
}

function matchesTrace(row) {
  const task = el.filterTask?.value || $("#filterTask")?.value || "";
  const query = (el.filterPrimitive?.value || $("#filterPrimitive")?.value || "").trim().toLowerCase();
  const corr = traceCorrelation(row);
  const taskValue = row.task || row.target_task || "";
  const hay = `${row.primitive || ""} ${corr} ${row.phase || ""} ${row.stage || ""} ${row.root_cause || ""}`.toLowerCase();
  if (!traceViewAccepts(row)) return false;
  if (task && taskValue !== task) return false;
  if (query && !hay.includes(query)) return false;
  if (el.filterFaultOnly?.checked && !isFaultRelated(row)) return false;
  if (traceFocusCorrelation && corr !== traceFocusCorrelation) return false;
  return true;
}

function valueText(value) {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function renderTraceDetail(item) {
  selectedTraceItem = item || null;
  if (!item) {
    el.traceDetailEmpty.hidden = false;
    el.traceDetailPanel.hidden = true;
    el.traceDetailStatus.textContent = "未选择";
    renderEvidence();
    return;
  }
  el.traceDetailEmpty.hidden = true;
  el.traceDetailPanel.hidden = false;
  const corr = traceCorrelation(item);
  const evidence = (state?.faultEvidence || []).find((row) => row.correlation_id === corr) || {};
  const report = state?.diagnosis?.lastReport?.correlation_id === corr ? state.diagnosis.lastReport : {};
  const before = evidence.before ?? item.before;
  const after = evidence.after ?? item.after ?? item.actual;
  const expected = report.expected ?? evidence.expected ?? item.expected;
  const actual = report.actual ?? evidence.actual ?? item.actual;
  el.traceDetailStatus.textContent = `${item.primitive || "Primitive"} · ${item.phase || item.status || "--"}`;
  const facts = [
    ["Task", item.task || item.target_task], ["阶段", evidence.target_step_label || item.stage],
    ["Primitive", item.primitive], ["流程关联 ID", shortFlowId(corr)],
    ["故障类型", evidence.fault_label || evidence.fault_type || item.fault_type || "无"],
    ["字段", report.field || evidence.field], ["Before", before], ["After", after],
    ["Expected", expected], ["Actual", actual],
    ["计时器", report.timer_label || evidence.timer_label || item.related_timer],
    ["根因", report.title || report.root_cause || evidence.root_cause],
  ];
  el.traceDetailPanel.innerHTML = `<dl class="trace-fact-grid">${facts.map(([label,value]) =>
    `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueText(value))}</dd></div>`).join("")}</dl>`;
  renderEvidence(corr);
}

function renderPrimitiveTrace(trace) {
  const filterSig = `${el.traceViewMode?.value || "key"}|${$("#filterTask")?.value || ""}|${$("#filterPrimitive")?.value || ""}|${el.filterFaultOnly?.checked}|${traceFocusCorrelation}`;
  if (!signatureChanged("primitive", lastSignature(trace, filterSig))) return;
  const rows = [...(trace || [])].filter(matchesTrace).slice(-500).reverse();
  lastRenderedTraceRows = rows;
  el.emptyPrimitiveTrace.hidden = rows.length > 0;
  el.primitiveTraceBody.innerHTML = rows.map((item, index) => {
    const phase = String(item.phase || item.status || "--");
    const phaseLabels = {CREATED:"创建",ENQUEUED:"入队",WAITING_RESPONSE:"等待响应",PROCESSING:"处理中",COMPLETED:"完成",ERROR:"失败",TIMEOUT:"超时",QUEUE_FULL:"队列满",STARTED:"就绪",STOPPED:"停止"};
    const corr = traceCorrelation(item);
    const abnormal = isFaultRelated(item);
    const stageKey = item.stage || item.target_step || "";
    const stageLabel = faultCatalog?.stages?.[stageKey]?.label || stageKey || "--";
    return `<tr class="trace-row${abnormal ? " is-fault-related" : ""}" data-trace-index="${index}" tabindex="0">
      <td class="time-cell">${formatTime(item.time)}</td>
      <td><strong>${escapeHtml(item.task || item.target_task || "--")}</strong></td>
      <td class="primitive-cell">${escapeHtml(item.primitive || "--")}</td>
      <td>${escapeHtml(stageLabel)}</td>
      <td><span class="primitive-phase ${escapeHtml(phase.toLowerCase().replaceAll("_", "-"))}">${escapeHtml(phaseLabels[phase] || phase)}</span>${abnormal ? '<span class="trace-alert-dot" title="异常相关">!</span>' : ""}</td>
      <td class="tx-cell">${escapeHtml(corr || "--")}</td>
    </tr>`;
  }).join("");
  if (selectedTraceItem) {
    const corr = traceCorrelation(selectedTraceItem);
    const replacement = rows.find((row) => traceCorrelation(row) === corr && row.primitive === selectedTraceItem.primitive) || rows[0];
    renderTraceDetail(replacement || null);
  } else if (rows.length && traceFocusCorrelation) {
    renderTraceDetail(rows[0]);
  }
}

function renderTimers(timers) {
  const report = state?.diagnosis?.lastReport || null;
  const currentTx = state?.flow?.transactionId || null;
  const standardOrder = ["T300", "T3410", "T3460", "T3450"];
  const all = Object.entries(timers || {});
  const relevantGuard = report?.related_timer;
  const chosen = [];
  standardOrder.forEach((name) => {
    const item = timers?.[name];
    if (!item) return;
    const sameRun = Boolean(currentTx && item?.transactionId === currentTx);
    const actuallyUsed = Boolean(item?.startedAt || item?.stoppedAt || ["RUNNING", "EXPIRED"].includes(item?.status));
    if (name === relevantGuard || (sameRun && actuallyUsed)) chosen.push([name, item]);
  });
  all.forEach(([name, item]) => {
    if (standardOrder.includes(name)) return;
    const sameRun = currentTx && item?.transactionId === currentTx;
    if (name === relevantGuard || (sameRun && ["RUNNING", "EXPIRED"].includes(item?.status))) chosen.push([name, item]);
  });
  if (!signatureChanged("timers", chosen)) return;
  if (!chosen.length) {
    el.timerCards.innerHTML = '<div class="timer-empty"><strong>当前没有相关计时器</strong><span>Attach 运行或发生超时后，这里会显示标准过程计时器，以及与本次异常直接相关的工程保护计时器。</span></div>';
    return;
  }
  el.timerCards.innerHTML = `<div class="timer-board">${chosen.map(([name, item]) => {
    const status = item?.status || "IDLE";
    const statusLabels = {IDLE:"未启动", RUNNING:"计时中", STOPPED:"已停止", EXPIRED:"已超时"};
    const label = item?.label || name;
    const purpose = item?.purpose || "过程保护";
    const isStandard = String(item?.kind || "").toLowerCase().includes("3gpp");
    const kind = isStandard ? "3GPP 标准" : "工程保护";
    const limit = item?.timeoutLimit ?? item?.durationMs;
    const elapsed = item?.elapsed;
    const limitText = limit != null ? `${Math.round(Number(limit))} ms` : "--";
    const elapsedText = elapsed != null ? `${Math.round(Number(elapsed))} ms` : "--";
    const ratio = limit && elapsed != null ? Math.max(0, Math.min(100, Number(elapsed) / Number(limit) * 100)) : (status === "EXPIRED" ? 100 : 0);
    const waiting = item?.waitingPrimitive || item?.waiting_primitive || report?.waiting_primitive || "--";
    return `<article class="timer-card-v52" data-status="${escapeHtml(status)}">
      <header><div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(kind)}</small></div><span>${escapeHtml(statusLabels[status] || status)}</span></header>
      <div class="timer-metrics-v52"><div><b>上限</b><strong>${escapeHtml(limitText)}</strong></div><div><b>实际</b><strong>${escapeHtml(elapsedText)}</strong></div><div><b>等待对象</b><strong>${escapeHtml(waiting)}</strong></div></div>
      <div class="timer-progress-v52" aria-label="计时进度"><i style="width:${ratio.toFixed(1)}%"></i></div>
      <p>${escapeHtml(purpose)}</p>
    </article>`;
  }).join("")}</div>`;
}

function renderSystemCheck(check) {
  if (!el.systemCheckSummary || !el.systemCheckGrid) return;
  if (!check) {
    el.systemCheckSummary.innerHTML = '<strong>运行检查未执行</strong><span>可随时检查状态机、Socket、TaskBus、Timer、网络侧决策与 Security 状态，不要求预先注入故障。</span>';
    el.systemCheckGrid.hidden = true;
    el.systemCheckGrid.replaceChildren();
    return;
  }
  const overallLabels = {PASS:"通过", WARN:"有警告", FAIL:"发现异常"};
  el.systemCheckSummary.dataset.status = check.overall || "PASS";
  el.systemCheckSummary.innerHTML = `<strong>系统检查 · ${escapeHtml(overallLabels[check.overall] || check.overall || "完成")}</strong><span>${escapeHtml(check.summary || "")}</span>`;
  el.systemCheckGrid.hidden = false;
  el.systemCheckGrid.innerHTML = (check.checks || []).map((item) => `<button type="button" class="system-check-card" data-status="${escapeHtml(item.status || "INFO")}" data-target-view="${escapeHtml(item.targetView || "debug")}"><span>${escapeHtml(item.area || "检查")}</span><strong>${escapeHtml(item.title || item.id || "检查项")}</strong><small>${escapeHtml(item.detail || "")}</small><i>${escapeHtml(item.status || "INFO")}</i></button>`).join("");
  el.systemCheckGrid.querySelectorAll("button[data-target-view]").forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.targetView || "debug")));
}

async function runSystemCheck() {
  if (!el.runSystemCheckButton) return;
  el.runSystemCheckButton.disabled = true;
  el.runSystemCheckButton.textContent = "检查中…";
  try {
    const result = await api("/api/diagnostics/check", { method: "POST" });
    if (result.state) renderState(result.state);
    else renderSystemCheck(result.check);
    toast(result.check?.overall === "FAIL" ? "系统检查发现异常" : "系统检查完成", result.check?.overall === "FAIL" ? "error" : "ok");
  } catch (error) {
    presentOperationError("系统检查失败", error, { targetView: "debug" });
  } finally {
    el.runSystemCheckButton.disabled = false;
    el.runSystemCheckButton.textContent = "运行系统检查";
  }
}

async function runBlindDiagnosis() {
  if (!el.runBlindDiagnosisButton) return;
  el.runBlindDiagnosisButton.disabled = true;
  el.runBlindDiagnosisButton.textContent = "正在复算…";
  try {
    const result = await api("/api/diagnostics/blind", { method: "POST" });
    // Directly paint the fresh report first so the user can see that a new
    // backend diagnosis ID/time/digest was produced by this click.
    renderBlindDiagnosis(result.blindReport, state?.diagnosis?.lastReport || null);
    el.blindDiagnosisPanel?.classList.remove("is-fresh");
    void el.blindDiagnosisPanel?.offsetWidth;
    el.blindDiagnosisPanel?.classList.add("is-fresh");
    if (result.state) renderState(result.state);
    const cmp = result.blindReport?.comparison || {};
    toast(`证据隔离复算完成：${cmp.blindVerdict || result.blindReport?.diagnosticVerdict || "完成"}`, cmp.verdictMatch === false ? "error" : "ok");
  } catch (error) {
    presentOperationError("证据隔离复算失败", error, { targetView: "debug" });
  } finally {
    el.runBlindDiagnosisButton.disabled = false;
    el.runBlindDiagnosisButton.textContent = "证据隔离复算";
  }
}

function renderRuntimeReplay(report) {
  if (!el.runtimeReplay) return;
  const rows = report?.runtimeReplay || [];
  if (!report || !rows.length) {
    el.runtimeReplay.innerHTML = '<div class="diagnosis-empty"><strong>运行链路回放</strong><span>失败后用紧凑链路显示消息经过 Modem、Socket、eNB/MME 与判定点的实际顺序。</span></div>';
    return;
  }
  const labels = {
    PRIMITIVE_CREATED:"原语创建", PRIMITIVE_CONSUMED:"Task 消费", SOCKET_TX:"Modem发送",
    SOCKET_PEER_RX:"eNB/MME接收", SOCKET_PEER_TX:"eNB/MME返回", SOCKET_RX:"Modem接收",
    TIMER_STARTED:"计时器开始", TIMER_EXPIRED:"计时器到期", NETWORK_AUTH_DECISION:"MME 鉴权判定",
    NETWORK_CONTROL_DECISION:"网络侧判定", UE_SYSTEM_INFO_DECISION:"UE/RRC 判定",
    CONTROL_PLANE_DELIVERY_DECISION:"交付判定", NETWORK_CONTEXT_READ:"读取网络上下文",
    NETWORK_STATE_TRANSITION:"网络状态迁移", NETWORK_REJECT_GENERATED:"生成 Reject", NETWORK_RESPONSE_GENERATED:"生成网络响应",
    VALIDATION_FAILED:"运行校验失败", STATE_TRANSITION:"状态迁移"
  };
  const tx = rows.filter(row => row.event === "SOCKET_TX" || row.event === "SOCKET_PEER_TX");
  const rx = rows.filter(row => row.event === "SOCKET_PEER_RX" || row.event === "SOCKET_RX");
  let pairTotal = 0, pairMatched = 0;
  tx.forEach(item => {
    if (!item.payloadSha256) return;
    pairTotal += 1;
    if (rx.some(peer => peer.payloadSha256 === item.payloadSha256)) pairMatched += 1;
  });
  const transportProof = pairTotal
    ? `<span class="runtime-proof-chip" data-pass="${pairMatched === pairTotal ? "true" : "false"}">Socket Hash 匹配 ${pairMatched}/${pairTotal}</span>`
    : '<span class="runtime-proof-chip">本段无跨 Socket Hash 对</span>';
  el.runtimeReplay.innerHTML = `<div class="runtime-replay-heading"><div><b>运行链路回放</b><span>后端 Runtime Recorder · 本次事务 ${escapeHtml(shortFlowId(report.transactionId || ""))}</span></div><div class="runtime-replay-proof">${transportProof}<span>${rows.length} 个关键事件</span></div></div><ol>${rows.map((row, index) => {
    const label = labels[row.event] || row.event || "运行事件";
    const hash = row.payloadSha256 ? `${String(row.payloadSha256).slice(0,12)}…` : "";
    const transitionText = row.event === "NETWORK_STATE_TRANSITION" ? `${row.stateLabel || row.field || "状态"} ${valueText(row.before)} → ${valueText(row.after)}` : "";
    const generatedMessage = row.outputMessage?.kind || row.wireMessageKind || "";
    const detail = transitionText || generatedMessage || (row.decision ? `${row.decision}${row.rejectCause ? ` · ${row.rejectCause}` : ""}` : (row.expectedSource || row.primitive || row.waiting_primitive || row.timer_label || row.timer || ""));
    const evidence = [row.eventId ? `事件 ${String(row.eventId).slice(-8)}` : "", hash ? `SHA-256 ${hash}` : ""].filter(Boolean).join(" · ");
    return `<li data-event="${escapeHtml(row.event || "")}"><b class="runtime-replay-index">${index + 1}</b><time>${formatTime(row.time)}</time><div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span>${evidence ? `<small>${escapeHtml(evidence)}</small>` : ""}</div></li>`;
  }).join("")}</ol>`;
}

function renderBlindDiagnosis(report, normalReport) {
  if (!el.blindDiagnosisPanel) return;
  if (!normalReport) {
    el.blindDiagnosisPanel.innerHTML = '<div class="diagnosis-empty"><strong>证据隔离复算</strong><span>当前没有失败事务。发生失败后，这里可以在剥离场景名和故障配置后重新计算根因。</span></div>';
    return;
  }
  if (!report) {
    el.blindDiagnosisPanel.innerHTML = '<div class="blind-diagnosis-head"><div><b>证据隔离复算</b><span>后端会重新执行诊断，而不是刷新同一份前端结果。</span></div><strong>等待复算</strong></div><div class="blind-compact-grid"><span><b>输入</b>运行证据</span><span><b>不提供</b>场景名称 / 故障配置</span><span><b>排除</b>故障注入记录</span></div><p>点击上方“证据隔离复算”后，将显示新的诊断 ID、证据摘要 SHA-256 与原诊断/复算结果对照。</p>';
    return;
  }
  const input = report.diagnosisInput || {};
  const cmp = report.comparison || {};
  const digest = String(input.evidenceDigest || "");
  const matched = cmp.verdictMatch !== false;
  el.blindDiagnosisPanel.innerHTML = `<div class="blind-diagnosis-head"><div><b>证据隔离复算</b><span>后端重新计算 · ${escapeHtml(formatTime(cmp.rerunAt || report.time))}</span></div><strong data-pass="${matched ? "true" : "false"}">${matched ? "结论一致" : "结论不一致"}</strong></div><div class="blind-result-flow"><span><b>原诊断</b><code>${escapeHtml(cmp.normalVerdict || normalReport.diagnosticVerdict || normalReport.root_cause || "--")}</code><small>${escapeHtml(shortFlowId(cmp.normalDiagnosisId || normalReport.id || ""))}</small></span><i>→</i><span><b>隔离复算</b><code>${escapeHtml(cmp.blindVerdict || report.diagnosticVerdict || report.root_cause || "--")}</code><small>${escapeHtml(shortFlowId(cmp.blindDiagnosisId || report.id || ""))}</small></span></div><div class="blind-compact-grid"><span><b>证据数量</b>${Number(input.eventCount || 0)} 条</span><span><b>已排除注入事件</b>${Number(input.excludedFaultEventCount || 0)} 条</span><span><b>场景名称 / 故障配置</b>未提供</span><span><b>证据摘要</b><code>${escapeHtml(digest ? `${digest.slice(0,16)}…` : "--")}</code></span></div><p>复算输入来自本次 transaction 的 Runtime Evidence；页面只负责显示后端返回的复算 ID、摘要和结论。</p>`;
}

function renderDiagnosis(diagnosis) {
  renderSystemCheck(diagnosis?.systemCheck || null);
  const report = diagnosis?.lastReport;
  renderRuntimeReplay(report);
  renderBlindDiagnosis(diagnosis?.blindReport || null, report);
  const reportId = report ? `${report.id || report.time || ""}|${report.code || report.root_cause || ""}|${report.failedStep || ""}` : null;
  if (reportId && reportId !== lastDiagnosisId) {
    lastDiagnosisId = reportId;
    showFaultDialog(report);
  } else if (!report) {
    lastDiagnosisId = null;
  }
  if (!signatureChanged("diagnosis", report || null)) return;
  if (!report) {
    el.diagnosisCode.textContent = "无故障";
    el.diagnosisBody.innerHTML = '<div class="diagnosis-empty"><strong>当前没有失败报告</strong><span>可先运行系统检查；出现异常后，这里只保留根因、失败检查项和关键运行证据。</span></div>';
    if (el.diagnosisEvidence) el.diagnosisEvidence.textContent = "暂无异常证据";
    lastDiagnosisId = null;
    return;
  }

  el.diagnosisCode.textContent = report.diagnosticVerdict || report.root_cause || report.code || "UNCLASSIFIED";
  const failedStepKey = report.failedStep || report.target_step;
  const failedStepLabel = faultCatalog?.stages?.[failedStepKey]?.label || failedStepKey;
  const modeLabels = {
    PARAMETER_MISMATCH:"参数校验异常", TIMEOUT_OR_MISSING_INPUT:"等待/计时器异常",
    NETWORK_AUTH_DECISION:"网络侧鉴权判定", NETWORK_POLICY_DECISION:"网络侧控制面判定", CONTROL_PLANE_DECISION:"控制面运行判定",
    TRANSPORT_OR_NETWORK_RESPONSE:"Socket/网络响应异常", CONTROL_PLANE_FAILURE:"控制面异常"
  };
  const facts = [
    ["失败步骤", failedStepLabel],
    ["诊断结论", report.diagnosticVerdict || report.root_cause],
    ["Primitive", report.primitive],
    ["失败字段", report.field || report.network_decision?.failedField],
    ["诊断类型", modeLabels[report.diagnosis_mode] || report.diagnosis_mode],
  ].filter(([,value]) => value !== undefined && value !== null && value !== "");
  const categoryLabels = {PROTOCOL:"协议响应", PRIMITIVE:"原语", STATE_MACHINE:"状态机", TIMER:"计时器", TRANSPORT:"传输", CONTROL_PLANE:"控制面"};

  let focus = "";
  if (report.network_decision?.decision) {
    const nd = report.network_decision;
    const allChecks = nd.checks || [];
    const failedChecks = allChecks.filter(item => !item.passed);
    const failed = failedChecks[0] || null;
    const checks = allChecks.map((item) => `<li data-pass="${item.passed ? "true" : "false"}"><span>${escapeHtml(item.name || item.field || "检查项")}</span><code>${escapeHtml(valueText(item.actual))}</code><i>${item.passed ? "通过" : "失败"}</i><small>期望 ${escapeHtml(valueText(item.expected))}</small></li>`).join("");
    const d = report.parameter_delta || {};
    const consumer = d.consumer || (String(nd.event || "").startsWith("NETWORK_") ? "网络侧 MME/eNB" : "目标 Worker");
    const causeChain = (nd.causeChain || []).filter(Boolean).map((item) => `<code>${escapeHtml(valueText(item))}</code>`).join('<i>→</i>');
    const actual = failed?.actual ?? nd.actualValue ?? d.targetConsumedValue ?? d.actual;
    const expected = failed?.expected ?? nd.expectedValue ?? d.contractExpectedValue ?? d.expected;
    const field = failed?.field || nd.failedField || d.field || "--";
    const transitions = nd.stateTransitions || [];
    const transitionText = transitions.length ? transitions.map((item) => `${item.label || item.field}: ${valueText(item.before)} → ${valueText(item.after)}`).join("；") : "状态保持";
    const pipeline = (nd.pipeline || []).map((item, index) => `<li><i>${index + 1}</i><div><b>${escapeHtml(item.label || item.stage || "判定步骤")}</b><span>${escapeHtml(valueText(item.detail))}</span></div></li>`).join("");
    const expectedOrigin = nd.expectedSource ? `<div class="network-expected-origin"><b>期望值来源</b><span><code>${escapeHtml(nd.expectedSource)}</code>${nd.contextCreatedBy ? ` · 建立于 ${escapeHtml(nd.contextCreatedBy)}` : ""}</span></div>` : "";
    focus = `<section class="diagnosis-focus-card network-decision"><div class="network-decision-head"><div><b>${escapeHtml(nd.decisionType || "控制面判定")}</b><span>网络侧读取当前 transaction 上下文后执行规则，不根据场景名称直接生成结果。</span></div><strong data-decision="${escapeHtml(nd.decision)}">${escapeHtml(nd.decision)}</strong></div><div class="diagnosis-failure-core"><span><b>失败检查</b><code>${escapeHtml(field)}</code></span><span><b>网络侧实收</b><code>${escapeHtml(valueText(actual))}</code></span><span><b>协议/策略期望</b><code>${escapeHtml(valueText(expected))}</code></span><span><b>生成响应</b><code>${escapeHtml(nd.responseGeneration?.message || nd.outputMessage?.kind || nd.rejectCause || "--")}</code></span></div>${expectedOrigin}<div class="network-decision-pipeline"><div class="network-pipeline-title"><b>网络侧决策流水线</b><span>Context → Rule → Decision → State → Message</span></div><ol>${pipeline || `<li><i>1</i><div><b>网络侧判定</b><span>${escapeHtml(nd.rule || "执行当前控制面规则")}</span></div></li>`}</ol><div class="network-state-transition-summary"><b>状态变化</b><span>${escapeHtml(transitionText)}</span></div></div>${causeChain ? `<div class="network-cause-chain"><b>原因链</b>${causeChain}</div>` : ""}${d.field ? `<div class="runtime-consumption-proof"><b>消费证据</b><span>${escapeHtml(consumer)} 实收 <code>${escapeHtml(d.field)}</code> = <strong>${escapeHtml(valueText(d.targetConsumedValue ?? d.actual))}</strong></span></div>` : ""}<details class="decision-check-details"><summary>查看全部网络侧检查（${allChecks.length} 项，${failedChecks.length} 项失败）</summary><ol class="network-decision-checks">${checks}</ol></details></section>`;
  } else if (report.parameter_delta?.field) {
    const d = report.parameter_delta;
    const consumer = d.consumer || "目标 Task";
    focus = `<section class="diagnosis-focus-card parameter v53-parameter-evidence"><div><b>运行时参数校验证据</b><span>顶层只显示消费者运行时实收值与协议期望；FaultConfig Before/After 放在高级调试中。</span></div><div class="diagnosis-failure-core"><span><b>字段</b><code>${escapeHtml(d.field)}</code></span><span><b>${escapeHtml(consumer)} 实收</b><code>${escapeHtml(valueText(d.targetConsumedValue ?? d.actual))}</code></span><span><b>协议期望</b><code>${escapeHtml(valueText(d.contractExpectedValue ?? d.expected))}</code></span></div>${report.mechanism_description ? `<p>${escapeHtml(report.mechanism_description)}</p>` : ""}</section>`;
  } else if (report.timer_evidence) {
    const t = report.timer_evidence;
    focus = `<section class="diagnosis-focus-card timer"><div><b>计时器到期证据</b><span>等待对象未在运行上限内完成。</span></div><div class="diagnosis-failure-core"><span><b>计时器</b><code>${escapeHtml(t.label || t.timer || "--")}</code></span><span><b>等待对象</b><code>${escapeHtml(t.waitingPrimitive || report.waiting_primitive || "--")}</code></span><span><b>实际/上限</b><code>${escapeHtml(`${valueText(t.elapsedMs)} / ${valueText(t.limitMs)} ms`)}</code></span></div></section>`;
  }

  const netCtx = report.network_decision?.networkContextAfter || state?.networkContext?.active || null;
  const ctxStates = netCtx ? [netCtx.rrcState, netCtx.authenticationState, netCtx.securityState, netCtx.attachState] : [];
  const showContext = netCtx && ctxStates.some(value => value && value !== "IDLE" && value !== "--");
  const networkContextCard = showContext ? `<section class="network-context-card"><div><b>网络侧 UE Context</b><span>网络侧按 transaction 持续维护，不由 Diagnosis 创建</span></div><dl><span><dt>RRC</dt><dd>${escapeHtml(netCtx.rrcState || "--")}</dd></span><span><dt>鉴权</dt><dd>${escapeHtml(netCtx.authenticationState || "--")}</dd></span><span><dt>安全</dt><dd>${escapeHtml(netCtx.securityState || "--")}</dd></span><span><dt>附着</dt><dd>${escapeHtml(netCtx.attachState || "--")}</dd></span></dl></section>` : "";
  const faultDebug = report.fault_id || report.fault_type || report.mechanism ? `<details class="diagnosis-advanced-debug"><summary>高级调试 · 故障配置 / 注入器</summary><dl><div><dt>Fault ID</dt><dd>${escapeHtml(shortFlowId(report.fault_id) || "--")}</dd></div><div><dt>故障动作</dt><dd>${escapeHtml(report.fault_label || report.fault_type || "--")}</dd></div><div><dt>实现机制</dt><dd>${escapeHtml(report.mechanism || "--")}</dd></div><div><dt>注入前</dt><dd>${escapeHtml(valueText(report.before))}</dd></div><div><dt>注入后</dt><dd>${escapeHtml(valueText(report.after))}</dd></div></dl></details>` : "";
  const primitiveSnapshots = report.primitive_before || report.primitive_after ? `<details class="diagnosis-primitive-snapshot"><summary>高级调试 · 完整参数快照</summary><div><section><b>注入前快照</b><pre>${escapeHtml(JSON.stringify(report.primitive_before || {}, null, 2))}</pre></section><section><b>注入后快照</b><pre>${escapeHtml(JSON.stringify(report.primitive_after || {}, null, 2))}</pre></section></div></details>` : "";
  const metadataRows = [
    ["流程关联 ID", shortFlowId(report.correlation_id)], ["计时器", report.timer_label || report.related_timer],
    ["等待原语", report.waiting_primitive], ["等待上限", report.timer_limit != null ? `${Math.round(Number(report.timer_limit))} ms` : null],
    ["实际耗时", report.elapsed != null ? `${Math.round(Number(report.elapsed))} ms` : null],
  ].filter(([,value]) => value !== undefined && value !== null && value !== "");
  const metadata = metadataRows.length ? `<details class="diagnosis-metadata-details"><summary>查看运行关联信息</summary><dl>${metadataRows.map(([label,value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueText(value))}</dd></div>`).join("")}</dl></details>` : "";

  el.diagnosisBody.innerHTML = `
    <div class="diagnosis-root-title"><strong>${escapeHtml(report.title || report.root_cause || report.code)}</strong><span>${escapeHtml(categoryLabels[report.category] || report.category || "运行异常")}</span></div>
    <p class="diagnosis-summary">${escapeHtml(report.summary || "运行失败")}</p>
    <dl class="diagnosis-facts diagnosis-facts-v601">${facts.map(([label,value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueText(value))}</dd></div>`).join("")}</dl>
    ${focus}${networkContextCard}
    <section class="diagnosis-followup"><div class="diagnosis-advice"><b>建议下一步</b><span title="${escapeHtml((report.actions || report.suggestions || []).join("；") || report.suggested_check || "查看相关运行证据")}">${escapeHtml((report.actions || report.suggestions || [])[0] || report.suggested_check || "查看相关运行证据")}</span></div><div class="diagnosis-tools">${metadata}${faultDebug}${primitiveSnapshots}</div></section>`;

  const evidence = (report.evidence_summary || report.evidence || []).filter(row => row.event !== "FAULT_INJECTED").slice(0, 12);
  if (el.diagnosisEvidence) {
    const evidenceLabels = {PRIMITIVE_CREATED:"原语已创建", PRIMITIVE_CONSUMED:"目标 Task 已消费", NETWORK_CONTEXT_READ:"网络侧读取上下文", NETWORK_AUTH_DECISION:"网络侧鉴权判断", NETWORK_CONTROL_DECISION:"网络侧控制判定", NETWORK_STATE_TRANSITION:"网络侧状态迁移", NETWORK_REJECT_GENERATED:"网络侧生成 Reject", NETWORK_RESPONSE_GENERATED:"网络侧生成响应", UE_SYSTEM_INFO_DECISION:"UE/RRC 判定", CONTROL_PLANE_DELIVERY_DECISION:"交付判定", VALIDATION_FAILED:"参数校验失败", TIMER_STARTED:"开始等待", TIMER_EXPIRED:"等待超时", SOCKET_TX:"Modem发送", SOCKET_PEER_RX:"eNB/MME接收", SOCKET_PEER_TX:"eNB/MME返回", SOCKET_RX:"Modem接收", SOCKET_DROP:"Socket 消息被丢弃", SOCKET_TIMEOUT:"Socket 等待超时", SOCKET_ERROR:"Socket 错误", STATE_TRANSITION:"状态已推进"};
    el.diagnosisEvidence.innerHTML = evidence.length ? evidence.map((row) => {
      const rawTitle = row.event || row.root_cause || row.fault_type || "运行证据";
      const title = evidenceLabels[rawTitle] || rawTitle;
      const subject = row.primitive || row.waiting_primitive || row.timer_label || row.timer || row.decision || "--";
      const transition = row.event === "NETWORK_STATE_TRANSITION" ? `${row.stateLabel || row.field}: ${valueText(row.before)} → ${valueText(row.after)}` : "";
      const delta = transition || row.expectedSource || (row.field ? `${row.field}: ${valueText(row.expected ?? row.expectedValue)} ↔ ${valueText(row.actual ?? row.actualValue)}` : (row.rejectCause || row.outputMessage?.kind || row.message || row.mechanism || ""));
      return `<article class="diagnosis-evidence-item"><div><strong>${escapeHtml(title)}</strong><time>${formatTime(row.time || row.injection_time)}</time></div><span>${escapeHtml(subject)}</span><small>${escapeHtml(delta)}</small></article>`;
    }).join("") : "暂无可用证据";
  }
}

function renderProtocolTrace(trace, summary) {
  // v5.1 keeps protocolTrace in backend/run artifacts, but the separate Web table
  // was removed because it duplicated the Task/Trace correlation timeline.
  return;
}

function renderPacketTrace(packets) {
  if (!signatureChanged("packets", lastSignature(packets))) return;
  const rows = [...(packets || [])].slice(-80).reverse();
  el.emptyPacketTrace.hidden = rows.length > 0;
  el.packetTraceBody.innerHTML = rows
    .map(
      (item) => `<tr>
    <td>${formatTime(item.time)}</td>
    <td>${escapeHtml(item.direction || "--")}</td>
    <td title="${escapeHtml(item.summary || "")}">${escapeHtml(item.messageType || item.event || "--")}</td>
    <td>${Number(item.sizeBytes || 0)}</td>
    <td>${item.rttMs == null ? "--" : `${item.rttMs} ms`}</td>
  </tr>`,
    )
    .join("");
}

function protocolSocketLabel(socketState) {
  const item = socketState || {};
  if (item.status === "OFFLINE" || item.status === "FAILED" || item.status === "STOPPED") return item.status;
  if (Number(item.connections || 0) > 0) return "CONNECTED";
  if (["LISTENING", "REMOTE", "STARTING"].includes(item.status)) return "READY";
  return item.status || "--";
}

function renderLanGuide(nextState) {
  if (!el.lanGuidePanel) return;
  const cfg = nextState.config || {};
  const lanMode = cfg.runMode === "lan-controller";
  el.lanGuidePanel.hidden = !lanMode;
  if (!lanMode) return;
  const lan = nextState.lan || {};
  el.lanControllerIp.textContent = lan.controllerIp || cfg.controllerHost || "--";
  el.lanModemIp.textContent = lan.modemIp || cfg.modemHost || "--";
  el.lanAgentStatus.textContent = lan.agentStatus || "CHECKING";
  el.lanApStatus.textContent = protocolSocketLabel(nextState.sockets?.apModem);
  el.lanEnbStatus.textContent = lan.remoteModemEnbStatus || "UNVERIFIED";
  el.lanManagementStatus.textContent = lan.managementStatus || "DISCONNECTED";
  el.lanHeartbeat.textContent = lan.heartbeatAt ? formatTime(lan.heartbeatAt) : "--";
  el.lanExternalWeb.textContent = cfg.externalWebUrl || "--";
  const error = lan.lastError;
  el.lanLastError.hidden = !error;
  el.lanLastError.textContent = error
    ? `LAN 连接异常：${error}。建议检查电脑 B Agent、IP、Windows 防火墙、端口和 Management token。`
    : "";
}

function renderState(nextState) {
  state = nextState;
  renderScenarioOptions(nextState);
  renderCustomFault(nextState);
  renderEvidence();
  setHealth(el.httpHealth, nextState.sockets.http);
  setHealth(el.apHealth, nextState.sockets.apModem);
  setHealth(el.enbHealth, nextState.sockets.modemEnb);
  el.versionChip.textContent = `v${nextState.version}`;

  const cfg = nextState.config || {};
  el.runModeValue.textContent = cfg.runMode || "local";
  if (el.exitModeButton) el.exitModeButton.hidden = !cfg.supportsModeExit;
  if (el.settingsCurrentMode) el.settingsCurrentMode.textContent = cfg.runMode || "--";
  if (el.settingsExportRunButton) el.settingsExportRunButton.disabled = !nextState.runArchive?.lastRunId;
  if (el.settingsModeHint) {
    el.settingsModeHint.hidden = Boolean(cfg.supportsModeExit);
    el.settingsModeHint.textContent = cfg.supportsModeExit ? "" : "当前浏览器 Web 运行方式不支持返回启动模式选择器。";
  }
  el.httpPort.textContent = `${cfg.bindHost || cfg.host || "127.0.0.1"}:${cfg.httpPort || "--"}`;
  el.apPort.textContent = `${cfg.runMode === "lan-controller" ? cfg.modemHost : (cfg.bindHost || cfg.host || "127.0.0.1")}:${cfg.apModemPort || "--"}`;
  el.enbPort.textContent = `${cfg.bindHost || cfg.host || "127.0.0.1"}:${cfg.enbPort || "--"}`;
  el.managementPort.textContent = cfg.runMode === "lan-controller"
    ? `${cfg.modemHost}:${cfg.managementPort}`
    : cfg.runMode === "lan-modem"
      ? `${cfg.bindHost}:${cfg.managementPort}`
      : "Local";
  el.managementPort.title = cfg.runMode === "local" ? "Local 模式无需独立 Management 通道" : "Management Channel";
  el.apPortInline.textContent = cfg.apModemPort || "--";
  el.enbPortInline.textContent = cfg.enbPort || "--";

  renderLanGuide(nextState);

  const modem = nextState.modem;
  flashValue(el.attachStatus, modem.attachStatus);
  el.attachStatus.dataset.status = modem.attachStatus;
  el.attachHint.textContent = nextState.flow.running
    ? "执行中"
    : modem.lastError
      ? "最近失败"
      : modem.attachStatus === "ATTACHED"
        ? "已附着"
        : modem.attachStatus === "CANCELLED"
          ? "已中断，可检查证据或重新运行"
          : "待机";
  flashValue(el.cellValue, modem.cell?.cellId || "未驻留");
  el.plmnValue.textContent = modem.cell
    ? `PLMN ${modem.cell.plmn} · TAC ${modem.cell.tac}`
    : "PLMN -- · TAC --";
  el.cfunBadge.textContent = `CFUN ${modem.cfun}`;

  const metrics = nextState.metrics;
  flashValue(
    el.metricSuccess,
    `${metrics.attachSuccesses} / ${metrics.attachAttempts}`,
  );
  el.metricFailures.textContent = `失败 ${metrics.attachFailures} · 取消 ${metrics.attachCancelled}`;

  const enb = nextState.enb;
  el.mibBandwidth.textContent = enb.mib.dlBandwidth;
  el.mibSfn.textContent = enb.mib.systemFrameNumber;
  el.mibPhich.textContent = enb.mib.phichConfig;
  el.sibBarred.textContent = String(enb.sib.cellBarred);
  el.sibQrx.textContent = `${enb.sib.qRxLevMin} dBm`;
  el.sibPlmn.textContent = enb.sib.plmn;
  el.sibTac.textContent = enb.sib.trackingAreaCode;

  el.lastError.hidden = !modem.lastError;
  if (modem.lastError) {
    const report = nextState.diagnosis?.lastReport;
    el.lastErrorTitle.textContent = report?.title || "最近失败";
    el.lastErrorText.textContent = report?.summary || modem.lastError;
    el.lastError.title = modem.lastError;
  }

  const security = nextState.security || {};
  const probe = security.coreProbe || {};
  const verified = Boolean(probe.verified);
  el.securityStatusBadge.textContent = verified ? "Security Core 已通过实测" : (probe.loaded ? "Security Core 验证失败" : "后端不可用");
  el.securityStatusBadge.dataset.active = String(verified);
  el.securityBackendValue.textContent = security.backend || "项目内置 Security Core / SRTP Engine";
  if (el.securityLibsrtpValue) el.securityLibsrtpValue.textContent = String(security.implementation?.libsrtpRequired ?? probe.libsrtpRequired ?? "--");
  if (el.securityProtocolImpl) el.securityProtocolImpl.textContent = security.implementation?.protocolLayer || probe.protocolImplementation || "SRTP";
  el.securityBindingVersion.textContent = security.implementation?.cryptoLayer || probe.cryptoPrimitives || probe.runtimeAdapter || "cryptography/OpenSSL 原语";
  el.securityProfileValue.textContent = probe.profile || "AES128_CM_SHA1_80";
  if (el.securityTestBoundary) el.securityTestBoundary.textContent = security.implementation?.testBoundary || "Security Core";
  if (el.securityIntegrationSummary) el.securityIntegrationSummary.textContent = verified ? "PASS" : (probe.error?.detail || probe.status || "FAIL");
  el.securitySessionStatus.textContent = security.active ? "会话已建立" : "会话未建立";
  el.securitySessionStatus.dataset.active = String(Boolean(security.active));
  el.nasCipherValue.textContent = security.nasCipher || "--";
  el.nasIntegrityValue.textContent = security.nasIntegrity || "--";
  el.nasNegotiatedValue.textContent = security.nasNegotiated ? "已协商" : "未协商";
  el.srtpCipherValue.textContent = security.srtpCipher || "--";
  el.srtpAuthValue.textContent = security.srtpAuth || "--";
  el.securityKeyId.textContent = security.keyId || "--";
  el.securityPacketCount.textContent = String(security.packetCount || 0);

  const ueNas = security.nasByteProtection || {};
  const mmeNas = nextState.networkContext?.active?.nasSecurity || {};
  const nasActive = Boolean(ueNas.active || mmeNas.active);
  if (el.nasByteProtectionStatus) {
    el.nasByteProtectionStatus.textContent = nasActive ? "字节保护已接入" : (security.nasNegotiated ? "已协商 · 等待字节证据" : "等待 Attach");
    el.nasByteProtectionStatus.dataset.active = String(nasActive);
  }
  if (el.nasByteAlgorithms) el.nasByteAlgorithms.textContent = `${security.nasIntegrity?.split(" /")[0] || "EIA2"} + ${security.nasCipher?.split(" /")[0] || "EEA2"}`;
  if (el.nasUeCount) el.nasUeCount.textContent = `UL TX ${ueNas.uplinkTxCount ?? "--"} / DL RX ${ueNas.downlinkRxHighest ?? "--"}`;
  if (el.nasMmeCount) el.nasMmeCount.textContent = `DL TX ${mmeNas.downlinkTxCount ?? "--"} / UL RX ${mmeNas.uplinkRxHighest ?? "--"}`;
  const nasEvent = [...(nextState.runtimeEvents || [])].reverse().find((item) => ["NAS_SECURITY_PDU_PROTECTED","NAS_SECURITY_PDU_VERIFIED","NAS_SECURITY_PDU_FAILED"].includes(item.event));
  if (el.nasLastSecurityEvent) {
    if (nasEvent) {
      const dir = nasEvent.direction === "UPLINK" ? "UL" : (nasEvent.direction === "DOWNLINK" ? "DL" : "--");
      el.nasLastSecurityEvent.textContent = `${nasEvent.event === "NAS_SECURITY_PDU_FAILED" ? "校验失败" : "PASS"} · ${dir} COUNT ${nasEvent.count ?? "--"}`;
    } else el.nasLastSecurityEvent.textContent = "尚无";
  }
  if (el.nasLastSecurityMeta) {
    const last = nasEvent || ueNas.last || mmeNas.last || {};
    const mac = last.macHex ? `MAC ${String(last.macHex).slice(0,8)}` : "MAC --";
    const hash = last.protectedPduSha256 || last.protectedSha256;
    el.nasLastSecurityMeta.textContent = `${last.primitive || last.messageKind || "protected NAS PDU"} · ${mac}${hash ? ` · SHA-256 ${String(hash).slice(0,12)}…` : ""}`;
  }

  renderRuntime(nextState);
  renderControlObservability(nextState);
  renderPrimitiveTrace(nextState.taskEvents || nextState.primitiveTrace || []);
  renderTimers(nextState.timers || {});
  renderDiagnosis(nextState.diagnosis || {});
  renderProtocolTrace(
    nextState.protocolTrace || [],
    nextState.traceSummary || {},
  );
  renderPacketTrace(nextState.packetTrace || []);
  renderFlow(nextState.flow);
  renderLogs(nextState.logs || []);
  setBusy(Boolean(nextState.flow.running));
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {}
  if (!response.ok) {
    const error = new Error(
      payload.message || payload.response || `${response.status} ${response.statusText}`,
    );
    error.code = payload.code || null;
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function sendCommand(command) {
  const trimmed = command.trim();
  if (!trimmed) return;
  el.commandFeedback.textContent = `> ${trimmed}\n发送中…`;
  try {
    const result = await api("/api/at-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: trimmed }),
    });
    el.commandFeedback.textContent = `> ${trimmed}\n${result.response}`;
  } catch (error) {
    el.commandFeedback.textContent = `> ${trimmed}\n${error.message}`;
    presentOperationError("AT 指令发送失败", error, {
      targetView: "at",
      impact: "AT 指令未完成，Modem 状态可能没有变化。",
    });
  }
}

async function changeScenario() {
  const scenario = el.scenarioSelect.value;
  const option = el.scenarioSelect.selectedOptions[0];
  el.scenarioDescription.textContent = option?.dataset.description || "";
  try {
    const result = await api("/api/scenario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario }),
    });
    renderState(result.state);
    toast(`场景已切换：${scenario}`, "ok");
  } catch (error) {
    presentOperationError("场景切换失败", error, {
      targetView: "overview",
      impact: "故障注入场景没有切换。",
    });
    if (state) el.scenarioSelect.value = state.scenario.id;
  }
}

async function applyCustomFault(event) {
  event.preventDefault();
  el.customFaultError.hidden = true;
  let value = el.faultMessageInput.value;
  if (el.faultActionInput.value === "MODIFY_FIELD") {
    try { value = parseFaultValue(value, faultFieldTypeName()); }
    catch (error) {
      el.customFaultError.textContent = error.message;
      el.customFaultError.hidden = false;
      el.customFaultError.focus();
      return;
    }
  }
  const payload = {
    enabled:true, stage:el.faultStageInput.value, task:$('#faultTaskInput').value,
    primitive:$('#faultPrimitiveInput').value, layer:$('#faultLayerInput').value,
    fault_type:el.faultActionInput.value, field:String(el.faultFieldInput.value || '').trim(), value,
    delay_ms:Number(el.faultDelayInput.value), timeout_ms:Number($('#faultTimeoutInput').value)
  };
  try {
    const result = await api("/api/custom-fault", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderState(result.state);
    closeCustomFaultDialog();
    toast(`已启用故障：${payload.stage} / ${payload.fault_type}`, "ok");
  } catch (error) {
    el.customFaultError.textContent = `${error.message}。请先确认字段属于左侧“可修改字段”，再按右侧显示的字段类型填写注入值。`;
    el.customFaultError.hidden = false;
    el.customFaultError.focus();
  }
}

async function stopAttachFlow() {
  if (!state?.flow?.running) {
    toast("当前没有正在运行的 Attach 流程", "info");
    return;
  }
  if (!window.confirm("确定中断当前 Attach？已完成步骤、Trace、日志和诊断证据会保留；不会执行 Reset，也不会关闭 CFUN。")) return;
  try {
    const nextState = await api("/api/attach/cancel", { method: "POST" });
    renderState(nextState);
    el.commandFeedback.textContent = "当前 Attach 已安全中断；已完成步骤和运行证据保留，可直接检查后再重跑。";
    toast("当前 Attach 已中断，未执行重置", "ok");
  } catch (error) {
    presentOperationError("中断 Attach 失败", error, { targetView: "debug" });
  }
}

async function resetSimulation() {
  if (
    state?.flow?.running &&
    !window.confirm("Attach 正在运行，确定中止并执行系统重置？当前流程、计时器、Task/Trace 与 Security 运行态会恢复初始值；历史 Run 和诊断记录保留。")
  )
    return;
  try {
    const nextState = await api("/api/reset", { method: "POST" });
    renderState(nextState);
    el.commandFeedback.textContent = "系统运行态已重置；当前事务、计时器、Task/Trace 与 Security 会话已恢复初始状态，历史归档保留。";
    toast("系统重置完成，历史归档已保留", "ok");
  } catch (error) {
    presentOperationError("系统重置失败", error, { targetView: "debug" });
  }
}

async function clearLogs() {
  try {
    await api("/api/logs/clear", { method: "POST" });
    toast("日志已清空", "ok");
  } catch (error) {
    presentOperationError("清空日志失败", error, { targetView: "debug" });
  }
}

function browserDownloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function browserDownloadUrl(url, filename) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
}

async function requestNativeExport(kind, { runId = null, fallback = null } = {}) {
  try {
    const result = await api("/api/export/native", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, runId }),
    });
    if (result.cancelled) {
      toast("已取消导出", "info");
      return false;
    }
    toast(`已保存到 ${result.path}`, "ok");
    return true;
  } catch (error) {
    if ([403, 409].includes(error.status) && typeof fallback === "function") {
      fallback();
      toast("当前环境使用浏览器下载方式导出", "info");
      return true;
    }
    throw error;
  }
}

async function exportLogs() {
  if (!state) return;
  const fallback = () => browserDownloadJson(
    `lte-sim-logs-${new Date().toISOString().replaceAll(":", "-")}.json`,
    { version: state.version, exportedAt: new Date().toISOString(), transactionId: state.flow?.transactionId, logs: state.logs || [] },
  );
  try {
    await requestNativeExport("logs", { fallback });
  } catch (error) {
    presentOperationError("导出日志失败", error, { targetView: "debug" });
  }
}

async function exportTrace() {
  if (!state) return;
  const fallback = () => browserDownloadJson(
    `lte-sim-trace-${new Date().toISOString().replaceAll(":", "-")}.json`,
    { version: state.version, exportedAt: new Date().toISOString(), transactionId: state.flow?.transactionId,
      taskEvents: state.taskEvents || [], runtimeEvents: state.runtimeEvents || [], faultEvidence: state.faultEvidence || [], timers: state.timers || {} },
  );
  try {
    await requestNativeExport("trace", { fallback });
  } catch (error) {
    presentOperationError("导出 Trace 失败", error, { targetView: "tasks" });
  }
}

async function exportDiagnosis() {
  if (!state) return;
  const fallback = () => browserDownloadJson(
    `lte-sim-diagnosis-${new Date().toISOString().replaceAll(":", "-")}.json`,
    { version: state.version, exportedAt: new Date().toISOString(), flow: state.flow || {}, scenario: state.scenario || {},
      diagnosis: state.diagnosis || {}, faultEvidence: state.faultEvidence || [] },
  );
  try {
    await requestNativeExport("diagnosis", { fallback });
  } catch (error) {
    presentOperationError("导出诊断失败", error, { targetView: "debug" });
  }
}

async function exportLastRun() {
  const runId = state?.runArchive?.lastRunId;
  if (!runId) {
    toast("当前没有可导出的已归档 Run", "info");
    return;
  }
  const fallback = () => browserDownloadUrl(`/api/runs/export?run=${encodeURIComponent(runId)}`, `${runId}.zip`);
  try {
    await requestNativeExport("run", { runId, fallback });
  } catch (error) {
    presentOperationError("导出 Run 失败", error, { targetView: "debug" });
  }
}

function securityStageMeta(stage) {
  const meta = {
    "Application Payload": ["应用层明文", "这是业务层准备发送的原始内容。它还没有被加密，后续会被装进 RTP Payload。"],
    "RTP Header / Payload": ["构造 RTP", "程序为 Payload 加上 RTP Header（Sequence、Timestamp、SSRC 等），形成待保护 RTP 包。"],
    "Security Core Protect": ["SRTP Protect", "Security Core 根据 SRTP Session、Packet Index/ROC、AES-128-CM 与 HMAC-SHA1-80 对 RTP 做机密性和认证保护。"],
    "Ciphertext + 80-bit Authentication Tag": ["生成 SRTP 线上的数据", "RTP Payload 被加密，同时附加 80-bit Authentication Tag；接收端后续会校验这个 Tag。"],
    "UDP TX": ["UDP 发送", "发送端通过操作系统 socket.sendto() 将 SRTP bytes 发送到本地接收端端口。"],
    "UDP RX": ["UDP 接收", "接收端通过 socket.recvfrom() 获取 SRTP bytes，并记录 TX/RX 长度、Peer 和 wire match。"],
    "Security Core Verify / Unprotect": ["认证、Replay 检查与解密", "接收端先验证 Authentication Tag / Replay Window，合法包才进入 unprotect；篡改、错误 Key 或 Replay 会在这里被拒绝。"],
    "Recovered Payload": ["恢复应用数据", "只有接收端校验成功，原始 RTP Payload 才会被恢复并交回上层。"],
  };
  return meta[stage] || [stage || "数据包详情", "展示当前 Security 运行记录的数据。"];
}

function securityDetailFacts(packet, stage = "ALL") {
  if (!packet) return [];
  const err = packet.verification?.error;
  const all = [
    ["Packet", packet.index], ["RTP Sequence", packet.rtp?.sequence], ["Timestamp", packet.rtp?.timestamp], ["SSRC", packet.rtp?.ssrc],
    ["RTP Length", packet.rtp?.length != null ? `${packet.rtp.length} bytes` : "--"],
    ["SRTP Profile", packet.srtp?.profile], ["Protected Length", packet.srtp?.protectedPacketLength != null ? `${packet.srtp.protectedPacketLength} bytes` : "--"],
    ["Authentication Tag", packet.srtp?.authenticationTagHex], ["ROC", packet.srtp?.roc],
    ["UDP", `${packet.udp?.sourceIp}:${packet.udp?.sourcePort} → ${packet.udp?.targetIp}:${packet.udp?.targetPort}`],
    ["TX / RX", `${packet.udp?.txBytes ?? "--"} / ${packet.udp?.rxBytes ?? "--"} bytes`], ["Wire Match", packet.udp?.wireBytesMatch],
    ["Receiver", packet.verification?.outcome], ["Error", err ? `${err.code} · ${err.message || err.detail || ""}` : "无"],
    ["Recovered Payload", packet.verification?.recoveredPayload ?? "未释放"],
  ];
  if (stage === "Application Payload") return [["原始 Payload", packet.applicationPayload], ["UTF-8 bytes", new TextEncoder().encode(packet.applicationPayload || "").length]];
  if (stage === "RTP Header / Payload") return [["Sequence", packet.rtp?.sequence], ["Timestamp", packet.rtp?.timestamp], ["SSRC", packet.rtp?.ssrc], ["RTP Header", packet.rtp?.headerHex], ["Payload Hex", packet.rtp?.payloadHex], ["Length", `${packet.rtp?.length ?? "--"} bytes`]];
  if (stage === "Security Core Protect" || stage === "Ciphertext + 80-bit Authentication Tag") return [["Profile", packet.srtp?.profile], ["Ciphertext", packet.srtp?.ciphertextHex], ["Authentication Tag", packet.srtp?.authenticationTagHex], ["Internal IV", packet.srtp?.internalIv], ["ROC", packet.srtp?.roc], ["Protected Length", `${packet.srtp?.protectedPacketLength ?? "--"} bytes`]];
  if (stage === "UDP TX") return [["Source", `${packet.udp?.sourceIp}:${packet.udp?.sourcePort}`], ["Target", `${packet.udp?.targetIp}:${packet.udp?.targetPort}`], ["TX", `${packet.udp?.txBytes ?? "--"} bytes`], ["sendto 时间", packet.udp?.sentAt]];
  if (stage === "UDP RX") return [["Peer", `${packet.udp?.peerIp}:${packet.udp?.peerPort}`], ["RX", `${packet.udp?.rxBytes ?? "--"} bytes`], ["recvfrom 时间", packet.udp?.receivedAt], ["Wire Match", packet.udp?.wireBytesMatch]];
  if (stage === "Security Core Verify / Unprotect") return [["Outcome", packet.verification?.outcome], ["Authentication / Replay", err ? err.code : "PASS"], ["Reason", err?.detail || err?.message || "认证和 Replay 检查通过"], ["Recovered Payload", packet.verification?.recoveredPayload ?? "未释放"]];
  if (stage === "Recovered Payload") return [["Receiver", packet.verification?.outcome], ["Recovered Payload", packet.verification?.recoveredPayload ?? "未释放"], ["与原始 Payload", packet.verification?.recoveredPayload === packet.applicationPayload ? "一致" : "未恢复 / 不一致"]];
  return all;
}

function renderSecurityDetail(packet, stage = "ALL") {
  selectedSecurityPacket = packet || null;
  selectedSecurityStage = stage || "ALL";
  if (!el.securityPacketDetail) return;
  if (!packet) {
    if (el.securityDetailTitle) el.securityDetailTitle.textContent = "链路 / 数据包详情";
    if (el.securityDetailHint) el.securityDetailHint.textContent = "点击左侧链路步骤或 Packet";
    el.securityPacketDetail.textContent = "尚未运行 Security 场景。";
    return;
  }
  const [title, explain] = stage === "ALL" ? ["完整数据包", "汇总展示这一个 Packet 从 RTP 到 Receiver 的关键字段。"] : securityStageMeta(stage);
  if (el.securityDetailTitle) el.securityDetailTitle.textContent = `${title} · Packet ${packet.index}`;
  if (el.securityDetailHint) el.securityDetailHint.textContent = stage === "ALL" ? `Seq ${packet.rtp.sequence}` : `链路步骤：${stage}`;
  const facts = securityDetailFacts(packet, stage);
  el.securityPacketDetail.innerHTML = `<div class="security-detail-explain">${escapeHtml(explain)}</div><dl class="security-detail-facts">${facts.map(([label,value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueText(value))}</dd></div>`).join("")}</dl>`;
}

function selectSecurityPacket(packet, button = null, stage = "ALL") {
  document.querySelectorAll(".security-packet-button").forEach((node) => node.classList.remove("selected"));
  document.querySelectorAll(".security-pipeline-step").forEach((node) => node.classList.remove("selected"));
  if (button) button.classList.add("selected");
  renderSecurityDetail(packet, stage);
}

function renderSecurityPipeline(result) {
  lastSecurityResult = result || null;
  el.securityPipeline.replaceChildren();
  const packets = result.packets || [];
  if (el.securityPipelineSummary) {
    const scenarioTitle = SECURITY_SCENARIO_GUIDE[result?.scenario]?.[0] || result?.scenario || "实际验证";
    el.securityPipelineSummary.textContent = packets.length ? `${scenarioTitle} · ${packets.length} 包 · 4 个阶段` : `${scenarioTitle} · 无可展示数据包`;
  }
  if (!packets.length) {
    el.securityPipeline.innerHTML = '<div class="security-pipeline-empty">本次场景没有生成可查看的数据包。</div>';
    if (el.securityPipelineSummary) el.securityPipelineSummary.textContent = '本次无可查看数据包';
    renderSecurityDetail(null);
    return;
  }

  const packetNav = document.createElement("div");
  packetNav.className = "security-packet-list security-packet-tabs v53-packet-tabs";
  const stepList = document.createElement("div");
  stepList.className = "security-step-list v53-security-steps";
  const stageGroups = [
    { label: "RTP 构造", stages: ["Application Payload", "RTP Header / Payload"], detailStage: "RTP Header / Payload", note: "Payload + RTP Header" },
    { label: "SRTP 保护", stages: ["Security Core Protect", "Ciphertext + 80-bit Authentication Tag"], detailStage: "Security Core Protect", note: "AES-CTR + HMAC" },
    { label: "UDP 传输", stages: ["UDP TX", "UDP RX"], detailStage: "UDP RX", note: "socket.sendto / recvfrom" },
    { label: "接收校验", stages: ["Security Core Verify / Unprotect", "Recovered Payload"], detailStage: "Security Core Verify / Unprotect", note: "Auth / Replay / Recover" },
  ];

  function renderStepsForPacket(packet) {
    stepList.replaceChildren();
    const rawSteps = (result.steps || []).filter((step) => String(step.packet) === String(packet.index));
    stageGroups.forEach((group, stepIndex) => {
      const members = rawSteps.filter((step) => group.stages.includes(step.stage));
      if (!members.length) return;
      const failed = members.find((step) => ["FAIL", "REJECTED"].includes(step.status));
      const representative = failed || members[members.length - 1];
      const row = document.createElement("button");
      row.type = "button";
      row.className = "security-pipeline-step v53-security-step";
      row.dataset.status = representative.status;
      row.dataset.packet = String(packet.index);
      row.dataset.stage = group.detailStage;
      const statusLabels = {PASS:"通过", FAIL:"失败", ACCEPTED:"接受", REJECTED:"拒绝"};
      row.innerHTML = `<span class="security-step-index">${stepIndex + 1}</span><span class="security-step-copy"><strong>${escapeHtml(group.label)}</strong><small>${escapeHtml(group.note)}</small></span><b>${escapeHtml(statusLabels[representative.status] || representative.status)}</b>`;
      row.addEventListener("click", () => {
        stepList.querySelectorAll(".security-pipeline-step").forEach((node) => node.classList.remove("selected"));
        row.classList.add("selected");
        renderSecurityDetail(packet, group.detailStage);
      });
      stepList.append(row);
    });
  }

  packets.forEach((packet, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "security-packet-button v53-packet-button";
    const error = packet.verification?.error;
    const outcome = packet.verification?.outcome || "--";
    button.innerHTML = `<strong>P${index + 1}</strong><span>Seq ${escapeHtml(packet.rtp.sequence)}</span><small>${escapeHtml(error?.code || outcome)}</small>`;
    button.title = `Packet ${packet.index} · Seq ${packet.rtp.sequence} · ${outcome}`;
    button.addEventListener("click", () => {
      packetNav.querySelectorAll(".security-packet-button").forEach((node) => node.classList.remove("selected"));
      button.classList.add("selected");
      renderStepsForPacket(packet);
      renderSecurityDetail(packet, "ALL");
    });
    packetNav.append(button);
    if (index === 0) window.setTimeout(() => button.click(), 0);
  });

  el.securityPipeline.append(packetNav, stepList);
}

function renderReferenceVectors(vectors, target = el.securitySelfTestNav) {
  const groups = [
    ["RFC 3711 B.2", "AES-CM", vectors.rfc3711AesCm],
    ["RFC 3711 B.3", "Key Derivation", vectors.rfc3711KeyDerivation],
    ["RFC 2202", "HMAC-SHA1-80", vectors.hmacSha1_80],
  ];
  groups.forEach(([ref, title, data]) => {
    if (!data || !target) return;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "security-vector-card";
    card.dataset.status = data.ok ? "PASS" : "FAIL";
    card.innerHTML = `<div><span>${escapeHtml(ref)}</span><b>${data.ok ? "PASS" : "FAIL"}</b></div><strong>${escapeHtml(title)}</strong><small>点击查看标准向量 expected / actual</small>`;
    card.addEventListener("click", () => {
      if (el.securityDetailTitle) el.securityDetailTitle.textContent = `${ref} · ${title}`;
      if (el.securityDetailHint) el.securityDetailHint.textContent = "标准向量详细结果";
      const rows = Object.entries(data).filter(([key]) => key !== "ok");
      el.securityPacketDetail.innerHTML = `<div class="security-detail-explain">该项直接使用公开 RFC 标准向量校验密码原语，不依赖 Attach 流程。</div><dl class="security-detail-facts">${rows.map(([key,value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(valueText(value))}</dd></div>`).join("")}</dl>`;
    });
    target.append(card);
  });
}

function renderSecurityLaneDetail(lane) {
  const packet = selectedSecurityPacket || lastSecurityResult?.packets?.[0];
  if (!packet) {
    toast("请先运行一次正常或异常 Security 验证", "error");
    return;
  }
  const stages = {sender:"SRTP Protect", network:"UDP RX", receiver:"Receiver Verification"};
  renderSecurityDetail(packet, stages[lane] || "ALL");
}

function setSecurityAccuracyStatus(node, text, status = "idle") {
  if (!node) return;
  node.textContent = text;
  node.dataset.status = status;
}

function renderSecurityAccuracyMatrix(result = null, udpResult = null) {
  if (result) {
    const standalone = result.standaloneCoreChecks || {};
    const vectors = result.referenceVectors || {};
    const vectorPass = [vectors.rfc3711AesCm?.ok, vectors.rfc3711KeyDerivation?.ok, vectors.hmacSha1_80?.ok].filter(Boolean).length;
    setSecurityAccuracyStatus(el.securityVectorValidation, `${vectorPass}/3 ${vectorPass === 3 ? "PASS" : "FAIL"}`, vectorPass === 3 ? "pass" : "fail");
    const corePass = Number(standalone.passed || 0), coreTotal = Number(standalone.total || 0);
    setSecurityAccuracyStatus(el.securityCoreValidation, `${corePass}/${coreTotal} ${coreTotal && corePass === coreTotal ? "PASS" : "FAIL"}`, coreTotal && corePass === coreTotal ? "pass" : "fail");
    const reference = standalone.optionalReferenceCrosscheck || {};
    if (reference.ok === true) setSecurityAccuracyStatus(el.securityReferenceValidation, "PASS", "pass");
    else if (reference.ok === false) setSecurityAccuracyStatus(el.securityReferenceValidation, "FAIL", "fail");
    else setSecurityAccuracyStatus(el.securityReferenceValidation, "未安装 · 可选", "skip");
  }
  if (udpResult) {
    const scenario = SECURITY_SCENARIO_GUIDE[udpResult.scenario]?.[0] || udpResult.scenario || "UDP";
    setSecurityAccuracyStatus(el.securityUdpValidation, `${scenario} · ${udpResult.ok ? "PASS" : "FAIL"}`, udpResult.ok ? "pass" : "fail");
  }
}

function renderSecuritySelfTestNavigator(result) {
  if (!el.securitySelfTestNav) return;
  el.securitySelfTestNav.hidden = false;
  el.securitySelfTestNav.replaceChildren();
  const title = document.createElement("div");
  title.className = "security-selftest-title";
  title.innerHTML = '<strong>Core 健康检查明细</strong><span>运行时独立检查 + RFC 标准向量；端到端 UDP 场景请使用下方“运行所选验证”。</span>';
  el.securitySelfTestNav.append(title);
  const standalone = result.standaloneCoreChecks || {};
  if (standalone.cases) {
    const coreTitle = document.createElement("div");
    coreTitle.className = "security-selftest-subtitle";
    coreTitle.innerHTML = `<strong>Security Core 独立检查</strong><span>${standalone.passed ?? 0}/${standalone.total ?? 0} 通过 · 不依赖 Web / HTTP / UDP / Attach</span>`;
    el.securitySelfTestNav.append(coreTitle);
    const coreGrid = document.createElement("div");
    coreGrid.className = "security-core-check-grid";
    Object.entries(standalone.cases).forEach(([name, item]) => {
      const card = document.createElement("div");
      card.className = "security-core-check-card";
      card.dataset.status = item.ok ? "PASS" : "FAIL";
      card.innerHTML = `<strong>${escapeHtml(name)}</strong><span>${item.ok ? "PASS" : "FAIL"}</span><small>${escapeHtml(item.detail || "")}</small>`;
      coreGrid.append(card);
    });
    el.securitySelfTestNav.append(coreGrid);
    const reference = standalone.optionalReferenceCrosscheck;
    if (reference) {
      const refCard = document.createElement("div");
      refCard.className = "security-reference-crosscheck";
      refCard.dataset.status = reference.ok === true ? "PASS" : (reference.ok === false ? "FAIL" : "SKIP");
      refCard.innerHTML = `<strong>可选 libSRTP 交叉对照</strong><span>${escapeHtml(reference.status || (reference.available ? "UNKNOWN" : "NOT_INSTALLED"))}</span><small>${escapeHtml(reference.detail || "开发环境安装 pylibsrtp 后，可将同一 key/packet 的结果与参考实现做双向差分。")}</small>`;
      el.securitySelfTestNav.append(refCard);
    }
  }
  const vectors = document.createElement("div");
  vectors.className = "security-vector-grid v53-vector-grid";
  renderReferenceVectors(result.referenceVectors || {}, vectors);
  el.securitySelfTestNav.append(vectors);
}

async function runStandaloneSecurityDemo() {
  if (!el.securityStandaloneDemoButton || !el.securityStandaloneResult) return;
  const payload = el.securityPlaintext?.value?.trim() || "standalone-sdk-demo";
  el.securityStandaloneDemoButton.disabled = true;
  el.securityStandaloneDemoButton.textContent = "后端执行中…";
  el.securityStandaloneResult.innerHTML = '<strong>正在调用 StandaloneSrtpModule</strong><span>本次调用不读取 LTE Attach、Scenario 或 FaultConfig。</span>';
  try {
    const result = await api("/api/security/standalone-demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload, sequence: 321 }),
    });
    const stateInfo = result.state || {};
    el.securityStandaloneResult.innerHTML = `<div class="security-standalone-verdict"><strong>${result.ok ? "独立后端 Demo · PASS" : "独立后端 Demo · FAIL"}</strong><span>Execution ID <code>${escapeHtml(result.executionId || "--")}</code></span></div><dl><div><dt>调用模块</dt><dd>${escapeHtml(result.module || "StandaloneSrtpModule")}</dd></div><div><dt>输入 RTP SHA-256</dt><dd><code>${escapeHtml(String(result.inputSha256 || "").slice(0,24))}…</code></dd></div><div><dt>输出 SRTP SHA-256</dt><dd><code>${escapeHtml(String(result.protectedSha256 || "").slice(0,24))}…</code></dd></div><div><dt>恢复 RTP SHA-256</dt><dd><code>${escapeHtml(String(result.recoveredSha256 || "").slice(0,24))}…</code></dd></div><div><dt>SRTCP / RTCP</dt><dd>${result.srtcpRoundtrip ? "PASS" : "FAIL"} · ${Number(result.rtcpBytes || 0)} B → ${Number(result.srtcpBytes || 0)} B</dd></div><div><dt>SRTP protect / unprotect</dt><dd>${Number(stateInfo.protectCount || 0)} / ${Number(stateInfo.unprotectCount || 0)}</dd></div><div><dt>SRTCP protect / unprotect</dt><dd>${Number(stateInfo.srtcpProtectCount || 0)} / ${Number(stateInfo.srtcpUnprotectCount || 0)}</dd></div><div><dt>会话代际 / re-key</dt><dd>${Number(stateInfo.lifecycle?.generation || 0)} / ${Number(stateInfo.lifecycle?.rekeyCount || 0)}</dd></div><div><dt>读取 Web / Attach / FaultConfig</dt><dd>${result.webStateRead || result.lteAttachStateRead || result.faultConfigRead ? "是" : "否"}</dd></div><div><dt>后端落盘证据</dt><dd><code>${escapeHtml(result.artifactPath || "--")}</code></dd></div></dl><p>SRTP：RTP ${Number(result.rtpBytes || 0)} B → SRTP ${Number(result.srtpBytes || 0)} B，输入与恢复摘要${result.inputSha256 === result.recoveredSha256 ? "一致" : "不一致"}；SRTCP 同时执行 RTCP → SRTCP → RTCP 回环验证。</p>`;
    toast(result.ok ? "独立 SRTP Demo 已在后端执行" : "独立 SRTP Demo 未通过", result.ok ? "ok" : "error");
  } catch (error) {
    el.securityStandaloneResult.innerHTML = `<strong>独立 Demo 执行失败</strong><span>${escapeHtml(error.message)}</span>`;
    presentOperationError("独立 Security Demo 失败", error, { targetView: "security" });
  } finally {
    el.securityStandaloneDemoButton.disabled = false;
    el.securityStandaloneDemoButton.textContent = "运行后端独立 Demo";
  }
}

async function securityProtect(scenario = "NORMAL") {
  const plaintext = el.securityPlaintext.value.trim();
  if (!plaintext) {
    toast("请输入测试载荷", "error");
    return;
  }
  try {
    const result = await api("/api/security/udp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, payload: plaintext }),
    });
    lastSecurityRunId = result.runId;
    el.securityPcapButton.hidden = false;
    if (el.securitySelfTestNav) { el.securitySelfTestNav.hidden = true; el.securitySelfTestNav.replaceChildren(); }
    if (el.securitySelfTestDetails) { el.securitySelfTestDetails.hidden = true; el.securitySelfTestDetails.open = false; }
    renderSecurityPipeline(result);
    renderSecurityAccuracyMatrix(null, result);
    const first = result.packets?.[0];
    const stats = result.statistics || {};
    const scenarioName = result.scenario === "NORMAL" ? "正常传输" : (SECURITY_SCENARIO_GUIDE[result.scenario]?.[0] || result.scenario);
    const accepted = stats.accepted ?? result.accepted ?? 0;
    const rejected = stats.rejected ?? result.rejected ?? 0;
    const outcomeText = result.ok ? "符合预期" : "不符合预期";
    el.securityResult.innerHTML = `<strong>${escapeHtml(scenarioName)} · ${outcomeText}</strong><span>UDP 发送/接收 ${stats.sent ?? 0}/${stats.received ?? 0} · Receiver 接受 ${accepted} / 拒绝 ${rejected}${stats.authenticationFailures ? ` · 认证失败 ${stats.authenticationFailures}` : ""}${stats.replayRejections ? ` · 重放拒绝 ${stats.replayRejections}` : ""}</span><small>后端 Run ID：${escapeHtml(result.runId || "--")} · ${escapeHtml(result.transport || "UDP/socket.sendto+recvfrom")} · ${escapeHtml(result.senderEndpoint || "--")} → ${escapeHtml(result.receiverEndpoint || "--")}</small><small>结果已由后端写入：${escapeHtml(result.runDir ? `${result.runDir}/result.json` : "runs/<runId>/result.json")}；PCAP 同目录保存。</small>${result.error ? `<small>${escapeHtml(`${result.error.code} · ${result.error.message || ""}`)}</small>` : ""}`;
    toast(result.ok ? `${scenario} 验证通过` : `${scenario} 验证失败`, result.ok ? "ok" : "error");
  } catch (error) {
    el.securityResult.textContent = error.message;
    presentOperationError("Security 保护验证失败", error, {
      targetView: "security",
      impact: "本次 Security Lab 数据没有完成保护/恢复验证。",
    });
  }
}

async function securitySelfTest() {
  try {
    const result = await api("/api/security/self-test", { method: "POST" });
    const vectors = result.referenceVectors || {};
    const standalone = result.standaloneCoreChecks || {};
    renderSecuritySelfTestNavigator(result);
    renderSecurityAccuracyMatrix(result, null);
    if (el.securitySelfTestDetails) {
      el.securitySelfTestDetails.hidden = false;
      el.securitySelfTestDetails.open = false;
    }
    const vectorPass = [vectors.rfc3711AesCm?.ok, vectors.rfc3711KeyDerivation?.ok, vectors.hmacSha1_80?.ok].filter(Boolean).length;
    const reference = standalone.optionalReferenceCrosscheck || {};
    const referenceText = reference.ok === true ? "libSRTP 差分 PASS" : (reference.ok === false ? "libSRTP 差分 FAIL" : "libSRTP 差分可选");
    el.securityResult.innerHTML = `<strong>Core 健康检查 · ${result.ok ? "PASS" : "FAIL"}</strong><span>Core 边界/状态 ${standalone.passed ?? 0}/${standalone.total ?? 0} · RFC 标准向量 ${vectorPass}/3 · ${escapeHtml(referenceText)}</span><small>准确性分层验证：协议状态与边界 → RFC known-answer vectors → 可选参考实现差分；真实 Sender/UDP/Receiver 集成由下方端到端场景验证。</small>`;
    toast(result.ok ? "Security Core 健康检查通过" : "Security Core 健康检查失败", result.ok ? "ok" : "error");
  } catch (error) {
    el.securityResult.textContent = error.message;
    presentOperationError("Security Core 健康检查失败", error, { targetView: "security" });
  }
}

function connectEvents() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/events");
  eventSource.onopen = () => {
    el.eventDot.classList.add("connected");
    sseErrorShown = false;
    clearTimeout(sseFailureTimer);
  };
  eventSource.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") renderState(message.payload);
  };
  eventSource.onerror = () => {
    el.eventDot.classList.remove("connected");
    if (!sseErrorShown) {
      toast("事件流断开，正在自动重连", "error");
      sseErrorShown = true;
      clearTimeout(sseFailureTimer);
      sseFailureTimer = setTimeout(() => {
        if (sseErrorShown)
          showFaultDialog(
            operationErrorReport(
              "实时事件流连接中断",
              new Error("浏览器暂时收不到仿真状态推送"),
              {
                impact: "页面状态可能暂时停留在旧值；后端仿真不一定停止。",
                targetView: "debug",
                checks: [
                  "确认 Web 服务仍在运行",
                  "检查网络/端口占用",
                  "等待 EventSource 自动重连",
                ],
                suggestions: [
                  "通常等待自动重连即可",
                  "若持续中断，运行 scripts/windows/run-web.ps1 并保留日志",
                ],
              },
            ),
          );
      }, 3000);
    }
  };
}

el.commandForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendCommand(el.commandInput.value);
});
el.quickActions.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-command]");
  if (!button) return;
  el.commandInput.value = button.dataset.command;
  sendCommand(button.dataset.command);
});
const UI_SCALE_MIN = 0.90;
const UI_SCALE_MAX = 1.35;
const UI_SCALE_STEP = 0.05;
let uiScale = Number(localStorage.getItem("lte-sim-ui-scale") || "1.10");
if (!Number.isFinite(uiScale)) uiScale = 1.10;

function applyUiScale(next, { persist = true } = {}) {
  uiScale = Math.max(UI_SCALE_MIN, Math.min(UI_SCALE_MAX, Math.round(next * 20) / 20));
  document.body.style.zoom = String(uiScale);
  const percent = Math.round(uiScale * 100);
  if (el.uiScaleValue) el.uiScaleValue.textContent = `${percent}%`;
  if (el.uiScaleRange) el.uiScaleRange.value = String(percent);
  if (el.uiScaleDown) el.uiScaleDown.disabled = uiScale <= UI_SCALE_MIN;
  if (el.uiScaleUp) el.uiScaleUp.disabled = uiScale >= UI_SCALE_MAX;
  if (persist) localStorage.setItem("lte-sim-ui-scale", String(uiScale));
}
applyUiScale(uiScale, { persist: false });
el.uiScaleDown?.addEventListener("click", () => applyUiScale(uiScale - UI_SCALE_STEP));
el.uiScaleUp?.addEventListener("click", () => applyUiScale(uiScale + UI_SCALE_STEP));
el.uiScaleRange?.addEventListener("input", () => applyUiScale(Number(el.uiScaleRange.value) / 100));
el.uiScaleReset?.addEventListener("click", () => applyUiScale(1.10));

async function refreshRunsLocation() {
  if (!el.settingsRunsPath) return;
  try {
    const result = await api("/api/runs/location");
    el.settingsRunsPath.textContent = result.path || "--";
    if (el.settingsOpenRunsButton) el.settingsOpenRunsButton.disabled = !result.canOpen;
    if (el.settingsRunsHint) el.settingsRunsHint.textContent = result.canOpen
      ? "点击后由主控电脑本机的文件管理器打开；删除记录后刷新页面即可。"
      : "当前是远程访问，只显示主控端路径；为避免远程触发本机窗口，打开按钮已禁用。";
  } catch (error) {
    el.settingsRunsPath.textContent = "读取失败";
    if (el.settingsOpenRunsButton) el.settingsOpenRunsButton.disabled = true;
    if (el.settingsRunsHint) el.settingsRunsHint.textContent = error.message;
  }
}

async function openRunsFolder() {
  try {
    const result = await api("/api/runs/open-folder", { method: "POST" });
    toast(`已打开 runs 文件夹：${result.path || ""}`, "ok");
  } catch (error) {
    presentOperationError("打开 runs 文件夹失败", error, { targetView: "overview" });
  }
}

function closeSettingsDialog() {
  if (!el.settingsDialog) return;
  if (typeof el.settingsDialog.close === "function") el.settingsDialog.close();
  else el.settingsDialog.removeAttribute("open");
}
el.openSettingsButton?.addEventListener("click", () => {
  if (!el.settingsDialog) return;
  refreshRunsLocation();
  if (typeof el.settingsDialog.showModal === "function") el.settingsDialog.showModal();
  else el.settingsDialog.setAttribute("open", "");
});
el.settingsCloseButton?.addEventListener("click", closeSettingsDialog);
el.settingsDoneButton?.addEventListener("click", closeSettingsDialog);
el.settingsOpenRunsButton?.addEventListener("click", openRunsFolder);
el.settingsExportRunButton?.addEventListener("click", exportLastRun);
el.settingsDialog?.addEventListener("click", (event) => { if (event.target === el.settingsDialog) closeSettingsDialog(); });

el.attachButton.addEventListener("click", () => sendCommand("AT+CFUN=1"));
el.stopAttachButton?.addEventListener("click", stopAttachFlow);
el.detachButton.addEventListener("click", () => sendCommand("AT+CFUN=0"));
el.resetButton.addEventListener("click", resetSimulation);
el.scenarioSelect.addEventListener("change", changeScenario);
el.customFaultForm?.addEventListener("submit", applyCustomFault);
el.faultFieldInput?.addEventListener("input", () => { syncFaultFieldMeta(); syncFaultPreview(); });
el.faultMessageInput?.addEventListener("input", syncFaultPreview);
el.openCustomFaultButton?.addEventListener("click", () => {
  if (!el.customFaultDialog) return;
  syncFaultPreview();
  if (typeof el.customFaultDialog.showModal === "function") el.customFaultDialog.showModal();
  else el.customFaultDialog.setAttribute("open", "");
});
el.runStatsCard?.addEventListener("click", openRunHistoryDialog);
el.runStatsCard?.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openRunHistoryDialog(); } });
el.showFlowGuideButton?.addEventListener("click", openFlowGuideDialog);
el.showFaultParametersButton?.addEventListener("click", openFaultParametersDialog);
el.toolbarFaultState?.addEventListener("click", openFaultParametersDialog);
el.showAtHistoryButton?.addEventListener("click", openAtHistoryDialog);
el.showDiagnosisHistoryButton?.addEventListener("click", openDiagnosisHistoryDialog);
el.infoDialogCloseButton?.addEventListener("click", () => closeDialog(el.infoDialog));
el.infoDialogConfirmButton?.addEventListener("click", () => closeDialog(el.infoDialog));
el.infoDialog?.addEventListener("click", (event) => { if (event.target === el.infoDialog) closeDialog(el.infoDialog); });
function closeCustomFaultDialog() {
  if (!el.customFaultDialog) return;
  if (typeof el.customFaultDialog.close === "function") el.customFaultDialog.close();
  else el.customFaultDialog.removeAttribute("open");
}
el.customFaultCloseButton?.addEventListener("click", closeCustomFaultDialog);
el.customFaultCancelButton?.addEventListener("click", closeCustomFaultDialog);
el.customFaultDialog?.addEventListener("click", (event) => {
  if (event.target === el.customFaultDialog) closeCustomFaultDialog();
});
el.customFaultDisableButton?.addEventListener("click", async () => {
  try {
    const result = await api("/api/scenario", {
      method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({scenario:"NORMAL"}),
    });
    renderState(result.state);
    closeCustomFaultDialog();
    toast("已恢复正常网络，故障注入关闭", "ok");
  } catch (error) { presentOperationError("恢复正常网络失败", error, {targetView:"overview"}); }
});
el.logSearch.addEventListener("input", () => {
  renderSignatures.delete("logs");
  state && renderLogs(state.logs || []);
});
el.logTypeFilter.addEventListener("change", () => {
  try {
    localStorage.setItem("lte-log-type", el.logTypeFilter.value);
  } catch (_) {}
  renderSignatures.delete("logs");
  state && renderLogs(state.logs || []);
});
el.pauseLogsButton.addEventListener("click", () => {
  logsPaused = !logsPaused;
  if (logsPaused) pausedLogs = [...(state?.logs || [])];
  el.pauseLogsButton.textContent = logsPaused ? "继续" : "暂停";
  renderSignatures.delete("logs");
  if (state) renderLogs(state.logs || []);
});
el.exportLogsButton.addEventListener("click", exportLogs);
el.exportTraceButton?.addEventListener("click", exportTrace);
el.exportDiagnosisButton?.addEventListener("click", exportDiagnosis);
el.runSystemCheckButton?.addEventListener("click", runSystemCheck);
el.runBlindDiagnosisButton?.addEventListener("click", runBlindDiagnosis);
el.clearLogsButton.addEventListener("click", clearLogs);
el.srtpScenarioActions?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-srtp-scenario]");
  if (button) securityProtect(button.dataset.srtpScenario);
});
el.securityScenarioRunButton?.addEventListener("click", () => securityProtect(el.srtpScenarioSelect?.value || "NORMAL"));
el.srtpScenarioSelect?.addEventListener("change", renderSecurityScenarioExpectation);
renderSecurityScenarioExpectation();
el.securitySelfTestButton.addEventListener("click", securitySelfTest);
el.securityStandaloneDemoButton?.addEventListener("click", runStandaloneSecurityDemo);
document.querySelectorAll("[data-security-lane]").forEach((button) => button.addEventListener("click", () => renderSecurityLaneDetail(button.dataset.securityLane)));
el.exitModeButton?.addEventListener("click", async () => {
  if (!window.confirm("退出当前模式并返回模式选择界面？本次运行中的 Attach/日志会结束。")) return;
  el.exitModeButton.disabled = true;
  closeSettingsDialog();
  try {
    await api("/api/mode/exit", { method: "POST" });
    toast("正在退出当前模式…", "ok");
  } catch (error) {
    el.exitModeButton.disabled = false;
    presentOperationError("退出当前模式失败", error, { targetView: "overview" });
  }
});
el.securityPcapButton?.addEventListener("click", async () => {
  if (!lastSecurityRunId) return;
  const fallback = () => browserDownloadUrl(`/api/security/pcap?run=${encodeURIComponent(lastSecurityRunId)}`, `${lastSecurityRunId}.pcap`);
  try {
    await requestNativeExport("pcap", { runId: lastSecurityRunId, fallback });
  } catch (error) {
    presentOperationError("导出 PCAP 失败", error, { targetView: "security" });
  }
});

async function testLanFromWorkspace() {
  if (!el.lanTestButton) return;
  el.lanTestButton.disabled = true;
  try {
    const result = await api("/api/lan/test", { method: "POST" });
    const check = result.check || {};
    el.lanAgentStatus.textContent = check.agent?.status || "--";
    el.lanApStatus.textContent = check.apModem?.status || "--";
    el.lanEnbStatus.textContent = check.modemEnb?.status || "--";
    el.lanManagementStatus.textContent = check.management?.status || "--";
    el.lanHeartbeat.textContent = check.heartbeat?.lastUpdated ? formatTime(check.heartbeat.lastUpdated) : "--";
    const issues = check.issues || [];
    el.lanLastError.hidden = check.ok;
    el.lanLastError.textContent = check.ok
      ? ""
      : issues.map((item) => `${item.code}: ${item.message}；建议：${item.advice}`).join("\n");
    toast(check.ok ? "LAN 连接测试通过" : "LAN 连接测试未通过", check.ok ? "ok" : "error");
  } catch (error) {
    el.lanLastError.hidden = false;
    el.lanLastError.textContent = `测试连接失败：${error.message}`;
    toast("LAN 连接测试失败", "error");
  } finally {
    el.lanTestButton.disabled = false;
  }
}
el.lanTestButton?.addEventListener("click", testLanFromWorkspace);

api("/api/state")
  .then((initial) => {
    renderState(initial);
    connectEvents();
  })
  .catch((error) => {
    el.commandFeedback.textContent = `初始化失败：${error.message}`;
    presentOperationError("页面初始化失败", error, {
      targetView: "debug",
      impact: "Dashboard 无法读取后端状态。",
    });
  });

el.lastErrorAction?.addEventListener("click", () => {
  const report = state?.diagnosis?.lastReport;
  if (report) showFaultDialog(report);
  else switchWorkspace("debug");
});
el.faultCloseButton?.addEventListener("click", closeFaultDialog);
el.faultDialog?.addEventListener("click", (event) => {
  if (event.target === el.faultDialog) closeFaultDialog();
});
el.faultDebugButton?.addEventListener("click", () => {
  closeFaultDialog();
  switchWorkspace("debug");
});
el.faultTargetButton?.addEventListener("click", () => {
  const target = activeFaultReport?.targetView || "debug";
  closeFaultDialog();
  if (target === "tasks") goFailureTrace(); else switchWorkspace(target);
});
el.faultCopyButton?.addEventListener("click", async () => {
  if (!activeFaultReport) return;
  try {
    await navigator.clipboard.writeText(diagnosisText(activeFaultReport));
    toast("诊断信息已复制", "ok");
  } catch (_) {
    toast("复制失败，请展开技术信息手动复制", "error");
  }
});

// Workspace navigation: keep one functional surface visible at a time.

const workspaceTabs = [...document.querySelectorAll(".workspace-tab")];
const workspacePanels = [...document.querySelectorAll("[data-view-panel]")];
function switchWorkspace(view) {
  const valid = workspacePanels.some(
    (panel) => panel.dataset.viewPanel === view,
  )
    ? view
    : "overview";
  workspaceTabs.forEach((tab) => {
    const active = tab.dataset.view === valid;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
    tab.tabIndex = active ? 0 : -1;
  });
  workspacePanels.forEach((panel) => {
    const active = panel.dataset.viewPanel === valid;
    panel.classList.toggle("active", active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  });
  try {
    localStorage.setItem("lte-workspace-view", valid);
  } catch (_) {}
  if (location.hash !== `#${valid}`)
    history.replaceState(null, "", `#${valid}`);
}
workspaceTabs.forEach((tab) =>
  tab.addEventListener("click", () => switchWorkspace(tab.dataset.view)),
);
workspaceTabs.forEach((tab, index) =>
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let target = index;
    if (event.key === "ArrowLeft")
      target = (index - 1 + workspaceTabs.length) % workspaceTabs.length;
    if (event.key === "ArrowRight") target = (index + 1) % workspaceTabs.length;
    if (event.key === "Home") target = 0;
    if (event.key === "End") target = workspaceTabs.length - 1;
    switchWorkspace(workspaceTabs[target].dataset.view);
    workspaceTabs[target].focus();
  }),
);

// Compact navigation: keyboard first, mouse friendly.
const workspaceOrder = ["overview", "at", "tasks", "security", "debug"];
document.querySelectorAll(".metric-card[data-target-view]").forEach((card) => {
  const go = () => switchWorkspace(card.dataset.targetView);
  card.addEventListener("click", go);
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      go();
    }
  });
});
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && ["+", "=", "-", "0"].includes(event.key)) {
    event.preventDefault();
    if (event.key === "-") applyUiScale(uiScale - UI_SCALE_STEP);
    else if (event.key === "0") applyUiScale(1.10);
    else applyUiScale(uiScale + UI_SCALE_STEP);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.altKey && /^[1-5]$/.test(event.key)) {
    event.preventDefault();
    switchWorkspace(workspaceOrder[Number(event.key) - 1]);
    return;
  }
  if (event.ctrlKey && event.key === "Enter") {
    event.preventDefault();
    if (!state?.flow?.running) sendCommand("AT+CFUN=1");
    return;
  }
  if (event.altKey && event.key === "0") {
    event.preventDefault();
    sendCommand("AT+CFUN=0");
    return;
  }
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(
    document.activeElement?.tagName,
  );
  if (event.key === "/" && !typing) {
    event.preventDefault();
    switchWorkspace("at");
    el.commandInput.focus();
    el.commandInput.select();
  }
});
try {
  const savedType = localStorage.getItem("lte-log-type");
  if (savedType) el.logTypeFilter.value = savedType;
} catch (_) {}
const initialWorkspace =
  location.hash.slice(1) ||
  (() => {
    try {
      return localStorage.getItem("lte-workspace-view");
    } catch (_) {
      return null;
    }
  })() ||
  "overview";
switchWorkspace(initialWorkspace);
window.addEventListener("hashchange", () =>
  switchWorkspace(location.hash.slice(1)),
);

function evidenceMatchesCorrelation(row, corr) {
  return !corr || row?.correlation_id === corr || row?.correlationId === corr;
}

function renderEvidence(corr = traceCorrelation(selectedTraceItem)) {
  if (!state) return;
  const faultRoot = $("#faultEvidenceDetails");
  const timelineRoot = $("#correlationEvents");
  if (!faultRoot || !timelineRoot) return;
  const faults = (state.faultEvidence || []).filter((row) => evidenceMatchesCorrelation(row, corr)).slice(-4).reverse();
  faultRoot.innerHTML = faults.length ? `<h3>故障证据</h3>${faults.map((row) => `
    <article class="trace-evidence-card">
      <div><strong>${escapeHtml(row.fault_label || row.fault_type || "FAULT")}</strong><span>${escapeHtml(row.target_step_label || row.target_step || "--")}</span></div>
      <p>${escapeHtml(row.primitive || "--")}${row.field ? ` · ${escapeHtml(row.field)}` : ""}</p>
      <small>${escapeHtml(valueText(row.before ?? row.expected))} → ${escapeHtml(valueText(row.after ?? row.actual))}</small>
      <em>${escapeHtml(row.root_cause || row.final_effect || "已注入，等待运行结果")}</em>
    </article>`).join("")}` : '<h3>故障证据</h3><p class="muted-copy">当前流程没有故障注入。</p>';
  const events = (state.runtimeEvents || []).filter((row) => evidenceMatchesCorrelation(row, corr)).slice(-8);
  const eventLabels = {
    FAULT_INJECTED:"故障已注入", PRIMITIVE_CREATED:"原语已创建", PRIMITIVE_CONSUMED:"目标 Task 已消费",
    VALIDATION_FAILED:"参数校验失败", TIMER_STARTED:"开始等待", TIMER_EXPIRED:"等待超时",
    SOCKET_TX:"Socket 已发送", SOCKET_RX:"Socket 已接收", SOCKET_DROP:"Socket 消息被丢弃",
    SOCKET_TIMEOUT:"Socket 等待超时", SOCKET_ERROR:"Socket 错误", STATE_TRANSITION:"状态已推进",
    PROCEDURE_TIMER_STARTED:"过程计时器启动"
  };
  timelineRoot.innerHTML = events.length ? `<h3>同一流程的关键时间线</h3>${events.map((row) => `
    <div class="correlation-event"><time>${formatTime(row.time)}</time><strong>${escapeHtml(eventLabels[row.event] || row.event || "事件")}</strong><span>${escapeHtml(row.primitive || row.timer_label || row.timer || row.waiting_primitive || "")}</span></div>`).join("")}` : '<h3>同一流程的关键时间线</h3><p class="muted-copy">选择一条原语后显示相关事件。</p>';
}

function goFailureTrace() {
  closeFaultDialog();
  traceFocusCorrelation = state?.diagnosis?.lastReport?.correlation_id || "";
  switchWorkspace("tasks");
  renderSignatures.delete("primitive");
  renderPrimitiveTrace(state?.taskEvents || state?.primitiveTrace || []);
  if (!lastRenderedTraceRows.length) renderTraceDetail(null);
}

$("#goFailureTrace")?.addEventListener("click", goFailureTrace);
$("#goFailureDiagnosis")?.addEventListener("click", () => switchWorkspace("debug"));
$("#faultLayerInput")?.addEventListener("change", syncFaultFields);
el.faultStageInput?.addEventListener("change", syncFaultFields);
el.faultActionInput?.addEventListener("change", syncFaultFields);
el.faultFieldInput?.addEventListener("change", syncFaultPreview);
el.faultMessageInput?.addEventListener("input", syncFaultPreview);
el.faultDelayInput?.addEventListener("input", syncFaultPreview);
$("#faultTimeoutInput")?.addEventListener("input", syncFaultPreview);
el.traceViewMode?.addEventListener("change", () => { traceFocusCorrelation = ""; renderSignatures.delete("primitive"); renderPrimitiveTrace(state?.taskEvents || state?.primitiveTrace || []); });
$("#filterTask")?.addEventListener("change", () => { traceFocusCorrelation = ""; renderSignatures.delete("primitive"); renderPrimitiveTrace(state?.taskEvents || state?.primitiveTrace || []); });
$("#filterPrimitive")?.addEventListener("input", () => { traceFocusCorrelation = ""; renderSignatures.delete("primitive"); renderPrimitiveTrace(state?.taskEvents || state?.primitiveTrace || []); });
el.filterFaultOnly?.addEventListener("change", () => { traceFocusCorrelation = ""; renderSignatures.delete("primitive"); renderPrimitiveTrace(state?.taskEvents || state?.primitiveTrace || []); });
$("#clearTraceFilters")?.addEventListener("click", () => {
  if (el.traceViewMode) el.traceViewMode.value = "key";
  $("#filterTask").value = "";
  $("#filterPrimitive").value = "";
  if (el.filterFaultOnly) el.filterFaultOnly.checked = false;
  traceFocusCorrelation = "";
  renderSignatures.delete("primitive");
  renderPrimitiveTrace(state?.taskEvents || state?.primitiveTrace || []);
  renderTraceDetail(null);
});

el.primitiveTraceBody?.addEventListener("click", (event) => {
  const row = event.target.closest("[data-trace-index]");
  if (!row) return;
  renderTraceDetail(lastRenderedTraceRows[Number(row.dataset.traceIndex)] || null);
});
el.primitiveTraceBody?.addEventListener("keydown", (event) => {
  if (!["Enter", " "].includes(event.key)) return;
  const row = event.target.closest("[data-trace-index]");
  if (!row) return;
  event.preventDefault();
  renderTraceDetail(lastRenderedTraceRows[Number(row.dataset.traceIndex)] || null);
});

document.addEventListener("click", (event) => {
  const step = event.target.closest(".flow-steps [data-step-key]");
  if (!step) return;
  if (step.matches("[data-failure-step]") && state?.diagnosis?.lastReport) showFaultDialog(state.diagnosis.lastReport);
  else openFlowStepDialog(step.dataset.stepKey);
});
document.addEventListener("keydown", (event) => {
  const step = event.target.closest?.(".flow-steps [data-step-key]");
  if (!step || !["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  if (step.matches("[data-failure-step]") && state?.diagnosis?.lastReport) showFaultDialog(state.diagnosis.lastReport);
  else openFlowStepDialog(step.dataset.stepKey);
});
