"""Fomo order clicks through the owner's onlinejobs-browser Playwright MCP.

Reads only the app's own account responses for reconciliation. It never sends
an order through HTTP. Response schemas were observed read-only on 2026-09-18.
"""
from __future__ import annotations

import json
import math
import re
import time
from contextlib import AsyncExitStack
from pathlib import Path

from .config import SOLANA_NETWORK_ID
from .execution import ExecutionBlocked, Proposal, Quote, Receipt, positive

USDC = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'

# Account data stays inside this browser context. Only the normalized public
# trade fields needed for confirmation leave it; never cookies/auth headers.
BOOTSTRAP = r"""
const context=page.context();
if(context.__fomoExecutor)throw Error('executor already attached');
const feed=await context.newPage();
const s={feed,trade:page,handle:args.handle,userId:null,balances:null,swaps:null,
         balancesAt:0,swapsAt:0,error:null};
context.__fomoExecutor=s;
feed.on('response',async response=>{
 try {
  const resource=response.url();
  if(!resource.startsWith('https://prod-api.fomo.family/')||response.request().method()!=='GET')return;
  const pathname=resource.slice('https://prod-api.fomo.family'.length).split('?')[0];
  if(pathname===`/v2/users/userHandle/${s.handle}`){
   const j=await response.json();
   if(response.status()!==200||j.success!==true||j.responseObject.userHandle!==s.handle){s.error='identity lookup failed';return;}
   const id=j.responseObject.id;
   if(s.userId && s.userId!==id){s.error='account changed';return;}
   s.userId=id;return;
  }
  const match=pathname.match(/^\/v2\/users\/([^/]+)\/(balances|swaps)$/);
  if(!match)return;
  const j=await response.json();
  if(response.status()!==200||j.success!==true){s.error='account feed unavailable';return;}
  const data=j.responseObject;
  if(match[2]==='balances'){
   if(!Array.isArray(data.balances))throw Error('invalid balances');
   s.balances={userId:match[1],items:data.balances.map(r=>({
    mint:r.balance.tokenAddress,network:r.tokenFilterResult.token.networkId,
    quantity:Number(r.balance.shiftedBalance),price:Number(r.tokenFilterResult.priceUSD)
   }))};s.balancesAt=Date.now()/1000;
  }else{
   if(!Array.isArray(data.swaps))throw Error('invalid swaps');
   s.swaps={userId:match[1],items:data.swaps.map(r=>({
    id:r.id,signature:r.signature,inNetworkId:r.inNetworkId,outNetworkId:r.outNetworkId,
    inTokenAddress:r.inTokenAddress,outTokenAddress:r.outTokenAddress,
    inHumanAmount:r.inHumanAmount,outHumanAmount:r.outHumanAmount,
    createdAt:r.createdAt,isOffPlatform:r.isOffPlatform
   }))};s.swapsAt=Date.now()/1000;
  }
 }catch{ s.error='account response could not be verified'; }
});
await feed.goto(`https://fomo.family/profile/${s.handle}`,{waitUntil:'domcontentloaded'});
await feed.getByRole('button',{name:'Edit profile',exact:true}).waitFor({timeout:20000});
return {attached:true};
"""

SNAPSHOT = r"""
const s=page.context().__fomoExecutor;
if(!s)throw Error('account feed not initialized');
if(s.error)throw Error(s.error);
if(s.feed.url()!==`https://fomo.family/profile/${s.handle}`)throw Error('account page changed');
if(await s.feed.getByRole('button',{name:'Edit profile',exact:true}).count()!==1)throw Error('account is not owned');
if(!s.userId||s.balances?.userId!==s.userId||s.swaps?.userId!==s.userId)throw Error('account feed incomplete');
return {handle:s.handle,balances:s.balances.items,swaps:s.swaps.items,
        balances_at:s.balancesAt,swaps_at:s.swapsAt};
"""

PREPARE = r"""
const s=page.context().__fomoExecutor;
if(!s||s.error)throw Error('account feed unavailable');
await s.feed.reload({waitUntil:'domcontentloaded'});
await s.trade.goto(`https://fomo.family/tokens/solana/${args.mint}`,{waitUntil:'domcontentloaded'});
await s.trade.getByRole('button',{name:'Buy',exact:true}).waitFor({timeout:20000});
return {prepared:true};
"""

# The final order button is invoked exactly once. No retry, no force click.
# The Sell 100% preset is permitted only when all holdings match our position.
CLICK = r"""
const s=page.context().__fomoExecutor;
if(!s||s.error)throw Error('account feed unavailable');
const expected=`https://fomo.family/tokens/solana/${args.mint}`;
if(s.trade.url()!==expected)throw Error('token page changed');
if(s.feed.url()!==`https://fomo.family/profile/${s.handle}`)throw Error('account page changed');
if(s.balances?.userId!==s.userId||s.swaps?.userId!==s.userId)throw Error('account mismatch');
if(Date.now()/1000-s.balancesAt>20||Date.now()/1000-s.swapsAt>20)throw Error('stale account snapshot');
const owned=s.balances.items.filter(x=>x.mint===args.mint && x.network===1399811149);
if(owned.some(x=>!Number.isFinite(x.quantity)||x.quantity<0))throw Error('invalid balance');
const qty=owned.reduce((a,b)=>a+b.quantity,0);
if(args.side==='buy' && qty>0)throw Error('token already held');
if(args.side==='sell' && Math.abs(qty-args.quantity)>Math.max(1e-8,args.quantity*1e-8))throw Error('position mismatch');
await s.trade.getByRole('button',{name:args.side==='buy'?'Buy':'Sell',exact:true}).click();
const amount=s.trade.getByPlaceholder('0',{exact:true});
if(args.side==='buy')await amount.fill(String(args.usd));
else await s.trade.getByRole('button',{name:'100%',exact:true}).click();
const label=(args.side==='buy'?'Buy ':'Sell ')+args.ticker;
const submit=s.trade.getByRole('button',{name:label,exact:true});
if(await submit.count()!==1||!await submit.isEnabled())throw Error('submit unavailable');
if(args.side==='buy' && Number(await amount.inputValue())!==args.usd)throw Error('amount changed');
if(s.trade.url()!==expected)throw Error('token page changed');
if(args.side==='buy' && Date.now()/1000>=args.expires)throw Error('expired proposal');
if(Date.now()/1000-args.quote_at>15)throw Error('stale quote before submission');
const baseline=s.swaps.items.map(x=>x.id);
const submittedAt=Date.now()/1000;
await submit.click({timeout:3000});
return {submitted_at:submittedAt,baseline};
"""


def normalize_fill(swaps: list[dict], *, p: Proposal, side: str,
                   baseline: set[str], submitted_at: float) -> Receipt | None:
    """Require one new signed same-chain USDC trade, never infer a fill from a toast."""
    from datetime import datetime
    matches = []
    for row in swaps:
        if row.get('id') in baseline:
            continue
        token_key = 'outTokenAddress' if side == 'buy' else 'inTokenAddress'
        if row.get(token_key) != p.token_address:
            continue
        if (row.get('inNetworkId') != SOLANA_NETWORK_ID or
                row.get('outNetworkId') != SOLANA_NETWORK_ID):
            continue
        cash_key = 'inTokenAddress' if side == 'buy' else 'outTokenAddress'
        if row.get(cash_key) != USDC or row.get('isOffPlatform') is not False:
            continue
        try:
            stamp = datetime.fromisoformat(row['createdAt'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError
            if stamp.timestamp() < submitted_at - 5:
                continue
            token_amount = float(row['outHumanAmount' if side == 'buy' else 'inHumanAmount'])
            dollars = float(row['inHumanAmount' if side == 'buy' else 'outHumanAmount'])
        except (KeyError, ValueError, TypeError):
            raise ExecutionBlocked('malformed matching trade receipt') from None
        if (not row.get('id') or not row.get('signature') or
                not positive(token_amount) or not positive(dollars)):
            raise ExecutionBlocked('unsigned or invalid fill')
        if side == 'buy' and not p.trade_usd * .90 <= dollars <= p.trade_usd * 1.001:
            raise ExecutionBlocked('fill does not match requested buy amount')
        matches.append(Receipt(p.proposal_id, p.token_address, side, token_amount,
                               dollars / token_amount, row['signature']))
    if len(matches) > 1:
        raise ExecutionBlocked('multiple matching trades require reconciliation')
    return matches[0] if matches else None


class FomoMCPBrowser:
    environment = 'fomo-live'

    def __init__(self, *, handle: str, config: Path | None = None):
        if not re.fullmatch(r'[A-Za-z0-9_]{1,50}', handle):
            raise ValueError('invalid account handle')
        self.handle = handle
        self.config = config or Path.home()/'.claude.json'
        self.stack = AsyncExitStack()
        self.session = None

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        c = json.loads(self.config.read_text())['mcpServers']['onlinejobs-browser']
        try:
            r, w = await self.stack.enter_async_context(stdio_client(StdioServerParameters(
                command=c['command'], args=c['args'], env=c.get('env'))))
            self.session = await self.stack.enter_async_context(ClientSession(r, w))
            await self.session.initialize()
            await self.code(BOOTSTRAP, {'handle': self.handle})
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *exc):
        await self.stack.aclose()

    async def code(self, source: str, args: dict | None = None):
        code = 'async (page) => {const args=' + json.dumps(args or {}, allow_nan=False) + ';\n' + source + '\n}'
        result = await self.session.call_tool('browser_run_code_unsafe', {'code': code})
        if result.is_error:
            # Do not dump MCP browser logs, headers, or auth state on failures.
            raise ExecutionBlocked('Playwright operation failed; inspect browser locally')
        text = '\n'.join(c.text for c in result.content if c.type == 'text')
        try:
            payload = text.split('### Result\n', 1)[1]
            return json.JSONDecoder().raw_decode(payload.lstrip())[0]
        except (IndexError, ValueError):
            raise ExecutionBlocked('unrecognized Playwright response') from None

    async def snapshot(self) -> dict:
        result = await self.code(SNAPSHOT)
        now = time.time()
        if result['handle'] != self.handle:
            raise ExecutionBlocked('wrong account')
        for key in ('balances_at', 'swaps_at'):
            if not 0 <= now - result[key] <= 20:
                raise ExecutionBlocked('stale account data')
        return result

    @staticmethod
    def quantity(snapshot: dict, mint: str) -> float:
        amounts = [float(x['quantity']) for x in snapshot['balances']
                   if x['mint'] == mint and x['network'] == SOLANA_NETWORK_ID]
        if any(not math.isfinite(x) or x < 0 for x in amounts):
            raise ExecutionBlocked('invalid position balance')
        return sum(amounts)

    async def prepare(self, p: Proposal):
        if not re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}', p.token_address):
            raise ExecutionBlocked('invalid Solana mint')
        await self.code(PREPARE, {'mint': p.token_address})
        # A response may finish just after navigation. Read only; no order retry.
        import asyncio
        for _ in range(10):
            try:
                return await self.snapshot()
            except ExecutionBlocked:
                await asyncio.sleep(.5)
        raise ExecutionBlocked('account feed not ready')

    async def _submit(self, p: Proposal, q: Quote, side: str, quantity: float = 0):
        import asyncio
        pre = await self.snapshot()
        held = self.quantity(pre, p.token_address)
        if side == 'buy' and held > 0:
            raise ExecutionBlocked('token already held')
        if side == 'sell' and not math.isclose(held, quantity, rel_tol=1e-8, abs_tol=1e-8):
            raise ExecutionBlocked('position differs from confirmed fill')
        submitted = await self.code(CLICK, {'side':side,'mint':p.token_address,'ticker':p.ticker,
                                            'usd':p.trade_usd,'quantity':quantity,
                                            'expires':p.expires_at,'quote_at':q.observed_at})
        # Submission is never repeated. An absent receipt becomes uncertain.
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            snapshot = await self.snapshot()
            receipt = normalize_fill(snapshot['swaps'], p=p, side=side,
                                     baseline=set(submitted['baseline']), submitted_at=submitted['submitted_at'])
            if receipt:
                expected = receipt.quantity if side == 'buy' else 0.0
                held = self.quantity(snapshot,p.token_address)
                if math.isclose(held,expected,rel_tol=1e-8,abs_tol=1e-8):
                    return receipt
            await asyncio.sleep(1)
        raise ExecutionBlocked('confirmation timed out; reconcile before any retry')

    async def buy(self, p: Proposal, q: Quote) -> Receipt:
        return await self._submit(p,q,'buy')

    async def sell(self, p: Proposal, q: Quote, quantity: float) -> Receipt:
        return await self._submit(p,q,'sell',quantity)
