# tests/ — 测试套件

## 概述

本目录包含桥接组件的全部自动化测试，按模块组织。

## 目录结构

```
tests/
├── downlink/                    # 下行测试
│   ├── test_command.py          # 命令校验 + ACK 构造（47 条）
│   ├── test_integration.py      # RPC + Pub/Sub + MQTT 集成（14 条）
│   ├── test_dedup.py            # 幂等去重缓存
│   ├── test_registry.py         # 设备注册表查询
│   ├── test_business_server.py  # 业务层 VSOA Server
│   ├── test_mqtt_router.py      # MQTT 多 Broker 路由
│   ├── verify.py                # 手动验证脚本（RPC + ACK + 超时）
│   └── mqtt_sub.py              # MQTT 订阅验证（终端工具）
├── uplink/                      # 上行测试
│   ├── test_adapters.py         # 适配器解析测试
│   ├── test_integration.py      # 上行管道集成
│   ├── test_registry.py         # 设备注册表写入
│   ├── test_camera_reassembler.py # HCv3 图片分片重组
│   └── conftest.py              # 共享 fixtures（MQTT + VSOA mock）
├── platform/                    # IoT 测试平台功能测试
│   ├── test_direct_lora_control.py    # LoRa 直连控制
│   ├── test_environment_dashboard.py  # 环境仪表盘
│   └── test_threshold_alerts.py       # 阈值告警
└── scene_engine/                # 场景引擎测试
    └── test_engine.py           # 条件匹配 + 触发 + 冷却 + 自动停止
```

## 运行方式

```powershell
# 全部测试
python -m pytest tests/ -v

# 按模块运行
python -m pytest tests/downlink/ -v      # 下行
python -m pytest tests/uplink/ -v        # 上行
python -m pytest tests/platform/ -v      # 平台
python -m pytest tests/scene_engine/ -v  # 场景引擎

# 运行单个文件
python -m pytest tests/downlink/test_command.py -v

# 带覆盖率
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

## 测试分类

| 类别 | 目录 | 说明 |
|------|------|------|
| 单元测试 | `test_command.py`, `test_adapters.py` 等 | 纯函数/独立模块测试，不需要外部服务 |
| 集成测试 | `test_integration.py` 等 | 需要 MQTT Broker 或 mock，测试模块间交互 |
| 手动验证 | `verify.py`, `mqtt_sub.py` | 终端手工运行，适合调试和演示 |

## 编写测试约定

- 使用 `pytest` 框架
- 文件名以 `test_` 开头
- 类名以 `Test` 开头
- 函数名以 `test_` 开头
- 使用 `conftest.py` 管理共享 fixtures
- 外部依赖（MQTT、VSOA）使用 mock 或 monkeypatch
