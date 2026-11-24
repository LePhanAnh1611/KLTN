from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModelMetric(Base):
    """UC-70 — một lần đo hiệu năng mô hình theo thời gian.

    Khác chỉ số AUC lúc huấn luyện (đo trên tập test cố định): bảng này đo trên
    DỮ LIỆU THẬT của hệ thống, nên mới thấy được mô hình có xuống cấp khi người
    dùng và từ vựng khác dần so với lúc train hay không.
    """

    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(30), nullable=False)   # accuracy | brier | coverage
    value: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
