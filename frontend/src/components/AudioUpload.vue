<template>
  <el-upload
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
        支持 MP3, WAV, FLAC, AAC, OGG, M4A 格式 | 最大 100MB
      </div>
    </template>
  </el-upload>
</template>

<script setup>
import { UploadFilled } from "@element-plus/icons-vue";

const emit = defineEmits(["file-selected"]);
const acceptFormats = ".mp3,.wav,.flac,.aac,.ogg,.m4a";

function handleChange(file) {
  emit("file-selected", file.raw);
}

function handleRemove() {
  emit("file-selected", null);
}
</script>

<style scoped>
.audio-upload {
  width: 100%;
}
</style>
