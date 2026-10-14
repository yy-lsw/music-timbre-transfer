<template>
  <div class="style-selector">
    <h3>选择质感风格</h3>
    <el-radio-group v-model="selectedStyle" @change="handleChange" size="large">
      <el-radio-button
        v-for="style in styles"
        :key="style.key"
        :value="style.key"
      >
        <div class="style-item">
          <span class="style-name">{{ style.name }}</span>
          <span class="style-desc">{{ style.description }}</span>
        </div>
      </el-radio-button>
    </el-radio-group>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { getStyles } from "../api";

const emit = defineEmits(["style-selected"]);
const styles = ref([]);
const selectedStyle = ref("hifi");

onMounted(async () => {
  try {
    const { data } = await getStyles();
    styles.value = data.styles;
  } catch (e) {
    // 离线回退
    styles.value = [
      { key: "classical", name: "古典", description: "温暖饱满的大厅混响质感" },
      { key: "rock", name: "摇滚", description: "强劲有力的动态压缩质感" },
      { key: "jazz", name: "爵士", description: "柔和细腻的俱乐部氛围质感" },
      { key: "hifi", name: "无损高保真", description: "纯净通透的录音室品质" },
      { key: "surround", name: "环绕增强", description: "宽广沉浸的空间环绕质感" },
      { key: "m2f", name: "男声→女声", description: "男声升高音调+共振峰，转为女声质感" },
      { key: "f2m", name: "女声→男声", description: "女声降低音调+共振峰，转为男声质感" },
    ];
  }
  emit("style-selected", selectedStyle.value);
});

function handleChange(val) {
  emit("style-selected", val);
}
</script>

<style scoped>
.style-selector {
  margin: 16px 0;
}
.style-selector h3 {
  margin-bottom: 12px;
  font-size: 15px;
  color: #606266;
}
.style-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 8px;
}
.style-name {
  font-weight: 600;
  font-size: 14px;
}
.style-desc {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}
</style>
