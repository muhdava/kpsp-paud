function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function warna(s){
  if(!s)return'abu';
  if(['Normal','Gizi baik','Berat badan normal','Sesuai umur'].includes(s))return'hijau';
  if(s.startsWith('Tidak dinilai')||s.startsWith('Di luar'))return'abu';
  if(['Gizi kurang','Pendek','Berat badan kurang','Berisiko gizi lebih','Risiko berat badan lebih','Gizi lebih','Tinggi','Meragukan'].includes(s))return'kuning';
  return'merah';
}
const LABEL={bbu:'BB/U',tbu:'PB/U atau TB/U',bbtb:'BB/PB atau BB/TB',imtu:'IMT/U',lku:'Lingkar kepala/U',lila:'LiLA'};
function renderGizi(g){
  if(!g)return'';
  const ks=Object.keys(LABEL).filter(k=>g[k]);
  if(!ks.length)return'<p class="redup kecil">Isi BB, TB, LK, atau LiLA untuk melihat status gizi.</p>';
  let h='';
  if(g.status_gizi)h+=`<div class="hasil-box ${warna(g.status_gizi)}"><small>Status gizi (${esc(g.indeks_utama)})</small><b class="big">${esc(g.status_gizi)}</b></div>`;
  h+='<div class="gz anim">'+ks.map(k=>`<div><small>${LABEL[k]}</small><b><span class="badge ${warna(g[k].status)}">${esc(g[k].status)}</span></b>${g[k].z!=null?`<small>z-score ${g[k].z>0?'+':''}${g[k].z.toFixed(2)}</small>`:''}</div>`).join('')+'</div>';
  if(g.imt)h+=`<p class="kecil redup">IMT ${g.imt} kg/m²${g.tb_koreksi?` · PB/TB dipakai ${g.tb_koreksi} cm`:''}</p>`;
  if(g.catatan&&g.catatan.length)h+=`<p class="kecil redup">${g.catatan.map(esc).join('; ')}</p>`;
  return h;
}

/* ---------- Motion ---------- */
const kurangGerak=matchMedia('(prefers-reduced-motion: reduce)').matches;

// muncul saat di-scroll (stagger per kelompok)
const pengamat='IntersectionObserver' in window?new IntersectionObserver(es=>{
  es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('terlihat');pengamat.unobserve(e.target)}})
},{threshold:.08,rootMargin:'0px 0px -30px 0px'}):null;
function amatiReveal(root=document){
  const el=root.querySelectorAll('.reveal:not(.terlihat)');
  el.forEach((x,i)=>{if(!x.style.getPropertyValue('--i'))x.style.setProperty('--i',Math.min(i,8));pengamat?pengamat.observe(x):x.classList.add('terlihat')});
  root.querySelectorAll('.kartu:has(.bar)').forEach(k=>{if(!k.classList.contains('reveal')){k.classList.add('reveal');pengamat?pengamat.observe(k):k.classList.add('terlihat')}});
}

// angka berjalan
function hitungNaik(el){
  const akhir=parseFloat(el.dataset.hitung)||0;if(kurangGerak||akhir===0){el.textContent=akhir;return}
  const t0=performance.now(),dur=900;
  (function f(t){const p=Math.min((t-t0)/dur,1),e=1-Math.pow(1-p,3);el.textContent=Math.round(akhir*e);if(p<1)requestAnimationFrame(f)})(t0);
}

// efek ripple tombol
document.addEventListener('pointerdown',e=>{
  const b=e.target.closest('.btn');if(!b||kurangGerak)return;
  const r=b.getBoundingClientRect(),s=Math.max(r.width,r.height),sp=document.createElement('span');
  sp.className='ripple';sp.style.cssText=`width:${s}px;height:${s}px;left:${e.clientX-r.left-s/2}px;top:${e.clientY-r.top-s/2}px`;
  b.appendChild(sp);setTimeout(()=>sp.remove(),650);
});

// lihat/sembunyikan password
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-lihat]');if(!b)return;const i=document.getElementById(b.dataset.lihat);i.type=i.type==='password'?'text':'password';
});

// transisi keluar halaman untuk tautan internal
document.addEventListener('click',e=>{
  const a=e.target.closest('a[href]');if(!a||kurangGerak||e.ctrlKey||e.metaKey||e.shiftKey||a.target||a.hasAttribute('download'))return;
  const u=new URL(a.href,location.href);if(u.origin!==location.origin||u.pathname===location.pathname&&u.hash||u.searchParams.get('format'))return;
  e.preventDefault();document.body.classList.add('keluar');setTimeout(()=>location.href=a.href,90);
});
addEventListener('pageshow',()=>document.body.classList.remove('keluar'));

// tombol loading saat form dikirim
document.addEventListener('submit',e=>{if(e.defaultPrevented)return;const b=e.submitter;if(b&&b.classList.contains('btn')&&!b.name)setTimeout(()=>b.classList.add('loading'),0)});

document.addEventListener('DOMContentLoaded',()=>{
  amatiReveal();
  document.querySelectorAll('[data-hitung]').forEach(el=>{
    if(pengamat){const o=new IntersectionObserver(es=>{if(es[0].isIntersecting){hitungNaik(el);o.disconnect()}});o.observe(el)}else hitungNaik(el)});
  // flash otomatis hilang
  document.querySelectorAll('.flash.ok').forEach(f=>setTimeout(()=>{f.classList.add('hilang');setTimeout(()=>f.remove(),500)},4500));
});

/* ---------- Navigasi: sidebar buka-tutup + indikator geser ---------- */
(function(){
  const html=document.documentElement;
  const simpan=(k,v)=>{try{sessionStorage.setItem(k,v)}catch(e){}};
  const ambil=k=>{try{return sessionStorage.getItem(k)}catch(e){return null}};
  const menus=[
    {el:document.getElementById('sbMenu'),ind:document.getElementById('sbInd'),sumbu:'y'},
    {el:document.getElementById('bnMenu'),ind:document.getElementById('bnInd'),sumbu:'x'}
  ].filter(m=>m.el&&m.ind);

  function geser(m,item,langsung){
    if(!item||!item.offsetParent){m.ind.classList.remove('siap');return}
    if(item.classList.contains('bn-plus')){m.ind.classList.remove('siap');return}
    if(langsung){m.ind.style.transition='none'}
    if(m.sumbu==='y'){m.ind.style.transform=`translateY(${item.offsetTop}px)`;m.ind.style.height=item.offsetHeight+'px'}
    else{const w=m.ind.offsetWidth||64;m.ind.style.transform=`translateX(${item.offsetLeft+item.offsetWidth/2-w/2}px)`}
    m.ind.classList.add('siap');
    if(langsung){m.ind.offsetWidth;m.ind.style.transition=''}
  }
  function aktif(m){return m.el.querySelector('[data-nav].on')}

  // posisi awal: mulai dari menu halaman sebelumnya, lalu geser ke menu sekarang
  const dari=ambil('navDari');
  menus.forEach(m=>{
    const sekarang=aktif(m),lama=dari&&m.el.querySelector(`[data-nav="${dari}"]`);
    if(lama&&lama!==sekarang&&!kurangGerak&&!lama.classList.contains('bn-plus')){
      geser(m,lama,true);
      if(sekarang){
        sekarang.classList.remove('on');lama.classList.add('on');
        requestAnimationFrame(()=>requestAnimationFrame(()=>{lama.classList.remove('on');sekarang.classList.add('on');geser(m,sekarang)}));
      }else m.ind.classList.remove('siap');
    }else geser(m,sekarang,true);
  });
  requestAnimationFrame(()=>requestAnimationFrame(()=>html.classList.remove('tanpa-anim')));
  simpan('masuk','1');

  // klik menu: indikator langsung bergeser, lalu pindah halaman
  menus.forEach(m=>m.el.addEventListener('click',e=>{
    const a=e.target.closest('a[data-nav]');if(!a||e.ctrlKey||e.metaKey||e.shiftKey)return;
    e.preventDefault();e.stopPropagation();
    if(a.classList.contains('on')&&a.href===location.href)return;
    menus.forEach(mm=>{const t=mm.el.querySelector(`[data-nav="${a.dataset.nav}"]`);mm.el.querySelectorAll('[data-nav]').forEach(x=>x.classList.toggle('on',x===t));if(t)geser(mm,t)});
    simpan('navDari',a.dataset.nav);
    setTimeout(()=>{location.href=a.href},kurangGerak?0:170);
  }));
  // pindah halaman lewat tautan lain: simpan menu aktif sekarang
  addEventListener('pagehide',()=>{const m=menus[0]||menus[1];const a=m&&aktif(m);if(a)simpan('navDari',a.dataset.nav)});

  // buka / tutup sidebar
  const tg=document.getElementById('sbToggle');
  if(tg)tg.addEventListener('click',()=>{
    const tutup=html.classList.toggle('sb-tutup');
    try{localStorage.setItem('sidebar',tutup?'tutup':'buka')}catch(e){}
    tg.setAttribute('aria-expanded',String(!tutup));
  });
  if('ResizeObserver' in window)menus.forEach(m=>new ResizeObserver(()=>geser(m,aktif(m),true)).observe(m.el));
  else addEventListener('resize',()=>menus.forEach(m=>geser(m,aktif(m),true)));
  // bila font selesai dimuat, ukuran bisa berubah
  if(document.fonts)document.fonts.ready.then(()=>menus.forEach(m=>geser(m,aktif(m),true)));
})();

/* ---------- Prefetch: muat halaman lebih dulu saat link disentuh/di-hover ---------- */
(function(){
  const sudah=new Set();
  function pre(a){
    if(!a||!a.href||sudah.has(a.href))return;const u=new URL(a.href,location.href);
    if(u.origin!==location.origin||u.pathname==='/logout'||u.searchParams.get('format'))return;
    sudah.add(a.href);const l=document.createElement('link');l.rel='prefetch';l.href=a.href;document.head.appendChild(l);
  }
  document.addEventListener('pointerover',e=>pre(e.target.closest&&e.target.closest('a[href]')),{passive:true});
  document.addEventListener('touchstart',e=>pre(e.target.closest&&e.target.closest('a[href]')),{passive:true});
})();

/* ---------- Tabel -> kartu di HP: beri label kolom otomatis ---------- */
document.querySelectorAll('.tbl-wrap table').forEach(t=>{
  if(t.classList.contains('tbl-hp'))return;
  const h=[...t.querySelectorAll('thead th')].map(th=>th.textContent.trim());
  if(!h.length)return;
  t.classList.add('tbl-kartu');
  t.querySelectorAll('tbody tr').forEach(tr=>[...tr.children].forEach((td,i)=>{if(h[i]&&!td.hasAttribute('data-label'))td.setAttribute('data-label',h[i])}));
});
