"""Execution fault tests. No credentials, real profiles, or broker traffic."""
import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from fomo_radar.config import SignalConfig
from fomo_radar.execution import (
    ExecutionBlocked, ExecutionStore, Quote, Receipt, SimulationExecutor, propose,
)
from fomo_radar.execution_browser import FomoUI, IsolatedBrowser
from fomo_radar.tests.test_entry_gate import make_signal

NOW = 1_800_000_000.0


def proposal(**overrides):
    sig = make_signal()
    sig.max_usd = 10000
    args = dict(source_id='thesis-1', source_at=datetime.fromtimestamp(NOW-30, timezone.utc).isoformat(),
                trade_usd=50., quote_at=NOW, now=NOW, cfg=SignalConfig())
    args.update(overrides)
    return propose(sig, **args)


class Browser:
    environment = 'isolated-simulation'
    calls = 0
    fail = False

    async def buy(self, p, q):
        self.calls += 1
        if self.fail:
            raise TimeoutError('uncertain after click')
        return Receipt(p.proposal_id, p.token_address, 'buy', p.trade_usd / (q.price * 1.01), q.price * 1.01, 'buy-1')

    async def sell(self, p, q, qty):
        self.calls += 1
        if self.fail:
            raise TimeoutError('uncertain after sell')
        return Receipt(p.proposal_id, p.token_address, 'sell', qty, q.price, 'sell-1')


@pytest.fixture
def harness(tmp_path):
    store = ExecutionStore(tmp_path / 'execution.sqlite3')
    p = proposal()
    store.enqueue(p)
    browser = Browser()
    worker = SimulationExecutor(store, browser, tmp_path / 'HALT')
    yield store, p, browser, worker
    worker.close()
    store.close()


def run(awaitable):
    return asyncio.run(awaitable)


def test_duplicate_reopen_preserves_original_snapshot(tmp_path):
    path = tmp_path / 'queue.sqlite3'
    a, b = ExecutionStore(path), ExecutionStore(path)
    p = proposal()
    assert a.enqueue(p)
    assert not b.enqueue(replace(p, trade_usd=999))
    assert json.loads(b.row(p.proposal_id)['proposal'])['trade_usd'] == 50
    a.close()
    b.close()
    c = ExecutionStore(path)
    assert not c.enqueue(p)
    c.close()


@pytest.mark.parametrize('overrides', [
    {'trade_usd': 0}, {'trade_usd': -1}, {'trade_usd': float('nan')},
    {'trade_usd': float('inf')}, {'quote_at': NOW-16}, {'quote_at': NOW+1},
    {'source_at': '2027-01-15T08:00:00'}, {'source_at': 'bad'},
    {'source_at': datetime.fromtimestamp(NOW+1, timezone.utc).isoformat()},
    {'source_at': datetime.fromtimestamp(NOW-1900, timezone.utc).isoformat()},
    {'source_id': ''},
])
def test_bad_proposal_rejected(overrides):
    with pytest.raises((ExecutionBlocked, ValueError)):
        proposal(**overrides)


def test_cost_gate_uses_actual_position_size():
    proposal(trade_usd=50)
    with pytest.raises(ExecutionBlocked, match='round trip'):
        proposal(trade_usd=50000)


def test_fresh_market_hard_gates_rechecked():
    sig = make_signal()
    sig.max_usd = 10000
    sig.liquidity.volume_h1_usd = 0
    with pytest.raises(ExecutionBlocked):
        propose(sig, source_id='t', source_at=datetime.fromtimestamp(NOW-1,timezone.utc).isoformat(),
                trade_usd=20, quote_at=NOW, now=NOW, cfg=SignalConfig())


@pytest.mark.parametrize('ratio,expected', [(0.8, 'stop_loss'), (1.10, 'take_profit'), (1.0, None)])
def test_exit_is_measured_from_fill_not_signal(harness, ratio, expected):
    store, p, browser, worker = harness
    run(worker.enter(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
    row = store.row(p.proposal_id)
    assert row['fill_price'] > p.reference_price
    assert row['stop_price'] == pytest.approx(row['fill_price'] * 0.8)
    assert row['target_price'] == pytest.approx(row['fill_price'] * 1.10)
    result = run(worker.monitor(p.proposal_id, Quote(p.token_address,row['fill_price']*ratio,NOW+1), now=NOW+1))
    assert result == expected
    assert store.row(p.proposal_id)['state'] == ('closed' if expected else 'open')
    assert browser.calls == (2 if expected else 1)


def test_live_adapter_never_touched(harness):
    store, p, browser, worker = harness
    browser.environment = 'live'
    with pytest.raises(ExecutionBlocked, match='isolated-simulation adapter'):
        run(worker.enter(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
    assert browser.calls == 0
    assert worker.halt.exists()


def test_manual_halt_before_buy(harness):
    store, p, browser, worker = harness
    worker.halt.touch()
    with pytest.raises(ExecutionBlocked,match='HALT'):
        run(worker.enter(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
    assert browser.calls == 0


def test_uncertain_buy_is_not_retried_after_restart(harness):
    store, p, browser, worker = harness
    browser.fail = True
    with pytest.raises(TimeoutError):
        run(worker.enter(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
    assert store.row(p.proposal_id)['state'] == 'uncertain'
    worker.close()
    worker.halt.unlink()  # Even manual deletion does not reconcile the journal.
    restarted = SimulationExecutor(store, browser, worker.halt)
    try:
        with pytest.raises(ExecutionBlocked):
            run(restarted.enter(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
        assert browser.calls == 1
        assert worker.halt.exists()
    finally:
        restarted.close()


def test_missing_stop_halts(harness):
    store, p, browser, worker = harness
    run(worker.enter(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
    with store.conn:
        store.conn.execute('UPDATE execution_orders SET stop_price=NULL WHERE id=?',(p.proposal_id,))
    with pytest.raises(ExecutionBlocked,match='missing protection'):
        run(worker.monitor(p.proposal_id, Quote(p.token_address,p.reference_price,NOW),now=NOW))
    assert worker.halt.exists()
    assert browser.calls == 1


def test_second_worker_refused(harness):
    store, p, browser, worker = harness
    with pytest.raises(ExecutionBlocked,match='another execution worker'):
        SimulationExecutor(store,browser,worker.halt)


@pytest.mark.parametrize('quote,now', [
    (Quote('WRONG',0.001,NOW),NOW), (Quote('MINT',float('nan'),NOW),NOW),
    (Quote('MINT',0.001,NOW-16),NOW), (Quote('MINT',0.002,NOW),NOW),
    (Quote('MINT',0.001,NOW+100),NOW+100),
])
def test_invalid_stale_moved_or_expired_entry_never_clicks(harness,quote,now):
    store,p,browser,worker=harness
    with pytest.raises(ExecutionBlocked):
        run(worker.enter(p.proposal_id,quote,now=now))
    assert browser.calls == 0


def test_production_form_has_no_submission_path():
    ui=FomoUI(None)
    for call in (ui.buy,ui.sell):
        with pytest.raises(NotImplementedError,match='not implemented'):
            run(call())


def test_real_playwright_buy_then_target_and_stop(tmp_path):
    async def scenario():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            for ratio,reason in [(1.10,'take_profit'),(.8,'stop_loss')]:
                browser=await IsolatedBrowser.create(pw)
                store=ExecutionStore(tmp_path/f'{reason}.sqlite3')
                worker=SimulationExecutor(store,browser,tmp_path/f'{reason}.HALT')
                try:
                    p=proposal()
                    store.enqueue(p)
                    await worker.enter(p.proposal_id,Quote(p.token_address,p.reference_price,NOW),now=NOW)
                    fill=store.row(p.proposal_id)['fill_price']
                    result=await worker.monitor(p.proposal_id,Quote(p.token_address,fill*ratio,NOW+1),now=NOW+1)
                    assert result == reason
                    assert store.row(p.proposal_id)['state']=='closed'
                    assert await browser.page.evaluate('clicks')==2
                    assert await browser.page.evaluate('position')==pytest.approx(0)
                    await browser.page.screenshot(path=str(tmp_path/f'{reason}.png'))
                finally:
                    worker.close()
                    store.close()
                    await browser.close()
    run(scenario())


def test_restart_open_position_requires_reconciliation(harness):
    store,p,browser,worker=harness
    run(worker.enter(p.proposal_id,Quote(p.token_address,p.reference_price,NOW),now=NOW))
    worker.close()
    restarted=SimulationExecutor(store,browser,worker.halt)
    try:
        assert worker.halt.exists()
        with pytest.raises(ExecutionBlocked,match='HALT'):
            run(restarted.monitor(p.proposal_id,Quote(p.token_address,p.reference_price,NOW),now=NOW))
        assert browser.calls==1
    finally:
        restarted.close()


@pytest.mark.parametrize('field', ['stop_price','target_price'])
def test_changed_protection_halts(harness,field):
    store,p,browser,worker=harness
    run(worker.enter(p.proposal_id,Quote(p.token_address,p.reference_price,NOW),now=NOW))
    with store.conn:
        store.conn.execute(f'UPDATE execution_orders SET {field}=? WHERE id=?',(0.000001,p.proposal_id))
    with pytest.raises(ExecutionBlocked,match='protection changed'):
        run(worker.monitor(p.proposal_id,Quote(p.token_address,p.reference_price,NOW),now=NOW))
    assert worker.halt.exists()
    assert browser.calls==1


def test_uncertain_sell_never_retried(harness):
    store,p,browser,worker=harness
    run(worker.enter(p.proposal_id,Quote(p.token_address,p.reference_price,NOW),now=NOW))
    browser.fail=True
    quote=Quote(p.token_address,store.row(p.proposal_id)['fill_price']*.7,NOW)
    with pytest.raises(TimeoutError):
        run(worker.monitor(p.proposal_id,quote,now=NOW))
    assert store.row(p.proposal_id)['state']=='uncertain'
    with pytest.raises(ExecutionBlocked):
        run(worker.monitor(p.proposal_id,quote,now=NOW))
    assert browser.calls==2


@pytest.mark.parametrize('dry_run', [False,True])
def test_signal_hook_stages_before_discord_failure_and_excludes_dry_runs(tmp_path,monkeypatch,dry_run):
    import time
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from fomo_radar.config import FomoConfig
    from fomo_radar.run import FomoRadar
    store=ExecutionStore(tmp_path/'execution.sqlite3')
    radar=FomoRadar(FomoConfig(db_path=tmp_path/'radar.sqlite3',dry_run=dry_run),
                    execution_store=store,execution_size_usd=50.)
    sig=make_signal()
    sig.max_usd=10000
    sig.liquidity.observed_at=time.time()
    item=SimpleNamespace(token_address=sig.token_address,network_id=sig.network_id,ticker='TEST',
                         item_id='source-1',created_at=datetime.now(timezone.utc).isoformat())
    radar._backfilled.add((sig.token_address,sig.network_id))
    monkeypatch.setattr(radar.store,'refresh_token_stats',Mock(return_value={'max_usd':10000,'total_usd':10000}))
    monkeypatch.setattr(radar,'_liquidity',AsyncMock(return_value=sig.liquidity))
    sink=SimpleNamespace(send=AsyncMock(side_effect=TimeoutError('Discord failed')))
    try:
        for _ in range(2):
            with pytest.raises(TimeoutError):
                run(radar._consider(None,sink,item))
        rows=store.conn.execute('SELECT * FROM execution_orders').fetchall()
        assert len(rows)==(0 if dry_run else 1)
        if rows:
            p=json.loads(rows[0]['proposal'])
            assert p['source_id']=='source-1'
            assert p['trade_usd']==50
            assert rows[0]['state']=='proposed'
    finally:
        radar.store.close()
        store.close()
