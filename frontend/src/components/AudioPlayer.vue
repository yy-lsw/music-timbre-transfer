<template>
  <div class="audio-player" v-if="src">
    <h3>{{ label }}</h3>
    <audio controls :src="src" style="width: 100%">
      您的浏览器不支持 HTML5 Audio
    </audio>
  </div>
</template>

<script setup>
defineProps({
  src: { type: String, default: "" },
  label: { type: String, default: "音频播放" },
});
</script>

<style scoped>
.audio-player {
  margin: 12px 0;
  padding: 12px;
  background: #f0f5ff;
  border-radius: 8px;
}
.audio-player h3 {
  margin-bottom: 8px;
  font-size: 14px;
  color: #409eff;
}
</style>
