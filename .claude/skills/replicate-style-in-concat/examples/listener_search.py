# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Concat contributors
# /// script
# dependencies = ["numpy"]
# ///
"""EXAMPLE: beam search of the listening footage for a split-screen reel (who looks alive while the other speaks).

Reference code from the 2026-11-07 reel (v12 of the search), to COPY AND ADAPT: thresholds were tuned to that person and room.
Read references/hacks.md section 6 and learnings.md (2026-11-07, "The person who listens") first. Inputs, all under $JOB:
  gaze2_A.json / gaze2_B.json   face_gaze.py output for each raw (yaw, pitch, eo, mo, cx, cy every 0.1 s, ok flag)
  desc_A.npy / desc_B.npy       frame_descriptors.py output (thumbnail per 0.1 s of the person)
  speechA/vad.json, speechB/vad.json   phrases.py voiced regions of each raw
  rev2/good.json                {"A": [seconds], "B": [seconds]} the seconds YOU judged good by looking at a face crop
                                every 0.5 s (frames_grid.py); the detectors alone let glances, tilts and hair-touching through
  nf.json                       length in frames of every turn (what the speaker's clips add up to)
  over.json, pieces.json        as in split_screen_gen.py
Output $JOB/listen4.json: for each person and turn the list of pieces {start, n, speed, src, rev} that split_screen_gen.py places
(rev = a pre-rendered reversed copy, make_reversed.py).  Edit CONFIG below (slots, FLAG blacklists, locked turns) for a new video.
Cost model: cost per cut 11 (boomerang cut 2), visible cut difference capped (CUTMAX 9, widened only if nothing fits), slow motion
(1 - v) * seconds * 0.8, reuse 5 per second, bonus for looking toward the speaker, same source never in adjacent turns, approved
turns LOCKED (FIXED) so a later search never changes what the user called perfect.
"""
import json,os,random,statistics as st,math
import numpy as np
J=os.environ.get("JOB",os.path.expanduser("~/concat-analysis/job"))
hand=json.load(open(J+"/rev2/good.json"))
vad={"A":"speechA","B":"speechB"}
FLAG={"A":[],"B":[]}   # CONFIG: (start,end) seconds of each raw that you or the user found bad (reading, hair, a laugh); add one per complaint
nf=json.load(open(J+"/nf.json")); over=json.load(open(J+"/over.json"))
slots={"A":["t2","t4","t6","t8","t10"],"B":["t1","t3","t5","t7","t9"]}
order=["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10"]
speaker={tn:("A" if int(tn[1:])%2==1 else "B") for tn in order}
pieces=json.load(open(J+"/pieces.json"))
G={k:json.load(open(f"{J}/gaze2_{k}.json")) for k in "AB"}
def at(k,t):
    i=min(max(int(round(t*10)),0),len(G[k])-1)
    for j in (0,1,-1,2,-2,3,-3):
        if 0<=i+j<len(G[k]) and G[k][i+j]["ok"]: o=G[k][i+j]; return (o["cx"],o["cy"],o["yaw"],o["pitch"])
    return (0.5,0.45,0,0.37)
def dist(p,q): return (abs(p[0]-q[0])+abs(p[1]-q[1]))*10+abs(p[2]-q[2])*0.6+abs(p[3]-q[3])*3
def disp(k,i):
    a,b=G[k][i-1],G[k][i]
    return 9 if not(a["ok"] and b["ok"]) else abs(a["cx"]-b["cx"])+abs(a["cy"]-b["cy"])+0.3*abs(a["yaw"]-b["yaw"])
DISP={k:[0]+[disp(k,i) for i in range(1,len(G[k]))] for k in "AB"}
def good_mask(k):
    g=G[k]; regs=json.load(open(f"{J}/{vad[k]}/vad.json"))["regions"]; n=len(g); med=st.median([o["cy"] for o in g if o["ok"]])
    m=[False]*n
    for i,o in enumerate(g):
        t=o["t"]
        if not o["ok"] or t<5: continue
        if abs(o["cy"]-med)>0.05 or o["pitch"]>(0.40 if k=="A" else 0.405) or o["eo"]<0.26: continue
        if any(s-0.3<=t<=e+0.3 for s,e in regs): continue
        if any(a<=t<=b for a,b in FLAG[k]): continue
        win=[g[j]["mo"] for j in range(max(0,i-3),min(n,i+4)) if g[j]["ok"]]
        if len(win)<5 or (max(win)-min(win))>0.25: continue
        if DISP[k][i]>0.09: continue
        if not any(abs(t-h)<=0.3 for h in hand[k]): continue
        m[i]=True
    # close short blink gaps (only the eye-opening test failing), up to 0.4 s
    def blink_ok(i):
        o=g[i]
        if not o["ok"] or o["t"]<5: return False
        if abs(o["cy"]-med)>0.05 or o["pitch"]>(0.40 if k=="A" else 0.405): return False
        if any(sv-0.3<=o["t"]<=ev+0.3 for sv,ev in regs): return False
        if any(a<=o["t"]<=b for a,b in FLAG[k]): return False
        if DISP[k][i]>0.09: return False
        return any(abs(o["t"]-h)<=0.3 for h in hand[k])
    i=0
    while i<n:
        if not m[i]:
            j=i
            while j<n and not m[j]: j+=1
            if i>0 and j<n and j-i<=4 and all(blink_ok(q) for q in range(i,j)):
                for q in range(i,j): m[q]=True
            i=j
        else: i+=1
    return m
MASK={k:good_mask(k) for k in "AB"}
def runs(k):
    m=MASK[k]; rs=[];s=None
    for i in range(len(m)+1):
        if i<len(m) and m[i]: s=i if s is None else s
        elif s is not None:
            if i-s>=8: rs.append((s,i))   # sample indices, 0.1 s each
            s=None
    return rs
def vmin(k,s,e):
    d=DISP[k][s+1:e]; mean=sum(d)/len(d); mx=max(d)
    if mean<0.0045 and mx<0.015: return 0.4
    if mean<0.008 and mx<0.025: return 0.5
    if mean<0.012 and mx<0.04: return 0.6
    if mean<0.016 and mx<0.055: return 0.75
    if mean<0.022 and mx<0.07: return 0.9
    return 1.0
def still_edge(k,i,dirn):   # mean disp over 3 samples next to i
    r=range(i+1,i+4) if dirn>0 else range(i-2,i+1)
    v=[DISP[k][j] for j in r if 0<j<len(G[k])]
    return sum(v)/len(v) if v else 9
def neighbours(k,tn):
    idx=order.index(tn); prev=nxt=None
    for t in reversed(order[:idx]):
        if speaker[t]==k:
            p=[x for x in pieces if x["turn"]==t][0]; pc=p["pieces"][-1]; prev=at(k,pc["in"]+over[f"{t}_{len(p['pieces'])-1}"]/30-0.1); break
    for t in order[idx+1:]:
        if speaker[t]==k:
            p=[x for x in pieces if x["turn"]==t][0]; nxt=at(k,p["pieces"][0]["in"]+0.1); break
    return prev,nxt


DESC={k:np.load(f"{J}/desc_{k}.npy") for k in "AB"}
def vd(k,i,j):
    i=min(max(i,0),len(DESC[k])-1); j=min(max(j,0),len(DESC[k])-1)
    return float(np.abs(DESC[k][i]-DESC[k][j]).mean())
def neigh_idx(k,tn):
    idx=order.index(tn); prev=nxt=None
    for t in reversed(order[:idx]):
        if speaker[t]==k:
            p=[x for x in pieces if x["turn"]==t][0]; n=len(p["pieces"])
            prev=int(round((p["pieces"][-1]["in"]+over[f"{t}_{n-1}"]/30-0.05)*10)); break
    for t in order[idx+1:]:
        if speaker[t]==k:
            p=[x for x in pieces if x["turn"]==t][0]; nxt=int(round((p["pieces"][0]["in"]+0.05)*10)); break
    return prev,nxt
SPEEDS=[1.0,0.9,0.8,0.7,0.6,0.55,0.5,0.45,0.4]
def excursion(k,s,e):
    g=G[k]; ref=g[min(e,len(g)-1)]
    if not ref["ok"]: return 9
    m=0
    for i in range(s,e+1):
        o=g[min(i,len(g)-1)]
        if not o["ok"]: return 9
        m=max(m,abs(o["cx"]-ref["cx"])+abs(o["cy"]-ref["cy"])+0.1*abs(o["yaw"]-ref["yaw"]))
    return m
def toward(k,s,e):
    g=G[k]; n=0;t=0
    for i in range(s,min(e,len(g))):
        o=g[i]
        if o["ok"]:
            t+=1; n+= (o["yaw"]<=-0.12) if k=="A" else (o["yaw"]>=0.25)
    return n/max(1,t)
CUTW=1.0
CUTMAX=9.0
def beam_turn(k,tn,used,beam_w=80,tidx=0,minL=20):
    D=nf[tn]/30; prev,nxt=neigh_idx(k,tn)
    R=runs(k); cand=[]
    for (a,b) in R:
        for s in range(a,b-minL+1):
            if still_edge(k,s,1)>0.022: continue
            for L in sorted(set(list(range(minL,min(b-s,70)+1,5))+[b-s])):
                if L<minL: continue
                e=s+L
                if still_edge(k,e,-1)>0.022: continue
                vm=vmin(k,s,e)
                for v in [x for x in SPEEDS if x>=vm][-5:]:
                    cand.append((s,e,v,False))
                    if vm<=0.75 and excursion(k,s,e)<0.02: cand.append((s,e,v,True))
    states=[(0.0,D,prev,[])]; best=None
    for level in range(7):
        ns=[]
        for cost,rem,lastidx,pcs in states:
            for (s,e,v,rev) in cand:
                boom = bool(pcs) and rev and (not pcs[-1][4]) and abs(e-pcs[-1][1])<=1
                boom2 = bool(pcs) and (not rev) and pcs[-1][4] and abs(s-pcs[-1][0])<=1
                if boom2: boom=True
                if not boom and any(s<pe and e>ps for ps,pe,_,_,_ in pcs): continue
                if boom and any(s<pe and e>ps for ps,pe,_,_,_ in pcs[:-1]): continue
                take=(e-s)/10; tlen=take/v; ee=e
                if tlen>rem+0.03:
                    take=rem*v; ee=s+int(round(take*10))
                    if ee-s<8: continue
                    take=(ee-s)/10; tlen=take/v
                key=lambda i:(i,rev)
                if any((key(i) in used and (len(used[key(i)])>=2 or tidx-used[key(i)][-1]<=1)) for i in range(s,ee)): continue
                reuse=sum(1 for i in range(s,ee) if key(i) in used)/max(1,ee-s)+0.35*sum(1 for i in range(s,ee) if (i,not rev) in used)/max(1,ee-s)
                si,ei=(ee,s) if rev else (s,ee)      # first and last frame shown
                dd=vd(k,lastidx,si) if lastidx is not None else 0
                if pcs and dd>CUTMAX: continue
                cutc=CUTW*dd*(0.7 if not pcs else 1.0)
                c=cost+((2.0 if boom else 11.0) if pcs else 0.0)+(2.5 if (boom and pcs and v>0.92*pcs[-1][2]) else 0)+cutc+(1-v)*tlen*0.8+reuse*tlen*5.0+(2.5 if rev else 0)+(1-toward(k,s,ee))*tlen*0.9
                nr=rem-tlen; np_=pcs+[(s,ee,v,tlen,rev)]
                if nr<=0.06:
                    fc=c+(CUTW*vd(k,ei,nxt)*0.7 if nxt is not None else 0)
                    if best is None or fc<best[0]: best=(fc,np_)
                else: ns.append((c,nr,ei,np_))
        ns.sort(key=lambda x:x[0]); states=ns[:beam_w]
        if not states: break
        if best and best[0]<states[0][0]: break
    return best
# CONFIG: turns the user approved are copied from the previous plan and never searched again
_prev=json.load(open(J+"/listen_prev.json")) if os.path.exists(J+"/listen_prev.json") else {"A":{},"B":{}}
REDO=()   # turns the user asked to change, e.g. ("t4","t8")
FIXED={k:{tn:p for tn,p in _prev[k].items() if tn not in REDO} for k in "AB"}
out={}
for k in "AB":
    rs=runs(k); print(k,"supply",round(sum(e-s for s,e in rs)/10,1),"s in",len(rs),"runs")
    used={}; out[k]={}
    for ti0,tn0 in enumerate(sorted(slots[k],key=lambda t:int(t[1:]))):
        for x in FIXED[k].get(tn0,[]):
            for q in range(int(round(x['start']*10)),int(round((x['start']+x['src'])*10))): used.setdefault((q,x['rev']),[]).append(ti0)
    for ti,tn in enumerate(sorted(slots[k],key=lambda t:int(t[1:]))):
        if tn in FIXED[k]:
            lst=[dict(x) for x in FIXED[k][tn]]
            out[k][tn]=lst; print(k,tn,"kept from v15"); continue
        b=None
        for cm in (9.0,11.0,13.0,16.0):
            CUTMAX=cm
            for ml in (20,15,12,10):
                b=beam_turn(k,tn,used,tidx=ti,minL=ml)
                if b: break
            if b: break
        print(k,tn,'cut limit used',cm)
        if not b: print(k,tn,"NO SOLUTION"); raise SystemExit(1)
        cost,pcs=b; n=nf[tn]; acc=0; lst=[]; cutd=[]
        prevend=None
        for i,(s,e,v,tlen,rev) in enumerate(pcs):
            f_=n-acc if i==len(pcs)-1 else round(tlen*30); acc+=f_
            si,ei=(e,s) if rev else (s,e)
            if prevend is not None: cutd.append(round(vd(k,prevend,si),1))
            prevend=ei
            lst.append({"start":round(round(G[k][s]["t"]*30)/30,4),"n":f_,"speed":v,"src":round((e-s)/10,2),"rev":rev})
        for (s,e,v,tlen,rev) in pcs:
            for q in range(s,e): used.setdefault((q,rev),[]).append(ti)
        out[k][tn]=lst
        print(k,tn,"cost",round(cost,1),[(x["start"],x["src"],x["speed"],"R" if x["rev"] else "F") for x in lst],"cut-diffs",cutd)
json.dump(out,open(J+"/listen4.json","w"),indent=1)
