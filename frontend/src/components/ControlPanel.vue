<template>
  <div class="control-panel">
    <el-button
      type="primary"
      size="large"
      :disabled="!canStart"
      :loading="isRunning"
      @click="$emit('start')"
    >
      {{ isRunning ? "转换中..." : "开始转换" }}
    </el-button>
    <el-button
      size="large"
      :disabled="!isRunning"
      @click="$emit('pause')"
    >
      暂停
    </el-button>
    <el-button
      size="large"
      :disabled="!hasResult"
      @click="$emit('reset')"
    >
      重置
    </el-button>
  </div>
</template>

<script setup>
defineProps({
  canStart: { type: Boolean, default: false },
  isRunning: { type: Boolean, default: false },
  hasResult: { type: Boolean, default: false },
});
defineEmits(["start", "pause", "reset"]);
</script>

<style scoped>
.control-panel {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin: 20px 0;
  flex-wrap: wrap;
}
</style>
