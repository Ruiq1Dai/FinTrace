---
name: jrkj-project-rules
description: Maintain JRKJ as a clean, organized, publication-ready project. Apply whenever adding, moving, modifying, or removing code, scripts, configuration, documentation, data resources, tests, or generated artifacts in JRKJ.
---

# JRKJ Project Rules

## Core Principle

始终保持项目结构规范、整洁、有组织，并使仓库随时达到可作为高质量开源项目发布的状态。不要为了完成当前任务而牺牲整体结构、可读性或可维护性。

## File Organization

- 新增或修改文件前，先判断其长期职责和合理归属。
- 将代码、脚本、测试、配置、文档、数据和生成物放入语义明确的目录；不要把临时文件或无关文件堆放在项目根目录。
- 参考成熟开源项目的组织方式，保持命名统一、职责单一、依赖关系清晰。
- 优先复用和扩展现有模块；避免重复代码、一次性杂乱脚本和无意义中间文件。
- 仅在确有内容需要归类时创建目录，不保留空目录或占位结构。
- 不在 JRKJ 中创建任何以 `.` 开头的文件夹；需要配置时采用不依赖隐藏目录的项目内方案。

## Change Discipline

- 完成功能后检查目录归属、文件命名、重复实现、临时产物和文档一致性。
- 将可复现的生成逻辑与大型生成物明确区分，避免来源数据、代码和输出混杂。
- 临时要求若会造成明显的文件堆积或结构性技术债务，选择同样满足需求且结构合理的实现方式。
- 后续出现稳定、长期有效且会反复使用的项目约定时，简洁地补充到本文件；不要记录一次性任务细节。

## Experiment Environment

- 所有实验、评测和相关验证均在执行 `conda activate jrkj` 后运行，确保依赖与结果可复现。
