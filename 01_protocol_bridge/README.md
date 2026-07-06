# MQTT-VSOA Protocol Bridge Project

项目名称：物联网传输协议桥接组件开发



## 1. 项目简介

本项目用于实现 MQTT 与 VSOA 协议之间的数据桥接，面向 LoRa、LoRaWAN、ZigBee 等物联网场景，完成设备数据接收、格式转换、消息转发、接口适配和测试验证。

当前版本提供课程实习所需的项目骨架，包括：

- MQTT -> VSOA 上行数据桥接
- VSOA -> MQTT 下行控制桥接
- 统一 topic 与 payload schema
- 本地模拟 VSOA 服务
- 测试脚本和验收清单
- 项目设计文档、测试说明、实验指导书和 PPT 模板

真实接入翼辉 ADP 或 VSOA SDK 时，只需要替换 `src/bridge/vsoa_adapter.py` 中的模拟实现。

## 2. 目录结构

```text
mqtt_vsoa_bridge_project/
  config/                 配置文件
  docs/                   项目文档与模板
  examples/               示例 payload
  logs/                   运行日志目录
  scripts/                启动和演示脚本
  src/bridge/             桥接组件源码
  tests/                  自动化测试
  README.md               项目总入口
  requirements.txt        Python 依赖
```

## 2.1 桥接支撑实验目录

```text
experiments/
  B00_common_framework/       公共工程模板与测试框架
  L05_mqtt_to_vsoa/           L5 LoRa MQTT -> VSOA 上行协议转换实验
  L06_vsoa_to_mqtt/           L6 LoRa VSOA -> MQTT 下行控制实验
  Z06_mqtt_vsoa_bridge/       Z6 ZigBee MQTT <-> VSOA 双向协议转换实验
```

每个支撑实验目录下均包含 `src/`、`config/`、`docs/`、`slides/`、`tests/`、`assets/` 六个子目录。

## 3. 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/demo_local_bridge.py
pytest
```

如果暂时没有 MQTT broker，可以先运行本地 demo。该 demo 不依赖真实 MQTT 服务，会直接调用桥接核心逻辑验证转换流程。

## 4. 核心流程

### 上行：MQTT -> VSOA

1. 设备或网关向 MQTT topic 发布数据。
2. 桥接组件订阅 MQTT topic。
3. 解析 payload 并校验字段。
4. 转换为统一设备数据模型。
5. 写入 VSOA 服务适配层。
6. VSOA 客户端可查询最新设备数据。

### 下行：VSOA -> MQTT

1. VSOA 客户端发起控制命令。
2. 桥接组件校验设备编号、命令类型和参数。
3. 转换为 MQTT downlink payload。
4. 发布到设备控制 topic。
5. 记录命令状态、回执或失败原因。



## 5. 交付物清单

- 源码：`src/bridge/`
- 配置：`config/bridge_config.yaml`
- 示例数据：`examples/`
- 测试用例：`tests/`
- 项目设计文档：`docs/project_design.md`
- 测试说明文档：`docs/test_plan.md`
- 实验指导书模板：`docs/templates/experiment_guide_template.md`
- PPT 大纲模板：`docs/templates/ppt_outline_template.md`
- 验收清单：`docs/acceptance_checklist.md`

