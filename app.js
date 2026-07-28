'use strict';
const money = value => value == null ? 'k. A.' : new Intl.NumberFormat('de-DE',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(value);
const number = value => value == null ? 'k. A.' : new Intl.NumberFormat('de-DE',{maximumFractionDigits:0}).format(value);
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
let buildings=[], listings=[], summary=[], deferredPrompt=null, currentListingFilter=null;
const byId=id=>document.getElementById(id);
const favorites=()=>JSON.parse(localStorage.getItem('condoAtlasFavorites')||'[]');
const saveFavorites=value=>localStorage.setItem('condoAtlasFavorites',JSON.stringify(value));

function toast(message){const el=byId('toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),1800)}
function facts(items){return `<div class="facts">${items.filter(Boolean).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>`}
function buildingSummary(id){return summary.find(x=>Number(x.building_id)===Number(id))||{}}
function isFavorite(id){return favorites().includes(Number(id))}

async function getJson(path){const response=await fetch(path);if(!response.ok)throw new Error(`${path}: ${response.status}`);return response.json()}
async function init(){
  try{
    [buildings,listings,summary]=await Promise.all([
      getJson('data/buildings.json'), getJson('data/listings.json'), getJson('data/summary.json')
    ]);
    listings.sort((a,b)=>String(b.observed_date||b.listing_date||'').localeCompare(String(a.observed_date||a.listing_date||'')));
    renderAll();
  }catch(error){
    console.error(error);document.querySelector('main').innerHTML='<div class="panel"><h2>Daten konnten nicht geladen werden</h2><p>Die App muss über GitHub Pages oder einen Webserver geöffnet werden. Lokales Antippen der HTML-Datei reicht nicht aus.</p></div>';
  }
}

function renderAll(){
  const underBudget=listings.filter(x=>Number(x.asking_price_brl)<=800000).length;
  const fourPlus=listings.filter(x=>Number(x.bedrooms)>=4).length;
  byId('kpis').innerHTML=[['Gebäude',buildings.length],['Anzeigen',listings.length],['bis R$ 800.000',underBudget],['4+ Schlafzimmer',fourPlus]].map(([label,value])=>`<div class="kpi"><strong>${number(value)}</strong><span>${label}</span></div>`).join('');
  renderBuildings();renderListings();renderFavorites();renderHomeMatches();
}

function buildingCard(b){
  const s=buildingSummary(b.building_id);const fav=isFavorite(b.building_id);
  return `<article class="card">
    <h3>${esc(b.name)}</h3>
    <div class="sub">${esc(b.district||'')} · ${esc(b.address||'Adresse offen')}</div>
    ${facts([b.completion_year&&`Baujahr ${b.completion_year}`,b.typical_area_m2&&`typ. ${number(b.typical_area_m2)} m²`,b.max_bedrooms&&`bis ${b.max_bedrooms} Schlafzimmer`,Number(b.has_pool)===1?'Pool':null])}
    <div class="price">${s.avg_asking_price_brl?`Ø ${money(s.avg_asking_price_brl)}`:'Preis noch offen'}</div>
    <div class="sub">${number(s.listing_count||0)} erfasste Anzeigen</div>
    <div class="actions"><button class="action" data-building-detail="${b.building_id}">Details</button><button class="secondary favorite ${fav?'active':''}" data-favorite="${b.building_id}">${fav?'★ Favorit':'☆ Favorit'}</button></div>
  </article>`;
}

function listingCard(l, compact=false){
  const floor=l.floor_number?`${l.floor_number}. Stock`:l.floor_text;
  return `<article class="card">
    <h3>${esc(l.building_name_raw||'Gebäude nicht zugeordnet')}</h3>
    <div class="sub">${esc(l.district||'')} · ${esc(l.portal_broker||l.source_name||'Quelle offen')}</div>
    <div class="price">${money(l.asking_price_brl)}</div>
    ${facts([l.area_m2&&`${number(l.area_m2)} m²`,l.bedrooms&&`${l.bedrooms} Schlafzimmer`,floor,Number(l.has_balcony)===1?'Varanda':null,Number(l.has_sea_view)===1?'Meerblick':null])}
    ${!compact&&l.price_per_m2_brl?`<div class="sub">${money(l.price_per_m2_brl)}/m²</div>`:''}
    <div class="actions">${l.url?`<a class="action" href="${esc(l.url)}" target="_blank" rel="noopener" style="text-decoration:none">Anzeige öffnen</a>`:''}<button class="secondary" data-listing-detail="${l.listing_id}">Details</button></div>
  </article>`;
}

function renderBuildings(){
  const query=byId('buildingSearch').value.trim().toLowerCase();const district=byId('buildingDistrict').value;
  const result=buildings.filter(b=>(!district||b.district===district)&&`${b.name} ${b.address||''}`.toLowerCase().includes(query));
  byId('buildingCount').textContent=`${number(result.length)} Treffer`;
  byId('buildingList').innerHTML=result.length?result.map(buildingCard).join(''):'<div class="empty">Keine Gebäude gefunden.</div>';
}
function renderListings(){
  const query=byId('listingSearch').value.trim().toLowerCase();const district=byId('listingDistrict').value;
  const source=currentListingFilter||listings;
  const result=source.filter(l=>(!district||l.district===district)&&`${l.building_name_raw||''} ${l.portal_broker||''}`.toLowerCase().includes(query));
  byId('listingCount').textContent=`${number(result.length)} Treffer`;
  byId('listingList').innerHTML=result.length?result.map(listingCard).join(''):'<div class="empty">Keine Anzeigen gefunden.</div>';
}
function renderFavorites(){
  const ids=favorites();const result=buildings.filter(b=>ids.includes(Number(b.building_id)));
  byId('favoriteList').innerHTML=result.length?result.map(buildingCard).join(''):'<div class="empty">Noch keine Favoriten gespeichert.</div>';
}
function matchingListings(){
  const max=Number(byId('maxPrice').value)||Infinity;const beds=Number(byId('minBeds').value)||0;const floor=Number(byId('minFloor').value)||0;
  return listings.filter(l=>(Number(l.asking_price_brl)||Infinity)<=max&&(Number(l.bedrooms)||0)>=beds&&(!byId('seaView').checked||Number(l.has_sea_view)===1)&&(!byId('balcony').checked||Number(l.has_balcony)===1)&&(!floor||Number(l.floor_number)>=floor||Number(l.high_floor)===1));
}
function renderHomeMatches(){const result=matchingListings().slice(0,6);byId('homeMatches').innerHTML=result.length?result.map(x=>listingCard(x,true)).join(''):'<div class="empty">Aktuell keine vollständig passenden Treffer in diesem Datenstand.</div>'}

function toggleFavorite(id){let values=favorites();const numberId=Number(id);if(values.includes(numberId)){values=values.filter(x=>x!==numberId);toast('Favorit entfernt')}else{values.push(numberId);toast('Favorit gespeichert')}saveFavorites(values);renderBuildings();renderFavorites()}
function showBuilding(id){
  const b=buildings.find(x=>Number(x.building_id)===Number(id));if(!b)return;const s=buildingSummary(id);const linked=listings.filter(x=>Number(x.building_id)===Number(id));
  byId('detailContent').innerHTML=`<span class="eyebrow dark">Gebäude</span><h2>${esc(b.name)}</h2><p class="sub">${esc(b.address||'Adresse offen')} · ${esc(b.district||'')}</p>
    ${facts([b.completion_year&&`Baujahr ${b.completion_year}`,b.typical_area_m2&&`typ. ${number(b.typical_area_m2)} m²`,b.max_known_area_m2&&`max. ${number(b.max_known_area_m2)} m²`,b.max_bedrooms&&`bis ${b.max_bedrooms} Schlafzimmer`,Number(b.has_pool)===1?'Pool':null])}
    <div class="panel"><div class="price">${s.avg_asking_price_brl?`Ø ${money(s.avg_asking_price_brl)}`:'Preis noch offen'}</div><div class="sub">${number(s.listing_count||0)} Anzeigen · Ø ${money(s.avg_price_per_m2_brl)}/m²</div></div>
    <h3>Zugeordnete Anzeigen</h3><div class="detail-listings">${linked.length?linked.map(x=>listingCard(x,true)).join(''):'<p class="sub">Keine Anzeigen zugeordnet.</p>'}</div>`;
  byId('detailDialog').showModal();
}
function showListing(id){
  const l=listings.find(x=>Number(x.listing_id)===Number(id));if(!l)return;
  byId('detailContent').innerHTML=`<span class="eyebrow dark">Anzeige</span><h2>${esc(l.building_name_raw||'Wohnung')}</h2><div class="price">${money(l.asking_price_brl)}</div>${facts([l.area_m2&&`${number(l.area_m2)} m²`,l.bedrooms&&`${l.bedrooms} Schlafzimmer`,l.floor_number&&`${l.floor_number}. Stock`,Number(l.has_balcony)===1?'Varanda':null,Number(l.has_sea_view)===1?'Meerblick':null])}<p>${esc(l.notes||'')}</p>${l.url?`<a class="action" href="${esc(l.url)}" target="_blank" rel="noopener" style="display:inline-block;text-decoration:none">Quelle öffnen</a>`:''}`;
  byId('detailDialog').showModal();
}
function switchView(id){document.querySelectorAll('.view,.tab').forEach(el=>el.classList.remove('active'));byId(id).classList.add('active');document.querySelector(`.tab[data-view="${id}"]`).classList.add('active');window.scrollTo({top:0,behavior:'smooth'})}

document.addEventListener('click',event=>{
  const detail=event.target.closest('[data-building-detail]');if(detail)showBuilding(detail.dataset.buildingDetail);
  const listing=event.target.closest('[data-listing-detail]');if(listing)showListing(listing.dataset.listingDetail);
  const fav=event.target.closest('[data-favorite]');if(fav)toggleFavorite(fav.dataset.favorite);
  const tab=event.target.closest('.tab');if(tab)switchView(tab.dataset.view);
});
byId('buildingSearch').addEventListener('input',renderBuildings);byId('buildingDistrict').addEventListener('change',renderBuildings);
byId('listingSearch').addEventListener('input',renderListings);byId('listingDistrict').addEventListener('change',renderListings);
['maxPrice','minBeds','minFloor','seaView','balcony'].forEach(id=>byId(id).addEventListener('change',renderHomeMatches));
byId('showMatches').addEventListener('click',()=>{currentListingFilter=matchingListings();switchView('listingsView');renderListings()});
byId('closeDialog').addEventListener('click',()=>byId('detailDialog').close());
byId('detailDialog').addEventListener('click',event=>{if(event.target===byId('detailDialog'))byId('detailDialog').close()});
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();deferredPrompt=event;byId('installButton').hidden=false});
byId('installButton').addEventListener('click',async()=>{if(!deferredPrompt)return;deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;byId('installButton').hidden=true});
window.addEventListener('appinstalled',()=>toast('App wurde installiert'));
if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('./service-worker.js'));
init();
