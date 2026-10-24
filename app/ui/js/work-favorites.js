/* Task catalogue preferences only: never adds or starts queue items. */
(()=>{
 const state={favorites:{},only:false,categories:{},pending:new Set(),loaded:false,error:''};
 const supported=r=>['gather','craft','alter'].includes(r.k);
 const key=r=>String(r.id).startsWith(r.k+':')?String(r.id):r.k+':'+String(r.id);
 function category(r){
  if(r.k==='craft')return String(r.rec?.cat||r.rec?.skill||'미분류').trim()||'미분류';
  if(r.k==='alter')return String(r.rec?.facility||r.rec?.cat||'미분류').trim()||'미분류';
  return '';
 }
 function render(){if(dwEl().open)dwRenderBody();}
 async function refresh(){
  try{const r=await api('/api/work/favorites');if(!r?.ok)throw new Error(r?.message||'작업 즐겨찾기를 불러오지 못했습니다.');state.favorites=r.favorites||{};state.loaded=true;state.error='';}
  catch(e){state.error=e.message||'작업 즐겨찾기 조회 오류';}
  render();
 }
 function html(r){
  if(!supported(r))return `<span class="kd ${esc(r.k)}">${esc(DW_KO[r.k]||'작업')}</span>`;
  const k=key(r),on=state.favorites[k]===true;
  return `<button type="button" class="kd work-favorite${on?' on':''}" data-work-favorite aria-pressed="${on}" aria-label="${esc(r.name)} 즐겨찾기 ${on?'해제':'추가'}" title="${esc(DW_KO[r.k])} · 즐겨찾기 ${on?'해제':'추가'}"${!state.loaded||state.pending.size?' disabled':''}>${on?'★':'☆'}</button>`;
 }
 function bind(el,r){
  const b=el.querySelector('[data-work-favorite]');if(!b)return;
  b.onclick=async e=>{
   e.preventDefault();e.stopPropagation();const k=key(r);if(state.pending.size||!state.loaded)return;
   state.pending.add(k);render();
   try{const result=await api('/api/work/favorites',{key:k,enabled:state.favorites[k]!==true});
    if(!result?.ok)throw new Error(result?.message||'즐겨찾기를 저장하지 못했습니다.');
    state.favorites=result.favorites||{};state.error='';
   }catch(error){state.error=error.message||'즐겨찾기 저장 오류';toast(state.error);}
   finally{state.pending.delete(k);render();}
  };
 }
 function chip(box){
  const header=$('dwHd')?.firstElementChild;
  if(header){header.textContent=DW.type==='collect'?'종류':'☆';header.title='즐겨찾기';header.setAttribute('aria-label','즐겨찾기');}
  $('dwWorkFavorites')?.remove();
  $('dwFavoriteDivider')?.remove();
  const count=DW.rows.filter(r=>supported(r)&&(DW.type==='all'||r.k===DW.type)&&state.favorites[key(r)]===true).length;
  const b=document.createElement('button');b.type='button';b.id='dwWorkFavorites';b.className='work-favorites-filter'+(state.only?' on':'');
  b.textContent='★';b.setAttribute('aria-label',`즐겨찾기 ${fmtN(count)}개`);b.setAttribute('aria-pressed',String(state.only));
  b.title=state.error||'별을 표시한 작업만 보기';b.disabled=!state.loaded;
  b.onclick=()=>{state.only=!state.only;if(!['all','gather','craft','alter'].includes(DW.type))DW.type='all';DW.limit=DW_PAGE;render();};
  const tabs=$('dwSeg');if(tabs){const divider=document.createElement('span');divider.id='dwFavoriteDivider';divider.textContent='|';divider.setAttribute('aria-hidden','true');tabs.prepend(divider);tabs.prepend(b);}
  if(state.error){const retry=document.createElement('button');retry.type='button';retry.textContent='즐겨찾기 다시 불러오기';retry.onclick=refresh;box.append(retry);}
 }
 function categories(box){
  if(['craft','alter'].includes(DW.type)){
   const counts=new Map();for(const row of DW.rows)if(row.k===DW.type){const c=category(row);counts.set(c,(counts.get(c)||0)+1);}
   const selected=state.categories[DW.type]||'';
   const values=[['',DW.rows.filter(r=>r.k===DW.type).length],...counts];
   box.innerHTML=values.map(([c,n])=>`<button type="button" data-work-category="${esc(c)}" class="${selected===c?'on':''}" aria-pressed="${selected===c}">${esc(c||'전체 분류')} ${fmtN(n)}</button>`).join('');
   box.querySelectorAll('[data-work-category]').forEach(b=>b.onclick=()=>{state.categories[DW.type]=b.dataset.workCategory;DW.limit=DW_PAGE;render();});
  }
  chip(box);
 }
 const filter=r=>{
  if(state.only&&['all','gather','craft','alter'].includes(DW.type)&&(!supported(r)||state.favorites[key(r)]!==true))return false;
  const c=state.categories[DW.type];return !c||!['craft','alter'].includes(DW.type)||category(r)===c;
 };
 Object.assign(MW,{workFavoriteHTML:html,workFavoriteBind:bind,workFavoritesChip:chip,workCategories:categories,workRowFilter:filter,refreshWorkFavorites:refresh});
 refresh();
})();
