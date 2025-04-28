from tuning import Tuning
import usb.core
import usb.util
import time

# 全てのUSBデバイスを取得
devices = usb.core.find(find_all=True)

# 対象のデバイスを検索し、管理するリストを作成
mic_tunings = []

for device in devices:
    try:
        print("Device:", device)
        print("  ID Vendor:ID Product: {:04x}:{:04x}".format(device.idVendor, device.idProduct))
        print("  Manufacturer:", usb.util.get_string(device, device.iManufacturer))
        print("  Product:", usb.util.get_string(device, device.iProduct))
        print("  Serial Number:", usb.util.get_string(device, device.iSerialNumber))
        print()
        
        # 対象のデバイスかどうかを確認
        if device.idVendor == 0x2886 and device.idProduct == 0x0018:
            mic_tunings.append(Tuning(device))
    except usb.core.USBError as e:
        print("Error accessing device:", e)

# デバイスが1台以上見つかった場合のみ処理を続行
if mic_tunings:
    try:
        while True:
            for idx, mic_tuning in enumerate(mic_tunings):
                try:
                    print(f"Device {idx} Direction: {mic_tuning.direction}")
                except Exception as e:
                    print(f"Error reading from device {idx}: {e}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Exiting...")
else:
    print("No target devices found.")
