#!/usr/bin/env node
// I1-R notable-filer roster: SEC EDGAR 13F, quarter-over-quarter NEW/increased BULLISH lines.
// CRITICAL: putCall filter — LONG+Call only. Burry's largest lines are PLTR/NVDA PUTS (bearish);
// a naive tracker surfaces them as buys. 13F is ~45d stale — never present as a live buy.
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };
const ROSTER = [
  ["Michael Burry / Scion",1649339],["Buffett / Berkshire",1067983],["Ackman / Pershing Square",1336528],
  ["Tepper / Appaloosa",1656456],["Klarman / Baupost",1061768],["Greenblatt / Gotham",1510387],
  ["Carl Icahn",921669],["Loeb / Third Point",1040273],["Druckenmiller / Duquesne",1536411],
  ["Coleman / Tiger Global",1167483],["Laffont / Coatue",1135730],["Li Lu / Himalaya",1709323],
  ["Marks / Oaktree",949509],["Dalio / Bridgewater",1350694],["Ken Fisher",850529],
  ["Cathie Wood / ARK",1697748],["Berkowitz / Fairholme",1056831],["Lone Pine",1061165],["Viking Global",1103804],
];
let _T=null;
async function tmap(){ if(_T)return _T; const d=await (await fetch("https://www.sec.gov/files/company_tickers.json",{headers:UA})).json();
  _T={}; for(const k in d) _T[d[k].title.toUpperCase()]=d[k].ticker; return _T; }
function mapT(n,m){ const u=n.toUpperCase().replace(/[.,]/g,""); if(m[u])return m[u];
  const w=u.split(" ")[0]; const h=Object.keys(m).find(x=>x.startsWith(w+" ")||x===w); return h?m[h]:null; }
async function infoTable(cik,acc){
  const dir=await (await fetch(`https://www.sec.gov/Archives/edgar/data/${cik}/${acc}/`,{headers:UA})).text();
  const f=[...dir.matchAll(/href="([^"]+\.xml)"/g)].map(m=>m[1].split("/").pop()).find(x=>/info|table/i.test(x));
  if(!f) return [];
  const xml=await (await fetch(`https://www.sec.gov/Archives/edgar/data/${cik}/${acc}/${f}`,{headers:UA})).text();
  const g=(b,t)=>(b.match(new RegExp(`<(?:\\w+:)?${t}>([^<]+)`))||[])[1];
  return [...xml.matchAll(/<(?:\w+:)?infoTable>[\s\S]*?<\/(?:\w+:)?infoTable>/g)].map(m=>{const b=m[0];
    return {name:g(b,"nameOfIssuer"),type:g(b,"putCall")||"LONG",val:+(g(b,"value")||0),sh:+((b.match(/sshPrnamt>([^<]+)/)||[])[1]||0)};});
}
for(const [fund,cik] of ROSTER){
 try{
  const p=String(cik).padStart(10,"0");
  const sub=await (await fetch(`https://data.sec.gov/submissions/CIK${p}.json`,{headers:UA})).json();
  const R=sub.filings.recent, accs=[];
  for(let i=0;i<R.form.length&&accs.length<2;i++) if(R.form[i]==="13F-HR") accs.push({acc:R.accessionNumber[i].replace(/-/g,""),date:R.filingDate[i]});
  if(!accs.length){console.log(JSON.stringify({fund,err:"no 13F-HR"}));continue;}
  const staleDays=Math.round((new Date("2026-09-22")-new Date(accs[0].date))/86400e3);
  const cur=await infoTable(cik,accs[0].acc), prev=accs[1]?await infoTable(cik,accs[1].acc):[];
  const ps={}; for(const h of prev) ps[h.name+"|"+h.type]=h.sh;
  const m=await tmap();
  const buys=cur.filter(h=>/LONG|Call/i.test(h.type)).filter(h=>(ps[h.name+"|"+h.type]||0)<h.sh)
    .map(h=>({ticker:mapT(h.name,m),valM:+(h.val/1e6).toFixed(1),isNew:!((h.name+"|"+h.type) in ps),type:h.type}))
    .sort((a,b)=>b.valM-a.valM).slice(0,8);
  console.log(JSON.stringify({fund,filed:accs[0].date,staleDays,nBuys:buys.length,top:buys}));
 }catch(e){console.log(JSON.stringify({fund,err:String(e).slice(0,50)}));}
 await new Promise(z=>setTimeout(z,350));
}
