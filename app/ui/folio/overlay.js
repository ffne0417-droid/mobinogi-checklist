/* Only loaded in the same-origin music overlay, never in the main app. */
(()=>{
  let view='list',wasPlaying=false,keyboardTarget=null;
  const originalOpen=openSheet,originalClose=closeSheet,originalMain=setMain;
  addEventListener('mobiworks-play-request',()=>parent.postMessage({type:'mobiworks-music-play-request'},location.origin));
  function send(){
    const input=document.activeElement===keyboardTarget&&!!keyboardTarget?.matches('input,textarea,[contenteditable="true"]');
    const picker=['isheet','csheet','dsheet'].some(id=>$(id).classList.contains('open'));
    parent.postMessage({type:'mobiworks-music-state',view,input,picker},location.origin);
  }
  function show(next){
    if(!['list','compact','expanded'].includes(next))return;
    if(next==='compact')next='list'; // Library and small player are one view.
    if(next==='expanded')originalOpen();else originalClose();
    view=next;document.body.dataset.musicView=view;send();
  }
  openSheet=()=>show('expanded');closeSheet=()=>show('compact');
  setMain=function(playing){
    originalMain(playing);
    if(playing&&!wasPlaying&&view==='list')show('compact');
    wasPlaying=!!playing;
  };
  // Original onclick properties hold the old functions; reconnect them.
  $('btnUp').onclick=e=>{e.stopPropagation();show('expanded');};
  $('grab').onclick=()=>show('compact');$('scrim').onclick=()=>show('compact');
  const edit=$('qEdit').onclick;
  $('qEdit').onclick=()=>{edit();show('list');};
  addEventListener('message',e=>{
    if(e.origin!==location.origin||e.source!==parent)return;
    if(e.data?.type==='mobiworks-music-view')show(e.data.view);
    if(e.data?.type==='mobiworks-music-status')send();
    if(e.data?.type==='mobiworks-music-refresh'){
      loadAll().then(()=>{if($('isheet').classList.contains('open'))renderInstSheet(false);}).catch(()=>toast('음악 목록을 다시 읽지 못했습니다.'));
    }
  });
  document.addEventListener('pointerdown',e=>{
    if(!e.isTrusted)return;
    keyboardTarget=e.target.matches('input:not([type="checkbox"]):not([type="radio"]):not([type="range"]),textarea,[contenteditable="true"]')?e.target:null;
    send();
  },true);
  document.addEventListener('focusin',()=>setTimeout(send,0));
  document.addEventListener('focusout',()=>setTimeout(send,0));
  window.addEventListener('blur',()=>{keyboardTarget=null;send();});
  // A picker or edit sheet needs room even if opened from the small player.
  const watch=new MutationObserver(send);
  for(const id of ['isheet','csheet','dsheet'])watch.observe($(id),{attributes:true,attributeFilter:['class']});
  show('list');
})();
