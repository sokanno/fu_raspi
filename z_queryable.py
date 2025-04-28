import zenoh
import random

def query_handler(sample):
    # クエリのキー（selector）を文字列として取得
    selector = str(sample.selector)
    print(f"Received Query: {selector}")

    # MACアドレスを抽出
    if selector.startswith("id/"):
        mac_address = selector[3:]  # "id/" を除去してMACアドレスを取得
        print(f"Identified MAC Address: {mac_address}")

        # 送信元のMACアドレス（コロンなし形式）
        expected_mac = "E89F6D09C758"  # コロンなしのMACアドレス形式

        # MACアドレスをコロンなしの形式に変換して比較
        normalized_mac = mac_address.replace(":", "")
        if normalized_mac == expected_mac:
            print(f"Returning data for MAC: {mac_address}")
            # 1~100のランダムな整数を生成
            response_data = random.randint(1, 100)
            response = str(response_data).encode("utf-8")
        else:
            response = f"Unknown device with MAC {mac_address}.".encode("utf-8")
    else:
        response = "Invalid query format.".encode("utf-8")

    # レスポンスをログ出力
    print(f"Response: {response}")
    return response

def main():
    # Zenoh Configを生成
    config = zenoh.Config()
    
    # Zenoh セッションを初期化
    session = zenoh.open(config)
    print("Zenoh session opened.")

    # Queryableを登録
    queryable = session.declare_queryable("id/**", query_handler)
    print("Queryable declared.")

    try:
        print("Waiting for queries...")
        while True:
            pass  # 無限ループで待機
    except KeyboardInterrupt:
        print("Stopping Queryable...")
    finally:
        queryable.undeclare()
        session.close()

if __name__ == "__main__":
    main()
