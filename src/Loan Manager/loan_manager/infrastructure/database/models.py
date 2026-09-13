from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer,
    Numeric, String, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LoanModel(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    borrower_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    borrower_group: Mapped[str] = mapped_column(String(255), nullable=False)
    depositor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    depositor_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    giving_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_period: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LoanMetaModel(Base):
    __tablename__ = "loan_meta"

    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    last_order: Mapped[int] = mapped_column(Integer, nullable=False)


class LoanHistoryModel(Base):
    __tablename__ = "loan_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    borrower_name: Mapped[str] = mapped_column(String(255), nullable=False)
    borrower_group: Mapped[str] = mapped_column(String(255), nullable=False)
    depositor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    depositor_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    giving_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paidoff_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ReportModel(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    report_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="Pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    records: Mapped[list[ReportRecordModel]] = relationship(
        "ReportRecordModel", back_populates="report", cascade="all, delete-orphan"
    )


class ReportRecordModel(Base):
    __tablename__ = "report_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(20), ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    reference_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    borrower_name: Mapped[str] = mapped_column(String(255), nullable=False)
    depositor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    depositor_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    giving_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    extension_period: Mapped[int] = mapped_column(Integer, nullable=False)
    extension_period_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interest_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    commission_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    tds_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    chq_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    post_extension_giving_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    post_extension_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paidoff_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    report: Mapped[ReportModel] = relationship("ReportModel", back_populates="records")


class ReportMetaModel(Base):
    __tablename__ = "report_meta"

    report_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    last_order: Mapped[int] = mapped_column(Integer, nullable=False)
