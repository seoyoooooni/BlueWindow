import json,glob,subprocess,os,time
ids={}
for f in sorted(glob.glob('list_*.json')):
    for r in (json.load(open(f)).get('RESULT_DATA') or []):
        ids[r['ID']]=r
json.dump(list(ids.values()),open('docs_index.json','w'),ensure_ascii=False)
os.makedirs('detail',exist_ok=True)
todo=[i for i in ids if not os.path.exists(f'detail/{i}.json')]
print('total',len(ids),'todo',len(todo),flush=True)
for n,i in enumerate(todo):
    out=subprocess.run(['curl','-sS','-m','60','-X','POST','https://www.khoa.go.kr/nwb/getDocAreaPoint.do','--data',f'id={i}&order_num=&searchArea='],capture_output=True,text=True).stdout
    try:
        d=json.loads(out); open(f'detail/{i}.json','w').write(json.dumps(d,ensure_ascii=False))
    except Exception: print('fail',i,out[:100],flush=True); time.sleep(2)
    if n%200==0: print(n,flush=True)
print('done',flush=True)
