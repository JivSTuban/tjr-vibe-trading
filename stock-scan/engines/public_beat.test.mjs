// Offline tests for the public-beat gate. Run: node --test stock-scan/engines/public_beat.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { publicBeat, parseDate } from "./public_beat.mjs";

const q = (reported, surpPct, qtr = "Jun 2026") => ({ qtr, reported, surpPct, eps: 1, est: 1 });
const feed = (rows) => async () => rows;

test("parseDate: Nasdaq MM/DD/YYYY and ISO, never a guess", () => {
  assert.equal(parseDate("08/05/2026").toISOString().slice(0, 10), "2026-08-05");
  assert.equal(parseDate("2026-08-05").toISOString().slice(0, 10), "2026-08-05");
  assert.equal(parseDate("N/A"), null);
  assert.equal(parseDate(null), null);
});

test("a beat 10 and 78 days before the event counts; 91 days does not (the measured 90d window)", async () => {
  for (const [rep, ok] of [["09/20/2026", true], ["07/14/2026", true], ["06/30/2026", false]]) {
    const r = await publicBeat("X", "2026-09-30", { surprise: feed([q(rep, 4.2)]) });
    assert.equal(r.status === "BEAT", ok, rep);
  }
});

test("a beat more than 25 days back still counts (the live 25d lookback would have missed it)", async () => {
  const r = await publicBeat("X", "2026-09-30", { surprise: feed([q("08/10/2026", 3)]) });
  assert.equal(r.status, "BEAT");
  assert.equal(r.daysBefore, 51);
});

test("a beat announced AFTER the insider event is not a catalyst (look-ahead guard)", async () => {
  const r = await publicBeat("X", "2026-09-10", { surprise: feed([q("09/15/2026", 9)]) });
  assert.equal(r.status, "NO_BEAT");
});

test("a miss or an in-line print is not a beat; latest quarter is named", async () => {
  const r = await publicBeat("X", "2026-09-30", { surprise: feed([q("09/01/2026", -2), q("06/01/2026", 0)]) });
  assert.equal(r.status, "NO_BEAT");
  assert.equal(r.latestReported, "2026-09-01");
});

test("picks the most recent qualifying quarter", async () => {
  const r = await publicBeat("X", "2026-09-30", { surprise: feed([q("07/20/2026", 1, "Q1"), q("09/10/2026", 2, "Q2")]) });
  assert.equal(r.qtr, "Q2");
});

test("does not require the market to have rewarded the print", async () => {
  // the gate has no price input at all: a beat is a beat
  const r = await publicBeat("X", "2026-09-30", { surprise: feed([q("09/10/2026", 0.5)]) });
  assert.equal(r.status, "BEAT");
});

test("fail closed: a failed feed, an empty feed, and unparseable dates are UNKNOWN, never NO_BEAT", async () => {
  assert.equal((await publicBeat("X", "2026-09-30", { surprise: async () => null })).status, "UNKNOWN");
  assert.equal((await publicBeat("X", "2026-09-30", { surprise: feed([]) })).status, "UNKNOWN");
  assert.equal((await publicBeat("X", "2026-09-30", { surprise: feed([q("not a date", 5)]) })).status, "UNKNOWN");
  assert.equal((await publicBeat("X", "garbage", { surprise: feed([q("09/10/2026", 5)]) })).status, "UNKNOWN");
});

test("a null surprise percentage is not a beat", async () => {
  const r = await publicBeat("X", "2026-09-30", { surprise: feed([q("09/10/2026", null)]) });
  assert.equal(r.status, "NO_BEAT");
});
