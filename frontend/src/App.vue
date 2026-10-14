<template>
  <el-container class="app-container">
    <!-- 顶部 Header（对应论文 4.1节：系统主界面） -->
    <el-header class="app-header">
      <div class="header-content">
        <h1>轻量化音乐质感转换系统</h1>
        <p class="subtitle">
          Lightweight Music Timbre Transfer | 作者: 余毅 |
          基于 MobileNetV3 + CBAM + CycleGAN
        </p>
        <el-divider />
      </div>
    </el-header>

    <!-- 主体内容 -->
    <el-main class="app-main">
      <el-row :gutter="24">
        <!-- 左侧：操作区 -->
        <el-col :xs="24" :md="14">
          <el-card shadow="hover">
            <template #header>
              <span>音频转换</span>
            </template>

            <!-- 1. 上传 -->
            <AudioUpload @file-selected="onFileSelected" />

            <!-- 2. 风格选择 -->
            <StyleSelector @style-selected="onStyleSelected" />

            <!-- 3. 控制按钮 -->
            <ControlPanel
              :can-start="!!selectedFile && !isRunning"
              :is-running="isRunning"
              :has-result="!!resultData"
              @start="onStartConvert"
              @pause="onPause"
              @reset="onReset"
            />

            <!-- 4. 进度条 -->
            <ProgressDisplay
              :visible="showProgress"
              :progress="progress"
              :status="taskStatus"
              :message="statusMessage"
              :frame="currentFrame"
              :latency-ms="currentLatency"
              :is-running="isRunning"
            />

            <!-- 5. 完成提示 & 下载 & 性能报告 -->
            <div v-if="resultData" class="result-area">
              <el-alert
                title="转换完成!"
                :description="`风格: ${resultData.style} | 耗时: ${resultData.total_time_sec}s | 时延: ${resultData.avg_latency_ms}ms`"
                type="success"
                show-icon
                :closable="false"
              />
              <div class="result-actions">
                <el-button type="primary" @click="downloadResult">
                  下载转换结果 (WAV)
                </el-button>
                <el-button type="info" @click="showReport = true">
                  查看性能报告
                </el-button>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：播放 & 报告区 -->
        <el-col :xs="24" :md="10">
          <!-- 音频播放 -->
          <el-card shadow="hover" style="margin-bottom: 16px">
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
            <el-empty v-if="!originalAudioUrl && !resultAudioUrl"
              description="上传音频并完成转换后可在此预览"
              :image-size="80" />
          </el-card>

          <!-- 转换历史 -->
          <el-card shadow="hover">
            <template #header><span>转换历史</span></template>
            <HistoryPanel ref="historyRef" @download="downloadResult" />
          </el-card>
        </el-col>
      </el-row>
    </el-main>

    <!-- 性能报告弹窗（对应论文 第5章） -->
    <el-dialog v-model="showReport" title="性能测试报告" width="600px">
      <template v-if="reportData">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item
            v-for="m in reportData.metrics" :key="m.name"
            :label="m.name">
            {{ m.value }}
            <el-tag size="small" type="success" style="margin-left: 4px">
              {{ m.target }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <h4>与基线模型对比</h4>
        <el-table :data="reportData.baseline_comparison" size="small" stripe>
          <el-table-column prop="method" label="方法" />
          <el-table-column prop="size" label="模型体积" />
          <el-table-column prop="accuracy" label="准确率" />
          <el-table-column prop="latency" label="帧时延" />
        </el-table>
        <p style="margin-top: 12px; color: #67c23a; font-weight: 600;">
          {{ reportData.conclusion }}
        </p>
      </template>
    </el-dialog>

    <!-- 页脚 -->
    <el-footer class="app-footer">
      <span>基于深度学习的轻量化音乐质感转换系统 &copy; 余毅 毕业设计作品</span>
    </el-footer>
  </el-container>
</template>

<script setup>
import { ref, nextTick } from "vue";
import AudioUpload from "./components/AudioUpload.vue";
import StyleSelector from "./components/StyleSelector.vue";
import ControlPanel from "./components/ControlPanel.vue";
import ProgressDisplay from "./components/ProgressDisplay.vue";
import AudioPlayer from "./components/AudioPlayer.vue";
import HistoryPanel from "./components/HistoryPanel.vue";
import {
  uploadAudio, startConvert, getTaskStatus, getDownloadUrl, getReport
} from "./api";

// ---- 状态 ----
const selectedFile = ref(null);
const selectedStyle = ref("hifi");
const isRunning = ref(false);
const showProgress = ref(false);
const progress = ref(0);
const taskStatus = ref("");
const statusMessage = ref("");
const currentFrame = ref(0);
const currentLatency = ref(0);
const resultData = ref(null);
const resultAudioUrl = ref("");
const originalAudioUrl = ref("");
const showReport = ref(false);
const reportData = ref(null);
const historyRef = ref(null);
let pollingTimer = null;

// ---- 事件处理 ----
function onFileSelected(file) {
  selectedFile.value = file;
  resultData.value = null;
  resultAudioUrl.value = "";
  showProgress.value = false;
  if (file) {
    originalAudioUrl.value = URL.createObjectURL(file);
  } else {
    originalAudioUrl.value = "";
  }
}

function onStyleSelected(style) {
  selectedStyle.value = style;
}

async function onStartConvert() {
  if (!selectedFile.value) return;

  isRunning.value = true;
  showProgress.value = true;
  progress.value = 0;
  taskStatus.value = "processing";
  statusMessage.value = "上传文件中...";

  try {
    // Step 1: 上传
    const uploadRes = await uploadAudio(selectedFile.value);
    const fileId = uploadRes.data.file_id;

    // Step 2: 开始转换
    statusMessage.value = "启动转换任务...";
    const convertRes = await startConvert(fileId, selectedStyle.value);
    const taskId = convertRes.data.task_id;

    // Step 3: 轮询进度
    pollingTimer = setInterval(async () => {
      try {
        const { data } = await getTaskStatus(taskId);
        progress.value = data.progress || 0;
        taskStatus.value = data.status;
        statusMessage.value = data.message || "";
        currentFrame.value = data.frame || 0;
        currentLatency.value = data.latency_ms || 0;

        if (data.status === "completed") {
          clearInterval(pollingTimer);
          isRunning.value = false;
          resultData.value = data.result;
          resultAudioUrl.value = getDownloadUrl(data.output_file);

          // 刷新历史
          await nextTick();
          if (historyRef.value) {
            historyRef.value.fetchHistory();
          }
        } else if (data.status === "error") {
          clearInterval(pollingTimer);
          isRunning.value = false;
        }
      } catch (e) {
        console.warn("轮询失败:", e.message);
      }
    }, 500);
  } catch (e) {
    isRunning.value = false;
    showProgress.value = false;
    statusMessage.value = "错误: " + (e.response?.data?.error || e.message);
    taskStatus.value = "error";
  }
}

function onPause() {
  // 简化实现：通过停止轮询模拟暂停
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
  isRunning.value = false;
  statusMessage.value = "已暂停";
}

function onReset() {
  clearInterval(pollingTimer);
  isRunning.value = false;
  showProgress.value = false;
  resultData.value = null;
  resultAudioUrl.value = "";
  progress.value = 0;
  selectedFile.value = null;
  originalAudioUrl.value = "";
  statusMessage.value = "";
}

function downloadResult() {
  if (resultAudioUrl.value) {
    window.open(resultAudioUrl.value, "_blank");
  } else if (resultData.value?.output_file) {
    window.open(getDownloadUrl(resultData.value.output_file), "_blank");
  }
}

// 监听报告弹窗
const unwatch = (() => {
  let lastVal = false;
  setInterval(async () => {
    if (showReport.value && !lastVal) {
      try {
        const { data } = await getReport();
        reportData.value = data;
      } catch (e) {
        console.warn("获取报告失败:", e.message);
      }
    }
    lastVal = showReport.value;
  }, 200);
})();
</script>

<style>
/* 全局样式 */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  background: #f0f2f5;
}

.app-container {
  min-height: 100vh;
}

.app-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: #fff;
  padding: 20px 24px;
  height: auto !important;
}
.app-header h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: 2px;
}
.subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  opacity: 0.8;
}
.app-header .el-divider {
  margin: 14px 0 0;
}
.app-main {
  max-width: 1200px;
  margin: 20px auto;
  padding: 0 16px;
}
.result-area {
  margin-top: 16px;
}
.result-actions {
  margin-top: 12px;
  display: flex;
  gap: 12px;
}
.app-footer {
  text-align: center;
  padding: 16px;
  color: #909399;
  font-size: 13px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .app-header h1 {
    font-size: 18px;
  }
  .subtitle {
    font-size: 11px;
  }
  .app-main {
    margin: 8px auto;
    padding: 0 8px;
  }
}
</style>
