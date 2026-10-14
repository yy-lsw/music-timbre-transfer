<template>
  <div class="progress-display" v-if="visible">
    <el-progress
      :percentage="progress"
      :status="progressStatus"
      :stroke-width="18"
      striped
      :striped-flow="isRunning"
    />
    <div class="progress-info">
      <el-tag :type="tagType" size="default">{{ statusMessage }}</el-tag>
      <span v-if="frame > 0" class="frame-info">
        帧: {{ frame }} | 时延: {{ latencyMs }}ms
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  progress: { type: Number, default: 0 },
  status: { type: String, default: "" },
  message: { type: String, default: "" },
  frame: { type: Number, default: 0 },
  latencyMs: { type: Number, default: 0 },
  isRunning: { type: Boolean, default: false },
});

const progressStatus = computed(() => {
  if (props.status === "completed") return "success";
  if (props.status === "error") return "exception";
  return "";
});

const tagType = computed(() => {
  if (props.status === "completed") return "success";
  if (props.status === "error") return "danger";
  return "warning";
});

const statusMessage = computed(() => props.message || "等待中...");
</script>

<style scoped>
.progress-display {
  margin: 16px 0;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}
.frame-info {
  font-size: 13px;
  color: #606266;
  font-family: monospace;
}
</style>
