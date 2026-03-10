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
onReady(setupLightbox);