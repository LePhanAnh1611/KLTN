"""Module luyện nói: ASR → đặc trưng → chấm theo rubric → nhận xét phát triển.

Độc lập với DKT (loose coupling): không đọc/ghi KNOWLEDGE_STATE, không sinh
INTERACTION. Muốn nối vào lộ trình học ở giai đoạn sau thì chỉ cần một adapter
đọc `SpeakingAssessment` — không phải sửa gì bên trong module này.

Toàn bộ suy luận chạy LOCAL (faster-whisper + Ollama), không gọi API bên ngoài.
"""
