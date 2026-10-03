import pytest

from app.providers.base import ListedSecurity
from app.providers.euronext import EuronextEtfListingProvider
from app.providers.listing_source import SourceListing, read_snapshot, write_snapshot
from app.providers.nordic import NordicListingProvider, parse_nordic
from app.providers.six import parse_six_etfs, parse_six_shares
from app.providers.us import UsListingProvider, parse_nasdaq_traded
from app.providers.xetra import XetraListingProvider, find_csv_url, parse_xetra_csv

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



XETRA_CSV = (
    "Market:;XETR\nDate Last Update:;02.10.2026\n"
    "Product Status;Instrument Status;Instrument;ISIN;Product ID;Instrument ID;WKN;Mnemonic;Instrument Type;Currency\n"
    "Active;Active;SAP SE O.N.;DE0007164600;1;2;716460;SAP;CS;EUR\n"
    "Active;Active;ISHS CORE MSCI WORLD;IE00B4L5Y983;3;4;A0RPWH;EUNL;ETF;EUR\n"
    "Active;Active;SOME ETN;DE000A0S9GB0;5;6;A0S9GB;4GLD;ETN;EUR\n"
    "Inactive;Active;OLD AG;DE0001234567;7;8;123456;OLD;CS;EUR\n"
)


def test_parse_xetra_keeps_active_stocks_and_etfs():
    listed = {s.yahoo_ticker: s for s in parse_xetra_csv(XETRA_CSV)}
    assert set(listed) == {"SAP.DE", "EUNL.DE"}
    assert (listed["SAP.DE"].kind, listed["SAP.DE"].market, listed["SAP.DE"].isin) == ("stock", "Xetra", "DE0007164600")
    assert listed["EUNL.DE"].kind == "etf"


def test_xetra_link_is_found_on_the_instruments_page():
    html = '<a href="https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/8d76/data/t7-xetr-allTradableInstruments.csv">CSV</a>'
    assert find_csv_url(html).endswith("t7-xetr-allTradableInstruments.csv")
    pages = {"page": html}

    def get(url):
        return XETRA_CSV if url.endswith(".csv") else pages["page"]

    provider = XetraListingProvider(http_get=get, sleep=lambda s: None)
    provider.min_rows = 1
    assert len(provider.fetch_listed()) == 2


SIX_SHARES = ("Company;ISIN;Symbol;Valor Number;Country;Traded Currency;Trading platform\n"
              "ABB Ltd;CH0012221716;ABBN;1222171;CH;CHF;XSWX\n"
              "3M Company;US88579Y1010;MMM;1405105;US;CHF;XSWX\n")
SIX_ETFS = ("ShortName;ValorSymbol;ISIN;TradingBaseCurrency;SecTypeDesc\n"
            "iShares Core S&P 500;CSSPX;IE00B5BMR087;USD;Exchange Traded Fund\n"
            "Some Fund;SFUND;CH0000000001;CHF;Sponsored Funds\n")


def test_parse_six():
    shares = {s.yahoo_ticker: s for s in parse_six_shares(SIX_SHARES)}
    assert (shares["ABBN.SW"].currency, shares["ABBN.SW"].market) == ("CHF", "SIX Swiss Exchange")
    assert "MMM.SW" in shares  # l'élimination des cotations secondaires se fait à la fusion (tâche 6)
    etfs = parse_six_etfs(SIX_ETFS)
    assert [(e.yahoo_ticker, e.kind, e.currency) for e in etfs] == [("CSSPX.SW", "etf", "USD")]


NORDIC_JSON = ('{"data":{"instrumentListing":{"rows":['
               '{"fullName":"AAK","currency":"SEK","symbol":"AAK","isin":"SE0011337708","assetClass":"SHARES"},'
               '{"fullName":"Acrinova A","currency":"SEK","symbol":"ACRI A","isin":"SE0000000001","assetClass":"SHARES"}]}}}')


def test_parse_nordic():
    listed = parse_nordic(NORDIC_JSON, "STO")
    assert [(s.yahoo_ticker, s.market, s.currency) for s in listed] == [
        ("AAK.ST", "Nasdaq Stockholm", "SEK"), ("ACRI-A.ST", "Nasdaq Stockholm", "SEK")]


def test_nordic_provider_reads_every_market_and_category(monkeypatch):
    import app.providers.nordic as nordic_module

    monkeypatch.setattr(nordic_module, "MIN_MAIN_MARKET", 1)  # réponse de test à 2 lignes
    urls = []

    def get(url):
        urls.append(url)
        return NORDIC_JSON

    provider = NordicListingProvider(http_get=get, sleep=lambda s: None)
    provider.min_rows = 1
    provider.fetch_listed()
    assert len(urls) == 8 and any("market=ICE" in u and "FIRST_NORTH" in u for u in urls)
