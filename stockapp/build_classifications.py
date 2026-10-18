"""Refresh public classification snapshot, never reads user holdings."""
import concurrent.futures, json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).parent
BASE='https://ic.tpex.org.tw/'
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:return r.read().decode('utf-8-sig')
def chain(item):
    name,url=item
    soup=BeautifulSoup(get(url),'html.parser')
    output=[]
    for a in soup.select('a[href^="company_basic.php?stk_code="]'):
        container=a.find_parent('table',id=re.compile('^sc_company_'))
        if container:
            code=container['id'].replace('sc_company_','')
            heading=soup.find(id='sc_link_'+code)
        else:
            container=a.find_parent(id=re.compile('^companyList_'))
            if not container:continue
            code=container['id'].replace('companyList_','')
            heading=soup.find(id='ic_link_'+code)
        if not heading:continue
        label=re.sub(r'^►\s*|\s*\(\d+家\)\s*$','',heading.get_text(' ',strip=True)).strip()
        sid=a['href'].split('stk_code=')[-1]
        if re.fullmatch(r'\d{4,6}[A-Z]?',sid):output.append((sid,dict(chain=name,detail=label,sourceUrl=url,node=code)))
    return output
def main():
    catalog={};errors=[]
    for exchange,url in [('tse','https://openapi.twse.com.tw/v1/opendata/t187ap03_L'),('otc','https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O')]:
        rows=json.loads(get(url))
        for r in rows:
            sid=r.get('公司代號') or r.get('SecuritiesCompanyCode')
            catalog[sid]=dict(id=sid,name=r.get('公司簡稱') or r.get('CompanyAbbreviation'),fullName=r.get('公司名稱') or r.get('CompanyName'),industryCode=r.get('產業別') or r.get('SecuritiesIndustryCode'),exchange=exchange,officialSource=url,officialDate=r.get('出表日期') or r.get('Date'),memberships=[])
    index=BeautifulSoup(get(BASE+'ic_report_index.php'),'html.parser')
    items=list(dict.fromkeys((a.get_text(strip=True),BASE+a['href']) for a in index.select('a[href^="introduce.php?ic="]')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(chain,item):item for item in items}
        for f in concurrent.futures.as_completed(futures):
            try:
                for sid,m in f.result():
                    if sid in catalog and m not in catalog[sid]['memberships']:catalog[sid]['memberships'].append(m)
            except Exception as e:errors.append(dict(chain=futures[f][0],error=type(e).__name__))
    data=dict(updatedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),companies=list(catalog.values()),chains=[name for name,_ in items],errors=errors)
    if len(catalog)<1500:raise ValueError('incomplete official company roster')
    (ROOT/'classifications.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(companies=len(catalog),chains=len(items),memberships=sum(len(c['memberships']) for c in catalog.values()),errors=errors),ensure_ascii=True))
if __name__=='__main__':main()
