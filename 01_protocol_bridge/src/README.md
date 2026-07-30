# src/ — 桥接组件源代码

## 架构总览

```
src/
├── main.py                  # 统一入口：同时启动上行 + 下行 + 场景引擎
├── config.py                # 类型化 YAML 配置加载（dataclass）
├── device_registry.py       # 统一设备注册表（线程安全，上行写入 + 下行查询）
├── error_codes.py           # 17 个 ErrorCode 枚举（1xxx 上行 + 2xxx 下行 + 3xxx 场景）
├── mqtt_handler.py          # paho-mqtt 封装（线程安全 publish + 多 Broker 路由）
├── trace_id.py              # traceId 生成器（br-{random}-{timestamp}）
│
├── uplink/                  # 上行管道：MQTT → VSOA
│   ├── main.py              # 上行独立入口（已废弃，统一入口为 src/main.py）
│   ├── vsoa_server.py       # VSOA 查询端点 + 发布通知
│   ├── tcp_inject.py        # TCP 9090 JSON Lines 注入（离线测试）
│   ├── camera_reassembler.py # LoRaWAN HCv3 图片分片重组
│   └── adapters/            # 协议适配器
│       ├── base.py          # Adapter 抽象基类 + 测量值别名表
│       ├── lora.py          # LoRa/LoRaWAN/ChirpStack
│       ├── zigbee.py        # Zigbee2MQTT
│       ├── wifi.py          # WiFi/EoRa 设备
│       └── generic.py       # 通用兜底
│
├── downlink/                # 下行管道：VSOA → MQTT
│   ├── main.py              # 下行独立入口（已废弃，统一入口为 src/main.py）
│   ├── rpc_server.py        # RPC handler（同步回执 + per-command 超时）
│   ├── pubsub_handler.py    # Pub/Sub 订阅 + ACK 发布
│   ├── business_server.py   # 业务层 VSOA Server（端口 3000，按需启动）
│   ├── command.py           # 命令校验 + MQTT 消息构造（纯函数，两通道共用）
│   └── dedup.py             # 幂等去重缓存（command_id + TTL 过期淘汰）
│
└── scene_engine/            # 场景联动引擎
    ├── engine.py            # 条件匹配、冷却、边沿触发、自动停止
    ├── models.py            # 规则模型与校验
    ├── sensors.py           # 8 种标准传感器定义与归一化
    ├── persistence.py       # scenes.yaml 原子读写
    └── rpc_api.py           # /scene/* VSOA 管理接口
```

## 启动方式

```bash
# 统一入口（推荐）
python src/main.py --config config.yaml

# 离线模式（无需 MQTT Broker）
python src/main.py --no-mqtt

# 仅上行（不启动 Pub/Sub 下行监听）
python src/main.py --uplink-only
```

## 核心设计原则

### Payload 透传
桥接只提取路由必需的 `device_id` 和 `device_type`，其余传感器数据放入 `raw: dict` 原样透传。新增传感器类型**无需改 bridge 代码**。

### 双通道下行
| 特性 | RPC | Pub/Sub |
|------|-----|---------|
| 调用方式 | `client.fetch("/bridge/send_command", ...)` | `client.datagram("/ctrl/cmd", ...)` |
| 阻塞特性 | 同步阻塞，等待回执 | 异步，发完即返回 |
| 回执方式 | `fetch()` 同步返回 | bridge publish `/ctrl/ack` |
| 超时支持 | ✅ per-command | ❌ |

### 模块职责
- `config.py` — 配置加载，不包含业务逻辑
- `command.py` — 纯函数，无状态，三通道共用
- `error_codes.py` — 枚举定义，不依赖任何其他模块
- `device_registry.py` — 线程安全，上行写入、下行只读
- `dedup.py` — 独立缓存层，可插拔
- `mqtt_handler.py` — MQTT 操作封装，publish 加锁保证线程安全
- `trace_id.py` — 独立工具，生成全链路追踪 ID

## 端口分配

| 端口 | 协议 | 用途 |
|:----:|------|------|
| 3002 | VSOA | 统一 VSOA Server（上行查询 + 下行 RPC + ACK/事件发布 + 场景管理） |
| 3000 | VSOA | 业务层 VSOA Server（bridge 自动托管，业务逻辑对接） |
| 1883 | MQTT | 连接 MQTT Broker |
| 9090 | TCP | JSON Lines 注入（离线测试） |

## 相关文档

- `../config.yaml` — 完整配置（含注释）
- `../iot_test_platform/docs/device_integration_contract.md` — 设备接入约定
- `./uplink/README.md` — 上行管道详解
- `./downlink/README.md` — 下行管道详解
- `./scene_engine/README.md` — 场景引擎详解
