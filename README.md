# 音频变声器（DSP + 可选零样本神经变声）

一个本地运行、可直接开源的音频变声器。默认使用纯 Python 数字信号处理（DSP）完成真实变声，
不需要训练、不需要数据集、也不需要模型权重，上传音频后即可在本机完成处理并下载结果。

核心处理全部由 Python 完成，浏览器界面使用 Vue 3 提供上传、试听、进度和历史记录交互。
项目同时预留了可选的零样本神经变声（Seed-VC）接入点，用于获得更自然的人声变声效果。

## 功能

- 真实音高迁移：基于相位声码器（Phase Vocoder）改变音高，男女声预设默认移动约 5 个半音，
  并把音高与共振峰分开调整，避免纯音高迁移产生的「花栗鼠」感。
- 频谱塑形：使用保留原始相位的 STFT 均衡器调整音色，避免 Griffin-Lim 重建带来的金属感。
- 多种风格：古典、摇滚、爵士、无损高保真、环绕增强。
- 动态与空间效果：摇滚失真、动态压缩、底噪门限、卷积混响、立体声扩展。
- 可调参数：音高偏移 -12 到 +12 个半音，效果强度 0.5 到 1.5。
- 真实统计：只上报本机实际处理耗时、音频时长和实时率（RTF），不虚构模型指标。
- 可选更自然的男女声：安装 Praat（parselmouth）后走专业共振峰算法；不装时使用内置的频谱包络搬移实现。

## 技术栈

- Python 3.10+
- Flask
- NumPy、SciPy、SoundFile
- Vue 3 + Vite + Element Plus
- SQLite

## 快速开始

先安装 Python 依赖：

```bash
pip install -r requirements.txt
```

可选：安装 Praat 绑定，让男女声互转更自然（不装也能用，只是音色略偏卡通）：

```bash
pip install -r backend/requirements_neural.txt
```

一键启动后端和前端：

```bash
python main.py
```

也可以分别启动。后端：

```bash
python -m backend.app
```

前端：

```bash
cd frontend
npm install
npm run dev
```

后端默认监听 `http://127.0.0.1:5000`，前端默认监听 `http://localhost:3000`。

## 处理流程

输入音频先被统一重采样到 44.1 kHz。变声风格使用基于短时傅里叶变换的相位声码器做音高迁移，
再用 STFT 均衡器保留原始相位进行频谱塑形。最后根据所选风格叠加失真、压缩、混响或声场扩展，
并写入 WAV 文件。所有处理都在本机完成，不上传任何数据。

男女声预设会处理整段输入，因此伴奏也会随音高一起变化；如果输入是干净的人声录音，效果最明显。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务状态与处理参数 |
| GET | `/api/styles` | 可用效果列表 |
| POST | `/api/upload` | 上传音频文件 |
| POST | `/api/convert` | 提交转换任务 |
| GET | `/api/status/<task_id>` | 查询任务进度 |
| POST | `/api/cancel/<task_id>` | 取消任务 |
| GET | `/api/download/<filename>` | 下载转换结果 |
| GET | `/api/history` | 转换历史 |
| GET | `/api/report` | 本机运行统计 |

## 目录

```text
Music_Timbre_Transfer/
├── main.py                  一键启动脚本
├── backend/
│   ├── app.py               Flask API
│   ├── config.py            参数与效果预设
│   ├── effects.py           DSP 效果实现
│   ├── inference.py         处理编排与真实计时
│   ├── neural.py            可选 Seed-VC 接入（未安装时优雅降级）
│   ├── preprocessor.py      音频加载
│   ├── reconstructor.py     输出写入
│   └── database.py          SQLite 存储
├── frontend/
│   └── src/                 Vue 3 界面
└── tests/
    └── test_backend.py      后端单元测试
```

## 零样本神经变声（Seed-VC，无需训练、无需自己录音）

DSP 的男女声变声虽然零依赖、零训练，但音色贴近真人有限。要想得到更像「变声器」的效果，
项目集成了 [Seed-VC](https://github.com/Plachtaa/Seed-VC) 的零样本语音转换。

这里**不需要你录素材，也不需要训练**：Seed-VC 的预训练权重已经学会「人是怎么发声的」，
推理时只需要两段音频——你的**源音频**（要变的声音），以及一段几秒钟的**目标音色参考音频**。
参考音频在 Seed-VC 仓库自带的 `examples/reference/` 里就有一批现成的（GitHub 上即可拿到），
前端也内置了「女声参考」「男声参考」两个预设，点一下就能用，不需要你另外找素材。

### 一键安装

在项目根目录打开 PowerShell 或双击运行：

```bat
scripts\setup_seedvc.bat
```

这个脚本会自动完成：克隆 Seed-VC 到 `third_party/Seed-VC`、拉取 Git LFS 示例音频、
创建独立虚拟环境 `third_party/seedvc-venv`、安装 PyTorch 等依赖。国内网络可以加镜像参数：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_seedvc.ps1 -ChinaMirror
```

安装完成后重启后端，前端会自动出现「智能变声（Seed-VC）」开关。首次推理时模型会从
Hugging Face 自动下载预训练权重（国内可先执行
`$env:SEEDVC_HF_ENDPOINT = "https://hf-mirror.com"` 走镜像）。

### 使用方式

- 前端：打开「智能变声（Seed-VC）」，选择「内置女声参考」「内置男声参考」，或上传任意一段参考音频。
- 命令行（在 Seed-VC 仓库目录内）：

```bash
python inference.py \
  --source 你的语音.wav \
  --target examples/reference/azuma_0.wav \
  --output ./output \
  --diffusion-steps 25
```

- 代码里调用本项目封装好的适配器：

```python
from backend.neural import NeuralVoiceConverter

converter = NeuralVoiceConverter()
if converter.available:
    converter.convert("你的语音.wav", "参考音色.wav", "./output")
```

说明：Seed-VC 及其权重没有随本项目预装，需联网安装一次；`examples/` 里的示例音频是官方演示素材，
仅建议用于测试，正式使用请换用你有权使用的音色。本项目默认走 DSP，未安装 Seed-VC 时零素材也能运行。

## 限制

默认 DSP 管线不包含神经网络的训练与评估。男女声互转目前对整段输入做音高迁移和频谱塑形，
没有把人声与伴奏分离；接入手声分离或 Seed-VC 后可以得到更贴近真人变声的效果。

## 性能与缓存说明

- 神经变声（Seed-VC）的模型常驻在一个后台 worker 进程里，只在首次使用时加载一次；
  第一次转换需要约 1–2 分钟加载模型，之后的转换会明显更快。
- 权重下载完成后，后端会自动以离线模式加载，不会每次转换都联网检查或重新下载；
  网络不稳定的环境下也不会出现重复的重试等待。

## License

MIT
