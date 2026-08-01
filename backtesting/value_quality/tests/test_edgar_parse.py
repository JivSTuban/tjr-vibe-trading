import pandas as pd
from backtesting.value_quality.edgar import pit_finyears

def _facts():
    # minimal 2-annual-year companyfacts shape: {"facts":{"us-gaap":{TAG:{"units":{"USD":[...]}}}}}
    def pts(tag_vals):
        return {"units":{"USD":[
            {"end":"2013-12-31","val":tag_vals[0],"form":"10-K","fp":"FY","filed":"2014-02-20"},
            {"end":"2014-12-31","val":tag_vals[1],"form":"10-K","fp":"FY","filed":"2015-02-20"},
        ]}}
    gaap = {t: pts(v) for t, v in {
        "NetIncomeLoss":[10,100], "Assets":[1000,1000],
        "NetCashProvidedByUsedInOperatingActivities":[5,150], "Revenues":[800,900],
        "GrossProfit":[240,360], "AssetsCurrent":[300,400], "LiabilitiesCurrent":[250,150],
        "LongTermDebt":[200,100], "CommonStockSharesOutstanding":[50,50],
        "StockholdersEquity":[500,600], "OperatingIncomeLoss":[120,170],
        "DepreciationDepletionAndAmortization":[10,10], "DebtCurrent":[0,0],
        "CashAndCashEquivalentsAtCarryingValue":[80,90],
        "PaymentsToAcquirePropertyPlantAndEquipment":[40,40],
    }.items()}
    return {"facts":{"us-gaap":gaap}}

def test_pit_respects_filed_date():
    # asof before the 2015 filing -> only one annual point available -> None
    assert pit_finyears(_facts(), pd.Timestamp("2014-06-01", tz="UTC")) is None

def test_pit_returns_two_years_when_filed():
    cur, prev = pit_finyears(_facts(), pd.Timestamp("2015-06-01", tz="UTC"))
    assert cur.net_income == 100 and prev.net_income == 10
    assert cur.shares == 50 and cur.filed <= pd.Timestamp("2015-06-01", tz="UTC")
