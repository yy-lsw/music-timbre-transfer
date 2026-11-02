<template>
  <div class="style-selector">
    <h3>选择效果</h3>
    <el-radio-group v-model="selectedStyle" size="large" @change="handleChange">
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

    <div v-if="isVoice" class="param-row">
      <span class="param-label">音高偏移</span>
      <el-slider
        v-model="pitchSemitones"
        :min="-12"
        :max="12"
        :step="1"
        show-input
        @input="emit('pitch-change', pitchSemitones)"
      />
    </div>

    <div class="param-row">
      <span class="param-label">效果强度</span>
      <el-slider
        v-model="intensity"
        :min="0.5"
        :max="1.5"
        :step="0.1"
        show-input
        @input="emit('intensity-change', intensity)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getStyles } from "../api";

const emit = defineEmits(["style-selected", "pitch-change", "intensity-change"]);
const styles = ref([]);
const selectedStyle = ref("hifi");
const pitchSemitones = ref(0);
const intensity = ref(1.0);

const fallbackStyles = [
  { key: "classical", name: "古典", description: "温暖饱满，带厅堂混响", kind: "timbre", pitch_semitones: 0 },
  { key: "rock", name: "摇滚", description: "强力失真与动态压缩", kind: "timbre", pitch_semitones: 0 },
  { key: "jazz", name: "爵士", description: "柔和低频与俱乐部混响", kind: "timbre", pitch_semitones: 0 },
  { key: "hifi", name: "无损高保真", description: "清晰透亮并抑制底噪", kind: "timbre", pitch_semitones: 0 },
  { key: "surround", name: "环绕增强", description: "扩展声场宽度与空间感", kind: "timbre", pitch_semitones: 0 },
  { key: "m2f", name: "男声转女声", description: "整体音高上移并提亮", kind: "voice", pitch_semitones: 7 },
  { key: "f2m", name: "女声转男声", description: "整体音高下移并压低", kind: "voice", pitch_semitones: -7 },
];

const isVoice = computed(() => {
  return styles.value.some(
    (style) => style.key === selectedStyle.value && style.kind === "voice"
  );
});

function syncPitch(styleKey) {
  const preset = styles.value.find((style) => style.key === styleKey);
  pitchSemitones.value = Number(preset?.pitch_semitones ?? 0);
}

function handleChange(styleKey) {
  syncPitch(styleKey);
  emit("style-selected", styleKey);
  emit("pitch-change", pitchSemitones.value);
}

onMounted(async () => {
  try {
    const { data } = await getStyles();
    styles.value = data.styles;
  } catch (error) {
    styles.value = fallbackStyles;
  }
  syncPitch(selectedStyle.value);
  emit("style-selected", selectedStyle.value);
  emit("pitch-change", pitchSemitones.value);
  emit("intensity-change", intensity.value);
});
</script>

<style scoped>
.style-selector {
  margin: 16px 0;
}

.style-selector h3 {
  margin-bottom: 12px;
  font-size: 15px;
  color: #52606d;
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
  color: #9aa5b1;
  margin-top: 2px;
}

.param-row {
  margin-top: 18px;
}

.param-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #52606d;
}
</style>
