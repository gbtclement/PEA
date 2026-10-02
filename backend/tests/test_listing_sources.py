import pytest

from app.providers.base import ListedSecurity
from app.providers.euronext import EuronextEtfListingProvider
from app.providers.listing_source import SourceListing, read_snapshot, write_snapshot
from app.providers.us import UsListingProvider, parse_nasdaq_traded

NASDAQ_TRADED = """Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares
Y|AAPL|Apple Inc. - Common Stock|Q|Q|N|100|N|N||AAPL|N
Y|BRK.B|Berkshire Hathaway Inc. New Common Stock|N| |N|100|N||BRK.B|BRK=B|N
Y|SPY|SPDR S&P 500 ETF Trust|P| |Y|100|N||SPY|SPY|N
Y|TSM|Taiwan Semiconductor Manufacturing Company Ltd. American Depositary Shares|N| |N|100|N||TSM|TSM|N
Y|AAC.U|Ares Acquisition Corporation III Units, each consisting of one Class A ordinary share|N| |N|100|N||AAC.U|AAC=|N
Y|AAC.W|Ares Acquisition Corporation III Redeemable warrants|N| |N|100|N||AAC.WS|AAC+|N
Y|AIIA.R|AI Infrastructure Acquisition Corp. Rights, each entitling the holder|N| |N|100|N||AIIAr|AIIA^|N
Y|BAC$K|Bank of America Corporation Depositary Shares Series KK Preferred|N| |N|100|N||BACpK|BAC-K|N
Y|ZZZTX|TXSE Test Stk 5 Common Stock|F| |N|40|Y||ZZZTX|ZZZTX|N
Y|ZVZZT|NASDAQ TEST STOCK|Q|G|N|100|Y|N||ZVZZT|N
Y|CBOE1|Some Cboe Listed Fund|Z| |Y|100|N||CBOE1|CBOE1|N
N|OLD|Not Traded Corp Common Stock|N| |N|100|N||OLD|OLD|N
File Creation Time: 1002202610:02|||||"""


def test_parse_nasdaq_traded_keeps_stocks_and_etfs():
    listed = {s.yahoo_ticker: s for s in parse_nasdaq_traded(NASDAQ_TRADED)}
    assert set(listed) == {"AAPL", "BRK-B", "SPY", "TSM"}
    assert (listed["AAPL"].market, listed["AAPL"].kind, listed["AAPL"].currency, listed["AAPL"].isin) == ("Nasdaq", "stock", "USD", None)
    assert (listed["SPY"].market, listed["SPY"].kind) == ("NYSE Arca", "etf")
    assert listed["BRK-B"].symbol == "BRK.B"


def test_parse_nasdaq_traded_rejects_other_files():
    with pytest.raises(ValueError):
        parse_nasdaq_traded("<html>Access denied</html>")


def test_us_provider_uses_live_file():
    provider = UsListingProvider(http_get=lambda url: NASDAQ_TRADED, sleep=lambda s: None)
    provider.min_rows = 1
    assert len(provider.fetch_listed()) == 4


def test_snapshot_round_trip(tmp_path):
    items = [ListedSecurity(None, "AAPL", "Apple", "Nasdaq", "AAPL", "stock", "USD"),
             ListedSecurity("IE00B4L5Y983", "EUNL", "iShares Core MSCI World", "Xetra", "EUNL.DE", "etf", None)]
    path = tmp_path / "x.csv"
    write_snapshot(path, items)
    assert read_snapshot(path) == items


class Broken(SourceListing):
    source = "broken"
    min_rows = 1

    def fetch_live(self):
        raise ConnectionError("KO")


def test_falls_back_to_snapshot(tmp_path):
    path = tmp_path / "broken.csv"
    write_snapshot(path, [ListedSecurity(None, "A", "A", "Nasdaq", "A", "stock", "USD")])
    assert [s.symbol for s in Broken(snapshot_path=path, sleep=lambda s: None).fetch_listed()] == ["A"]


def test_too_few_rows_uses_snapshot(tmp_path):
    path = tmp_path / "us.csv"
    write_snapshot(path, [ListedSecurity(None, "X", "X", "Nasdaq", "X", "stock", "USD")])
    provider = UsListingProvider(http_get=lambda url: NASDAQ_TRADED, sleep=lambda s: None, snapshot_path=path)
    assert [s.symbol for s in provider.fetch_listed()] == ["X"]  # 4 lignes < 5 000 : fichier tronqué


def test_no_live_and_no_snapshot_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Broken(snapshot_path=tmp_path / "absent.csv", sleep=lambda s: None).fetch_listed()


ETF_CSV = "﻿Name;ISIN;Symbol;Market;Currency;\"Open Price\"\n\"European ETFS, Funds, ETVs, ETNs. Type : ETFs\"\n\"02 Oct 2026\"\n\"All datapoints provided as of end of last active trading day.\"\n" \
    "\"AM ASIP EXJ PEA\";FR0011869312;PAEJ;\"Euronext Paris\";EUR;27.80\n" \
    "\"AB ActEBNDETFP\";LU3322521785;EBND;\"ETF Plus\";EUR;14.776\n"


def test_euronext_etf_provider_posts_the_form():
    seen = {}

    def post(url, data):
        seen.update(url=url, data=data)
        return ETF_CSV

    provider = EuronextEtfListingProvider(http_post=post, sleep=lambda s: None)
    provider.min_rows = 1
    listed = {s.yahoo_ticker: s for s in provider.fetch_listed()}
    assert set(listed) == {"PAEJ.PA", "EBND.MI"}
    assert all(s.kind == "etf" for s in listed.values())
    assert "track/download" in seen["url"] and seen["data"]["args[fe_type]"] == "csv"
