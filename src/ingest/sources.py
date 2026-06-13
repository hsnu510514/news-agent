from __future__ import annotations

from src.core.config import settings


def rsshub_url(path: str) -> str:
    """Build a RSSHub feed URL from base URL, optional path params, and access key."""
    base = settings.RSSHUB_BASE_URL.rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    if settings.RSSHUB_ACCESS_KEY:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={settings.RSSHUB_ACCESS_KEY}"
    return url


def get_rss_feeds() -> dict[str, list[dict[str, str]]]:
    return {
        "zh": [
            {"name": "36Kr", "url": "https://36kr.com/feed", "category": "tech_business"},
            {"name": "华尔街见闻", "url": "https://wallstreetcn.com/rss", "category": "finance"},
            {"name": "新浪财经", "url": "https://finance.sina.com.cn/7x24/roll.d.html", "category": "finance"},
            {"name": "第一财经", "url": "https://www.yicai.com/feed", "category": "finance"},
            {"name": "财新网", "url": rsshub_url("caixin/latest"), "category": "finance"},
        ],
        "en": [
            {"name": "Bloomberg", "url": "https://feeds.bloomberg.com/markets/news.rss", "category": "finance"},
            {
                "name": "CNBC Business",
                "url": "https://search.cnbc.com/rsps/search/actions/rss.action?outputfile=cnbcsearch&categories=exclude:redit,dod,pressrelease&pubtimezone=ET&sort=date&referenceLocation=&partnerId=2",
                "category": "finance",
            },
            {
                "name": "CNBC Markets",
                "url": "https://search.cnbc.com/rsps/search/actions/rss.action?outputfile=cnbcsearch&categories=exclude:redit,dod,pressrelease&pubtimezone=ET&sort=date&partnerId=2&querystring=markets",
                "category": "market",
            },
            {"name": "FT Markets", "url": "https://www.ft.com/markets?format=rss", "category": "market"},
            {"name": "Economics - Economist", "url": "https://www.economist.com/economics/rss.xml", "category": "macro"},
        ],
    }


# Backward-compatible module-level export
RSS_FEEDS = get_rss_feeds()

MACRO_INDICATORS = {
    "US": [
        {"code": "GDP", "name": "US GDP Growth Rate", "fred_id": "A191RL1Q225SBEA"},
        {"code": "CPI", "name": "US CPI (Consumer Price Index)", "fred_id": "CPIAUCSL"},
        {"code": "UNEMPLOYMENT", "name": "US Unemployment Rate", "fred_id": "UNRATE"},
        {"code": "INTEREST_RATE", "name": "US Federal Funds Rate", "fred_id": "FEDFUNDS"},
        {"code": "M2", "name": "US M2 Money Supply", "fred_id": "M2SL"},
        {"code": "PMI", "name": "US ISM Manufacturing PMI", "fred_id": "IPMAN"},
        {"code": "RETAIL_SALES", "name": "US Retail Sales", "fred_id": "RSAFS"},
        {"code": "HOUSE_PRICE", "name": "US House Price Index", "fred_id": "CSUSHPISA"},
        {"code": "TRADE_BALANCE", "name": "US Trade Balance", "fred_id": "BOPGSTB"},
        {"code": "NONFARM", "name": "US Non-Farm Payrolls", "fred_id": "PAYEMS"},
    ],
    "CN": [
        {"code": "GDP_CN", "name": "China GDP Growth Rate", "source": "akshare"},
        {"code": "CPI_CN", "name": "China CPI", "source": "akshare"},
        {"code": "PPI_CN", "name": "China PPI", "source": "akshare"},
        {"code": "PMI_CN", "name": "China Manufacturing PMI", "source": "akshare"},
        {"code": "M2_CN", "name": "China M2 Money Supply", "source": "akshare"},
        {"code": "INTEREST_RATE_CN", "name": "China LPR", "source": "akshare"},
    ],
}

TRACKED_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "BRK-B",
    "JPM", "V", "JNJ", "WMT", "PG", "MA", "HD", "UNH",
    "BAC", "XOM", "DIS", "NFLX",
    "0700.HK", "9988.HK", "0005.HK",
    "600519.SS", "000858.SZ", "601318.SS",
]
