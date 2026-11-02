<template>
  <div v-if="visible" class="progress-display">
    <el-progress
      :percentage="progress"
      :status="progressStatus"
      :stroke-width="18"
      striped
      :striped-flow="isRunning"
    />
    <div class="progress-info">
      <el-tag :type="tagType" size="default">{{ statusMessage }}</el-tag>
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
  isRunning: { type: Boolean, default: false },
});

const progressStatus = computed(() => {
  if (props.status === "completed") return "success";
  if (props.status === "error") return "exception";
  if (props.status === "cancelled") return "warning";
  return "";
});

const tagType = computed(() => {
  if (props.status === "completed") return "success";
  if (props.status === "error") return "danger";
  if (props.status === "cancelled") return "info";
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
  align-items: center;
  margin-top: 10px;
}
</style>
