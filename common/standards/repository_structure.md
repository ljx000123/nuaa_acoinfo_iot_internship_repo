# 仓库结构规范

## 总仓库结构

```text
01_protocol_bridge/
02_lora_lorawan/
03_zigbee/
common/
```

## 单个项目目录建议

```text
{project}/
  assets/       项目级图片、截图、素材
  config/       项目级配置文件
  docs/         项目文档、测试文档、说明文档
  examples/     示例数据、示例 payload、演示材料
  experiments/  各实验独立目录
  logs/         项目级运行日志或汇总日志
  scripts/      启动脚本、演示脚本、辅助脚本
  src/          项目源码
  tests/        项目级测试脚本和测试记录
  README.md     项目入口说明
```

## 单个实验目录建议

```text
experiments/{实验编号}_{实验名称}/
  src/        源码
  config/     配置文件
  docs/       实验指导书、说明文档
  slides/     PPT 或汇报材料
  tests/      测试脚本和测试记录
    logs/     本实验的编译日志、烧录日志、串口日志、联调日志
  assets/     接线图、截图、图片素材
  README.md   实验入口说明
```

## 命名规范

| 类型 | 规范 | 示例 |
| --- | --- | --- |
| LoRa 实验 | `Lxx_实验名` | `L05_mqtt_to_vsoa_uplink` |
| ZigBee 实验 | `Zxx_实验名` | `Z06_mqtt_vsoa_bidirectional` |
| 桥接实验 | `Bxx_实验名` | `B01_common_bridge_framework` |
| 图片 | `fig序号_说明.png` | `fig01_mqtt_message.png` |
| 测试记录 | `test_record_日期.md` | `test_record_2026-07-06.md` |

## 提交前检查

- README 是否说明运行方式
- 配置文件是否有示例
- 测试脚本是否能运行
- 指导书是否包含步骤、截图和测试记录
- PPT 是否能用于汇报或授课
- 验收清单是否更新

