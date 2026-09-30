#!/usr/bin/env node
// I5-DD leg 1: EDGAR recent filings + split history + latest-10Q staleness.
// Dilution is the #1 small-cap killer, BUT a 424B is not automatically equity: ADC's 424B5
// was partnership NOTES and UBER's 424B2/B3 were EUR4.5B of senior notes (2026-09-17). Print
// the form + date so the prospectus can be read rather than headline-vetoed.
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };
const YUA = { "User-Agent": "Mozilla/5.0 stock-scan research" };
let _C=null;
async function cik(t){ if(!_C) _C=await (await fetch("https://www.sec.gov/files/company_tickers.json",{headers:UA})).json();
 t=t.toUpperCase(); for(const k in _C) if(_C[k].ticker.toUpperCase()===t) return String(_C[k].cik_str).padStart(10,"0"); return null; }
const DILUTIVE=/^(S-1|S-3|424B|F-1|F-3)/;
// A registered-offering form is NOT the only way shares get issued. Convertible notes and
// private note-for-equity EXCHANGES are announced by 8-K and never touch S-1/S-3/424B, so a
// form-name-only filter reports "no dilution" on real dilution. This hole hid ~55.5M shares
// of GME issuance (08-03 exchange, ~12% of the count) and RWT's $185M 7% convertible priced
// four days before its insider cluster bought (both 2026-09-22). Read the 8-K bodies.
const BUYBACK_TEXT=/share repurchase|repurchase program|buyback/i;
const DILUTIVE_TEXT=/convertible|exchange of.{0,40}notes|at.the.market|ATM program|private placement|equity offering|PIPE|secondary offering|shelf/i;
for(const t of process.argv.slice(2)){
 const c=await cik(t); if(!c){console.log(`${t}: no CIK`);continue;}
 const s=await (await fetch(`https://data.sec.gov/submissions/CIK${c}.json`,{headers:UA})).json();
 const R=s.filings.recent, rows=[];
 for(let i=0;i<R.form.length;i++) rows.push({f:R.form[i],d:R.filingDate[i],doc:R.primaryDocument[i],acc:R.accessionNumber[i]});
 const cutoff="2026-06-22";
 const dil=rows.filter(r=>DILUTIVE.test(r.f)&&r.d>=cutoff);
 const latestQ=rows.find(r=>["10-Q","10-K","20-F","40-F"].includes(r.f));
 // A 20-F/40-F foreign filer has no 8-K: it announces via 6-K. Scanning only 8-K reported
 // "clean" on GRAB (2026-09-22) and its dilution had to be re-checked by hand. Foreign
 // issuers are a growing share of this mode's clusters, so scan both form families.
 const eightK=rows.filter(r=>(r.f==="8-K"||r.f==="6-K")&&r.d>=cutoff);
 // scan recent 8-K/6-K bodies for dilution language the form name cannot reveal
 const hits=[], buybacks=[];
 for(const k of eightK.slice(0,12)){
  try{
   const acc=k.acc.replace(/-/g,"");
   const txt=await (await fetch(`https://www.sec.gov/Archives/edgar/data/${+c}/${acc}/${k.doc}`,{headers:UA})).text();
   const plain=txt.replace(/<[^>]+>/g," ").replace(/&#?\w+;/g," ").replace(/\s+/g," ");
   const m=plain.match(DILUTIVE_TEXT);
   if(m){ const i=plain.search(DILUTIVE_TEXT); hits.push(`${k.d} "${m[0]}" ...${plain.slice(Math.max(0,i-90),i+150).trim()}`); }
   if(BUYBACK_TEXT.test(plain)) buybacks.push(k.d);
  }catch{}
  await new Promise(r=>setTimeout(r,180));
 }
 // split check: a split makes a name look beaten-down when it is not
 const p2=Math.floor(Date.now()/1000), p1=p2-800*86400;
 const j=await (await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${t}?period1=${p1}&period2=${p2}&interval=1d&events=split`,{headers:YUA})).json();
 const sp=Object.values(j.chart?.result?.[0]?.events?.splits||{}).map(x=>`${x.splitRatio}@${new Date(x.date*1000).toISOString().slice(0,10)}`);
 console.log(`${t} [${s.name}] sic=${s.sic} ${s.sicDescription}`);
 console.log(`  dilutive filings since ${cutoff} (${dil.length}): ${dil.map(r=>r.f+" "+r.d).join(", ")||"NONE"}`);
 console.log(`  latest periodic: ${latestQ?.f} ${latestQ?.d} | 8-K/6-K since ${cutoff}: ${eightK.length} | splits: ${sp.join(",")||"none"}`);
 if(hits.length){ console.log(`  *** 8-K/6-K DILUTION LANGUAGE (${hits.length}) ***`); hits.forEach(h=>console.log("   - "+h.slice(0,260))); }
 else console.log("  8-K/6-K dilution scan: clean");
 if(buybacks.length) console.log(`  BUYBACK language (anti-dilutive) in ${buybacks.length} filing(s): ${buybacks.join(", ")}`);
 await new Promise(r=>setTimeout(r,400));
}
