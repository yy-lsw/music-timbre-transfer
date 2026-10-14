<template>
  <div class="history-panel">
    <h3>转换历史</h3>
    <el-table :data="history" stripe style="width: 100%" max-height="300" size="small">
      <el-table-column prop="created_at" label="时间" width="160" />
      <el-table-column prop="style_label" label="质感风格" width="110" />
      <el-table-column prop="duration_sec" label="时长(秒)" width="90" />
      <el-table-column prop="conversion_time_sec" label="耗时(秒)" width="90" />
      <el-table-column prop="avg_frame_latency_ms" label="帧时延(ms)" width="110" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" type="primary" link
            @click="$emit('download', row.output_filename)">
            下载
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!history.length" description="暂无转换记录" :image-size="60" />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { getHistory } from "../api";

defineEmits(["download"]);
const history = ref([]);

async function fetchHistory() {
  try {
    const { data } = await getHistory(20);
    history.value = data.history;
  } catch (e) {
    console.warn("获取历史记录失败:", e.message);
  }
}

onMounted(fetchHistory);

// 暴露刷新方法供父组件调用
defineExpose({ fetchHistory });
</script>

<style scoped>
.history-panel {
  margin-top: 24px;
}
.history-panel h3 {
  margin-bottom: 12px;
  font-size: 15px;
  color: #606266;
}
</style>
