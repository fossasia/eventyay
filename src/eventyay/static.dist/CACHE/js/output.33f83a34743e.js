const onReady=(fn)=>{if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",fn)}else{fn()}};const setupLightbox=()=>{const dialog=document.querySelector("dialog#lightbox-dialog")
const img=dialog.querySelector("img")
const caption=dialog.querySelector("figcaption")
if(!dialog||!img)return
dialog.addEventListener("click",()=>dialog.close())
dialog.querySelector(".modal-card-content").addEventListener("click",(ev)=>ev.stopPropagation())
dialog.querySelector("button#lightbox-close").addEventListener("click",()=>dialog.close())
document.querySelectorAll("a[data-lightbox], img[data-lightbox]").forEach((element)=>{element.addEventListener("click",function(ev){console.log("lightbox click")
const image=element.tag==="A"?element.querySelector("img"):element
console.log(image)
const imageUrl=element.dataset.lightbox||element.href||image.src
console.log(imageUrl)
const label=image.alt
console.log(label)
if(!imageUrl)return
ev.preventDefault()
img.src=imageUrl
caption.textContent=label||""
dialog.showModal()})})}
onReady(setupLightbox);'use strict';const GLOBAL_INIT_FLAG='eventyayDropdownGlobalInit';const initializedDropdowns=new WeakSet();const getOpenDropdowns=function(){return document.querySelectorAll('details.dropdown[open]');};const closeAllDropdowns=function(){getOpenDropdowns().forEach(function(dropdown){dropdown.open=false;});};const closeOtherDropdowns=function(current){getOpenDropdowns().forEach(function(other){if(other===current)return;if(other.contains(current))return;if(current.contains(other))return;other.open=false;});};const ensureGlobalListeners=function(){if(document.documentElement.dataset[GLOBAL_INIT_FLAG]==='1'){return;}
document.documentElement.dataset[GLOBAL_INIT_FLAG]='1';const handlePossibleOutsideInteraction=function(event){getOpenDropdowns().forEach(function(dropdown){if(!dropdown.contains(event.target)){dropdown.open=false;}});};document.addEventListener('pointerdown',handlePossibleOutsideInteraction,true);document.addEventListener('keydown',function(event){if(event.key!=='Escape'&&event.key!=='Esc')return;closeAllDropdowns();});};const initDropdowns=function(){ensureGlobalListeners();document.querySelectorAll('details.dropdown').forEach(function(dropdown){if(initializedDropdowns.has(dropdown))return;initializedDropdowns.add(dropdown);dropdown.addEventListener('toggle',function(){if(!dropdown.open)return;closeOtherDropdowns(dropdown);});});};if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',initDropdowns);}else{initDropdowns();}
export{initDropdowns};;