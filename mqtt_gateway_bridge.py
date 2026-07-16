import paho.mqtt.client as mqtt


# ==========================
# MQTT配置
# ==========================

# T113上的ChirpStack MQTT
SOURCE = "192.168.137.118"


# PC局域网MQTT Broker
TARGET = "192.168.3.219"


PORT = 1883


# ChirpStack原始Topic
SOURCE_TOPIC = (
    "application/+/device/+/event/up"
)


# 统一后的Topic
TARGET_TOPIC = (
    "bridge/uplink/lora/lora_env_01/data"
)



# ==========================
# 目标MQTT连接
# ==========================

target = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)


try:

    target.connect(
        TARGET,
        PORT,
        60
    )

    target.loop_start()


    print(
        "Target MQTT connected:",
        TARGET
    )


except Exception as e:

    print(
        "Target MQTT failed:",
        e
    )

    exit()



# ==========================
# 源MQTT回调
# ==========================

def on_connect(
        client,
        userdata,
        flags,
        rc
):

    if rc == 0:

        print(
            "Source MQTT connected:",
            SOURCE
        )


        client.subscribe(
            SOURCE_TOPIC,
            qos=1
        )


        print(
            "Subscribe:",
            SOURCE_TOPIC
        )


    else:

        print(
            "Source MQTT failed:",
            rc
        )



# ==========================
# 转发消息
# ==========================

def on_message(
        client,
        userdata,
        msg
):

    print(
        "Receive:",
        msg.topic
    )


    result = target.publish(
        TARGET_TOPIC,
        msg.payload,
        qos=1
    )


    if result.rc == 0:

        print(
            "Forward success ->",
            TARGET_TOPIC
        )


    else:

        print(
            "Forward failed:",
            result.rc
        )



# ==========================
# 源MQTT连接
# ==========================

source = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)


source.on_connect = on_connect
source.on_message = on_message



source.connect(
    SOURCE,
    PORT,
    60
)


print(
    "MQTT Gateway Bridge Running..."
)


source.loop_forever()