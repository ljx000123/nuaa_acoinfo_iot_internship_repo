# Z6 Zigbee MQTT↔VSOA双向协议转换实验

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 方向 | Zigbee |
| 类型 | 协议转换 |
| 难度 | 高 |
| 主要设备 | CC2530网关脚本、MQTT broker、VSOA服务/客户端 |
| 协议/接口 | MQTT↔VSOA |
| 负责人 | 辛澳翔 |
| 协作人 | 方宏波、王道嘉、兰佳和 |
| 成果物 | 代码+指导书+PPT |

## 实验目标

将Zigbee上行数据转为VSOA服务接口，并支持VSOA下行控制转MQTT命令

## 备注

Zigbee方向核心协议转换实验

## 目录结构

```text
Z06_mqtt_vsoa_bridge/
  src/      实验源码
  config/   配置文件
  docs/     实验指导书、说明文档
  slides/   PPT 或汇报材料
  tests/    测试脚本、测试记录
  assets/   接线图、截图、素材
```

## 每周任务

| 周次 | 工作重点 | 主要任务 | 本周交付物 | 验收标准 |
| --- | --- | --- | --- | --- |
| 第1周 | 上行桥接框架 | 搭建MQTT broker与VSOA服务端开发环境；定义统一设备数据模型、MQTT topic规范、VSOA接口草案。 | bridge-uplink代码骨架、schema.md、topic命名规范、接口说明初稿。 | 用模拟MQTT消息成功触发VSOA服务端数据更新。 |
| 第1周 | 下行控制框架 | 搭建VSOA客户端/服务端调用demo；设计VSOA命令到MQTT命令的转换规则、错误码、超时重试策略。 | bridge-downlink代码骨架、命令schema、错误码表、配置文件模板。 | 用模拟VSOA命令成功发布MQTT控制消息。 |
| 第2周 | 实现上行桥接最小版本 | 实现MQTT订阅、payload解析、设备注册、VSOA上行数据接口；为LoRa/Zigbee分别准备适配器。 | 上行bridge代码、adapter接口、schema测试样例、接口文档初稿。 | 模拟LoRa和Zigbee MQTT消息均可转换为VSOA查询结果。 |
| 第2周 | 实现下行桥接最小版本 | 实现VSOA命令接收、命令校验、MQTT发布、回执等待与错误处理；准备LoRa/Zigbee下行topic适配。 | 下行bridge代码、命令schema、配置文件、接口文档初稿。 | 通过VSOA客户端可发布一条可被设备侧脚本识别的控制命令。 |
| 第3周 | 联调MQTT→VSOA上行桥接 | 对接L4/Z3/Z8真实MQTT topic；完成上行适配器、VSOA查询接口、数据缓存/日志；补充桥接指导书。 | L5/Z6上行代码、接口文档、联调记录、PPT主体。 | LoRa和Zigbee至少各1条真实链路可被VSOA端查询。 |
| 第3周 | 联调VSOA→MQTT下行控制 | 对接L6/Z4/Z7真实设备命令；完善命令校验、回执、超时处理；补充下行控制指导书。 | L6/Z6下行代码、命令文档、联调记录、PPT主体。 | VSOA客户端可分别触发LoRa和Zigbee控制动作，并收到状态回执。 |
| 第4周 | 上行桥接课程定稿 | 定稿MQTT→VSOA上行桥接代码和文档；整理LoRa/Zigbee两个适配案例；配合综合场景验收。 | L5/Z6上行最终代码、接口文档、指导书/PPT定稿、API测试记录。 | 上行桥接在LoRa、Zigbee两个方向均有可复现实例。 |
| 第4周 | 下行桥接课程定稿 | 定稿VSOA→MQTT下行桥接代码和文档；整理错误码、配置说明、命令示例；支援演示。 | L6/Z6下行最终代码、接口文档、指导书/PPT定稿、命令测试记录。 | 下行控制在LoRa、Zigbee两个方向均可稳定执行并返回回执。 |

## 交付检查

- [ ] `src/` 中包含可运行代码或代码说明
- [ ] `config/` 中包含配置样例
- [ ] `docs/` 中包含实验指导书
- [ ] `slides/` 中包含实验 PPT
- [ ] `tests/` 中包含测试脚本或测试记录
- [ ] `assets/` 中包含关键截图、接线图或拓扑图
- [ ] 至少 1 名非作者完成交叉复现
