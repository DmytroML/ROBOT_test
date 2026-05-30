import asyncio
import cv2
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame

class CameraVideoStreamTrack(MediaStreamTrack):
    """
    A video stream track that captures frames from the laptop camera.
    """
    kind = "video"

    def __init__(self):
        super().__init__()
        # Open the default laptop camera (0)
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open laptop camera.")

    async def recv(self):
        """
        Receive the next video frame. aiortc calls this automatically.
        """
        pts, time_base = await self.next_timestamp()

        # Capture frame-by-frame from webcam
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from camera.")

        # OpenCV uses BGR, but we need to convert it to a PyAV VideoFrame
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base

        # Optional: Add a tiny sleep to prevent overloading the CPU
        await asyncio.sleep(0.03) 
        return video_frame

    def stop(self):
        super().stop()
        self.cap.release()

async def run_webrtc():
    # Initialize the two sides of the WebRTC connection
    pc_sender = RTCPeerConnection()
    pc_receiver = RTCPeerConnection()

    # Create the camera track and add it to the sender connection
    local_track = CameraVideoStreamTrack()
    pc_sender.addTrack(local_track)

    @pc_receiver.on("track")
    def on_track(track):
        """
        Triggered when the receiver gets the video track from the sender.
        """
        if track.kind == "video":
            print("Video track received! Displaying stream...")
            
            async def display_stream():
                while True:
                    try:
                        # Get the decoded frame from the WebRTC stream
                        frame = await track.recv()
                        img = frame.to_ndarray(format="bgr24")
                        
                        # Display the video in an OpenCV window
                        cv2.imshow("WebRTC Received Video", img)
                        
                        # Press 'q' to quit the video window
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            print("Quitting...")
                            break
                    except Exception as e:
                        print(f"Stream ended or error: {e}")
                        break
                
                # Cleanup inside the loop
                cv2.destroyAllWindows()
                local_track.stop()
                await pc_sender.close()
                await pc_receiver.close()
                asyncio.get_event_loop().stop()

            # Run the display loop in the background
            asyncio.ensure_future(display_stream())

    # --- WebRTC Handshake (Signaling) ---
    # 1. Sender creates an Offer
    offer = await pc_sender.createOffer()
    await pc_sender.setLocalDescription(offer)

    # 2. Receiver accepts the Offer
    await pc_receiver.setRemoteDescription(pc_sender.localDescription)

    # 3. Receiver creates an Answer
    answer = await pc_receiver.createAnswer()
    await pc_receiver.setLocalDescription(answer)

    # 4. Sender accepts the Answer
    await pc_sender.setRemoteDescription(pc_receiver.localDescription)

    print("WebRTC connection established. Press 'q' in the video window to stop.")
    
    # Keep the connection alive
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    # Run the async main loop
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_webrtc())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")