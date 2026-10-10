'use strict';
const $ = (s) => document.querySelector(s);
const money = (n) => n == null ? '—' : new Intl.NumberFormat('ru-RU', {style:'currency', currency:'RUB', maximumFractionDigits:0}).format(n/100);
const pct = (n) => n == null ? '—' : new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(n) + '%';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, page = 'overview', mode = 'demo', requestVersion = 0, search = '';
const pages = {
  overview: ['Обзор бизнеса', 'Все магазины. Одна картина бизнеса.'],
  products: ['Экономика товаров', 'Выручка и результат по внутреннему артикулу.'],
  ads: ['Эффективность рекламы', 'Атрибуция площадки и финансовый результат — отдельные показатели.'],
  finance: ['Финансы', 'От результата бизнеса до исходной операции.'],
  expenses: ['Расходы и себестоимость', 'Собственные затраты и история закупочной стоимости.'],
  integrations: ['Подключения', 'Пять кабинетов, два юридических лица и ваши источники данных.'],
  roadmap: ['План разработки', 'Что уже работает и что требуется для достоверной аналитики.']
};
const labels = {sale:'Реализация',refund:'Возврат выручки',cogs:'Себестоимость',commission:'Комиссия',logistics:'Логистика',storage:'Хранение',ads:'Реклама',other:'Прочие расходы',overhead:'Операционные расходы',compensation:'Компенсации',tax:'Налог'};
function params(){ return new URLSearchParams({mode, account:$('#account').value, start:$('#start').value, end:$('#end').value}); }
async function load(){
  const version = ++requestVersion;
  $('#refresh').disabled = true;
  $('#error').hidden = true;
  try {
    const response = await fetch('/api/state?' + params());
    const body = await response.json();
    if (!response.ok) throw Error(body.error);
    if (version !== requestVersion) return;
    state = body;
    if ($('#account').options.length === 1) body.accounts.forEach(a => $('#account').add(new Option(a.name,a.id)));
    render();
  } catch(e) {
    if(version !== requestVersion) return;
    $('#error').textContent = 'Не удалось обновить данные: ' + e.message;
    $('#error').hidden = false;
    $('#page').innerHTML = '<div class="empty">Данные не показаны: исправьте период или повторите загрузку.</div>';
  } finally { if(version===requestVersion) $('#refresh').disabled = false; }
}
function go(next){ page = next; search=''; if(state) render(); }
function render(){
  $('#title').textContent = pages[page][0]; $('#crumb').textContent = pages[page][0]; $('#subtitle').textContent = pages[page][1];
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active',b.dataset.page===page));
  $('#demo-mode').classList.toggle('selected',mode==='demo'); $('#local-mode').classList.toggle('selected',mode==='local');
  $('#notice').className = 'notice' + (mode==='local' ? ' live' : '');
  $('#notice').innerHTML = mode==='demo'
    ? '<strong>Демонстрационные данные</strong> Все суммы и товары вымышлены. Пример за сентябрь 2026. Данные ваших магазинов ещё не загружены.'
    : '<strong>Ваши локальные данные</strong> API ещё не подключены. Ручные расходы и импорт себестоимости сохраняются на этом компьютере.';
  const builders = {overview, products, ads, finance, expenses, integrations, roadmap};
  $('#page').innerHTML = builders[page]();
  document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
  if(page==='products') $('#search').oninput = e => { search=e.target.value; $('#product-body').innerHTML=productRows(filteredProducts()); };
  if(page==='expenses') bindExpenses();
}
function metric(label, value, note, icon='', extra='') {
  return `<div class="card"><div class="metric-label">${label}<span class="metric-icon">${icon}</span></div><div class="metric-value ${extra}">${value}</div><div class="metric-note">${note}</div></div>`;
}
function cards(){const s=state.summary;return `<div class="metrics">
  ${metric('Выручка после возвратов',mode==='local'?'Нет данных':money(s.revenue),mode==='local'?'Продажи ещё не загружены':'По дате финансовой операции','↗',mode==='local'?'unavailable':'')}
  ${metric('Результат до налогов',mode==='local'?'Нет полной оценки':money(s.pre_tax_profit),mode==='local'?'Нет продаж и затрат площадок':`Маржинальность ${pct(s.margin_before_tax)} · пример`,'◫',mode==='local'?'unavailable':'')}
  ${metric('Чистая прибыль','Не рассчитана','Нужны налоги и полный состав расходов','◇','unavailable')}
  ${metric('Учтённые расходы на рекламу',mode==='local'&&!s.ad_spend?'Нет данных':money(s.ad_spend),mode==='local'?'Только ручные записи; источники не подключены':`Общая ДРР ${pct(s.drr_total)} · от реализованной выручки`,'↗',mode==='local'&&!s.ad_spend?'unavailable':'')}
  </div>`;}
function chart(){
  const rows=state.trends;
  if(!rows.length) return '<div class="empty">Операций за период пока нет</div>';
  const max=Math.max(1,...rows.map(r=>Math.max(r.revenue,Math.abs(r.pre_tax_profit))));
  const min=Math.min(0,...rows.map(r=>Math.min(r.revenue,r.pre_tax_profit)));
  const width=680, left=58, inner=610, scale=245/(max-min), base=35+max*scale, step=inner/rows.length;
  let svg='';
  [0,.5,1].forEach(f=>{const y=base-max*scale*f;svg+=`<line x1="${left}" x2="675" y1="${y}" y2="${y}"/><text x="0" y="${y+4}">${Math.round(max*f/100000)} тыс.</text>`;});
  rows.forEach((r,i)=>{const x=left+i*step+2,w=Math.max(1,step*.31);const revenueH=Math.abs(r.revenue)*scale, profitH=Math.abs(r.pre_tax_profit)*scale;
    svg+=`<rect class="sales-bar" x="${x}" y="${r.revenue>=0?base-revenueH:base}" width="${w}" height="${revenueH}" rx="2"><title>${esc(r.day)}: выручка ${money(r.revenue)}</title></rect>`;
    svg+=`<rect class="profit-bar" x="${x+w+1}" y="${r.pre_tax_profit>=0?base-profitH:base}" width="${w}" height="${profitH}" rx="2"><title>До налогов: ${money(r.pre_tax_profit)}</title></rect>`;
    if(i===0 || i===rows.length-1 || i%Math.max(1,Math.ceil(rows.length/6))===0) svg+=`<text x="${x}" y="320">${r.day.slice(8)}.${r.day.slice(5,7)}</text>`;
  });
  return `<svg class="chart" viewBox="0 0 ${width} 340" role="img" aria-label="Выручка и результат до налогов по дням">${svg}</svg>`;
}
function attention(){return `<div class="card"><div class="card-heading"><h2>Требует внимания</h2><span class="tag">3 задачи</span></div><div class="stack">
  <div class="attention"><span class="attention-icon">!</span><div><h3>Настроить налоговые профили</h3><p>Все 5 кабинетов на АУСН. Объект налога и привязка к двум юрлицам пока не подтверждены.</p></div></div>
  <div class="attention"><span class="attention-icon">⇄</span><div><h3>Связать артикулы площадок</h3><p>Нужен единый справочник: товары, варианты, наборы и производство.</p></div></div>
  <div class="attention"><span class="attention-icon">◇</span><div><h3>Подключить источники</h3><p>Доступы API ещё не настроены. Следующий этап — защищённый ввод ключей и загрузчики API.</p><button class="text-button" data-go="integrations">Перейти к подключениям →</button></div></div>
  </div></div>`;}
function overview(){
  if(mode==='local' && !state.total_entries) return cards()+emptyLocal()+`<div class="section-space">${attention()}</div>`;
  return cards()+`<div class="grid"><section class="card"><div class="card-heading"><h2>Динамика бизнеса</h2><span class="tag">По дням</span></div><div class="chart-legend"><span><i></i>Выручка</span><span><i class="profit"></i>До налогов</span></div>${chart()}<div class="chart-caption">Возвраты отражены по дате операции. Результат текущего периода может корректироваться.</div></section>${attention()}</div>
  <section class="card"><div class="card-heading"><h2>Товары в фокусе</h2><button class="text-button" data-go="products">Все товары →</button></div>${productTable(state.products.slice().sort((a,b)=>b.pre_tax_profit-a.pre_tax_profit).slice(0,5))}</section>`;
}
function emptyLocal(){return '<div class="empty"><h2>Начнём с ваших данных</h2><p>Кабинеты ещё не подключены. Уже можно загрузить себестоимость из CSV и внести собственные расходы. Прибыль появится после загрузки продаж и проверки полноты затрат.</p><button class="button" data-go="expenses">Добавить себестоимость и расходы</button></div>';}
function productRows(rows){return rows.length ? rows.map(p=>`<tr><td><div class="product-name"><span class="product-icon">▦</span><div><strong>${esc(p.name)}</strong><small>${esc(p.sku)} · ${esc(p.category)}</small></div></div></td><td class="number">${money(p.revenue)}</td><td class="number">${money(p.costs)}</td><td class="number ${p.pre_tax_profit>=0?'positive':'negative'}">${money(p.pre_tax_profit)}</td><td class="number">${pct(p.margin_before_tax)}</td><td><span class="pill ${p.pre_tax_profit<0?'red':''}">${p.pre_tax_profit<0?'Убыток до налогов':'До налогов'}</span></td></tr>`).join(''):'<tr><td colspan="6" class="muted">Нет товаров по выбранным условиям</td></tr>';}
function productTable(rows){return `<div class="table-wrap"><table><thead><tr><th>Товар</th><th class="number">Выручка</th><th class="number">Учтённые расходы</th><th class="number">До налогов</th><th class="number">Маржа</th><th>Статус</th></tr></thead><tbody id="product-body">${productRows(rows)}</tbody></table></div>`;}
function filteredProducts(){return state.products.filter(p=>(p.name+' '+p.sku+' '+p.category).toLowerCase().includes(search.toLowerCase()));}
function products(){return `<div class="info-box">${mode==='demo'?'В примере 8 условных товаров. Ваши 100+ артикулов появятся после подключения кабинетов.':'Товары площадок ещё не загружены.'} Расходы без товарной привязки остаются на уровне кабинета; они не распределяются незаметно между товарами.</div><section class="card"><div class="card-heading"><h2>Товарная аналитика</h2><input class="search" id="search" placeholder="Название или артикул" aria-label="Найти товар" value="${esc(search)}"></div>${productTable(filteredProducts())}</section>`;}
function ads(){return `<div class="info-box">${mode==='demo'?'Кампании и атрибуция вымышлены; расходы взяты из демонстрационного реестра.':'Рекламные источники не подключены.'} ДРР здесь рассчитана от рекламной выручки. Окно атрибуции и правила конкретной площадки ещё не проверены. Прибыль кампании и управление ставками пока недоступны.</div><section class="card"><div class="card-heading"><h2>Кампании · ${state.campaigns.length}</h2><span class="tag">Только просмотр</span></div><div class="table-wrap"><table><thead><tr><th>Кампания / товар</th><th>Кабинет</th><th class="number">Расход</th><th class="number">Рекламная выручка</th><th class="number">Клики</th><th class="number">Заказы</th><th class="number">ДРР</th><th class="number">ROAS</th></tr></thead><tbody>${state.campaigns.length?state.campaigns.map(c=>`<tr><td>${esc(c.name)}</td><td>${esc(c.account)}</td><td class="number">${money(c.spend)}</td><td class="number">${money(c.attributed)}</td><td class="number">${c.clicks}</td><td class="number">${c.orders}</td><td class="number">${pct(c.drr)}</td><td class="number">${c.roas}×</td></tr>`).join(''):'<tr><td colspan="8">Рекламные данные отсутствуют</td></tr>'}</tbody></table></div></section>`;}
function finance(){const s=state.summary;return `${cards()}<div class="grid"><section class="card"><div class="card-heading"><h2>Доходы и расходы</h2><span class="tag">По начислению</span></div><div class="table-wrap"><table><tbody>${Object.entries(s.totals).map(([kind,amount])=>`<tr><td>${esc(labels[kind]||kind)}</td><td class="number ${amount<0?'':'positive'}">${money(amount)}</td></tr>`).join('')}<tr><td><strong>Сальдо учтённых операций до налогов</strong></td><td class="number"><strong>${money(s.pre_tax_profit)}</strong></td></tr><tr><td>Налоги / чистая прибыль</td><td class="number">Не рассчитаны</td></tr></tbody></table></div></section><section class="card"><h2>Рентабельность и деньги</h2><p class="form-note">Рентабельность учтённых затрат до налогов = результат до налогов / учтённые затраты. Это не ROI на вложенный капитал.</p><div class="metric-value">${mode==='demo'?pct(s.return_on_cost_before_tax):'—'}</div><p class="form-note">Для ROI нужны вложения и согласованная база расчёта. Для движения денег — выплаты, банковские операции, закупки и начальные остатки.</p><span class="pill gray">ДДС и ROI — следующий этап</span></section></div><section class="card"><div class="card-heading"><h2>Исходные операции</h2><span class="tag">${Math.min(250,state.total_entries)} из ${state.total_entries} · полный CSV в экспорте</span></div><div class="table-wrap"><table><thead><tr><th>Дата</th><th>Кабинет</th><th>Артикул</th><th>Статья</th><th class="number">Сумма</th><th>Источник / ID</th></tr></thead><tbody>${state.entries.map(r=>`<tr><td>${esc(r.day)}</td><td>${esc(r.account_id)}</td><td>${esc(r.sku||'Не распределено')}</td><td>${esc(labels[r.kind]||r.kind)}${r.note?`<small>${esc(r.note)}</small>`:''}</td><td class="number">${money(r.amount)}</td><td><small>${esc(r.source)}<br>${esc(r.source_id)}</small></td></tr>`).join('')||'<tr><td colspan="6">Нет операций</td></tr>'}</tbody></table></div></section>`;}
function expenses(){return `<div class="info-box">${mode==='demo'?'Изменения в режиме «Демо» сохраняются отдельно и не попадут в ваши данные.':'Ввод сохраняется только в локальную базу.'} Импорт пока хранит историю себестоимости; привязка к продажам и перерасчёт будут добавлены с интеграцией. Не импортируйте повторно расходы, уже включённые в отчёты площадок.</div><div class="grid"><section class="card"><div class="card-heading"><h2>Добавить расход</h2><span class="tag">${mode==='demo'?'Демо':'Ваши данные'}</span></div><form id="expense-form" class="form-grid"><label>Кабинет<select name="account_id">${state.accounts.map(a=>`<option value="${a.id}">${esc(a.name)}</option>`).join('')}</select></label><label>Дата<input name="day" type="date" value="${esc(state.end)}" required></label><label>Статья<select name="kind"><option value="overhead">Операционные расходы</option><option value="other">Прочие расходы</option><option value="ads">Реклама вне отчёта</option></select></label><label>Сумма, ₽<input name="amount" inputmode="decimal" placeholder="12500,00" required></label><label class="full">Описание<input name="note" placeholder="Например, услуги фулфилмента за сентябрь" maxlength="500" required></label><button class="button" type="submit">Сохранить расход</button><p class="form-note full">Расход без артикула учитывается на уровне кабинета. Редактирование и распределение между юрлицами — в следующей версии.</p></form></section><section class="card"><h2>Загрузить себестоимость</h2><p class="form-note">CSV в рублях. Столбцы: <code>sku</code>, <code>effective_from</code>, <code>cost_rub</code>. Дата в формате ГГГГ-ММ-ДД. Повтор артикула и даты обновляет существующую запись.</p><button id="template" class="text-button">↓ Скачать шаблон CSV</button><form id="cost-form" class="form-grid"><label class="full">Файл CSV<input id="cost-file" type="file" accept=".csv,text/csv" required></label><button type="submit" class="button">Импортировать</button></form><p class="form-note">Валютные закупки, состав наборов и производственная себестоимость потребуют отдельной модели. Автоматического пересчёта валют здесь нет.</p></section></div><section class="card"><div class="card-heading"><h2>История себестоимости</h2><span class="tag">Все даты · без фильтра кабинета</span></div><div class="table-wrap"><table><thead><tr><th>Внутренний артикул</th><th>Действует с</th><th class="number">Себестоимость единицы</th></tr></thead><tbody>${state.cost_history.map(c=>`<tr><td>${esc(c.sku)}</td><td>${esc(c.effective_from)}</td><td class="number">${money(c.unit_cost)}</td></tr>`).join('')||'<tr><td colspan="3">Пока не загружена</td></tr>'}</tbody></table></div></section>`;}
function integrations(){return `<div class="info-box">По вашему решению разработка идёт локально, без публикации. Будущий сервер — в России. Формы для секретов и отправки данных наружу пока нет. Подключение API, Google и Telegram пока не реализовано.</div><div class="integration-grid">${state.accounts.map(a=>`<section class="card integration-card"><div class="integration-logo ${a.platform==='Ozon'?'ozon':''}">${a.platform==='Ozon'?'Ozon':'WB'}</div><h2>${esc(a.name)}</h2><span class="pill gray">Не подключён</span><p>Юридическое лицо не назначено.<br>Схемы продаж определим по источнику.</p><small>Нужны защищённое хранилище ключей и загрузчик API</small></section>`).join('')}<section class="card integration-card"><div class="integration-logo ozon">＋</div><h2>Дополнительные источники</h2><span class="pill gray">Запланировано</span><p>Google Sheets · Диск · Почта<br>Telegram · утренний отчёт</p><small>Провайдер почты, время отчёта и получатели не заданы</small></section></div><section class="card section-space"><h2>Два юридических лица</h2><p class="form-note">По вашему уточнению все пять кабинетов используют АУСН. Для расчёта необходимы распределение кабинетов, объект АУСН, НДС, даты действия режима и правила корректировок. Налог не рассчитывается простым процентом от выплаты маркетплейса.</p></section>`;}
function roadmap(){const rows=[['Локальная основа','Демонстрационный обзор, фильтры, реестр операций, ввод расходов, CSV себестоимости и экспорт.','Готово'],['Реальные источники','Локально сейчас, сервер в России позже → защищённые ключи → WB и Ozon → доступная история и сверка.','Далее'],['Финансовая модель','Юрлица и налоги, сопоставление SKU, партии, валюта, состав наборов и производство.','В плане'],['Рабочая аналитика','Полный P&L, рекламная атрибуция, денежный поток, ROI, остатки и закупки.','В плане'],['Уведомления и действия','Telegram за вчера, контроль аномалий, управление ставками с лимитами и журналом действий.','В плане'],['Версия для других селлеров','Авторизация, проверенная изоляция клиентов, права, онбординг, резервное копирование и эксплуатация.','В плане']];return `<section class="card">${rows.map((r,i)=>`<div class="roadmap-row"><span class="step">${i+1}</span><div><h3>${r[0]}</h3><p>${r[1]}</p></div><span class="pill ${i?'gray':''}">${r[2]}</span></div>`).join('')}</section><div class="info-box section-space">Это однопользовательский локальный прототип. Поле владельца данных заложено в базе, но полноценная авторизация и разграничение доступа ещё не реализованы. Размещать эту сборку в открытом доступе нельзя.</div>`;}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify({...body,mode})}); const data=await r.json();if(!r.ok)throw Error(data.error);return data;}
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
function download(content,filename){const a=document.createElement('a');const url=URL.createObjectURL(new Blob(['\ufeff'+content],{type:'text/csv;charset=utf-8'}));a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function bindExpenses(){
  const requestId=crypto.randomUUID();
  $('#expense-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{await post('/api/expenses',{...Object.fromEntries(new FormData(e.target)),request_id:requestId});await load();toast('Расход сохранён в '+(mode==='demo'?'демонстрационную':'вашу локальную')+' базу.');}catch(error){toast(error.message);button.disabled=false;}};
  $('#template').onclick=()=>download('sku;effective_from;cost_rub\nMY-SKU-001;2026-09-01;570.00\n','cost-template.csv');
  $('#cost-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{const file=$('#cost-file').files[0];if(file.size>1500000)throw Error('Файл должен быть меньше 1,5 МБ');const result=await post('/api/costs/import',{csv:await file.text()});await load();toast(`Сохранено строк: ${result.count}. История стоимости ещё не связана с продажами.`);}catch(error){toast(error.message);button.disabled=false;}};
}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>go(b.dataset.page));
$('#demo-mode').onclick=()=>{mode='demo';$('#start').value='2026-09-01';$('#end').value='2026-09-30';load();};
$('#local-mode').onclick=()=>{mode='local';$('#start').value='2026-10-01';$('#end').value='2026-10-10';load();};
$('#refresh').onclick=load;$('#account').onchange=load;$('#start').onchange=load;$('#end').onchange=load;
$('#export').onclick=()=>{if(!$('#start').value||!$('#end').value||$('#start').value>$('#end').value){toast('Проверьте период');return;}window.location.href='/api/export?'+params();};
load();
