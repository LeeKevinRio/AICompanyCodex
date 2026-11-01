"""Local background collection: symbols only, private state outside the checkout."""
import json,os,re,threading,math
from copy import deepcopy
from pathlib import Path
from datetime import datetime,date,timedelta
try:
    from .market_calendar import TZ,is_session,next_sessions
except ImportError:
    from market_calendar import TZ,is_session,next_sessions

def default_path():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'ClearSignal'/'daily-state.json'

def evaluate(record,bars,calendar,events):
    anchor=next((b for b in bars if b['date']==record['asOf']),None)
    if not anchor:return None
    if anchor['close']<=0 or abs(anchor['close']/record['baseClose']-1)>.001:return None
    expected=next_sessions(date.fromisoformat(record['asOf']),record['days'],calendar)
    if not expected:return None
    created=datetime.fromisoformat(record['recordedAt'].replace('Z','+00:00')).astimezone(TZ)
    if created>=datetime.fromisoformat(expected[0]+'T09:00:00+08:00'):return dict(status='建立過晚，不納入',return_=None)
    by_date={b['date']:b for b in bars}
    if any(d not in by_date for d in expected) or any(record['asOf']<e['date']<=expected[-1] for e in events):return None
    previous=record['baseClose']
    for d in expected:
        b=by_date[d]
        if b['close']<=0 or abs(b['close']/previous-1)>.3 or '**' in str(b.get('note','')):return None
        previous=b['close']
    value=(previous/record['baseClose']-1)*100;realized='偏多' if value>.5 else '偏空' if value<-.5 else '震盪'
    return dict(status='已到期',return_=value,realized=realized,hit=realized==record['bias'],endDate=expected[-1])

class DailyService:
    def __init__(self,path=None):
        self.path=Path(path) if path else default_path();self.lock=threading.RLock();self.running=False;self.error=''
        self.state=dict(version=1,enabled=False,targets=[],records=[],candidates=[],runs=[])
        if self.path.exists():
            try:
                value=json.loads(self.path.read_text(encoding='utf-8'))
                if value.get('version')!=1 or not isinstance(value.get('enabled'),bool) or not all(isinstance(value.get(k),list) for k in ['targets','records','candidates','runs']):raise ValueError()
                self.validate_targets(value['targets']);self.state=value
                if not all(self.valid_record(r) for r in value['records']+value['candidates']):raise ValueError()
                for key in ['records','candidates']:
                    if len(value[key])>10000 or len({r['key'] for r in value[key]})!=len(value[key]):raise ValueError()
                if not all(isinstance(r,dict) and isinstance(r.get('rows'),list) and isinstance(r.get('status'),str) and date.fromisoformat(r['date']) and datetime.fromisoformat(r['startedAt']).tzinfo for r in value['runs']):raise ValueError()
            except Exception:self.error='本機排程檔案無法讀取，原檔未覆寫。'
    @staticmethod
    def valid_record(r):
        try:
            created=datetime.fromisoformat(r['recordedAt'].replace('Z','+00:00'))
            outcome=r.get('outcome')
            if outcome is not None:
                if not isinstance(outcome,dict):return False
                if outcome.get('status')=='已到期':
                    if (type(outcome.get('return')) not in [int,float] or not math.isfinite(outcome['return']) or
                        outcome.get('realized') not in ['偏多','偏空','震盪'] or type(outcome.get('hit')) is not bool or
                        outcome['hit']!=(outcome['realized']==r['bias']) or not date.fromisoformat(outcome['endDate'])):return False
                elif outcome.get('status')!='建立過晚，不納入' or outcome.get('return') is not None:return False
            return (r['kind']=='stock' and isinstance(r['model'],str) and bool(r['model']) and isinstance(r['key'],str) and
                bool(re.fullmatch(r'[0-9]{4,6}[A-Z]?',r['id'])) and r['exchange'] in ['tse','otc'] and
                r['days'] in [3,5] and (r['bias'] in ['偏多','偏空','震盪'] or ('candidateId' in r and r['bias'] is None)) and
                type(r['baseClose']) in [int,float] and math.isfinite(r['baseClose']) and r['baseClose']>0 and
                bool(date.fromisoformat(r['asOf'])) and created.tzinfo is not None)
        except (TypeError,ValueError,KeyError,AttributeError):return False
    @staticmethod
    def validate_targets(targets):
        if not isinstance(targets,list) or len(targets)>200:raise ValueError('最多200檔')
        for t in targets:
            if not isinstance(t,dict) or set(t)!={'id','exchange'} or not isinstance(t['id'],str) or not re.fullmatch(r'[0-9]{4,6}[A-Z]?',t['id']) or t['exchange'] not in ['tse','otc']:raise ValueError('只能同步有效台股代碼與市場')
        if len({t['id'] for t in targets})!=len(targets):raise ValueError('股票代碼重複')
    def save(self):
        if self.error:raise ValueError(self.error)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.state,ensure_ascii=False,allow_nan=False),encoding='utf-8');tmp.replace(self.path)
    def configure(self,targets,enabled):
        self.validate_targets(targets)
        if not isinstance(enabled,bool):raise ValueError('排程狀態無效')
        with self.lock:
            if self.error:raise ValueError(self.error)
            old=self.state;self.state={**old,'enabled':enabled,'targets':targets}
            try:self.save()
            except Exception:self.state=old;raise
    def snapshot(self):
        with self.lock:return json.loads(json.dumps({**self.state,'running':self.running,'error':self.error,'storage':'本機使用者資料夾，非Git／雲端'}))
    def run(self,analyzer,calendar_loader,refresh,now=None,force=False,clock=None):
        clock=clock or ((lambda:now) if now is not None else (lambda:datetime.now(TZ)))
        now=clock().astimezone(TZ);today=now.date().isoformat()
        with self.lock:
            if self.running or self.error or not self.state['enabled']:return
            if not force and now.strftime('%H:%M')<'17:30':return
            if force and now.strftime('%H:%M')<'14:30':return
            last=self.state['runs'][-1] if self.state['runs'] else None
            if not force and last and last['date']==today:
                if last['status'] in ['完成','休市跳過']:return
                if (now-datetime.fromisoformat(last['startedAt'])).total_seconds()<900:return
            self.running=True;targets=list(self.state['targets'])
        run=dict(date=today,startedAt=now.isoformat(),status='執行中',rows=[])
        try:
            calendar=calendar_loader();state=is_session(now.date(),calendar)
            if state is not True:
                run.update(status='休市跳過' if state is False else '日曆不足',reason='官方排程休市' if state is False else '不猜交易日');return
            refresh();calendar=calendar_loader()
            for t in targets:
                before_records=before_candidates=None
                try:
                    a=analyzer(t['id'],t['exchange']);row=dict(id=t['id'],asOf=a.get('asOf'),status='跳過')
                    with self.lock:
                        before_records=deepcopy(self.state['records']);before_candidates=deepcopy(self.state['candidates'])
                        for r in self.state['records']+self.state['candidates']:
                            if r['id']==t['id'] and not r.get('outcome'):
                                outcome=evaluate(r,a['bars'],calendar,a.get('corporateActions',[]))
                                if outcome:outcome['return']=outcome.pop('return_');r['outcome']=outcome
                    if a.get('asOf')!=today or not a.get('planEnabled'):
                        row['reason']='來源尚非當日日線' if a.get('asOf')!=today else '；'.join(a.get('alerts',[]));run['rows'].append(row);continue
                    next_day=next_sessions(now.date(),1,calendar)
                    created_at=clock().astimezone(TZ)
                    if created_at.date()!=now.date():raise ValueError('分析完成已跨日，不補造前日預測')
                    if not next_day or created_at>=datetime.fromisoformat(next_day[0]+'T09:00:00+08:00'):raise ValueError('已超過合法建立時間')
                    anchor=next(b for b in a['bars'] if b['date']==today);created=0
                    with self.lock:
                        for f in a.get('forecasts',[]):
                            if f['days'] not in [3,5] or f['bias'] not in ['偏多','偏空','震盪']:continue
                            key=f"stock:{t['id']}:{today}:{f['days']}:{a['model']}"
                            if any(r['key']==key for r in self.state['records']):continue
                            if len(self.state['records'])>=10000:raise ValueError('本機紀錄已滿，請備份')
                            self.state['records'].append(dict(key=key,kind='stock',id=t['id'],exchange=t['exchange'],asOf=today,days=f['days'],bias=f['bias'],baseClose=anchor['close'],recordedAt=created_at.isoformat(),model=a['model'],adjusted=False,evidence=dict(combinedSignal=a.get('combinedSignal'),score=a.get('technical',{}).get('score'),reasons=a.get('technical',{}).get('reasons',[]),sampleCount=f.get('sampleCount'),financialContext=a.get('fundamental',{}).get('context')),members=None));created+=1
                        research=a.get('candidateResearch') or {}
                        for s in research.get('signals',[]):
                            key=f"candidate:{t['id']}:{today}:{s['days']}:{s['model']}"
                            if s['asOf']!=today or any(r['key']==key for r in self.state['candidates']):continue
                            if len(self.state['candidates'])>=10000:raise ValueError('候選觀察已滿，請備份')
                            self.state['candidates'].append(dict(key=key,kind='stock',id=t['id'],exchange=t['exchange'],asOf=today,days=s['days'],bias=s['bias'],baseClose=anchor['close'],recordedAt=created_at.isoformat(),model=s['model'],candidateId=s['id'],name=s['name'],protocol=research['protocol'],specHash=research['specHash'],engineHash=research['engineHash'],adjusted=False,evidence={},members=None))
                        actual=[r['days'] for r in self.state['records'] if r['id']==t['id'] and r['asOf']==today and r['model']==a['model']]
                        row['status']=('成功' if created else '已存在，未重複') if 3 in actual and 5 in actual else '失敗'
                        if row['status']=='失敗' and a.get('combinedSignal',{}).get('available') is False:
                            row.update(status='跳過',reason='現金流檢查未齊：'+a['combinedSignal'].get('reason','資料不足'))
                        self.save()
                    run['rows'].append(row)
                except Exception as exc:
                    with self.lock:
                        if before_records is not None:self.state['records']=before_records;self.state['candidates']=before_candidates
                    run['rows'].append(dict(id=t['id'],status='失敗',reason=str(exc)))
            run['status']='完成' if targets and all(r['status'] in ['成功','已存在，未重複'] for r in run['rows']) else ('失敗' if all(r['status']=='失敗' for r in run['rows']) else '部分失敗') if any(r['status']=='失敗' for r in run['rows']) else '資料未齊' if targets else '無追蹤股'
        except Exception as exc:run.update(status='失敗',reason=str(exc))
        finally:
            with self.lock:
                run['finishedAt']=datetime.now(TZ).isoformat();self.state['runs']=(self.state['runs']+[run])[-200:]
                try:self.save()
                except Exception:self.error='本機排程保存失敗，不能視為已留存。'
                self.running=False
