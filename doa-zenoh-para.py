from tuning import Tuning
import usb.core
import usb.util
import time
import zenoh
import threading

# Zenohの初期化
session = zenoh.open(zenoh.Config())
publishers = []

# 全てのUSBデバイスを取得
devices = usb.core.find(find_all=True)

# 対象のマイクデバイスを管理するリスト
mic_tunings = []

# 停止フラグを作成
stop_event = threading.Event()

# マイクごとの処理を行うスレッド関数
def process_mic(mic_tuning, mic_id, publisher, stop_event):
    try:
        while not stop_event.is_set():
            try:
                if mic_tuning.is_voice():
                    doa = mic_tuning.direction
                    print(f"Mic {mic_id}: Voice detected! Direction of Arrival (DoA): {doa}")
                    publisher.put(f"{doa}")
                    # 検出後、このスレッドを0.5秒休止
                    time.sleep(0.5)
                else:
                    # 検出がない場合は短い間隔でチェック
                    time.sleep(0.01)
            except Exception as e:
                print(f"Error reading from Mic {mic_id}: {e}")
                time.sleep(0.1)  # エラー時も少し待機
    except KeyboardInterrupt:
        print(f"Mic {mic_id} thread interrupted.")
    print(f"Mic {mic_id} thread exiting gracefully...")

# USBデバイスの列挙とフィルタリング
for device in devices:
    try:
        print("Device detected:")
        print(f"  ID Vendor:ID Product: {device.idVendor:04x}:{device.idProduct:04x}")
        
        # 各フィールドの取得時にエラーを無視
        try:
            manufacturer = usb.util.get_string(device, device.iManufacturer)
        except (ValueError, usb.core.USBError):
            manufacturer = "Unknown"
        
        try:
            product = usb.util.get_string(device, device.iProduct)
        except (ValueError, usb.core.USBError):
            product = "Unknown"
        
        try:
            serial_number = usb.util.get_string(device, device.iSerialNumber)
        except (ValueError, usb.core.USBError):
            serial_number = "Unknown"
        
        print("  Manufacturer:", manufacturer)
        print("  Product:", product)
        print("  Serial Number:", serial_number)
        print()
        
        # 対象のデバイスかどうかを確認
        if device.idVendor == 0x2886 and device.idProduct == 0x0018:
            mic_tunings.append(Tuning(device))
            mic_id = len(mic_tunings)  # マイクの番号（1から始まる）
            publisher = session.declare_publisher(f"mic/{mic_id}/doa")
            publishers.append(publisher)
            print(f"Mic device {mic_id} added to the list and Zenoh publisher created.")
    except usb.core.USBError as e:
        print("Error accessing device:", e)

# マイクが1台以上見つかった場合のみ処理を続行
if mic_tunings:
    print(f"Total mic devices found: {len(mic_tunings)}")
    
    # マイクごとにスレッドを起動
    threads = []
    for idx, mic_tuning in enumerate(mic_tunings):
        mic_id = idx + 1
        publisher = publishers[idx]
        thread = threading.Thread(target=process_mic, args=(mic_tuning, mic_id, publisher, stop_event))
        threads.append(thread)
        thread.start()
    
    # メインスレッドで他の処理を維持
    try:
        while True:
            time.sleep(1)  # メインスレッドを維持するためのスリープ
    except KeyboardInterrupt:
        print("Main thread received interrupt. Stopping threads...")
        stop_event.set()  # 全スレッドに停止フラグを通知

    # 全スレッドが終了するのを待機
    for thread in threads:
        thread.join()

else:
    print("No target mic devices found.")

# Zenohのクリーンアップ
session.close()
print("Program exited gracefully.")
