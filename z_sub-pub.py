import zenoh
import random

def main():
    # Zenoh Configを生成
    config = zenoh.Config()
    session = zenoh.open(config)
    print("Zenoh session opened.")

    # Subscribeのコールバック関数
    def callback(sample):
        try:
            # payloadをバイト配列に変換
            payload = bytes(sample.payload)
            print(f"Received: {payload.decode('utf-8')} on {sample.key_expr}")

            # key_exprを文字列に変換
            key_expr = str(sample.key_expr)
            mac_address = key_expr.split('/')[-1]  # MACアドレスを抽出

            # ランダムなデータ生成
            id_value = random.randint(1, 100)
            x_value = random.uniform(-10.0, 10.0)
            y_value = random.uniform(-10.0, 10.0)

            # 各キーにデータをpublish
            session.put(f"{mac_address}/id", str(id_value).encode("utf-8"))
            session.put(f"{mac_address}/x", str(x_value).encode("utf-8"))
            session.put(f"{mac_address}/y", str(y_value).encode("utf-8"))

            print(f"Published: {id_value} to {mac_address}/id")
            print(f"Published: {x_value} to {mac_address}/x")
            print(f"Published: {y_value} to {mac_address}/y")
        except Exception as e:
            print(f"Error in callback: {e}")

    # Subscribe
    key_expr = "id/**"
    session.declare_subscriber(key_expr, callback)
    print(f"Subscribed to {key_expr}")

    try:
        print("Waiting for incoming messages...")
        while True:
            pass  # 無限ループで待機
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        session.close()

if __name__ == "__main__":
    main()
