'use strict';
// Loaded only by the static build, never by the local application.
const hostedPreview = {
  dataset: null,
  ratio(n,d,percent=true){return d>0 ? Math.round(n/d*(percent?100:1)*100)/100 : null;},
  summarize(rows){
    const totals={}; rows.forEach(r=>totals[r.kind]=(totals[r.kind]||0)+r.amount);
    const revenue=(totals.sale||0)+(totals.refund||0);
    const costs=-['cogs','commission','logistics','storage','ads','other','overhead'].reduce((s,k)=>s+(totals[k]||0),0);
    const pre_tax_profit=revenue+(totals.compensation||0)-costs, ad_spend=-(totals.ads||0);
    return {revenue,gross_sales:totals.sale||0,refunds:-(totals.refund||0),costs,ad_spend,pre_tax_profit,net_profit:null,
      margin_before_tax:this.ratio(pre_tax_profit,revenue),drr_total:this.ratio(ad_spend,revenue),return_on_cost_before_tax:this.ratio(pre_tax_profit,costs),totals};
  },
  async rows(params){
    const start=params.get('start'),end=params.get('end'),account=params.get('account');
    if(!/^\d{4}-\d{2}-\d{2}$/.test(start)||!/^\d{4}-\d{2}-\d{2}$/.test(end)||start>end) throw Error('Проверьте период');
    if(!this.dataset){const r=await fetch('/preview-data.json');if(!r.ok)throw Error('Демонстрационные данные недоступны');this.dataset=await r.json();}
    return this.dataset.entries.filter(r=>r.day>=start&&r.day<=end&&(!account||r.account_id===account));
  },
  async state(params){
    const rows=await this.rows(params),d=this.dataset,campaigns=[];
    d.accounts.forEach(a=>d.products.forEach((p,i)=>{
      const spend=-rows.filter(r=>r.account_id===a.id&&r.sku===p.sku&&r.kind==='ads').reduce((s,r)=>s+r.amount,0);
      if(!spend)return;
      const attributed=spend*(2+i%5),clicks=Math.max(1,Math.floor(spend/2300));
      campaigns.push({name:p.name,account:a.name,spend,attributed,clicks,orders:Math.floor(clicks/8),roas:this.ratio(attributed,spend,false),drr:this.ratio(spend,attributed)});
    }));
    return {mode:'demo',accounts:d.accounts,summary:this.summarize(rows),products:d.products.map(p=>({...p,...this.summarize(rows.filter(r=>r.sku===p.sku))})),
      campaigns,trends:[...new Set(rows.map(r=>r.day))].sort().map(day=>({day,...this.summarize(rows.filter(r=>r.day===day))})),
      entries:rows.slice(0,250),total_entries:rows.length,cost_history:[],start:params.get('start'),end:params.get('end')};
  },
  async csv(params){
    const rows=await this.rows(params),cell=v=>'"'+String(v??'').replace(/^[=+@\t\r-]/,"'$&").replace(/"/g,'""')+'"';
    return [['mode','day','account','sku','kind','amount_rub','source','source_id'],...rows.map(r=>['demo',r.day,r.account_id,r.sku,r.kind,(r.amount/100).toFixed(2),r.source,r.source_id])].map(row=>row.map(cell).join(';')).join('\r\n');
  }
};
