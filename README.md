# 轻量化音乐质感转换系统

上传一段音频,选择目标质感,后端完成音频处理并返回结果,前端展示转换进度、历史记录与性能报告。本科毕业设计项目。

## 功能

- 音频上传,支持 mp3 / wav / flac / aac / ogg / m4a
- 7 种质感风格:古典、摇滚、爵士、无损高保真、环绕增强、男声→女声、女声→男声
- 异步转换任务,前端轮询进度
- 结果试听与下载、转换历史、性能报告

## 技术栈

- 后端:Python 3 + Flask,音频处理使用 librosa / numpy / scipy / soundfile
- 前端:Vue 3 + Vite + Element Plus + axios
- 存储:SQLite(转换历史)

## 目录结构

```text
Music_Timbre_Transfer/
├── main.py                 一键启动脚本
├── backend/
│   ├── app.py              Flask 接口层
│   ├── config.py           音频参数与风格预设
│   ├── preprocessor.py     预处理:重采样、MFCC、STFT
│   ├── inference.py        质感转换与进度回调
│   ├── reconstructor.py    音频重建与导出
│   ├── database.py         历史记录存储
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── App.vue
        ├── api/index.js
        └── components/     ControlPanel / StyleSelector / ProgressDisplay / HistoryPanel / AudioUpload / AudioPlayer
```

## 运行

一键启动(会自动拉起后端和前端):

```bash
python main.py
```

只启动后端:

```bash
python main.py backend
```

只启动前端:

```bash
python main.py frontend
```

手动分开跑也可以:

```bash
cd backend
pip install -r requirements.txt
python app.py
```

```bash
cd frontend
npm install
npm run dev
```

后端默认监听 `http://127.0.0.1:5000`。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/styles` | 返回可选质感风格列表 |
| POST | `/api/upload` | 上传音频文件 |
| POST | `/api/convert` | 提交转换任务 |
| GET | `/api/status/<task_id>` | 查询任务进度 |
| GET | `/api/download/<filename>` | 下载转换结果 |
| GET | `/api/history` | 转换历史 |
| GET | `/api/report` | 性能报告 |

## 音频处理参数

重采样目标 44.1kHz,MFCC 40 维,STFT 窗长 2048、帧移 512。

## 说明

- `node_modules/`、虚拟环境、数据库与日志文件已加入 `.gitignore`,克隆后需要自行安装依赖。
- 性能指标(模型体积、内存占用、平均转换耗时等)对应 `backend/config.py` 中的常量,来自论文实验记录。
