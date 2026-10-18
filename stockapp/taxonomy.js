(function(root){
const groups={
'半導體':['晶圓代工','IC 設計','IC 設計服務／ASIC','矽智財 IP','封裝測試','先進封裝','半導體設備','半導體材料','矽晶圓','功率半導體'],
'記憶體':['DRAM','NAND Flash','NOR Flash','記憶體模組','記憶體控制晶片','記憶體封測'],
'PCB／載板':['PCB','軟板 FPC','HDI','IC 載板','ABF 載板','BT 載板','銅箔基板 CCL','銅箔','玻纖布','PCB 設備及材料'],
'面板／顯示':['LCD 面板','OLED','Mini LED','Micro LED','LED','背光模組','驅動 IC','觸控','偏光板及顯示材料'],
'伺服器／電腦':['AI 伺服器','一般伺服器','伺服器主機板','機殼','機櫃','筆電','桌機','工業電腦','儲存設備'],
'散熱':['散熱模組','風扇','熱管／均熱板','均熱片','液冷','冷板','CDU','浸沒式散熱'],
'電源／電力電子':['電源供應器','UPS','電源管理 IC','變壓器','電池模組','電力轉換設備'],
'電子零組件':['被動元件','MLCC','電阻／電感','連接器','線材','石英元件','繼電器','感測器'],
'網通／光通訊':['交換器','路由器','Wi-Fi','寬頻設備','5G','基地台','光纖','光收發模組','矽光子／CPO','衛星通訊'],
'消費電子／光學':['手機供應鏈','穿戴裝置','聲學','鏡頭','影像模組','AR／VR','遊戲硬體'],
'軟體／數位服務':['資訊服務','系統整合','企業軟體','雲端服務','資安','AI 軟體','電子商務','數位支付'],
'電子通路':['半導體通路','零組件通路','資訊產品通路'],
'汽車／車用':['整車','汽車零組件','車用電子','ADAS','車用鏡頭','車用照明','電動車','充電樁','電池材料'],
'機械／自動化':['工具機','精密機械','工業自動化','機器人','運動控制','氣動元件','機械零組件'],
'重電／電纜':['變壓器','配電盤','開關設備','電線電纜','電網工程'],
'綠能／環保':['太陽能','風電','儲能','再生能源開發','能源管理','廢棄物處理','資源回收','水處理'],
'原物料／化工':['鋼鐵','不鏽鋼','非鐵金屬','水泥','塑膠','石化','特用化學','肥料','橡膠','玻璃陶瓷','造紙'],
'紡織／製鞋':['化纖','紡紗','織布','機能布','成衣','製鞋','鞋材'],
'航運／物流':['貨櫃航運','散裝航運','航空','貨運承攬','倉儲物流','陸運'],
'金融':['金控','銀行','壽險','產險','再保險','證券','期貨','投信／資產管理','租賃／融資','金融服務'],
'生技／醫療':['新藥研發','藥品製劑','學名藥','原料藥 API','CDMO／CMO','生物製劑／生物相似藥','疫苗','細胞治療','幹細胞研發','基因治療','再生醫療','細胞儲存／臍帶血','體外診斷 IVD','基因檢測／定序','血糖監測','醫學影像／診斷設備','手術／治療設備','醫療耗材','眼科／隱形眼鏡','牙科／齒科','骨科／植入物','復健／輔具','洗腎／血液透析','醫材通路','藥局／藥品通路','醫療院所／服務','長照／居家照護','數位醫療','保健食品','醫學美容'],
'食品／農業':['食品加工','飲料','飼料','畜牧','水產','農業科技'],
'內需／消費':['百貨','零售','超商','餐飲','觀光','飯店','旅行社','居家生活'],
'運動／休閒':['自行車','運動用品','健身器材','戶外用品'],
'營建／資產':['不動產開發','住宅建設','商辦／商用不動產','營造工程','土木／公共工程','廠房／機電工程','建材','預拌混凝土','鋼構','裝修／室內工程','不動產租賃','物業管理','資產開發'],
'油電／燃氣':['石油','天然氣','燃氣供應','發電'],
'文化／娛樂':['遊戲軟體','影音','出版','文創'],
'其他／多角化':['多事業公司','綜合事業','待確認'],
'ETF／基金':['市值型 ETF','高股息 ETF','主題型 ETF','債券 ETF','主動式 ETF','槓桿／反向 ETF','REIT／不動產基金']};
const official={'01':'水泥工業','02':'食品工業','03':'塑膠工業','04':'紡織纖維','05':'電機機械','06':'電器電纜','08':'玻璃陶瓷','09':'造紙工業','10':'鋼鐵工業','11':'橡膠工業','12':'汽車工業','14':'建材營造','15':'航運業','16':'觀光餐旅','17':'金融保險','18':'貿易百貨','19':'綜合','20':'其他','21':'化學工業','22':'生技醫療業','23':'油電燃氣業','24':'半導體業','25':'電腦及週邊設備業','26':'光電業','27':'通信網路業','28':'電子零組件業','29':'電子通路業','30':'資訊服務業','31':'其他電子業','32':'文化創意業','33':'農業科技','34':'電子商務','35':'綠能環保','36':'數位雲端','37':'運動休閒','38':'居家生活'};
const broad={'01':'原物料／化工','02':'食品／農業','03':'原物料／化工','04':'紡織／製鞋','05':'機械／自動化','06':'重電／電纜','08':'原物料／化工','09':'原物料／化工','10':'原物料／化工','11':'原物料／化工','12':'汽車／車用','14':'營建／資產','15':'航運／物流','16':'內需／消費','17':'金融','18':'內需／消費','21':'原物料／化工','22':'生技／醫療','23':'油電／燃氣','24':'半導體','25':'伺服器／電腦','26':'面板／顯示','27':'網通／光通訊','28':'電子零組件','29':'電子通路','30':'軟體／數位服務','32':'文化／娛樂','33':'食品／農業','34':'軟體／數位服務','35':'綠能／環保','36':'軟體／數位服務','37':'運動／休閒','38':'內需／消費'};
const chainGroups={'半導體':'半導體','製藥':'生技／醫療','醫療器材':'生技／醫療','食品生技':'生技／醫療','再生醫療':'生技／醫療','印刷電路板':'PCB／載板','平面顯示器':'面板／顯示','觸控面板':'面板／顯示','金融':'金融','建材營造':'營建／資產','被動元件':'電子零組件','連接器':'電子零組件'};
// Rule labels come from official value-chain membership, never from price or a news headline.
const rules=[['記憶體',/DRAM/i,'DRAM'],['記憶體',/NAND/i,'NAND Flash'],['記憶體',/NOR/i,'NOR Flash'],['記憶體',/記憶體模組/,'記憶體模組'],['半導體',/晶圓代工/,'晶圓代工'],['半導體',/IC設計|IC 設計/,'IC 設計'],['半導體',/封裝|測試/,'封裝測試'],['半導體',/矽晶圓/,'矽晶圓'],['PCB／載板',/載板/,'IC 載板'],['PCB／載板',/銅箔基板/,'銅箔基板 CCL'],['PCB／載板',/軟板|軟性/,'軟板 FPC'],['金融',/金融控股|金控/,'金控'],['金融',/銀行/,'銀行'],['金融',/人壽|壽險/,'壽險'],['金融',/產物|產險/,'產險'],['金融',/證券/,'證券'],['金融',/期貨/,'期貨'],['金融',/租賃|融資/,'租賃／融資'],['營建／資產',/混凝土/,'預拌混凝土'],['營建／資產',/鋼構/,'鋼構'],['營建／資產',/營造/,'營造工程'],['營建／資產',/建設/,'不動產開發'],['營建／資產',/建材/,'建材'],['營建／資產',/機電工程/,'廠房／機電工程'],['營建／資產',/物業管理/,'物業管理'],['營建／資產',/裝潢/,'裝修／室內工程'],['營建／資產',/基礎工程/,'土木／公共工程'],['生技／醫療',/原料藥/,'原料藥 API'],['生技／醫療',/CDMO|CMO|委託.*製造/i,'CDMO／CMO'],['生技／醫療',/新藥/,'新藥研發'],['生技／醫療',/製劑/,'藥品製劑'],['生技／醫療',/疫苗/,'疫苗'],['生技／醫療',/臍帶血|細胞儲存|幹細胞收集儲存/,'細胞儲存／臍帶血'],['生技／醫療',/細胞治療/,'細胞治療'],['生技／醫療',/幹細胞開發/,'幹細胞研發'],['生技／醫療',/基因治療/,'基因治療'],['生技／醫療',/隱型眼鏡|隱形眼鏡|光學鏡片/,'眼科／隱形眼鏡'],['生技／醫療',/血糖/,'血糖監測'],['生技／醫療',/體外診斷/,'體外診斷 IVD'],['生技／醫療',/基因檢測|定序/,'基因檢測／定序'],['生技／醫療',/牙科|齒科/,'牙科／齒科'],['生技／醫療',/骨科|植入|人工關節/,'骨科／植入物'],['生技／醫療',/復健|輔具|輪椅/,'復健／輔具'],['生技／醫療',/醫療耗材/,'醫療耗材'],['生技／醫療',/醫療器材代理/,'醫材通路'],['生技／醫療',/藥局|藥品.*通路/,'藥局／藥品通路'],['生技／醫療',/保健|機能性食品/,'保健食品']];
const themeChains=new Set(['人工智慧','雲端運算','資通訊安全','大數據','太空衛星科技','金融科技','區塊鏈','再生醫療','自動化']);
const verifiedDetails={
"3707":{"expectedName": "漢磊", "group": "半導體", "details": ["晶圓代工", "功率半導體"], "url": "https://www.episil.com/zh-tw", "checkedAt": "2026-10-17", "note": "功率半導體與GaN／SiC晶圓代工；舊DRAM分類撤除"},
"6770":{"expectedName": "力積電", "group": "半導體", "details": ["晶圓代工"], "url": "https://www.powerchip.com/zh-tw/staticpage/company-profile", "checkedAt": "2026-10-17", "note": "以專業晶圓代工為主分類；保留原供應鏈記憶體角色，不等同DRAM品牌商"},
"2337":{"expectedName": "旺宏", "group": "記憶體", "details": ["NOR Flash"], "url": "https://www.macronix.com/zh-tw/products/NOR-Flash/Pages/default.aspx", "checkedAt": "2026-10-17", "note": "非揮發性NOR Flash產品"},
"2344":{"expectedName": "華邦電", "group": "記憶體", "details": ["DRAM", "NOR Flash", "NAND Flash"], "url": "https://www.winbond.com.tw/hq/?__locale=zh_TW", "checkedAt": "2026-10-17", "note": "DRAM與快閃記憶體產品"},
"2408":{"expectedName": "南亞科", "group": "記憶體", "details": ["DRAM"], "url": "https://www.nanya.com/tw/About", "checkedAt": "2026-10-17", "note": "DRAM研發設計製造銷售"},
"8299":{"expectedName": "群聯", "group": "記憶體", "details": ["記憶體控制晶片"], "url": "https://www.phison.com/zh/", "checkedAt": "2026-10-17", "note": "NAND控制晶片及儲存解決方案，不歸為DRAM製造"},
"3260":{"expectedName": "威剛", "group": "記憶體", "details": ["記憶體模組"], "url": "https://www.adata.com/tw/consumer/category/computer-memory/?brand=consumer", "checkedAt": "2026-10-17", "note": "記憶體模組產品，不歸為DRAM晶片製造"},
"2451":{"expectedName": "創見", "group": "記憶體", "details": ["記憶體模組"], "url": "https://www.transcend.com.tw/support/product/dram-module", "checkedAt": "2026-10-17", "note": "記憶體模組產品"},

"3483":{"expectedName": "力致", "group": "散熱", "details": ["散熱模組", "冷板", "浸沒式散熱"], "url": "https://www.forcecon.com/zh-hant/about/", "checkedAt": "2026-10-15", "note": "熱管理、模組與水冷／浸沒式冷卻"},
"3008":{"expectedName": "大立光", "group": "消費電子／光學", "details": ["鏡頭", "影像模組"], "url": "https://www.largan.com.tw/cn/product", "checkedAt": "2026-10-15", "note": "影像鏡頭模組及光學產品"},
"3406":{"expectedName": "玉晶光", "group": "消費電子／光學", "details": ["鏡頭"], "url": "https://www.gseo.com/tw", "checkedAt": "2026-10-15", "note": "光學鏡頭產品"},

"3017":{"expectedName": "奇鋐", "group": "散熱", "details": ["散熱模組"], "url": "https://www.avc.co/zh-tw/投資人專區/公司治理", "checkedAt": "2026-10-15", "note": "整體散熱解決方案"},
"3324":{"expectedName": "雙鴻", "group": "散熱", "details": ["散熱模組", "熱管／均熱板"], "url": "https://www.auras.com.tw/Product/19", "checkedAt": "2026-10-15", "note": "散熱模組與熱管均熱板"},
"2421":{"expectedName": "建準", "group": "散熱", "details": ["風扇", "散熱模組", "液冷"], "url": "https://www.sunon.com/about.aspx/1000", "checkedAt": "2026-10-15", "note": "散熱風扇、模組與液冷系統"},
"3338":{"expectedName": "泰碩", "group": "散熱", "details": ["散熱模組"], "url": "https://www.taisol.com/about-ts/company_profile/", "checkedAt": "2026-10-15", "note": "散熱解決方案"},
"3653":{"expectedName": "健策", "group": "散熱", "details": ["均熱片"], "url": "https://www.jentech.com.tw/zh/heatspreader", "checkedAt": "2026-10-15", "note": "均熱片與散熱元件，與熱管／均熱板分開分類"},
"2308":{"expectedName": "台達電", "group": "電源／電力電子", "details": ["電源供應器"], "url": "https://www.deltaww.com/zh-TW/products/Industrial-Power-Supplies", "checkedAt": "2026-10-15", "note": "電源及系統；多業務公司依App研究用途指定主群，不代表全部營收"},
"2301":{"expectedName": "光寶科", "group": "電源／電力電子", "details": ["電源供應器"], "url": "https://power.liteon.com/zh-TW", "checkedAt": "2026-10-15", "note": "交換式電源；仍保留官方產業及多角化業務"},
"6282":{"expectedName": "康舒", "group": "電源／電力電子", "details": ["電源供應器"], "url": "https://stream.acbel.com/csr/2021_AcBel_Sustainability_Report_CN.pdf", "checkedAt": "2026-10-15", "note": "公司報告電源管理業務；來源年度2021，需持續更新"},
"3015":{"expectedName": "全漢", "group": "電源／電力電子", "details": ["電源供應器"], "url": "https://www.fsp-group.com.tw/tw/index.html", "checkedAt": "2026-10-15", "note": "電源供應器與電源解決方案"},
"3078":{"expectedName": "僑威", "group": "電源／電力電子", "details": ["電源供應器"], "url": "https://www.cwt.com.tw/tw/about/group", "checkedAt": "2026-10-15", "note": "OEM／ODM電源供應器"},
"6203":{"expectedName": "海韻電", "group": "電源／電力電子", "details": ["電源供應器"], "url": "https://investor.seasonic.com/about/", "checkedAt": "2026-10-15", "note": "交換式電源設計製造"},

'4743':{expectedName:'合一',group:'生技／醫療',details:['新藥研發'],url:'https://onenessbio.com/pipeline/',checkedAt:'2026-10-13',note:'公司新藥研發管線'},
'6589':{expectedName:'台康生技',group:'生技／醫療',details:['CDMO／CMO','生物製劑／生物相似藥'],url:'https://www.eirgenix.com/about-eirgenix',checkedAt:'2026-10-13',note:'公司生物藥開發與CDMO業務'},
'3176':{expectedName:'基亞',group:'生技／醫療',details:['新藥研發'],url:'https://www.medigen.com.tw/about',checkedAt:'2026-10-13',note:'公司新藥與分子檢測等業務'}
};
function classify(company){const code=company.industryCode, memberships=company.memberships||[];let group=broad[code]||'其他／多角化',details=[];if(group==='其他／多角化'&&memberships.some(m=>m.chain==='金融'&&m.detail==='租賃業'))group='金融';
for(const m of memberships){const cg=chainGroups[m.chain];if(!cg||(m.chain==='金融'&&m.detail.includes('/')))continue;for(const [g,re,label] of rules){if(re.test(m.detail)&&(g===group||(group==='半導體'&&g==='記憶體')||(group==='電子零組件'&&g==='PCB／載板'))){if(!details.includes(label))details.push(label);if(g==='記憶體'||g==='PCB／載板')group=g;}}}
if(group==='金融'){const n=company.fullName||company.name;if(/金融控股/.test(n))details=['金控'];else if(/銀行/.test(n))details=['銀行'];else if(/人壽/.test(n))details=['壽險'];else if(/產物保險/.test(n))details=['產險'];else if(/證券/.test(n))details=['證券'];else if(/再保險/.test(n))details=['再保險'];}
const candidate=verifiedDetails[company.id],extra=candidate&&candidate.expectedName===company.name?candidate:null;if(extra){group=extra.group;details=[...extra.details];}const ambiguous=details.length>3;if(ambiguous)details=[];return {tags:[...new Set(memberships.filter(m=>themeChains.has(m.chain)).map(m=>m.chain))],businessEvidence:extra||null,sector:group,officialIndustry:official[code]||'待取得官方分類',subsectors:details,classificationStatus:extra?'公司業務來源核對':ambiguous?'多角色／主細項待確認':details.length?'來源規則分類':'細項待確認',memberships,classificationSource:company.officialSource,classificationDate:company.officialDate};}
const api={groups,official,classify};root.StockTaxonomy=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);




