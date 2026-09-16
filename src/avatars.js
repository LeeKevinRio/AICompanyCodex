// Stable IDs map old male/female choices to the expanded 7x5 atlas.
const slots=[27,0,28,1,29,30,2,31,...Array.from({length:24},(_,i)=>i+3),32,33,34];
export const avatarNames=slots.map(s=>s<27?`女・${String(s+1).padStart(2,'0')}`:`男・${String(s-26).padStart(2,'0')}`);
export function avatarSvg(id=0){id=Number.isInteger(id)&&id>=0&&id<35?id:0;const s=slots[id];return `<span class="real-portrait" role="img" aria-label="${avatarNames[id]}" style="background-image:url('/portraits-35.png');background-size:700% 500%;background-position:${s%7*100/6}% ${Math.floor(s/7)*25}%"></span>`;}
