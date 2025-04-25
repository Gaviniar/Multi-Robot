# 系统模式 (System Patterns) - [自动记录日期：2025年4月26日]

**核心架构模式:** 中心化协调器 + 分布式执行器 (Centralized Coordinator + Distributed Executors)

*   **中心化任务分配器 (Task Assigner / Oracle):** (`src/experiment/PEFA/LLM_oracle.py`)
    *   作为系统的“大脑”，负责接收高级用户指令。
    *   维护全局任务目标和对话历史。
    *   访问所有机器人的观测信息（经过文本化处理）。
    *   利用 LLM 进行高层任务规划、子任务分解和分配。
    *   根据 Robot Executor 的反馈动态调整规划。
    *   优点：具有全局视野，便于进行复杂的跨机器人协调和长时程规划。
    *   缺点：可能是性能瓶颈，对 Assigner LLM 的能力要求高。
*   **分布式机器人执行器 (Robot Executor):** (`src/experiment/PEFA/LLM_agent.py`)
    *   每个机器人实例对应一个 Executor。
    *   接收来自 Assigner 的特定子任务指令。
    *   仅访问自身的局部观测信息和能力列表。
    *   利用 LLM（可能是一个较小的模型或针对特定能力的模型）将子任务映射到具体的可执行动作。
    *   执行动作（通过底层模拟器接口）。
    *   生成关于执行结果的反馈（成功、失败、部分完成等）发送给 Assigner。
    *   优点：职责单一，专注于执行，可以并行处理（如果 Assigner 的规划支持）。
    *   缺点：缺乏全局视野，完全依赖 Assigner 的指令。

**关键交互模式:** PEFA (Proposal-Execution-Feedback-Adjustment) 循环

*   这是 Task Assigner 和 Robot Executors 之间的核心交互流程，由 `LLM_oracle.py` 中的 `step` 方法驱动。
*   **Proposal:** Assigner 生成子任务并发送给选定的 Executor (`Hello <class name>(id): #message#.` 格式)。
*   **Execution:** Executor 解析指令，调用 LLM 选择动作 (`plan`)。
*   **Feedback:** Executor 将 LLM 生成的反馈 (`message`) 和选定的动作返回给 Assigner。
*   **Adjustment:** Assigner 将反馈记录到对话历史 (`dialogue_history`)，并在下一次规划时考虑该历史，实现闭环调整。

**数据流:**

1.  **环境 -> 文本:** 仿真环境 (`OmniGibson`) 状态通过 `get_env_info.py` 和 `LLM_oracle.py` 中的 `agent_obs2text` 转换为自然语言文本描述。
2.  **文本 -> LLM:** 格式化的观测、任务目标、指令、历史记录和 Prompt 模板被送入 LLM (Task Assigner 和 Robot Executor)。
3.  **LLM -> 文本:** LLM 输出自然语言的规划、反馈和思考过程。
4.  **文本 -> 动作:** Robot Executor LLM 的输出被解析为具体的可执行动作 (`[verb] <object> (id)` 格式)，送入仿真环境执行。

**依赖注入/配置:**

*   主要通过命令行参数 (`args.py`) 和 Prompt 文件 (`src/experiment/PEFA/prompt/`) 进行配置，例如选择 LLM 模型、API Key、指定 Prompt 模板路径等。

**关键技术决策:**

*   **选择中心化架构而非去中心化对话:** 论文明确指出中心化架构在异构机器人协作中更有效，便于全局规划。
*   **使用 LLM 作为规划和决策核心:** 利用 LLM 的常识推理和语言理解能力。
*   **明确的 Prompt 工程:** 通过详细的 Prompt（尤其是 `oracle_prompt.txt`）来指导和约束 LLM 的行为，定义机器人能力、交互规则和输出格式。
*   **基于文本的环境状态表示:** 将结构化的仿真环境状态转换为文本，以便 LLM 处理。
*   **依赖 OmniGibson 仿真环境:** 项目的运行和基准测试建立在 OmniGibson/Isaac Sim 之上。
