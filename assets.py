"""Asset universe for the Inside Bar Strategy Dashboard."""

# ─── COMMODITIES ───
COMMODITIES = {
    "Gold (GC=F)": "GC=F",
    "Silver (SI=F)": "SI=F",
    "Platinum (PL=F)": "PL=F",
    "Palladium (PA=F)": "PA=F",
    "Crude Oil WTI (CL=F)": "CL=F",
    "Brent Crude (BZ=F)": "BZ=F",
    "Natural Gas (NG=F)": "NG=F",
    "Copper (HG=F)": "HG=F",
    "Corn (ZC=F)": "ZC=F",
    "Wheat (ZW=F)": "ZW=F",
    "Soybeans (ZS=F)": "ZS=F",
    "Coffee (KC=F)": "KC=F",
    "Sugar (SB=F)": "SB=F",
    "Cocoa (CC=F)": "CC=F",
    "Cotton (CT=F)": "CT=F",
}

# ─── CRYPTO ───
CRYPTO = {
    "Bitcoin (BTC-USD)": "BTC-USD",
    "Ethereum (ETH-USD)": "ETH-USD",
    "Solana (SOL-USD)": "SOL-USD",
    "BNB (BNB-USD)": "BNB-USD",
    "XRP (XRP-USD)": "XRP-USD",
    "Cardano (ADA-USD)": "ADA-USD",
    "Avalanche (AVAX-USD)": "AVAX-USD",
    "Dogecoin (DOGE-USD)": "DOGE-USD",
    "Polkadot (DOT-USD)": "DOT-USD",
    "Chainlink (LINK-USD)": "LINK-USD",
    "Polygon (MATIC-USD)": "MATIC-USD",
    "Litecoin (LTC-USD)": "LTC-USD",
    "Uniswap (UNI-USD)": "UNI-USD",
    "Stellar (XLM-USD)": "XLM-USD",
    "Cosmos (ATOM-USD)": "ATOM-USD",
}

# ─── INDICES / ETFs ───
INDICES = {
    "S&P 500 ETF (SPY)": "SPY",
    "Nasdaq 100 ETF (QQQ)": "QQQ",
    "Dow Jones ETF (DIA)": "DIA",
    "Russell 2000 ETF (IWM)": "IWM",
    "FTSE China (FXI)": "FXI",
    "Emerging Markets (EEM)": "EEM",
    "Volatility (VIX)": "^VIX",
    "US Dollar Index (DX-Y.NYB)": "DX-Y.NYB",
    "10Y Treasury ETF (TLT)": "TLT",
    "Gold Miners ETF (GDX)": "GDX",
}

# ─── TOP STOCKS BY SECTOR ───
STOCKS_TECH = {
    "Apple (AAPL)": "AAPL", "Microsoft (MSFT)": "MSFT", "Alphabet (GOOGL)": "GOOGL",
    "Amazon (AMZN)": "AMZN", "NVIDIA (NVDA)": "NVDA", "Meta (META)": "META",
    "Tesla (TSLA)": "TSLA", "Broadcom (AVGO)": "AVGO", "Taiwan Semi (TSM)": "TSM",
    "Adobe (ADBE)": "ADBE", "Salesforce (CRM)": "CRM", "AMD (AMD)": "AMD",
    "Netflix (NFLX)": "NFLX", "Intel (INTC)": "INTC", "Cisco (CSCO)": "CSCO",
    "Oracle (ORCL)": "ORCL", "Qualcomm (QCOM)": "QCOM", "IBM (IBM)": "IBM",
    "Uber (UBER)": "UBER", "Snowflake (SNOW)": "SNOW", "Palantir (PLTR)": "PLTR",
    "ServiceNow (NOW)": "NOW", "Intuit (INTU)": "INTU", "Palo Alto (PANW)": "PANW",
    "CrowdStrike (CRWD)": "CRWD", "Shopify (SHOP)": "SHOP", "MercadoLibre (MELI)": "MELI",
    "Datadog (DDOG)": "DDOG", "Fortinet (FTNT)": "FTNT", "Twilio (TWLO)": "TWLO",
    "Snap (SNAP)": "SNAP", "Pinterest (PINS)": "PINS", "Block (SQ)": "SQ",
    "Roblox (RBLX)": "RBLX", "Arm Holdings (ARM)": "ARM", "Spotify (SPOT)": "SPOT",
    "Atlassian (TEAM)": "TEAM", "Cloudflare (NET)": "NET", "Zscaler (ZS)": "ZS",
    "MongoDB (MDB)": "MDB", "Confluent (CFLT)": "CFLT",
}

STOCKS_FINANCE = {
    "JPMorgan (JPM)": "JPM", "Bank of America (BAC)": "BAC", "Wells Fargo (WFC)": "WFC",
    "Goldman Sachs (GS)": "GS", "Morgan Stanley (MS)": "MS", "Citigroup (C)": "C",
    "BlackRock (BLK)": "BLK", "Charles Schwab (SCHW)": "SCHW", "Visa (V)": "V",
    "Mastercard (MA)": "MA", "American Express (AXP)": "AXP", "PayPal (PYPL)": "PYPL",
    "Berkshire Hathaway (BRK-B)": "BRK-B", "S&P Global (SPGI)": "SPGI",
    "CME Group (CME)": "CME", "Intercontinental (ICE)": "ICE",
    "Capital One (COF)": "COF", "US Bancorp (USB)": "USB",
    "PNC Financial (PNC)": "PNC", "Truist (TFC)": "TFC",
    "Robinhood (HOOD)": "HOOD", "SoFi (SOFI)": "SOFI",
    "Coinbase (COIN)": "COIN", "Affirm (AFRM)": "AFRM",
}

STOCKS_HEALTH = {
    "UnitedHealth (UNH)": "UNH", "Johnson & Johnson (JNJ)": "JNJ",
    "Eli Lilly (LLY)": "LLY", "Pfizer (PFE)": "PFE", "AbbVie (ABBV)": "ABBV",
    "Merck (MRK)": "MRK", "Thermo Fisher (TMO)": "TMO", "Abbott Labs (ABT)": "ABT",
    "Amgen (AMGN)": "AMGN", "Gilead (GILD)": "GILD", "Moderna (MRNA)": "MRNA",
    "Regeneron (REGN)": "REGN", "Vertex (VRTX)": "VRTX", "Intuitive Surgical (ISRG)": "ISRG",
    "Danaher (DHR)": "DHR", "Biogen (BIIB)": "BIIB",
    "Edwards Lifesciences (EW)": "EW", "Hologic (HOLX)": "HOLX",
    "Humana (HUM)": "HUM", "Cigna (CI)": "CI",
}

STOCKS_CONSUMER = {
    "Walmart (WMT)": "WMT", "Costco (COST)": "COST", "Home Depot (HD)": "HD",
    "McDonald's (MCD)": "MCD", "Nike (NKE)": "NKE", "Starbucks (SBUX)": "SBUX",
    "Coca-Cola (KO)": "KO", "PepsiCo (PEP)": "PEP", "Procter & Gamble (PG)": "PG",
    "Disney (DIS)": "DIS", "Target (TGT)": "TGT", "Lowe's (LOW)": "LOW",
    "TJX Companies (TJX)": "TJX", "Dollar General (DG)": "DG",
    "Chipotle (CMG)": "CMG", "Ross Stores (ROST)": "ROST",
    "Booking Holdings (BKNG)": "BKNG", "Marriott (MAR)": "MAR",
    "Airbnb (ABNB)": "ABNB", "Hilton (HLT)": "HLT",
    "Colgate (CL)": "CL", "Estee Lauder (EL)": "EL",
    "Lululemon (LULU)": "LULU", "Yum Brands (YUM)": "YUM",
}

STOCKS_ENERGY = {
    "ExxonMobil (XOM)": "XOM", "Chevron (CVX)": "CVX",
    "ConocoPhillips (COP)": "COP", "EOG Resources (EOG)": "EOG",
    "Schlumberger (SLB)": "SLB", "Pioneer Natural (PXD)": "PXD",
    "Halliburton (HAL)": "HAL", "Valero (VLO)": "VLO",
    "Marathon Petroleum (MPC)": "MPC", "Devon Energy (DVN)": "DVN",
    "Diamondback (FANG)": "FANG", "Occidental (OXY)": "OXY",
    "Phillips 66 (PSX)": "PSX", "Enbridge (ENB)": "ENB",
    "NextEra Energy (NEE)": "NEE", "Duke Energy (DUK)": "DUK",
    "Southern Company (SO)": "SO", "Dominion (D)": "D",
}

STOCKS_INDUSTRIAL = {
    "Caterpillar (CAT)": "CAT", "Deere (DE)": "DE",
    "Honeywell (HON)": "HON", "3M (MMM)": "MMM",
    "General Electric (GE)": "GE", "Boeing (BA)": "BA",
    "Lockheed Martin (LMT)": "LMT", "Raytheon (RTX)": "RTX",
    "Union Pacific (UNP)": "UNP", "FedEx (FDX)": "FDX",
    "UPS (UPS)": "UPS", "Waste Management (WM)": "WM",
    "Parker Hannifin (PH)": "PH", "Illinois Tool Works (ITW)": "ITW",
    "Northrop Grumman (NOC)": "NOC", "L3Harris (LHX)": "LHX",
    "TransDigm (TDG)": "TDG", "PACCAR (PCAR)": "PCAR",
}

STOCKS_REALESTATE = {
    "American Tower (AMT)": "AMT", "Prologis (PLD)": "PLD",
    "Crown Castle (CCI)": "CCI", "Equinix (EQIX)": "EQIX",
    "Public Storage (PSA)": "PSA", "Realty Income (O)": "O",
    "Simon Property (SPG)": "SPG", "Welltower (WELL)": "WELL",
    "Digital Realty (DLR)": "DLR", "VICI Properties (VICI)": "VICI",
}

STOCKS_COMM = {
    "AT&T (T)": "T", "Verizon (VZ)": "VZ", "T-Mobile (TMUS)": "TMUS",
    "Comcast (CMCSA)": "CMCSA", "Charter (CHTR)": "CHTR",
}

STOCKS_MATERIALS = {
    "Linde (LIN)": "LIN", "Air Products (APD)": "APD",
    "Freeport-McMoRan (FCX)": "FCX", "Newmont (NEM)": "NEM",
    "Nucor (NUE)": "NUE", "Dow Inc (DOW)": "DOW",
    "DuPont (DD)": "DD", "Sherwin-Williams (SHW)": "SHW",
    "Barrick Gold (GOLD)": "GOLD", "Albemarle (ALB)": "ALB",
}

# ─── MASTER CATEGORIES ───
ASSET_CATEGORIES = {
    "🏆 Commodities": COMMODITIES,
    "₿ Crypto": CRYPTO,
    "📊 Indices & ETFs": INDICES,
    "💻 Tech Stocks": STOCKS_TECH,
    "🏦 Finance Stocks": STOCKS_FINANCE,
    "🏥 Healthcare Stocks": STOCKS_HEALTH,
    "🛒 Consumer Stocks": STOCKS_CONSUMER,
    "⛽ Energy & Utilities": STOCKS_ENERGY,
    "🏭 Industrial Stocks": STOCKS_INDUSTRIAL,
    "🏠 Real Estate Stocks": STOCKS_REALESTATE,
    "📡 Communication Stocks": STOCKS_COMM,
    "🧪 Materials Stocks": STOCKS_MATERIALS,
}


def get_all_assets_flat():
    """Return a flat dict of all display_name -> ticker."""
    out = {}
    for cat_name, cat_dict in ASSET_CATEGORIES.items():
        for display, ticker in cat_dict.items():
            out[display] = ticker
    return out


def get_category_for_ticker(ticker):
    """Return the category name for a given ticker."""
    for cat_name, cat_dict in ASSET_CATEGORIES.items():
        for display, t in cat_dict.items():
            if t == ticker:
                return cat_name
    return "Unknown"
