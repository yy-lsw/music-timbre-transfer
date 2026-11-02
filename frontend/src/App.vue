<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-content">
        <h1>DSP 音频变声器</h1>
        <p class="subtitle">
          Phase Vocoder + EQ + Dynamics + Reverb | 本地实时处理，无需训练
        </p>
      </div>
    </el-header>

    <el-main class="app-main">
      <el-row :gutter="24">
        <el-col :xs="24" :md="14">
          <el-card shadow="hover">
            <template #header>
              <span>音频转换</span>
            </template>

            <AudioUpload ref="uploadRef" @file-selected="onFileSelected" />

            <StyleSelector
              @style-selected="onStyleSelected"
              @pitch-change="onPitchChange"
              @intensity-change="onIntensityChange"
            />

            <el-divider content-position="left">智能变声（Seed-VC）</el-divider>

            <div v-if="neuralState === 'available'" class="neural-panel">
              <el-switch v-model="neuralMode" active-text="启用神经变声" />
              <div v-if="neuralMode" class="neural-options">
                <el-radio-group v-model="referenceChoice" size="small">
                  <el-radio-button label="female">内置女声参考</el-radio-button>
                  <el-radio-button label="male">内置男声参考</el-radio-button>
                  <el-radio-button label="upload">上传参考音频</el-radio-button>
                </el-radio-group>
                <el-upload
                  v-if="referenceChoice === 'upload'"
                  ref="referenceUploadRef"
                  :auto-upload="false"
                  :limit="1"
                  :on-change="onReferenceChange"
                  accept=".mp3,.wav,.flac,.ogg"
                >
                  <el-button size="small">选择参考音频</el-button>
                </el-upload>
              </div>
            </div>
            <el-alert
              v-else-if="neuralState === 'unavailable'"
              title="智能变声当前不可用"
              :description="neuralHint"
              type="warning"
              :closable="false"
              show-icon
            />

            <el-divider content-position="left">实时变声（变声器）</el-divider>
            <div v-if="realtimeAvailable" class="realtime-panel">
              <el-radio-group v-model="realtimePreset" size="small">
                <el-radio-button
                  v-for="(preset, key) in realtimePresets"
                  :key="key"
                  :label="key"
                >
                  {{ preset.label }}
                </el-radio-button>
              </el-radio-group>
              <el-button
                :type="realtimeActive ? 'danger' : 'success'"
                size="small"
                style="margin-left: 10px"
                @click="toggleRealtime"
              >
                {{ realtimeActive ? "停止实时变声" : "开始实时变声" }}
              </el-button>
              <div v-if="realtimeActive" class="realtime-hint">
                实时变声已开启，请对着麦克风说话，声音会从扬声器/耳机实时输出。
              </div>
            </div>
            <el-alert
              v-else
              title="实时变声不可用"
              description="需要 sounddevice 库：在项目根目录运行 pip install sounddevice 后重启后端。"
              type="info"
              :closable="false"
              show-icon
            />

            <ControlPanel
              :can-start="!!selectedFile && !isRunning"
              :is-running="isRunning"
              :has-result="!!resultData"
              @start="onStartConvert"
              @cancel="onCancel"
              @reset="onReset"
            />

            <ProgressDisplay
              :visible="showProgress"
              :progress="progress"
              :status="taskStatus"
              :message="statusMessage"
              :is-running="isRunning"
            />

            <div v-if="resultData" class="result-area">
              <el-alert
                title="转换完成"
                :description="`风格: ${resultData.style} | 处理耗时: ${resultData.total_time_sec}s | RTF: ${resultData.rtf}`"
                type="success"
                show-icon
                :closable="false"
              />
              <div class="result-actions">
                <el-button type="primary" @click="downloadResult()">
                  下载转换结果
                </el-button>
                <el-button @click="showReport = true">
                  查看运行统计
                </el-button>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="10">
          <el-card shadow="hover" class="preview-card">
            <template #header><span>音频预览</span></template>
            <AudioPlayer
              v-if="originalAudioUrl"
              :src="originalAudioUrl"
              label="原始音频"
            />
            <AudioPlayer
              v-if="resultAudioUrl"
              :src="resultAudioUrl"
              label="转换结果"
            />
            <el-empty
              v-if="!originalAudioUrl && !resultAudioUrl"
              description="上传音频并完成转换后可在此预览"
              :image-size="80"
            />
          </el-card>

          <el-card shadow="hover">
            <template #header><span>转换历史</span></template>
            <HistoryPanel ref="historyRef" @download="downloadResult" />
          </el-card>
        </el-col>
      </el-row>
    </el-main>

    <el-dialog v-model="showReport" title="本机运行统计" width="620px">
      <template v-if="reportData">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item
            v-for="metric in reportData.metrics"
            :key="metric.name"
            :label="metric.name"
          >
            {{ metric.value }}
            <el-tag
              v-if="metric.target && metric.target !== '-'"
              size="small"
              type="info"
              style="margin-left: 4px"
            >
              {{ metric.target }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <p class="report-conclusion">{{ reportData.conclusion }}</p>
      </template>
    </el-dialog>

    <el-footer class="app-footer">
      <span>DSP Audio Effects | Python + Vue，所有处理均在本机完成</span>
    </el-footer>
  </el-container>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import AudioUpload from "./components/AudioUpload.vue";
import StyleSelector from "./components/StyleSelector.vue";
import ControlPanel from "./components/ControlPanel.vue";
import ProgressDisplay from "./components/ProgressDisplay.vue";
import AudioPlayer from "./components/AudioPlayer.vue";
import HistoryPanel from "./components/HistoryPanel.vue";
import {
  cancelTask,
  getDownloadUrl,
  getNeuralStatus,
  getRealtimeStatus,
  getReport,
  getTaskStatus,
  startConvert,
  startNeuralConvert,
  startRealtime,
  stopRealtime,
  uploadAudio,
} from "./api";

const selectedFile = ref(null);
const selectedStyle = ref("hifi");
const pitchSemitones = ref(0);
const intensity = ref(1.0);
const isRunning = ref(false);
const showProgress = ref(false);
const progress = ref(0);
const taskStatus = ref("");
const statusMessage = ref("");
const resultData = ref(null);
const resultAudioUrl = ref("");
const originalAudioUrl = ref("");
const showReport = ref(false);
const reportData = ref(null);
const historyRef = ref(null);
const uploadRef = ref(null);
const referenceUploadRef = ref(null);
const neuralMode = ref(false);
const neuralState = ref("unknown");
const neuralHint = ref("");
const referenceChoice = ref("female");
const referenceFile = ref(null);
const taskIdRef = ref(null);
const realtimeAvailable = ref(false);
const realtimeActive = ref(false);
const realtimePreset = ref("female");
const realtimePresets = ref({});
let pollingTimer = null;

function onFileSelected(file) {
  if (originalAudioUrl.value) {
    URL.revokeObjectURL(originalAudioUrl.value);
  }
  selectedFile.value = file;
  resultData.value = null;
  resultAudioUrl.value = "";
  showProgress.value = false;
  originalAudioUrl.value = file ? URL.createObjectURL(file) : "";
}

function onStyleSelected(style) {
  selectedStyle.value = style;
}

function onPitchChange(value) {
  pitchSemitones.value = Number(value);
}

function onIntensityChange(value) {
  intensity.value = Number(value);
}

function onReferenceChange(file) {
  referenceFile.value = file.raw || null;
}

onMounted(async () => {
  try {
    const { data } = await getNeuralStatus();
    if (data.available) {
      neuralState.value = "available";
    } else {
      neuralState.value = "unavailable";
      neuralHint.value = data.hint || "Seed-VC 未就绪，请先完成安装。";
    }
  } catch (error) {
    neuralState.value = "unavailable";
    neuralHint.value =
      "连不上后端服务（端口 5000）。请先运行 start.bat 启动后端，再刷新本页面。";
  }

  try {
    const { data } = await getRealtimeStatus();
    realtimeAvailable.value = !!data.available;
    realtimeActive.value = !!data.active;
    realtimePreset.value = data.preset || "female";
    realtimePresets.value = data.presets || {};
  } catch (error) {
    realtimeAvailable.value = false;
  }
});

async function toggleRealtime() {
  if (realtimeActive.value) {
    try {
      await stopRealtime();
      realtimeActive.value = false;
    } catch (error) {
      console.error(error);
    }
    return;
  }
  try {
    await startRealtime({ preset: realtimePreset.value });
    realtimeActive.value = true;
  } catch (error) {
    console.error(error);
    ElMessage.error(
      "实时变声启动失败: " + (error.response?.data?.error || error.message)
    );
  }
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

async function onStartConvert() {
  if (!selectedFile.value || isRunning.value) return;

  isRunning.value = true;
  showProgress.value = true;
  progress.value = 0;
  taskStatus.value = "processing";
  statusMessage.value = "上传文件中...";

  try {
    const uploadResponse = await uploadAudio(selectedFile.value);
    const fileId = uploadResponse.data.file_id;

    let convertResponse;
    if (neuralMode.value) {
      if (referenceChoice.value === "upload" && !referenceFile.value) {
        throw new Error("请先选择参考音频");
      }
      const payload = {};
      if (referenceChoice.value === "upload") {
        statusMessage.value = "上传参考音频...";
        const refUpload = await uploadAudio(referenceFile.value);
        payload.reference_file_id = refUpload.data.file_id;
      } else {
        payload.reference_key = referenceChoice.value;
      }
      statusMessage.value = "启动神经变声任务...";
      convertResponse = await startNeuralConvert(fileId, payload);
    } else {
      statusMessage.value = "启动转换任务...";
      convertResponse = await startConvert(fileId, selectedStyle.value, {
        intensity: intensity.value,
        pitch_semitones: pitchSemitones.value,
      });
    }
    taskIdRef.value = convertResponse.data.task_id;

    pollingTimer = setInterval(async () => {
      try {
        const { data } = await getTaskStatus(taskIdRef.value);
        progress.value = data.progress || 0;
        taskStatus.value = data.status;
        statusMessage.value = data.message || "";

        if (data.status === "completed") {
          stopPolling();
          isRunning.value = false;
          resultData.value = data.result;
          resultAudioUrl.value = getDownloadUrl(data.output_file);
          await nextTick();
          historyRef.value?.fetchHistory();
        } else if (data.status === "error" || data.status === "cancelled") {
          stopPolling();
          isRunning.value = false;
        }
      } catch (error) {
        console.warn("轮询失败:", error.message);
      }
    }, 500);
  } catch (error) {
    stopPolling();
    isRunning.value = false;
    showProgress.value = false;
    taskStatus.value = "error";
    statusMessage.value =
      "错误: " + (error.response?.data?.error || error.message);
  }
}

async function onCancel() {
  if (taskIdRef.value) {
    cancelTask(taskIdRef.value).catch(() => {});
  }
  stopPolling();
  isRunning.value = false;
  showProgress.value = false;
  statusMessage.value = "已取消";
}

function onReset() {
  stopPolling();
  isRunning.value = false;
  showProgress.value = false;
  resultData.value = null;
  resultAudioUrl.value = "";
  progress.value = 0;
  selectedFile.value = null;
  taskStatus.value = "";
  statusMessage.value = "";
  if (originalAudioUrl.value) {
    URL.revokeObjectURL(originalAudioUrl.value);
    originalAudioUrl.value = "";
  }
  uploadRef.value?.clearFiles();
  referenceFile.value = null;
  referenceUploadRef.value?.clearFiles();
}

function downloadResult(filename) {
  const target = filename || resultData.value?.output_file;
  if (target) {
    window.open(getDownloadUrl(target), "_blank");
  }
}

watch(showReport, async (open) => {
  if (!open) return;
  reportData.value = null;
  try {
    const { data } = await getReport();
    reportData.value = data;
  } catch (error) {
    console.warn("获取运行统计失败:", error.message);
  }
});

onBeforeUnmount(() => {
  stopPolling();
  if (originalAudioUrl.value) {
    URL.revokeObjectURL(originalAudioUrl.value);
  }
});
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  background: #f4f6f8;
  color: #1f2933;
}

.app-container {
  min-height: 100vh;
}

.app-header {
  background: linear-gradient(135deg, #0f172a 0%, #0f766e 100%);
  color: #fff;
  padding: 22px 24px;
  height: auto !important;
}

.app-header h1 {
  margin: 0;
  font-size: 24px;
}

.subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  opacity: 0.82;
}

.app-main {
  max-width: 1180px;
  margin: 20px auto;
  padding: 0 16px;
}

.preview-card {
  margin-bottom: 16px;
}

.result-area {
  margin-top: 16px;
}

.result-actions {
  margin-top: 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.neural-panel {
  margin-bottom: 8px;
}

.neural-options {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.realtime-panel {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.realtime-hint {
  width: 100%;
  margin-top: 4px;
  color: #67c23a;
  font-size: 13px;
}

.report-conclusion {
  margin: 14px 0 0;
  color: #0f766e;
  font-size: 13px;
}

.app-footer {
  text-align: center;
  padding: 16px;
  color: #7b8794;
  font-size: 13px;
}

@media (max-width: 768px) {
  .app-header h1 {
    font-size: 20px;
  }

  .app-main {
    margin: 10px auto;
    padding: 0 8px;
  }
}
</style>
