from tuning import Tuning
import usb.core
import usb.util
import time

# 全てのUSBデバイスを取得
devices = usb.core.find(find_all=True)

# 対象のデバイスを検索
target_device = None
for device in devices:
    print("Device:", device)
    print("  ID Vendor:ID Product: {:04x}:{:04x}".format(device.idVendor, device.idProduct))
    print("  Manufacturer:", usb.util.get_string(device, device.iManufacturer))
    print("  Product:", usb.util.get_string(device, device.iProduct))
    print("  Serial Number:", usb.util.get_string(device, device.iSerialNumber))
    print()
    
    # 対象のデバイスかどうかを確認
    if device.idVendor == 0x2886 and device.idProduct == 0x0018:
        target_device = device
        break

# 対象のデバイスが見つかった場合のみ処理を続行
if target_device:
    Mic_tuning = Tuning(target_device)
    print(Mic_tuning.direction)
    while True:
        try:
            print(Mic_tuning.direction)
            time.sleep(0.1)
        except KeyboardInterrupt:
            break
else:
    print("Target device not found.")
