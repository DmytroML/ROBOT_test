
from aiortc import MediaStreamTrack, VideoStreamTrack
from av import VideoFrame
import cv2
import asyncio


class CameraStreamTrack(VideoStreamTrack):
    """
    Асинхронний медіа-трек, з якого aiortc буде "тягнути" кадри камери.
    """
    kind = "video"  # Обов'язково вказуємо тип треку
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

        # Повертаємо готовий для кодування кадр
        return video_frame
    # Метод для очищення ресурсів, коли трек більше не потрібен
    def stop(self):
            # Метод для очищення ресурсів, коли трек більше не потрібен
            super().stop()
            self.cap.release()

async def main():
    # Створюємо наш новий aiortc-трек
    track = CameraStreamTrack()
    print("Трек створено. Починаємо фейковий прийом кадрів... Натисни Ctrl+C для виходу.")
    try:
        while True:
                # Симулюємо те, що робить aiortc під капотом: "тягне" кадр
                video_frame = await track.recv()
                
                # Щоб показати його через OpenCV, конвертуємо назад у NumPy масив
                img = video_frame.to_ndarray(format="bgr24")
                
                cv2.imshow('Testing aiortc Track', img)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    except KeyboardInterrupt as e:
            print("\nЗупинка тесту.",e)
    finally:
            # Прибираємо за собою
            track.stop()
            cv2.destroyAllWindows()
            

# Запускаємо асинхронний цикл подій
if __name__ == "__main__":
    # Запускаємо асинхронний цикл подій
    asyncio.run(main())
