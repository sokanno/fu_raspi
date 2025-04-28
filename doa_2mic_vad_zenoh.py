from tuning import Tuning
import usb.core
import usb.util
import time
import zenoh

# Zenohの初期化
session = zenoh.open(zenoh.Config())
publishers = []

# 全てのUSBデバイスを取得
devices = usb.core.find(find_all=True)

# 対象のマイクデバイスを管理するリスト
mic_tunings = []

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
            publishers.append(session.declare_publisher(f"mic/{mic_id}/doa"))
            print(f"Mic device {mic_id} added to the list and Zenoh publisher created.")
    except usb.core.USBError as e:
        print("Error accessing device:", e)

# マイクが1台以上見つかった場合のみ処理を続行
if mic_tunings:
    print(f"Total mic devices found: {len(mic_tunings)}")
    try:
        while True:
            for idx, mic_tuning in enumerate(mic_tunings):
                try:
                    # 音声検出があればDoAを取得して表示
                    if mic_tuning.is_voice():
                        doa = mic_tuning.direction
                        print(f"Mic {idx + 1}: Voice detected! Direction of Arrival (DoA): {doa}")
                        # Zenohでデータをパブリッシュ
                        publishers[idx].put(f"{doa}")
                except Exception as e:
                    print(f"Error reading from Mic {idx + 1}: {e}")
            time.sleep(0.01)  # チェック間隔を設定
    except KeyboardInterrupt:
        print("Exiting gracefully...")
else:
    print("No target mic devices found.")

# Zenohのクリーンアップ
session.close()
