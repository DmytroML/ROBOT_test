
from aiortc import RTCPeerConnection, RTCSessionDescription


import asyncio
import cv2
import aiohttp

# Конфігурація: вкажи IP-адресу пристрою-відправника.
# Якщо запускаєш обох на одному комп'ютері, залиш "localhost".
SENDER_IP = "localhost" 
SENDER_URL = f"http://{SENDER_IP}:8080/offer"


# 1. Створюємо абсолютно звичайну функцію (без жодних @ зверху)
def my_track_handler(track):
    if track.kind == "video":
        print("→ Успіх! Відео-трек отримано з мережі.")
        
        async def display_stream():
            while True:
                try:
                    frame = await track.recv()
                    img = frame.to_ndarray(format="bgr24")
                    cv2.imshow("WebRTC Remote Camera Stream", img)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                except Exception as e:
                    break
            cv2.destroyAllWindows()
            await pc.close()

        asyncio.ensure_future(display_stream())

#2. Створюємо асинхронну функцію, яка буде виконуватися при запуску скрипта
async def run_receiver():

    # 1. Створюємо об'єкт WebRTC з'єднання
    pc = RTCPeerConnection()
    print("→ WebRTC Peer Connection створено.")

    # 2. Налаштовуємо слухача подій: що робити, коли прилетить відео-трек
    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            print("→ Успіх! Відео-трек отримано з мережі. Відкриваємо вікно...")
            
            # Внутрішня асинхронна функція для постійного виведення кадрів
            async def display_stream():
                while True:
                    try:
                        # Чекаємо і забираємо декодований кадр
                        frame = await track.recv()
                        # Конвертуємо у звичний для OpenCV формат матриці
                        img = frame.to_ndarray(format="bgr24")
                        
                        # Показуємо відео у вікні OpenCV
                        cv2.imshow("WebRTC Remote Camera Stream", img)
                        
                        # Зупинка на клавішу 'q'
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            print("Закриття трансляції...")
                            break
                    except Exception as e:
                        print(f"Стрім перервано: {e}")
                        break
                
                # Прибираємо за собою
                cv2.destroyAllWindows()
                await pc.close()
                asyncio.get_event_loop().stop()

            # Запускаємо відображення у фоні, щоб не блокувати головний цикл
            asyncio.ensure_future(display_stream())


    # --- КРОК СИГНАЛІНГУ (КЛІЄНТСЬКА СТОРОНА) ---
    # Нам потрібно створити Offer (пропозицію) без власного медіа-треку.
    # aiortc автоматично зрозуміє, що ми хочемо тільки приймати відео, 
    # оскільки ми не викликали pc.addTrack(), але налаштували слухача @pc.on("track").
    
    
    # Створюємо пустий "приймач" для відео, щоб повідомити серверу, що ми чекаємо на потік
    pc.addTransceiver("video", direction="recvonly")

    print("Генерація Offer (SDP)...")
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Пакуємо наш Offer у JSON формат
    payload = {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }

    print(f"Відправка POST запиту на сервер {SENDER_URL}...")
    try:
        # Відкриваємо HTTP-сесію для відправки JSON
        async with aiohttp.ClientSession() as session:
            async with session.post(SENDER_URL, json=payload) as response:
                if response.status != 200:
                    print(f"Помилка сервера: {response.status}")
                    await pc.close()
                    return

                # Отримуємо Answer (відповідь) від сервера
                answer_data = await response.json()
                print("→ Отримано Answer від сервера. Встановлюємо з'єднання...")
                
                # Прописуємо конфігурацію сервера в наш WebRTC об'єкт
                answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
                await pc.setRemoteDescription(answer)

    except Exception as e:
        print(f"Не вдалося підключитися до сервера: {e}")
        await pc.close()
        return

    print("З'єднання встановлено за допомогою WebRTC. Очікуємо перші кадри...")
    
    # Тримаємо клієнтський скрипт активним
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(run_receiver())
    except KeyboardInterrupt:
        print("\nКлієнт зупинений.")