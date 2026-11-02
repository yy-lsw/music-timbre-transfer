<template>
  <el-upload
    ref="uploadRef"
    class="audio-upload"
    drag
    :auto-upload="false"
    :accept="acceptFormats"
    :limit="1"
    :on-change="handleChange"
    :on-remove="handleRemove"
  >
    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
    <div class="el-upload__text">
      将音频文件拖拽到此处，或 <em>点击选择</em>
    </div>
    <template #tip>
      <div class="el-upload__tip">
        支持 MP3, WAV, FLAC, OGG | 最大 100MB
      </div>
    </template>
  </el-upload>
</template>

<script setup>
import { ref } from "vue";
import { UploadFilled } from "@element-plus/icons-vue";

const emit = defineEmits(["file-selected"]);
const acceptFormats = ".mp3,.wav,.flac,.ogg";
const uploadRef = ref(null);

function handleChange(file) {
  emit("file-selected", file.raw);
}

function handleRemove() {
  emit("file-selected", null);
}

function clearFiles() {
  uploadRef.value?.clearFiles();
}

defineExpose({ clearFiles });
</script>

<style scoped>
.audio-upload {
  width: 100%;
}
</style>
