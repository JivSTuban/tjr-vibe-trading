#!/usr/bin/env node
// I3 insider-quality + I2 alive-gate, per ticker.
// The insider history is read UNWINDOWED. A 30-day screener window reports a confident
// sellM=$0.00 while a $270.9M director sale sits 94 days outside it (CAVA, 2026-09-17) --
// so the net-selling check MUST run on the full per-ticker history, not the feed window.
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };
const TAGS = { net_income:["NetIncomeLoss"], assets:["Assets"],
  cfo:["NetCashProvidedByUsedInOperatingActivities","NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
  revenue:["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet"],
  gross_profit:["GrossProfit"], cur_assets:["AssetsCurrent"], cur_liab:["LiabilitiesCurrent"],
  lt_debt:["LongTermDebtNoncurrent","LongTermDebt"],
  shares:["CommonStockSharesOutstanding","EntityCommonStockSharesOutstanding"], equity:["StockholdersEquity"] };
let _C=null;
async function cikFor(t){ if(!_C) _C=await (await fetch("https://www.sec.gov/files/company_tickers.json",{headers:UA})).json();
  t=t.toUpperCase(); for(const k in _C) if(_C[k].ticker.toUpperCase()===t) return String(_C[k].cik_str).padStart(10,"0"); return null; }
function annual(f,tl){ const src={...(f.facts?.["us-gaap"]||{}),...(f.facts?.["dei"]||{})};
  for(const tag of tl){ const n=src[tag]; if(!n?.units) continue; const o={};
    for(const u in n.units) for(const pt of n.units[u]){ if(pt.form!=="10-K"&&pt.form!=="10-K/A")continue; if(pt.fp&&pt.fp!=="FY")continue; o[pt.end]=Number(pt.val);} 
    if(Object.keys(o).length) return o; } return {}; }
async function qualityGate(t){
 try{ const cik=await cikFor(t); if(!cik) return {err:"no CIK"};
  const r=await fetch(`https://data.sec.gov/api/xbrl/companyfacts/CIK${cik}.json`,{headers:UA});
  if(!r.ok) return {err:"companyfacts "+r.status};
  const f=await r.json(); const F={}; for(const k in TAGS) F[k]=annual(f,TAGS[k]);
  const ends=Object.keys(F.net_income).filter(e=>e in F.assets).sort();
  if(ends.length<2) return {err:"<2 annual pts"};
  const ec=ends.at(-1), ep=ends.at(-2);
  const g=(k,e)=>F[k]?.[e]!==undefined?F[k][e]:NaN, div=(a,b)=>b?a/b:NaN;
  const c={ni:g("net_income",ec),cfo:g("cfo",ec),a:g("assets",ec),rev:g("revenue",ec),gp:g("gross_profit",ec),ca:g("cur_assets",ec),cl:g("cur_liab",ec),ltd:g("lt_debt",ec),sh:g("shares",ec),eq:g("equity",ec)};
  const p={ni:g("net_income",ep),a:g("assets",ep),rev:g("revenue",ep),gp:g("gross_profit",ep),ca:g("cur_assets",ep),cl:g("cur_liab",ep),ltd:g("lt_debt",ep),sh:g("shares",ep)};
  const ck=[c.ni>0,c.cfo>0,div(c.ni,c.a)>div(p.ni,p.a),c.cfo>c.ni,div(c.ltd,c.a)<div(p.ltd,p.a),div(c.ca,c.cl)>div(p.ca,p.cl),c.sh<=p.sh,div(c.gp,c.rev)>div(p.gp,p.rev),div(c.rev,c.a)>div(p.rev,p.a)];
  const fs=ck.filter(x=>x===true).length;
  const da=div(c.ltd,c.a), solvent=c.eq>0&&!(da>0.6);
  return {fy:ec,fscore:fs,profit:c.ni>0,cfo:c.cfo>0,eq:c.eq>0,da:Number.isFinite(da)?+da.toFixed(2):null,alive:c.ni>0&&c.cfo>0&&solvent};
 }catch(e){return {err:String(e).slice(0,40)};}
}
function parseDetail(html){
 const out=[];
 for(const r of html.match(/<tr[^>]*>[\s\S]*?<\/tr>/g)||[]){
  const cells=(r.match(/<td[^>]*>[\s\S]*?<\/td>/g)||[]).map(c=>c.replace(/<[^>]+>/g," ").replace(/&#?\w+;/g," ").replace(/\|/g,"").replace(/\s+/g," ").trim());
  const tt=cells.findIndex(c=>/^[A-Z] - (Purchase|Sale)/.test(c)); if(tt<4) continue;
  const num=s=>+(String(s||"").replace(/[$,+%\s]/g,""))||0;
  out.push({trade:(cells[2]||"").slice(0,10),insider:(cells[tt-2]||"").slice(0,30),title:(cells[tt-1]||"").slice(0,26),
    kind:cells[tt][0],price:num(cells[tt+1]),value:Math.abs(num(cells[tt+5]))});
 }
 return out;
}
const TICKERS=process.argv.slice(2);
for(const t of TICKERS){
 let det=[],derr=null;
 try{ det=parseDetail(await (await fetch(`http://openinsider.com/search?q=${t}`,{headers:UA})).text()); }catch(e){derr=String(e).slice(0,30);}
 const buys=det.filter(d=>d.kind==="P"), sells=det.filter(d=>d.kind==="S");
 const bV=buys.reduce((a,d)=>a+d.value,0), sV=sells.reduce((a,d)=>a+d.value,0);
 const q=await qualityGate(t);
 // routine-vs-opportunistic: many buys spread over many months = a standing program (no information)
 const bDates=[...new Set(buys.map(d=>d.trade))].sort();
 const spanMo=bDates.length>1?Math.round((new Date(bDates.at(-1))-new Date(bDates[0]))/86400e3/30):0;
 const topSell=sells.sort((a,b)=>b.value-a.value)[0];
 console.log(JSON.stringify({t,
   hist:{nBuys:buys.length,buyM:+(bV/1e6).toFixed(2),nSells:sells.length,sellM:+(sV/1e6).toFixed(2),
     buyDateSpanMonths:spanMo,distinctBuyDates:bDates.length,oldestBuy:bDates[0]||null,
     biggestSell:topSell?`${topSell.trade} ${topSell.insider} $${(topSell.value/1e6).toFixed(2)}M @${topSell.price}`:null},
   alive:q, derr}));
 await new Promise(r=>setTimeout(r,450));
}
