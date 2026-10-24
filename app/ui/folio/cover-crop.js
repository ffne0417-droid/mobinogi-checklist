/* Fixed cover canvas; images stay local until the user chooses Save. */
(()=>{
  const W=1000,H=1420;let current=null,frame=0,sequence=0;
  function setup(){
    if(document.getElementById('cropSheet'))return;
    const scrim=document.createElement('div');scrim.id='cropScrim';scrim.hidden=true;
    const sheet=document.createElement('section');sheet.id='cropSheet';sheet.hidden=true;sheet.setAttribute('role','dialog');sheet.setAttribute('aria-modal','true');sheet.setAttribute('aria-labelledby','cropHeading');
    sheet.innerHTML='<div class="crop-head"><b id="cropHeading">커버 위치 조정</b><small>1000 × 1420 · 세로형 JPG</small></div><div class="crop-preview"><div id="cropStage"><canvas id="cropCanvas" width="300" height="426" aria-label="이미지를 드래그해 커버 위치 조정"></canvas></div><div class="crop-card"><canvas id="cropThumb" width="150" height="213"></canvas><div class="crop-meta"><small>적용 미리보기</small><div id="cropTitle"></div><div id="cropArtist"></div><div id="cropInfo"></div></div></div></div><div class="crop-controls"><button id="cropFill">꽉 채우기</button><button id="cropFit">전체 보기</button><label for="cropZoom">확대</label><input id="cropZoom" type="range" step="0.1"><span id="cropPercent"></span></div><div class="crop-foot"><button id="cropCancel">취소</button><span id="cropStatus">이미지를 드래그하고 크기를 조정하세요.</span><button id="cropSave" class="pri">저장 · 적용</button></div>';
    document.body.append(scrim,sheet);
    const stretch=document.createElement('div');stretch.className='crop-stretch';
    stretch.innerHTML='<label for="cropWidth">가로</label><input id="cropWidth" type="range" min="50" max="200" value="100"><output id="cropWidthValue">100%</output><label for="cropHeight">세로</label><input id="cropHeight" type="range" min="50" max="200" value="100"><output id="cropHeightValue">100%</output><button id="cropRatioReset">비율 초기화</button>';
    sheet.querySelector('.crop-foot').before(stretch);
    $('cropWidth').oninput=()=>stretchAxis('sx',Number($('cropWidth').value)/100);
    $('cropHeight').oninput=()=>stretchAxis('sy',Number($('cropHeight').value)/100);
    $('cropRatioReset').onclick=()=>{stretchAxis('sx',1);stretchAxis('sy',1);};
    $('cropCancel').onclick=close;scrim.onclick=close;
    $('cropFill').onclick=()=>fit(true);$('cropFit').onclick=()=>fit(false);
    $('cropZoom').oninput=()=>zoom(Number($('cropZoom').value)/100*current.cover);
    $('cropSave').onclick=save;
    const canvas=$('cropCanvas');let drag=null;
    canvas.onpointerdown=e=>{if(!current||current.busy||e.button!==0)return;e.preventDefault();drag={id:e.pointerId,x:e.clientX,y:e.clientY,left:current.x,top:current.y};canvas.setPointerCapture(e.pointerId);};
    canvas.onpointermove=e=>{if(!drag||drag.id!==e.pointerId||!current)return;const rect=canvas.getBoundingClientRect();current.x=drag.left+(e.clientX-drag.x)*W/rect.width;current.y=drag.top+(e.clientY-drag.y)*H/rect.height;current.uploaded=null;clamp();schedule();};
    const end=e=>{if(drag?.id!==e.pointerId)return;drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);};
    canvas.onpointerup=end;canvas.onpointercancel=end;
    document.addEventListener('keydown',e=>{if(current&&e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();close();}},true);
  }
  function clamp(){const c=current;if(!c)return;const width=c.image.naturalWidth*c.scale*c.sx,height=c.image.naturalHeight*c.scale*c.sy;c.x=Math.min(Math.max(c.x,Math.min(0,W-width)),Math.max(0,W-width));c.y=Math.min(Math.max(c.y,Math.min(0,H-height)),Math.max(0,H-height));}
  function paint(canvas){const c=current,ctx=canvas.getContext('2d');ctx.setTransform(canvas.width/W,0,0,canvas.height/H,0,0);ctx.fillStyle='#ffffff';ctx.fillRect(0,0,W,H);ctx.drawImage(c.image,c.x,c.y,c.image.naturalWidth*c.scale*c.sx,c.image.naturalHeight*c.scale*c.sy);}
  function render(){frame=0;if(!current)return;paint($('cropCanvas'));paint($('cropThumb'));$('cropZoom').value=String(current.scale/current.cover*100);$('cropPercent').textContent=Math.round(current.scale/current.cover*100)+'%';for(const [axis,id] of [['sx','cropWidth'],['sy','cropHeight']]){$(id).value=String(current[axis]*100);$(id+'Value').textContent=Math.round(current[axis]*100)+'%';}}
  function schedule(){if(!frame)frame=requestAnimationFrame(render);}
  function fit(fill){if(!current||current.busy)return;current.sx=current.sy=1;current.scale=fill?current.cover:current.contain;current.x=(W-current.image.naturalWidth*current.scale)/2;current.y=(H-current.image.naturalHeight*current.scale)/2;current.uploaded=null;schedule();}
  function stretchAxis(axis,value){const c=current;if(!c||c.busy)return;const pos=axis==='sx'?'x':'y',mid=axis==='sx'?W/2:H/2;c[pos]=mid-(mid-c[pos])*value/c[axis];c[axis]=value;c.uploaded=null;clamp();schedule();}
  function zoom(scale){if(!current||current.busy)return;const c=current,cx=(W/2-c.x)/c.scale,cy=(H/2-c.y)/c.scale;c.scale=scale;c.x=W/2-cx*scale;c.y=H/2-cy*scale;c.uploaded=null;clamp();schedule();}
  function close(){if(current?.busy)return;sequence++;if(frame)cancelAnimationFrame(frame);frame=0;if(current)URL.revokeObjectURL(current.url);current=null;if($('cropSheet')){$('cropSheet').hidden=true;$('cropScrim').hidden=true;}$('cAdd').disabled=false;$('cHint').textContent='원본 8MB까지 · 위치 조정 후 1000×1420 JPG로 저장';}
  async function open(file,song){
    setup();close();const seq=++sequence,image=new Image();let url='';$('cAdd').disabled=true;$('cHint').textContent='이미지 읽는 중…';
    try{
      url=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('파일을 읽지 못했습니다.'));reader.readAsDataURL(file);});
      await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error('이미지를 읽지 못했습니다. 다른 파일을 선택해주세요.'));image.src=url;});
      if(seq!==sequence){URL.revokeObjectURL(url);return;}
      if(!image.naturalWidth||!image.naturalHeight||image.naturalWidth*image.naturalHeight>40000000)throw new Error('원본 이미지가 너무 큽니다. 4천만 픽셀 이하 이미지를 선택해주세요.');
      current={image,url,song,file,cover:Math.max(W/image.naturalWidth,H/image.naturalHeight),contain:Math.min(W/image.naturalWidth,H/image.naturalHeight),busy:false,uploaded:null};
      $('cropZoom').min=String(current.contain/current.cover*100);$('cropZoom').max='400';
      const item=libOf(song)||song;$('cropTitle').textContent=item.song||item.cleaned||item.title||'';$('cropArtist').textContent=item.artist||'';
      $('cropInfo').textContent=[songTag(songIdOf(item)),item.duration?fmtSec(item.duration):''].filter(Boolean).join(' · ');
      $('cropStatus').textContent='드래그로 조정하세요. 저장 후에는 원본을 옮기거나 삭제해도 커버가 유지됩니다.';$('cropSheet').hidden=false;$('cropScrim').hidden=false;fit(true);
    }catch(error){URL.revokeObjectURL(url);if(seq===sequence){close();toast(error.message);}}
  }
  async function save(){
    const c=current;if(!c||c.busy)return;if(coverFor?.key!==c.song.key){$('cropStatus').textContent='곡 선택이 바뀌었습니다. 취소 후 다시 열어주세요.';return;}
    c.busy=true;const controls=[...$('cropSheet').querySelectorAll('button,input')];controls.forEach(b=>b.disabled=true);$('cropStatus').textContent='저장 중…';
    try{
      if(!c.uploaded){
        const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;paint(canvas);
        const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.92));if(!blob)throw new Error('이미지를 변환하지 못했습니다.');
        if(blob.size>(S.coverMax||8*1024*1024))throw new Error('저장 이미지가 8MB를 넘습니다.');
        const name=c.file.name.replace(/\.[^.]+$/,'')+'-cover.jpg';
        const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);let response;
        try{response=await fetch('/api/folio/covers/upload?name='+encodeURIComponent(name),{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Requested-With':'mobiworks','X-MobiWorks-Token':TOKEN},body:blob,signal:controller.signal});}
        catch(error){if(error.name==='AbortError')throw new Error('업로드 응답이 늦어 중단했습니다. 다시 저장을 눌러주세요.');throw error;}
        finally{clearTimeout(timer);}
        const data=await response.json().catch(()=>null);if(!response.ok||!data?.ok)throw new Error(data?.message||'커버 이미지를 올리지 못했습니다.');c.uploaded=data.value;
      }
      await setCover(c.uploaded);
      if(coverFor?.key===c.song.key)throw new Error('이미지는 업로드됐지만 곡에 적용하지 못했습니다. 다시 저장을 눌러주세요.');
      c.busy=false;close();
    }catch(error){$('cropStatus').textContent=error.message;}
    finally{c.busy=false;controls.forEach(b=>b.disabled=false);}
  }
  window.openCoverCrop=open;
  window.addEventListener('pagehide',()=>{if(current)URL.revokeObjectURL(current.url);});
})();
