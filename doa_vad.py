from tuning import Tuning
import usb.core
import usb.util
import time

# デバイスを探す
dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)

if dev:
    # Tuningオブジェクトを作成
    Mic_tuning = Tuning(dev)
    print("Device initialized. Waiting for voice...")

    while True:
        try:
            # 音声検出
            if Mic_tuning.is_voice():
                # DoA（角度）を取得して表示
                print("Voice detected! Direction of Arrival (DoA):", Mic_tuning.direction)
            time.sleep(0.1)  # 100msごとにチェック
        except KeyboardInterrupt:
            print("Exiting...")
            break
else:
    print("Target device not found.")
