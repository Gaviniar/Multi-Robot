# 项目上下文 (Product Context) - [自动记录日期：2025年4月26日]

**项目名称:** COHERENT (Collaboration of Heterogeneous Multi-Robot System with Large Language Models)

**核心目标:**
*   解决复杂长时程任务中，异构机器人（如四旋翼无人机、机器狗、机械臂）的协同规划问题。
*   利用大型语言模型 (LLM) 强大的推理能力进行任务分解、分配和调整。

**要解决的问题:**
*   现有基于 LLM 的机器人规划方法主要关注单一或同构机器人处理简单任务。
*   实际应用中，复杂任务通常需要不同类型机器人（具有不同能力和动作空间）进行紧密协作，这增加了规划的难度。
*   需要一个能够理解各机器人能力、动态环境并有效协调不同机器人动作的规划框架。

**预期工作方式:**
*   提出一个基于 LLM 的**中心化**任务规划框架 COHERENT。
*   采用 **PEFA (Proposal-Execution-Feedback-Adjustment)** 循环机制：
    1.  **Proposal (提议):** 中心化的 Task Assigner (Oracle) LLM 分解高级指令为子任务，并分配给合适的 Robot Executor。
    2.  **Execution (执行):** Robot Executor LLM 选择具体动作执行子任务。
    3.  **Feedback (反馈):** Robot Executor 提供执行结果和自我反思的反馈。
    4.  **Adjustment (调整):** Task Assigner 根据反馈调整后续规划。
*   该循环持续进行，直至任务完成。
*   提供一个包含 100 个复杂任务的异构多机器人基准测试环境 (基于 BEHAVIOR-1K 和 OmniGibson)。
*   旨在超越现有方法在任务成功率和执行效率方面的表现。
