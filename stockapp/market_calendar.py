"""Annual TWSE schedule. Uncovered years/dates remain unknown."""
import json, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
TZ=timezone(timedelta(hours=8))
SOURCE='https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule'
FILE=Path(__file__).with_name('market-calendar.json')

def iso_date(value):
    parts=re.findall(r'\d+',str(value))
    try:
        if len(parts)==3:y,m,d=map(int,parts)
        elif len(parts)==1 and len(parts[0]) in (7,8):
            raw=parts[0];n=3 if len(raw)==7 else 4;y,m,d=int(raw[:n]),int(raw[n:n+2]),int(raw[n+2:])
        else:return None
        return datetime(y+1911 if y<1911 else y,m,d).date().isoformat()
    except (ValueError,TypeError):return None

def parse_schedule(rows):
    closed={};opened={};unknown={};years=set()
    for r in rows:
        date=iso_date(r.get('Date'));name=str(r.get('Name',''));description=str(r.get('Description',''))
        if not date:continue
        years.add(int(date[:4]));text=name+' '+description
        if any(s in name for s in ['開始交易','最後交易']):opened[date]=name
        elif any(s in text for s in ['無交易','休市','放假','補假']):closed[date]=name
        else:unknown[date]=name
    if not years or not closed:raise ValueError('schedule incomplete')
    return dict(years=sorted(years),closed=closed,opened=opened,unknown=unknown,source=SOURCE,scope='年度排程；未含即時臨時停市')

def merge_schedules(old,new):
    years=set(new['years']);result=dict(new)
    for key in ['closed','opened','unknown']:
        result[key]={k:v for k,v in (old or {}).get(key,{}).items() if int(k[:4]) not in years}
        result[key].update(new[key])
    result['years']=sorted(set((old or {}).get('years',[]))|years)
    result['yearFetchedAt']={**(old or {}).get('yearFetchedAt',{}),**{str(y):new.get('fetchedAt') for y in years}}
    return result

def load_calendar():
    try:
        d=json.loads(FILE.read_text(encoding='utf-8'))
        if d.get('version')!=1: return None
        return d['calendar']
    except (OSError,ValueError,KeyError):return None

def is_session(day,calendar):
    if not calendar or day.year not in calendar.get('years',[]):return None
    date=day.isoformat()
    if date in calendar.get('unknown',{}):return None
    if date in calendar.get('opened',{}):return True
    if date in calendar.get('closed',{}):return False
    return day.weekday()<5

def previous_session(day,calendar):
    for i in range(1,61):
        candidate=day-timedelta(days=i);state=is_session(candidate,calendar)
        if state is None:return None
        if state:return candidate
    return None

def next_sessions(day,count,calendar):
    result=[]
    for i in range(1,91):
        candidate=day+timedelta(days=i);state=is_session(candidate,calendar)
        if state is None:return None
        if state:result.append(candidate.isoformat())
        if len(result)==count:return result
    return None

def context(now=None):
    now=now or datetime.now(TZ);cal=load_calendar();day=now.date();state=is_session(day,cal)
    previous=previous_session(day,cal);phase='排程待補' if state is None else ('休市' if not state else '開盤前' if now.strftime('%H:%M')<'09:00' else '盤中' if now.strftime('%H:%M')<'13:30' else '盤後')
    next_date=day.isoformat() if state and now.strftime('%H:%M')<'09:00' else (next_sessions(day,1,cal) or [None])[0]
    return dict(calendar=cal,phase=phase,reason=(cal or {}).get('closed',{}).get(day.isoformat(), '週末' if day.weekday()>=5 else ''),previousSession=previous.isoformat() if previous else None,nextSession=next_date,asOf=now.isoformat())
