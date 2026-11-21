
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    func
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    guest_token = Column(String(100), unique=True, nullable=True, index=True)

    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="doctor")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analyses = relationship("Analysis", back_populates="user")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    age = Column(Integer, nullable=True)
    sex = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analyses = relationship("Analysis", back_populates="patient")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)

    analysis_code = Column(
        String(30),
        unique=True,
        nullable=True,
        index=True
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)

    modality = Column(String(50), nullable=False)
    task = Column(String(100), nullable=False)
    filename = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="analyses")
    patient = relationship("Patient", back_populates="analyses")
    result = relationship(
        "AnalysisResult",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan"
    )
    report = relationship(
        "Report",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan"
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id"),
        unique=True,
        nullable=False
    )

    prediction = Column(String(150), nullable=True)
    confidence = Column(Float, nullable=True)
    result_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analysis = relationship("Analysis", back_populates="result")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id"),
        unique=True,
        nullable=False
    )

    report_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analysis = relationship("Analysis", back_populates="report")
