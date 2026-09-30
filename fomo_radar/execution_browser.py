"""Observed Fomo form selectors and a network-isolated Playwright test adapter.

Selectors verified through onlinejobs-browser MCP on 2026-09-18. The production
surface has no verified native stop order or fill-reconciliation contract yet.
Consequently FomoUI only inspects forms. All order clicks target a synthetic page.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from .execution import ExecutionBlocked, Proposal, Quote, Receipt


class FomoUI:
    environment = "fomo-live"

    def __init__(self, page):
        self.page = page

    async def inspect(self, mint: str, ticker: str) -> dict:
        """Read the exact token's trade form; no order fields or buttons changed."""
        if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", mint):
            raise ExecutionBlocked("invalid Solana mint")
        url = urlsplit(self.page.url)
        if (url.scheme != "https" or url.netloc != "fomo.family"
                or url.path != f"/tokens/solana/{mint}"):
            raise ExecutionBlocked("wrong token page or environment")
        amount = self.page.get_by_placeholder("0", exact=True)
        buy = self.page.get_by_role("button", name=f"Buy {ticker}", exact=True)
        sell = self.page.get_by_role("button", name=f"Sell {ticker}", exact=True)
        return {"amount_fields": await amount.count(), "buy_buttons": await buy.count(),
                "sell_buttons": await sell.count(), "live_enabled": False}

    async def buy(self, *args):
        raise NotImplementedError("Fomo buy submission and fill reconciliation are not implemented")

    async def sell(self, *args):
        raise NotImplementedError("Fomo sell submission and position reconciliation are not implemented")


# Match the observed form's public controls without copying account data.
# Receipt fields are a TEST contract, not an assertion about Fomo's actual UI.
FIXTURE = """<!doctype html><html><body>
<h1>Isolated execution simulator</h1><p>No network or wallet connection</p>
<section id="trade"><button id="buy-tab">Buy</button><button id="sell-tab">Sell</button>
<label>$ <input placeholder="0" inputmode="decimal"></label>
<button id="all" hidden>100%</button><button id="submit" disabled>Buy TEST</button>
</section><output id="receipt"></output>
<script>
let side='buy', position=0, request=null, clicks=0;
const amount=document.querySelector('input');
const submit=document.querySelector('#submit');
const all=document.querySelector('#all');
function update(){submit.textContent=(side==='buy'?'Buy ':'Sell ')+'TEST';
submit.disabled=!(Number(amount.value)>0);all.hidden=side!=='sell';}
document.querySelector('#buy-tab').onclick=()=>{side='buy';amount.value='';update();};
document.querySelector('#sell-tab').onclick=()=>{side='sell';amount.value='';update();};
amount.oninput=update;
all.onclick=()=>{amount.value=String(position);update();};
submit.onclick=()=>{
 if(!request || request.side!==side)throw Error('wrong request');
 const quantity=side==='buy'?Number(amount.value)/request.price:Number(amount.value);
 if(side==='sell' && quantity>position+1e-9)throw Error('position mismatch');
 if(side==='buy')position+=quantity;else position-=quantity;
 clicks++;
 document.querySelector('#receipt').textContent=JSON.stringify({
   order_id:request.id,token_address:request.token,side,quantity,
   price:request.price,reference:'sim-'+clicks});
};
</script></body></html>"""


class IsolatedBrowser:
    environment = "isolated-simulation"

    @classmethod
    async def create(cls, playwright):
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(service_workers="block")
        # Fresh context, no credentials, and an unconditional network block.
        await context.route("**/*", lambda route: route.abort())
        page = await context.new_page()
        await page.set_content(FIXTURE)
        self = cls()
        self.browser, self.page = browser, page
        return self

    async def close(self):
        await self.browser.close()

    async def _submit(self, p: Proposal, q: Quote, side: str, quantity: float = 0) -> Receipt:
        if self.page.url != "about:blank":
            raise ExecutionBlocked("simulation page navigated away")
        await self.page.evaluate("r => {request=r; document.querySelector('#receipt').textContent='';}",
                                 {"id": p.proposal_id, "token": p.token_address,
                                  "price": q.price, "side": side})
        await self.page.get_by_role("button", name=side.capitalize(), exact=True).click()
        # Sell only the owned quantity, never a wallet-wide percentage.
        await self.page.get_by_placeholder("0", exact=True).fill(str(p.trade_usd if side == "buy" else quantity))
        await self.page.get_by_role("button", name=f"{side.capitalize()} TEST", exact=True).click()
        from playwright.async_api import expect
        receipt = self.page.locator("#receipt")
        await expect(receipt).not_to_have_text("")
        return Receipt(**json.loads(await receipt.inner_text()))

    async def buy(self, p: Proposal, q: Quote) -> Receipt:
        return await self._submit(p, q, "buy")

    async def sell(self, p: Proposal, q: Quote, quantity: float) -> Receipt:
        return await self._submit(p, q, "sell", quantity)
