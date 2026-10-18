(function(root){
 function nextDates(asOf,count,calendar){
  if(!calendar)return null;const d=new Date(asOf+'T00:00:00Z');if(!Number.isFinite(d.getTime()))return null;const result=[];
  for(let i=0;i<90;i++){d.setUTCDate(d.getUTCDate()+1);const date=d.toISOString().slice(0,10);if(!(calendar.years||[]).includes(d.getUTCFullYear())||Object.hasOwn(calendar.unknown||{},date))return null;const open=Object.hasOwn(calendar.opened||{},date)||(!Object.hasOwn(calendar.closed||{},date)&&![0,6].includes(d.getUTCDay()));if(open)result.push(date);if(result.length===count)return result}return null;
 }
 root.CalendarModel={nextDates};if(typeof module!=='undefined')module.exports=root.CalendarModel;
})(typeof globalThis!=='undefined'?globalThis:this);
