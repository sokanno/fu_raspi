import usb.core
import usb.util
# from usb_pixel_ring_v2 import PixelRing
# from pixel_ring import pixel_ring
from pixel_ring.usb_pixel_ring_v2 import PixelRing

import time
import math
import threading
from queue import Queue
from tuning import Tuning

import matplotlib.pyplot as plt
from matplotlib.widgets import Button

# ------------------------------------------------------------------------------
# 1. パラメータ類 & マイクの配置
# ------------------------------------------------------------------------------
MIC_POSITIONS = {
    1: ( 1.25,  0.25),
    2: ( 1.25, -1.65),
    3: (-1.25, -1.65),
    4: (-1.25,  0.25)
}

# 部屋の境界（例: 横幅=3.8 => ±1.9, 今回ご指定のY範囲）
ROOM_X_MIN = -1.9
ROOM_X_MAX =  1.9

# ご要望により設定
ROOM_Y_MIN = -6.95
ROOM_Y_MAX =  1.35

VAD_IGNORE_DURATION = 0.3      # VAD 検出後は1秒間再検出を抑制
COLLECT_WINDOW      = 0.2      # イベント集約ウィンドウ (秒)
DETECTION_LIFETIME  = 3.0     # 30秒を超えた検出点は自動で消去
MIC_LINE_LENGTH     = 2.0      # マイクから DoA 方向に引く線の長さ(メートル)


# ------------------------------------------------------------------------------
# 2. 音源推定 (直線交点の簡易手法)
# ------------------------------------------------------------------------------
def estimate_source_position(detections):
    """
    detections: [(mic_id, doa_deg), (mic_id, doa_deg), ...]
    戻り値: (x_est, y_est) または None
    """
    if len(detections) < 2:
        return None

    lines = []
    for mic_id, doa_deg in detections:
        if mic_id not in MIC_POSITIONS:
            continue
        mx, my = MIC_POSITIONS[mic_id]
        # -- 角度変換 --
        # 北=270, 東=180, 南=90, 西=0 となるように設定:
        # θ (deg) = (180 + doa_deg) % 360
        theta_deg = (180 + doa_deg) % 360
        theta_rad = math.radians(theta_deg)
        vx = math.cos(theta_rad)
        vy = math.sin(theta_rad)
        lines.append(((mx, my), (vx, vy)))

    if len(lines) < 2:
        return None

    points = []
    for i in range(len(lines)):
        p1, d1 = lines[i]
        for j in range(i+1, len(lines)):
            p2, d2 = lines[j]
            cross = d1[0]*d2[1] - d1[1]*d2[0]
            if abs(cross) < 1e-6:
                continue
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            t = (dx*d2[1] - dy*d2[0]) / cross
            ix = p1[0] + t*d1[0]
            iy = p1[1] + t*d1[1]
            points.append((ix, iy))
    if not points:
        return None

    sx = sum(p[0] for p in points) / len(points)
    sy = sum(p[1] for p in points) / len(points)
    return (sx, sy)


# ------------------------------------------------------------------------------
# 3. マイクスレッド: VAD 検出 -> (mic_id, doa) を main_queue に送信
# ------------------------------------------------------------------------------
def mic_thread_proc(mic_tuning, mic_id, stop_event, main_queue):
    last_detect_time = 0
    while not stop_event.is_set():
        try:
            if mic_tuning.is_voice():
                now = time.time()
                if now - last_detect_time < VAD_IGNORE_DURATION:
                    time.sleep(0.01)
                    continue
                doa = mic_tuning.direction
                print(f"[Mic {mic_id}] Voice detected! DoA={doa}")
                last_detect_time = now

                main_queue.put((time.time(), mic_id, doa))
                time.sleep(VAD_IGNORE_DURATION)
            else:
                time.sleep(0.01)
        except Exception as e:
            print(f"[Mic {mic_id}] Error: {e}")
            time.sleep(0.1)
    print(f"[Mic {mic_id}] Exiting thread.")


# ------------------------------------------------------------------------------
# 4. 集約スレッド + リアルタイム描画
# ------------------------------------------------------------------------------
def aggregator_thread_proc(stop_event, main_queue):
    """
    - 0.2秒ウィンドウで集めた複数マイクの検出から位置推定
    - 検出点をプロット (一定時間で自動消去 or ボタンでクリア)
    - 各マイクの最新の DoA 方向に線を描画 (古い線は消す)
    """

    # --- 図のサイズを大きく (12 x 8 インチ) ---
    plt.ion()
    fig, ax = plt.subplots(figsize=(12, 8))
    plt.subplots_adjust(bottom=0.2)  # 下にボタンを置くため余白

    # (1) 検出点 (赤い点)
    sc = ax.scatter([], [], c='red', label='Detections')

    # (2) マイク位置 (青▲) + 番号ラベル
    mic_ids = sorted(MIC_POSITIONS.keys())
    mic_x = [MIC_POSITIONS[m][0] for m in mic_ids]
    mic_y = [MIC_POSITIONS[m][1] for m in mic_ids]
    ax.scatter(mic_x, mic_y, c='blue', marker='^', label='Mics')
    for i, (mx, my) in enumerate(zip(mic_x, mic_y), start=1):
        ax.text(mx, my + 0.05, f"Mic{i}", color='blue',
                ha='center', va='bottom', fontsize=10)

    # (3) 部屋の境界を破線で
    rect_x = [ROOM_X_MIN, ROOM_X_MIN, ROOM_X_MAX, ROOM_X_MAX, ROOM_X_MIN]
    rect_y = [ROOM_Y_MIN, ROOM_Y_MAX, ROOM_Y_MAX, ROOM_Y_MIN, ROOM_Y_MIN]
    ax.plot(rect_x, rect_y, '--', c='black', label='Room boundary')

    ax.set_xlim(ROOM_X_MIN - 0.5, ROOM_X_MAX + 0.5)
    ax.set_ylim(ROOM_Y_MIN - 0.5, ROOM_Y_MAX + 0.5)
    ax.set_aspect('equal', 'box')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_title('Estimated Sound Source Positions')
    ax.legend()
    ax.grid(True)

    # ----------------------
    # 検出点を保持するリスト [(x, y, t), ...]
    detected_points = []

    # 各マイクの現在の「線」オブジェクトを保持
    mic_lines = {}

    # --- ボタン (Clear) ---
    from matplotlib.widgets import Button
    ax_clear = plt.axes([0.8, 0.05, 0.1, 0.075])
    button_clear = Button(ax_clear, 'Clear')

    def clear_detections(event):
        # ボタンが押されたら検出点を全部消去 + 線も消す
        detected_points.clear()
        nonlocal sc
        sc.remove()
        sc = ax.scatter([], [], c='red', label='Detections')
        # マイク線も消去
        for mid in mic_lines:
            line_obj = mic_lines[mid]
            if line_obj is not None:
                line_obj.remove()
                mic_lines[mid] = None
        plt.draw()

    button_clear.on_clicked(clear_detections)

    plt.draw()
    plt.pause(0.01)

    # ----------------------
    # 集約処理ループ
    while not stop_event.is_set():
        try:
            first_event = main_queue.get(timeout=1.0)
        except:
            continue
        if first_event is None:
            continue

        t0, mic_id_0, doa_0 = first_event
        collected = [(mic_id_0, doa_0)]
        end_time = t0 + COLLECT_WINDOW

        # 0.2秒間、追加の検出を集める
        while time.time() < end_time:
            remain = end_time - time.time()
            if remain <= 0:
                break
            try:
                evt = main_queue.get(timeout=remain)
                if evt:
                    _, mid, doa = evt
                    collected.append((mid, doa))
            except:
                pass

        print(f"\n=== Aggregator ===")
        print(f"  Window started by Mic {mic_id_0}, DoA={doa_0}")
        print(f"  Collected {len(collected)} detections: {collected}")

        # (A) 音源推定
        pos = estimate_source_position(collected)
        if pos is not None:
            x_est, y_est = pos
            # クリップ（壁際まで）
            if x_est < ROOM_X_MIN: x_est = ROOM_X_MIN
            if x_est > ROOM_X_MAX: x_est = ROOM_X_MAX
            if y_est < ROOM_Y_MIN: y_est = ROOM_Y_MIN
            if y_est > ROOM_Y_MAX: y_est = ROOM_Y_MAX
            print(f"  --> Estimated source: (x={pos[0]:.2f}, y={pos[1]:.2f})")
            if (x_est, y_est) != pos:
                print(f"      Clamped -> (x={x_est:.2f}, y={y_est:.2f})")

            # 検出点をリストに格納
            detected_points.append((x_est, y_est, time.time()))
        else:
            print("  --> Could not estimate source (need >=2 angles).")

        print("=== End of aggregator window ===\n")

        # (B) 古い検出点を削除
        now = time.time()
        detected_points = [
            (x, y, t) for (x, y, t) in detected_points
            if (now - t) <= DETECTION_LIFETIME
        ]

        # (C) 「各マイクからの角度に線を引く」: collected に含まれる全マイク分
        for (mid, doa_deg) in collected:
            # 1) 古い線を消す
            old_line = mic_lines.get(mid)
            if old_line is not None:
                old_line.remove()
                mic_lines[mid] = None

            # 2) 新しい線を描画
            if mid in MIC_POSITIONS:
                mx, my = MIC_POSITIONS[mid]
                theta_deg = (180 + doa_deg) % 360  # 北=270, 東=180, 南=90, 西=0
                theta_rad = math.radians(theta_deg)
                vx = math.cos(theta_rad)
                vy = math.sin(theta_rad)

                x2 = mx + MIC_LINE_LENGTH * vx
                y2 = my + MIC_LINE_LENGTH * vy

                line_obj, = ax.plot([mx, x2], [my, y2], c='green', linewidth=2)
                mic_lines[mid] = line_obj

        # (D) グラフ再描画
        sc.remove()
        xs = [p[0] for p in detected_points]
        ys = [p[1] for p in detected_points]
        sc = ax.scatter(xs, ys, c='red', label='Detections')

        plt.draw()
        plt.pause(0.01)


# ------------------------------------------------------------------------------
# 5. メイン処理: マイク列挙 -> スレッド起動 -> 終了待機
# ------------------------------------------------------------------------------
def main():
    devices = usb.core.find(find_all=True)
    mic_tunings = []
    vad_rings    = []     # ← PixelRing インスタンスを入れるリスト
    stop_event = threading.Event()
    main_queue = Queue()

    # デバイス列挙
    for device in devices:
        try:
            if device.idVendor == 0x2886 and device.idProduct == 0x0018:
                # --- マイク調整オブジェクト生成 ---
                mic_tunings.append(Tuning(device))

                # --- PixelRing インスタンス化 & LED 全消灯 ---
                ring = PixelRing(device)
                ring.off()            # リング LED をオフ
                ring.set_vad_led(0)   # 中央 VAD LED もオフ :contentReference[oaicite:0]{index=0}

                vad_rings.append(ring)

                mic_id = len(mic_tunings)
                print(f"Detected ReSpeaker mic -> Mic ID={mic_id}")
        except usb.core.USBError as e:
            print(f"Error accessing device: {e}")


    if not mic_tunings:
        print("No ReSpeaker 4 Mic Array devices found.")
        return

    print(f"Total mic devices found: {len(mic_tunings)}")

    # マイクスレッド起動
    threads = []
    for idx, mic_tuning in enumerate(mic_tunings, start=1):
        t = threading.Thread(
            target=mic_thread_proc,
            args=(mic_tuning, idx, stop_event, main_queue),
            daemon=True
        )
        threads.append(t)
        t.start()

    # 集約スレッド起動
    agg_thread = threading.Thread(
        target=aggregator_thread_proc,
        args=(stop_event, main_queue),
        daemon=True
    )
    agg_thread.start()

    # メインスレッド: Ctrl + C 待ち
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Main thread: received interrupt, stopping all threads...")
        stop_event.set()

    # 終了待機
    for t in threads:
        t.join(timeout=1.0)
    agg_thread.join(timeout=1.0)

    print("Program exited gracefully.")


if __name__ == "__main__":
    main()
