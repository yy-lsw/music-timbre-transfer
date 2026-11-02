<template>
  <div class="history-panel">
    <el-table
      :data="history"
      stripe
      style="width: 100%"
      max-height="300"
      size="small"
    >
      <el-table-column prop="created_at" label="时间" width="150" />
      <el-table-column prop="original_filename" label="原文件" show-overflow-tooltip />
      <el-table-column prop="style_label" label="效果" width="100" />
      <el-table-column prop="duration_sec" label="时长" width="70" />
      <el-table-column prop="conversion_time_sec" label="耗时" width="70" />
      <el-table-column prop="rtf" label="RTF" width="70" />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            link
            @click="$emit('download', row.output_filename)"
          >
            下载
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty
      v-if="!history.length"
      description="暂无转换记录"
      :image-size="60"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getHistory } from "../api";

defineEmits(["download"]);
const history = ref([]);

async function fetchHistory() {
  try {
    const { data } = await getHistory(20);
    history.value = data.history;
  } catch (error) {
    console.warn("获取历史记录失败:", error.message);
  }
}

onMounted(fetchHistory);
defineExpose({ fetchHistory });
</script>

<style scoped>
.history-panel {
  margin-top: 4px;
}
</style>
