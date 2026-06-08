import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LanguageEnum(enum.StrEnum):
    ZH = "zh"
    EN = "en"


class SentimentEnum(enum.StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class UrgencyEnum(enum.StrEnum):
    FLASH = "flash"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceTypeEnum(enum.StrEnum):
    RSS = "rss"
    NEWSAPI = "newsapi"
    JIN10 = "jin10"
    FUTU = "futu"
    EDGAR = "edgar"
    FRED = "fred"
    AKSHARE = "akshare"
    YFINANCE = "yfinance"


def _uuid() -> str:
    return str(uuid.uuid4())


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_type: Mapped[SourceTypeEnum] = mapped_column(Enum(SourceTypeEnum), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[LanguageEnum] = mapped_column(Enum(LanguageEnum), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    title_zh: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    extra: Mapped[dict | None] = mapped_column(JSONB)
    is_relevant: Mapped[bool | None] = mapped_column(Boolean, default=True)
    duplicate_of_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("news_articles.id", ondelete="SET NULL"), index=True
    )

    duplicate_of = relationship(
        "NewsArticle", remote_side=[id], backref="syndicated_articles"
    )

    __table_args__ = (Index("ix_news_published", "published_at", "source_type"),)


class EarningsReport(Base):
    __tablename__ = "earnings_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(500))
    source_type: Mapped[SourceTypeEnum] = mapped_column(Enum(SourceTypeEnum), nullable=False)
    period: Mapped[str | None] = mapped_column(String(20))
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    eps_estimate: Mapped[float | None] = mapped_column(Float)
    revenue_estimate: Mapped[float | None] = mapped_column(Float)
    report_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filing_url: Mapped[str | None] = mapped_column(String(2048))
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("ticker", "period", "fiscal_year", name="uq_earnings_ticker_period"),
        Index("ix_earnings_ticker_date", "ticker", "report_date"),
    )


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    indicator_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    indicator_name: Mapped[str] = mapped_column(String(500), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="US")
    source_type: Mapped[SourceTypeEnum] = mapped_column(Enum(SourceTypeEnum), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("indicator_code", "period", name="uq_macro_indicator_period"),
        Index("ix_macro_code_ts", "indicator_code", "timestamp"),
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("news_articles.id", ondelete="SET NULL"), index=True
    )
    urgency: Mapped[UrgencyEnum | None] = mapped_column(Enum(UrgencyEnum))
    sentiment: Mapped[SentimentEnum | None] = mapped_column(Enum(SentimentEnum))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    topics: Mapped[list | None] = mapped_column(JSONB)
    entities: Mapped[dict | None] = mapped_column(JSONB)
    companies_mentioned: Mapped[list | None] = mapped_column(JSONB)
    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    impact_assessment: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String(100))
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    article = relationship("NewsArticle", backref="analysis")


class MarketWire(Base):
    __tablename__ = "market_wires"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_type: Mapped[SourceTypeEnum] = mapped_column(Enum(SourceTypeEnum), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    language: Mapped[LanguageEnum] = mapped_column(Enum(LanguageEnum), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=0)
    related_symbols: Mapped[list | None] = mapped_column(JSONB)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_market_wire_published", "published_at", "importance"),)


class JobConfig(Base):
    __tablename__ = "job_configs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), default="interval", nullable=False)  # "interval" or "cron"
    schedule_value: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "30" or "0 0 * * *"
    last_run_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[str | None] = mapped_column(String(20))  # "success" or "failed"
    last_run_message: Mapped[str | None] = mapped_column(Text)


class SubjectTypeEnum(enum.StrEnum):
    TICKER = "ticker"
    MACRO = "macro"
    THEME = "theme"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    type: Mapped[SubjectTypeEnum] = mapped_column(Enum(SubjectTypeEnum), nullable=False)
    tags: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    insights = relationship("Insight", back_populates="subject", cascade="all, delete-orphan")


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_name: Mapped[str] = mapped_column(String(500), nullable=False)
    summary_en: Mapped[str] = mapped_column(Text, nullable=False)
    summary_zh: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[UrgencyEnum] = mapped_column(Enum(UrgencyEnum), default=UrgencyEnum.MEDIUM, nullable=False)
    sentiment: Mapped[SentimentEnum] = mapped_column(Enum(SentimentEnum), default=SentimentEnum.NEUTRAL, nullable=False)
    tags: Mapped[list | None] = mapped_column(JSONB)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    subject = relationship("Subject", back_populates="insights")
    facts = relationship("InsightFact", back_populates="insight", cascade="all, delete-orphan")


class InsightFact(Base):
    __tablename__ = "insight_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    insight_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insights.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bullet_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    bullet_text_zh: Mapped[str] = mapped_column(Text, nullable=False)
    source_article_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("news_articles.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    insight = relationship("Insight", back_populates="facts")
    source_article = relationship("NewsArticle")


class EntityGlossary(Base):
    __tablename__ = "entity_glossary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    term_en: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    term_zh: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="company")  # "company", "theme", "institution", "person"
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    summary_en: Mapped[str] = mapped_column(Text, nullable=False)
    summary_zh: Mapped[str] = mapped_column(Text, nullable=False)
    key_takeaways_en: Mapped[list | None] = mapped_column(JSONB)
    key_takeaways_zh: Mapped[list | None] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # "scheduled" or "manual"
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # "running", "success", "failed"
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)