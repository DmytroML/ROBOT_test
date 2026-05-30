
from aiortc import  VideoStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame
import cv2
import asyncio
from aiohttp import web
import json

# Глобальні змінні для відстеження з'єднань та треку
pcs = set()
local_track = None


# --- 1. НАШ ТРЕК КАМЕРИ ---
class CameraStreamTrack(VideoStreamTrack):
    """
    Асинхронний медіа-трек, з якого aiortc буде "тягнути" кадри камери.
    """
    #kind = "video"  # Обов'язково вказуємо тип треку
    def __init__(self):
        super().__init__()  # Тепер супер-ініціалізація викличе конструктор VideoStreamTrack
        # Open the default laptop camera (0)
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open laptop camera.")

    async def recv(self):
        """
        Цей метод aiortc викликає автоматично, коли мережі потрібен новий кадр.
        """
        # 1. Генеруємо мітки часу для кадру (потрібно для синхронізації WebRTC)
        pts, time_base = await self.next_timestamp()
        # 2. Захоплюємо кадр з веб-камери
        # 2. Захоплюємо кадр з OpenCV (це синхронна операція)
        ret, frame = self.cap.read()

        if not ret:
            raise RuntimeError("Не вдалося зчитати кадр з камери.")        

        # 3. Перетворюємо масив OpenCV (BGR) в об'єкт VideoFrame для aiortc
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base

        # Невелика пауза, щоб не перевантажувати процесор (близько 30 FPS)
        await asyncio.sleep(0.01)
        # Повертаємо готовий для кодування кадр
        return video_frame
    # Метод для очищення ресурсів, коли трек більше не потрібен
    def stop(self):
            # Метод для очищення ресурсів, коли трек більше не потрібен
            super().stop()
            self.cap.release()


# --- 2. ОБРОБНИК СИГНАЛІНГУ (HTTP POST) ---
async def handle_offer(request):
    """
    Цей метод спрацьовує, коли Отримувач надсилає свій Offer (SDP)
    """
    # Отримуємо JSON з Offer від клієнта
    params = await request.json()
    # Створюємо об'єкт RTCSessionDescription з отриманого JSON
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Створюємо нове WebRTC з'єднання для клієнта, що підключився
    pc = RTCPeerConnection()
    # Додаємо це з'єднання до глобального набору для відстеження
    pcs.add(pc)

    print(f"→ Отримано запит на підключення від {request.remote}")

    # Слідкуємо за станом з'єднання
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Стан з'єднання змінено на: {pc.connectionState}")
        if pc.connectionState in ["failed", "closed"]:
            await pc.close()
            pcs.discard(pc)
            print("З'єднання закрите та видалене.")

    # ДОДАЄМО НАШУ КАМЕРУ В ЦЕ З'ЄДНАННЯ
    pc.addTrack(local_track)

    # Встановлюємо отриману від клієнта конфігурацію (Offer)
    await pc.setRemoteDescription(offer)

    # Створюємо нашу відповідь (Answer)
    answer = await pc.createAnswer()
    # Встановлюємо нашу відповідь (Answer) як локальний опис
    await pc.setLocalDescription(answer)

    # Відправляємо Answer назад клієнту у форматі JSON
    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    )

# --- 3. ОЧИЩЕННЯ РЕСУРСІВ ПРИ ЗАКРИТТІ СЕРВЕРА ---
async def on_shutdown(app):
    print("Закриття всіх WebRTC з'єднань...")
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    if local_track:
        local_track.stop()
    print("Камеру вимкнено. Сервер зупинено.")




def main():
    global local_track
    # Ініціалізуємо камеру один раз для всіх майбутніх клієнтів
    local_track = CameraStreamTrack()
    # Створюємо веб-сервер та додаємо маршрут для обробки Offer
    app = web.Application()
    # Створюємо маршрут: Отримувач буде робити POST запит на http://IP_АДРЕСА:8080/offer
    app.router.add_post("/offer", handle_offer)
    # Реєструємо хук для коректного вимкнення
    app.on_shutdown.append(on_shutdown)
    print("Запуск сервера Відправника відео...")
    # host="0.0.0.0" означає, що сервер буде доступний в усій локальній мережі
    web.run_app(app, host="0.0.0.0", port=8080)



# Запускаємо асинхронний цикл подій
if __name__ == "__main__":
    # Запускаємо асинхронний цикл подій
    main()
