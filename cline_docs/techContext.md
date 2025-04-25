# 技术上下文 (Tech Context) - [自动记录日期：2025年4月26日]

**核心编程语言:**
*   Python 3.10

**主要 Python 库 (`requirement.txt`):**
*   `torch`: 用于深度学习任务（虽然在 PEFA 核心代码中直接使用不明显，但底层或依赖库可能需要）。
*   `openai`: 与 OpenAI API 交互，用于调用大型语言模型 (LLM)。
*   `backoff`: 用于实现 API 调用的指数退避重试逻辑。
*   `scipy`: 科学计算库。
*   `tqdm`: 显示进度条。
*   `sentence_transformers`: 可能用于文本嵌入或相似度计算（具体用途需进一步代码分析）。
*   `ipdb`: Python 交互式调试器。

**大型语言模型 (LLM):**
*   **提供商:** OpenAI (通过 API 调用)。
*   **配置:** 需要在 `args.py` 或 `arguments.py` 中配置 OpenAI API Key 和 Organization ID。模型 ID（如 `gpt-4-0125-preview`）也可配置。

**仿真环境:**
*   **核心平台:** NVIDIA Omniverse Isaac Sim (需要特定版本 **2022.2.0**)。
*   **机器人与场景库:** OmniGibson (项目使用 **v0.2.1 的修改版**，包含在仓库的 `OmniGibson/` 目录中)。
*   **依赖:** 建立在 BEHAVIOR-1K 平台基础之上。
*   **场景描述:** 可能使用 USD (Universal Scene Description) 格式（Isaac Sim 的标准）。

**开发与运行环境:**
*   **依赖管理:** Conda (需要创建 `coherent` 和 `omnigibson` 两个环境)。
*   **操作系统 (参考设置):** Ubuntu 20.04 (根据 `setup.sh` 脚本提及)。
*   **机器人操作系统 (参考设置):** ROS1 Noetic (根据 `setup.sh` 脚本和 `ros_hademo_ws` 目录提及，可能用于底层控制或真实世界接口)。
*   **设置流程:**
    1.  安装特定版本的 Isaac Sim。
    2.  克隆仓库。
    3.  设置环境变量 (`COHERENT_PATH`)。
    4.  运行 `./OmniGibson/scripts/setup.sh` (需要在 conda 环境外运行，会创建 `omnigibson` conda 环境)。
    5.  下载数据集 (`./OmniGibson/scripts/download_datasets.py`)。
    6.  下载并放置特定的机器人资源文件到 `OmniGibson/Benchmark/assets`。
    7.  复制 `oven` 资源文件。
    8.  激活 `omnigibson` conda 环境后运行 `./OmniGibson/Benchmark/run.sh` 启动模拟。
    9.  在 `coherent` conda 环境中运行实验脚本 (`python main.py ...`)。

**数据格式:**
*   **LLM 输入/输出:** 自然语言文本。
*   **Prompts:** `.txt` 文件。
*   **环境状态:** 通过代码从仿真 API 获取，转换为文本供 LLM 使用。
*   **场景/资源:** USD (Isaac Sim), 可能有其他格式的资源文件。

**技术约束:**
*   严格依赖特定版本的 Isaac Sim (2022.2.0)。
*   需要 NVIDIA GPU 以运行 Isaac Sim 和可能的本地 LLM 推理。
*   运行成本依赖于 OpenAI API 的使用量。
*   设置过程涉及多个步骤和环境切换，较为复杂。
