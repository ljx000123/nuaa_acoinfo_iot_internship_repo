# 南航-翼辉项目制实习物联网课程开发仓库

本仓库用于统一管理南京航空航天大学与南京翼辉信息技术有限公司项目制实习中的三个物联网方向项目。

## 项目结构

```text
nuaa_winghui_iot_internship_repo/
  01_protocol_bridge/   物联网传输协议桥接组件开发
  02_lora_lorawan/      物联网 LoRa/LoRaWAN 应用案例开发
  03_zigbee/            物联网 ZigBee 应用案例开发
  common/               三个项目共用模板、规范、校标和验收材料
```

## 三个项目

| 编号 | 项目名称 | 主要目标 |
| --- | --- | --- |
| 01 | 物联网传输协议桥接组件开发 | 实现 MQTT 与 VSOA 之间的数据转换、消息转发和接口适配 |
| 02 | 物联网 LoRa/LoRaWAN 应用案例开发 | 完成 LoRa 终端数据采集、网关接入、平台解析和应用展示 |
| 03 | 物联网 ZigBee 应用案例开发 | 完成 ZigBee 组网、数据采集、网关接入和应用展示 |

## 公共交付物

公共模板放在 `common/` 目录：

- `common/templates/实验指导书模板_丰富版.docx`
- `common/templates/实验汇报PPT模板.pptx`
- `common/templates/experiment_guide_template.md`
- `common/templates/ppt_outline_template.md`
- `common/acceptance/acceptance_checklist.md`
- `common/assets/nuaa_logo_cropped.png`

## 协作规则

1. 每个实验单独建立目录，命名格式建议为 `L01_xxx`、`Z01_xxx` 或 `B01_xxx`。
2. 每个实验至少包含 `src/`、`docs/`、`slides/`、`tests/`、`assets/`。
3. 所有实验指导书和 PPT 优先使用 `common/templates/` 中的统一模板。
4. 代码、配置、测试记录和截图应能支持非作者交叉复现。
5. 提交前先更新 README 和验收清单。

