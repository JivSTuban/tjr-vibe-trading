"""Run the owner-authorized Fomo UI executor; default is a read-only check.

Signals are staged by fomo_radar.run. This separate worker monitors confirmed
fills continuously and submits browser market sells at -20% or +10%.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import time
from pathlib import Path

from memecoin_radar.sources.dexscreener import DexScreenerClient

from .execution import ExecutionBlocked, ExecutionStore, Proposal, Quote, Receipt, SimulationExecutor, positive
from .live_browser import FomoMCPBrowser

log = logging.getLogger('fomo_radar.live')


class LiveExecutor(SimulationExecutor):
    environment = 'fomo-live'
    restart_states = ('submitting', 'closing', 'uncertain')

    def __init__(self, store, browser, halt, *, trade_usd: float):
        if not positive(trade_usd):
            raise ValueError('fixed USD amount must be positive')
        self.trade_usd = trade_usd
        super().__init__(store, browser, halt)
        # A journal cannot silently move to a different account or size.
        self.store.conn.execute('CREATE TABLE IF NOT EXISTS execution_binding (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
        binding = json.dumps({'account': browser.handle, 'size':trade_usd},sort_keys=True)
        with self.store.conn:
            self.store.conn.execute('INSERT OR IGNORE INTO execution_binding VALUES (1,?)',(binding,))
            old = self.store.conn.execute('SELECT value FROM execution_binding WHERE id=1').fetchone()[0]
        if old != binding:
            self.close()
            raise ExecutionBlocked('journal account/size differs; reconcile before changing configuration')

    def validate_buy_amount(self, receipt: Receipt, proposal: Proposal):
        # Fomo deducts fees from the entered budget. Exact equality would mark
        # every fee-bearing successful buy uncertain and leave it unmonitored.
        spent = receipt.quantity * receipt.price
        if not proposal.trade_usd * .90 <= spent <= proposal.trade_usd * 1.001:
            raise ExecutionBlocked('confirmed fill outside requested budget')

    async def enter(self, order_id, quote, *, now=None):
        row = self.store.row(order_id)
        if row is None:
            raise ExecutionBlocked('unknown proposal')
        p = Proposal(**json.loads(row['proposal']))
        if p.trade_usd != self.trade_usd:
            raise ExecutionBlocked('proposal amount differs from configured amount')
        await super().enter(order_id,quote,now=now)

    async def reconcile_open(self):
        self.check()
        rows = self.store.conn.execute("SELECT * FROM execution_orders WHERE state='open'").fetchall()
        if len(rows)>1:
            self.trip('multiple_open_positions')
            raise ExecutionBlocked('multiple positions require reconciliation')
        for row in rows:
            p = Proposal(**json.loads(row['proposal']))
            snapshot = await self.browser.prepare(p)
            held = self.browser.quantity(snapshot,p.token_address)
            if (not row['receipt'] or not positive(row['quantity']) or
                    not math.isclose(held,row['quantity'],rel_tol=1e-8,abs_tol=1e-8)):
                self.trip('restart_position_mismatch')
                raise ExecutionBlocked('restart holding does not match confirmed position')


async def market_quote(dex, mint: str) -> Quote:
    states = await dex.token_states([mint])
    state = states.get(mint)
    if state is None or not positive(state.price_usd):
        raise ExecutionBlocked('no usable current token price')
    return Quote(mint,state.price_usd,time.time())


async def cycle(worker: LiveExecutor, dex):
    worker.check()
    store = worker.store
    row = store.conn.execute("SELECT * FROM execution_orders WHERE state='open' LIMIT 1").fetchone()
    if row:
        p = Proposal(**json.loads(row['proposal']))
        try:
            snapshot = await worker.browser.snapshot()
        except ExecutionBlocked:
            snapshot = await worker.browser.prepare(p)
        held = worker.browser.quantity(snapshot,p.token_address)
        if not math.isclose(held,row['quantity'],rel_tol=1e-8,abs_tol=1e-8):
            worker.trip('position_changed_outside_executor')
            raise ExecutionBlocked('position changed outside executor')
        try:
            quote = await market_quote(dex,p.token_address)
        except Exception:
            worker.trip('position_monitor_unavailable')
            raise
        result = await worker.monitor(p.proposal_id,quote)
        if result:
            log.info('closed %s: %s',p.proposal_id[:12],result)
        return

    rows = store.conn.execute("SELECT * FROM execution_orders WHERE state='proposed' ORDER BY rowid").fetchall()
    for row in rows:
        p = Proposal(**json.loads(row['proposal']))
        if p.expires_at <= time.time() or p.trade_usd != worker.trade_usd:
            with store.conn:
                store.conn.execute("UPDATE execution_orders SET state='rejected' WHERE id=?",(p.proposal_id,))
                store.event(p.proposal_id,'expired_or_size_mismatch')
            continue
        # Browser preparation is read-only and happens before the order claim.
        await worker.browser.prepare(p)
        quote = await market_quote(dex,p.token_address)
        await worker.enter(p.proposal_id,quote)
        log.info('opened %s; software stop -20%%, target +10%%',p.proposal_id[:12])
        return


async def run(args):
    async with FomoMCPBrowser(handle=args.account,config=args.mcp_config) as browser:
        # The browser-only check never opens a journal or calls enter/sell.
        if not args.execute:
            for _ in range(20):
                try:
                    snapshot = await browser.snapshot()
                    print(json.dumps({'account':args.account,'connected':True,
                                      'balance_rows':len(snapshot['balances']),
                                      'recent_swaps':len(snapshot['swaps']),'orders_enabled':False}))
                    return
                except ExecutionBlocked:
                    await asyncio.sleep(.5)
            raise ExecutionBlocked('account feed not ready')
        store = ExecutionStore(args.db)
        worker = None
        try:
            worker = LiveExecutor(store,browser,args.halt,trade_usd=args.trade_usd)
            await worker.reconcile_open()
            async with DexScreenerClient() as dex:
                while True:
                    await cycle(worker,dex)
                    await asyncio.sleep(3)
        except BaseException:
            if worker and store.conn.execute(
                "SELECT 1 FROM execution_orders WHERE state IN ('open','submitting','closing','uncertain')"
            ).fetchone():
                worker.trip('worker_stopped_with_unresolved_position')
            raise
        finally:
            if worker:
                worker.close()
            store.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account',required=True,help='exact Fomo account handle')
    parser.add_argument('--mcp-config',type=Path,default=Path.home()/'.claude.json')
    parser.add_argument('--execute',action='store_true',help='consume proposals and submit real browser orders')
    parser.add_argument('--trade-usd',type=float,help='required fixed USD budget per buy')
    parser.add_argument('--db',type=Path,help='proposal journal also used by the signaler')
    parser.add_argument('--halt',type=Path,help='persistent execution kill-switch file')
    args=parser.parse_args()
    if args.execute and (args.db is None or args.halt is None or args.trade_usd is None or not positive(args.trade_usd)):
        parser.error('--execute requires --db, --halt, and positive --trade-usd')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        return
    except Exception as exc:
        # Browser/session failures may embed private response information.
        log.error('executor stopped (%s); inspect journal, HALT, and local browser',type(exc).__name__)
        raise SystemExit(1) from None


if __name__=='__main__':
    main()
