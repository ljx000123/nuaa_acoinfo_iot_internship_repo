# vsoa/ — VSOA Python SDK v1.0.4

## 概述

本目录包含 **VSOA Python SDK v1.0.4**，已针对 Python 3.8 进行兼容性处理。协议逻辑保持不变，许可证见 `LICENSE` 文件。

VSOA（Virtual Service-Oriented Architecture）是一个轻量级 RPC 框架，支持：
- 同步 RPC 调用（`client.fetch()`）
- 服务端方法注册（`@server.command()`）
- Pub/Sub 发布订阅（`server.publish()` + `client.subscribe()`）
- Datagram 单向消息（`client.datagram()`）

## 为什么内置于仓库

1. **版本锁定** — SDK v1.0.4 经过充分测试与项目兼容，避免 pip 安装版本不一致
2. **Python 3.8 兼容** — 已处理类型注解兼容性问题
3. **加载优先级** — 从仓库根目录启动时，`vsoa/` 优先于系统 pip 包加载
4. **零外部依赖** — VSOA SDK 仅依赖 Python 标准库，无需额外安装

## 核心模块

| 文件 | 用途 |
|------|------|
| `server.py` | VSOA Server：`@server.command` 注册 handler + `server.publish()` 发布 |
| `client.py` | VSOA Client：`client.connect()` + `client.fetch()` + `client.subscribe()` + `client.datagram()` |
| `parser.py` | VSOA 协议解析（URL、Payload、序列化） |
| `interface.py` | 网络接口抽象层 |
| `events.py` | 事件循环与回调管理 |
| `workqueue.py` | 工作队列（线程池） |
| `timer.py` | 定时器管理 |
| `sockopt.py` | Socket 选项配置 |
| `sslwork.py` | SSL/TLS 支持 |
| `position.py` | 流数据位置追踪 |

## 关键 API

### Server

```python
import vsoa

server = vsoa.Server({"name": "my-server", "version": "1.0"})

# 注册 RPC handler
@server.command("/my/endpoint")
def handler(cli, request, payload):
    # cli.reply(seqno, payload) — 发送回执
    cli.reply(request.seqno(), vsoa.Payload(param={"status": "ok"}))

# 发布事件
server.publish("/my/event", vsoa.Payload(param={"data": "hello"}))

# 启动
server.run("0.0.0.0", 3001)
```

### Client

```python
import vsoa

client = vsoa.Client({"name": "my-client"})
client.connect("vsoa://127.0.0.1:3001")

# 同步 RPC 调用（阻塞等待回执）
reply = client.fetch("/my/endpoint", vsoa.Payload(param={"cmd": "hello"}))

# 订阅 Pub/Sub
client.subscribe("/my/event", lambda url, payload: print(payload))

# 单向 datagram（不等待回执）
client.datagram("/ctrl/cmd", vsoa.Payload(param={"cmd": "hello"}))

# 运行事件循环
client.run()
```

## 关键发现与注意事项

1. **`@server.command()` handler 不会自动发送 reply** — 必须手动调用 `cli.reply(seqno, payload)`
2. **`client.fetch()` 需要后台线程运行 `client.run()`** 才能收到响应
3. **`fetch()` 传参必须使用 `vsoa.Payload(param=cmd)`**，纯 dict 会被丢弃
4. **`@server.command` handler 签名是 `(cli, request, payload)`** 三个参数
5. **`vsoa.Client` 没有 `publish()` 方法** — publish 是 `vsoa.Server` 的方法
