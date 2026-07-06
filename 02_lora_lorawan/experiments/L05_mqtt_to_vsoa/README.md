# L5 LoRa MQTT→VSOA上行协议转换实验

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 方向 | LoRa |
| 类型 | 协议转换 |
| 难度 | 中 |
| 主要设备 | LoRaWAN网关、MQTT broker、VSOA服务端 |
| 协议/接口 | MQTT→VSOA |
| 负责人 | 辛澳翔 |
| 协作人 | 熊依萱、范文尧、公共测试负责人 |
| 成果物 | 代码+指导书+PPT |

## 实验目标

订阅LoRa上行topic，将payload转换为VSOA服务数据模型并提供查询接口

## 备注

桥接组提供公共转换框架

## 目录结构

```text
L05_mqtt_to_vsoa/
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
| 第2周 | 实现上行桥接最小版本 | 实现MQTT订阅、payload解析、设备注册、VSOA上行数据接口；为LoRa/Zigbee分别准备适配器。 | 上行bridge代码、adapter接口、schema测试样例、接口文档初稿。 | 模拟LoRa和Zigbee MQTT消息均可转换为VSOA查询结果。 |
| 第3周 | 联调MQTT→VSOA上行桥接 | 对接L4/Z3/Z8真实MQTT topic；完成上行适配器、VSOA查询接口、数据缓存/日志；补充桥接指导书。 | L5/Z6上行代码、接口文档、联调记录、PPT主体。 | LoRa和Zigbee至少各1条真实链路可被VSOA端查询。 |
| 第4周 | 上行桥接课程定稿 | 定稿MQTT→VSOA上行桥接代码和文档；整理LoRa/Zigbee两个适配案例；配合综合场景验收。 | L5/Z6上行最终代码、接口文档、指导书/PPT定稿、API测试记录。 | 上行桥接在LoRa、Zigbee两个方向均有可复现实例。 |

## 交付检查

- [ ] `src/` 中包含可运行代码或代码说明
- [ ] `config/` 中包含配置样例
- [ ] `docs/` 中包含实验指导书
- [ ] `slides/` 中包含实验 PPT
- [ ] `tests/` 中包含测试脚本或测试记录
- [ ] `assets/` 中包含关键截图、接线图或拓扑图
- [ ] 至少 1 名非作者完成交叉复现
