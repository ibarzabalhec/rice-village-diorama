import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/'
D=ROOT+'data/'
OWN_RAW=os.environ.get('OWN_RAW',ROOT+'inputs/parcels_owner.json')
import json
P=json.load(open(D+'pack.json'))
LA=json.load(open(D+'linkaudit.json'))
LK={r['n']+'|'+r['suite']:r for r in LA['rows']}
import collections as _c
for b in P['buildings']:
    pids=_c.OrderedDict()
    for t in b['tenants']:
        r=LK.get(t['n']+'|'+t['suite'])
        if not r: continue
        L={}
        for k in ('web','listing','social'):
            if k in r: L[k]={x:r[k][x] for x in ('url','final','status','flags','loc','src') if x in r[k]}
        if 'costar' in r: L['costar']=r['costar']
        if 'rejected' in r: L['rejected']=r['rejected']
        if 'dropped' in r: L['dropped']=r['dropped']
        if r.get('notes'): L['notes']=r['notes']
        t['links']=L
        if 'costar' in r and r['costar']['pid']:
            p=r['costar']['pid'];pids.setdefault(p,{'pid':p,'url':r['costar']['url'],'n':0});pids[p]['n']+=1
    if pids: b['costar']=list(pids.values())
# properties spanning several drawn buildings
span=_c.defaultdict(set)
for b in P['buildings']:
    for c in b.get('costar',[]): span[c['pid']].add(b['id'])
P['linkmeta']=dict(checked=LA['checked'],span={p:sorted(s) for p,s in span.items() if len(s)>1},
  unplaced=[{'n':r['n'],'links':{k:r[k] for k in ('web','costar') if k in r}} for r in LA['rows'] if r['bid'] is None and ('web' in r or 'costar' in r)])
YB=json.load(open(D+'yearbuilt.json'))
for b in P['buildings']:
    y=YB.get(b['id'])
    if not y or not y.get('yb'): continue
    L=sorted({int(v) for v in str(y['yb']).split(',') if v.strip().isdigit() and int(v)>1800})
    if not L: continue
    b['ybl']=L;b['yb']=L[0]
    if L==[1955,1995,2021]: b['yb']=1995
    rm=[int(v) for v in str(y.get('yr') or '0').split(',') if v.strip().isdigit() and int(v)>1800]
    if rm: b['yrm']=max(rm)
# ---- ownership: the gold line follows parcels the county roll lists under Rice entities (owner mails to 6100 Main St)
import math as _m
from shapely.geometry import shape as _shape,Polygon as _Poly,box as _box
from shapely.ops import unary_union as _uu
_lon0,_lat0=-95.41554,29.71808;_kx=111320*_m.cos(_m.radians(_lat0))*3.28084;_ky=110540*3.28084
def _loc(g):
    from shapely.ops import transform as _tr
    return _tr(lambda x,y,z=None:((x-_lon0)*_kx,(y-_lat0)*_ky),g)
_SQ=_box(-1250,-1250,1250,1250)
_rp=[]
for f in (json.load(open(OWN_RAW)) if os.path.exists(OWN_RAW) else []):
    pr=f['properties'];m=(pr.get('mail_addr_1') or '').upper();o=(pr.get('owner_name_1') or '').upper()
    if not f['geometry']: continue
    if ('6100 MAIN' in m and any(k in o for k in ('LLC','UNIVERSITY','INSTITUTE','RICE','CHAUCER'))) or 'RICE UNIV' in o or 'RICE INST' in o:
        g=_loc(_shape(f['geometry'])).buffer(0).intersection(_SQ)
        if not g.is_empty and g.area>50: _rp.append(g)
if _rp:
    _rvfp=[_Poly(b['tiers'][0]['p']).buffer(0) for b in P['buildings'] if b['role']=='rv']
    _core=[g for g in _rp if any(g.intersection(f).area>max(150,0.04*f.area) for f in _rvfp)]
    _other=[g for g in _rp if g not in _core]
    _prop=_uu([g.buffer(1,join_style=2) for g in _core]).buffer(-1,join_style=2)
    _oth=_uu([g.buffer(1,join_style=2) for g in _other]).buffer(-1,join_style=2).difference(_prop.buffer(2))
    def _prings(g):
        gs=g.geoms if hasattr(g,'geoms') else [g];res=[]
        for q in gs:
            if q.geom_type!='Polygon' or q.area<20: continue
            res.append([[[round(x,1),round(y,1)] for x,y in list(r.coords)[:-1]] for r in [q.exterior]+list(q.interiors)])
        return res
    P['site']=_prings(_prop);P['band']=_prings(_prop.buffer(2.5,join_style=2).difference(_prop.buffer(-9,join_style=2)))
    P['rice2']=_prings(_oth);P['band2']=_prings(_oth.buffer(1.2,join_style=2).difference(_oth.buffer(-2.5,join_style=2)))
    for b in P['buildings']:
        if b['role']!='rv': continue
        f=_Poly(b['tiers'][0]['p']).buffer(0)
        if f.intersection(_prop).area<0.5*f.area: b['ownNote']='On the Rice Village tenant roster. The county roll lists this parcel under an owner not tied to Rice.'
    P['ownmeta']=dict(core=len(_core),other=len(_other),core_sf=round(_prop.area),other_sf=round(_oth.area))
    print('ownership: core parcels',len(_core),'other',len(_other),'core sf',round(_prop.area),'other sf',round(_oth.area),'flagged',[b['id'] for b in P['buildings'] if b.get('ownNote')])
    json.dump({k:P[k] for k in ('site','band','rice2','band2','ownmeta')}|{'ownNote':{b['id']:b['ownNote'] for b in P['buildings'] if b.get('ownNote')}},open(D+'ownership.json','w'))
else:
    _o=json.load(open(D+'ownership.json'));[P.__setitem__(k,_o[k]) for k in ('site','band','rice2','band2','ownmeta')]
    for b in P['buildings']:
        if b['id'] in _o['ownNote']: b['ownNote']=_o['ownNote'][b['id']]
# ---- street labels: slide each along its own street to the middle of its block, away from crossings
import math as _mm
def _fixlabels(L,H=1250):
    D=[(_mm.cos(_mm.radians(l['a'])),_mm.sin(_mm.radians(l['a']))) for l in L]
    out=[]
    for i,l in enumerate(L):
        px,py=l['x'],l['y'];dx,dy=D[i];ts=[]
        for j,m in enumerate(L):
            if m['n']==l['n']:continue
            ex,ey=D[j];cr=dx*ey-dy*ex
            if abs(cr)<0.7:continue
            t=((m['x']-px)*ey-(m['y']-py)*ex)/cr
            if all(abs(t-u)>25 for u in ts):ts.append(t)
        def edge(sg):
            t=0
            while abs(px+dx*t)<H-90 and abs(py+dy*t)<H-90 and abs(t)<3000:t+=sg*10
            return t
        lo=max([t for t in ts if t<-1]+[edge(-1)]);hi=min([t for t in ts if t>1]+[edge(1)])
        tn=(lo+hi)/2 if hi-lo<900 else (0 if min(-lo,hi)>160 else (lo+160 if -lo<hi else hi-160))
        out.append(dict(l,x=round(px+dx*tn),y=round(py+dy*tn)))
    for i,l in enumerate(out):
        for k in range(i):
            m=out[k]
            if m['n']==l['n'] and _mm.hypot(m['x']-l['x'],m['y']-l['y'])<300: out[i]=dict(L[i])
    return out
def _blocklabels(L,H=1250):
    # one more label in every other block of each street, shown only when zoomed in
    D={};extra=[]
    for l in L: D.setdefault(l['n'],l)
    lines=[(n,(l['x'],l['y']),(_mm.cos(_mm.radians(l['a'])),_mm.sin(_mm.radians(l['a']))),l['a']) for n,l in D.items()]
    for n,(px,py),(dx,dy),ang in lines:
        ts=[]
        for n2,(qx,qy),(ex,ey),_ in lines:
            if n2==n:continue
            cr=dx*ey-dy*ex
            if abs(cr)<0.7:continue
            t=((qx-px)*ey-(qy-py)*ex)/cr
            if abs(px+dx*t)<H and abs(py+dy*t)<H: ts.append(t)
        ts=sorted(ts)
        for a0,a1 in zip(ts,ts[1:]):
            if a1-a0<180:continue
            t=(a0+a1)/2;x,y=px+dx*t,py+dy*t
            if abs(x)>H-90 or abs(y)>H-90:continue
            if any(m['n']==n and _mm.hypot(m['x']-x,m['y']-y)<200 for m in L+extra):continue
            extra.append(dict(n=n,x=round(x),y=round(y),a=ang,near=1))
    return extra
_old=[(l['n'],l['x'],l['y']) for l in P['labels']]
_old2=[dict(l) for l in P['labels']];P['labels']=_fixlabels(P['labels']);P['labels']+=_blocklabels(P['labels'])
from shapely.geometry import Point as _Pt, Polygon as _SP
from shapely.strtree import STRtree as _STR
_fps=[_SP(b['tiers'][0]['p']).buffer(8) for b in P['buildings'] if b.get('tiers')]+[_SP(r).buffer(-4) for r in P['parcels'] if len(r)>2]
_fps=[g for g in _fps if not g.is_empty];_tr=_STR(_fps)
def _onroad(l):
    pt=_Pt(l['x'],l['y']);return not any(_fps[i].contains(pt) for i in _tr.query(pt))
_keep=[]
for i,l in enumerate(P['labels']):
    if _onroad(l): _keep.append(l)
    elif not l.get('near') and i<len(_old2): _keep.append(_old2[i])
P['labels']=_keep
print('labels moved:',sum(1 for o,l in zip(_old,P['labels']) if (o[1],o[2])!=(l['x'],l['y'])))
# ---- suite clean-up: close the gaps between traced suites, drop slivers, square the result
import numpy as _np, shapely as _sh
from shapely.geometry import Polygon as _SP,MultiPolygon as _MP,box as _bx
from shapely.ops import unary_union as _uu2
def _clean_suites(b):
    S=b.get('suites') or []
    if not S: return 0
    fp=_SP(b['tiers'][0]['p']).buffer(0)
    orig=[]
    for q in S:
        g=_SP(q['p']).buffer(0).intersection(fp)
        if g.is_empty: g=_SP(q['p']).buffer(0)
        orig.append(g)
    taken=_uu2(orig)
    gap=fp.difference(taken)
    grow=[[] for _ in S]
    if gap.area>4:
        x0,y0,x1,y1=gap.bounds
        xs=_np.arange(_np.floor(x0)+.5,x1,1.0);ys=_np.arange(_np.floor(y0)+.5,y1,1.0)
        if len(xs)*len(ys)<400000:
            X,Y=_np.meshgrid(xs,ys);pts=_sh.points(X.ravel(),Y.ravel())
            inside=_sh.contains(gap,pts);pts=pts[inside];X=X.ravel()[inside];Y=Y.ravel()[inside]
            if len(pts):
                D=_np.stack([_sh.distance(o,pts) for o in orig])
                k=D.argmin(0);dm=D.min(0)
                for i in range(len(S)):
                    sel=(k==i)&(dm<=7.0)
                    if sel.any(): grow[i]=list(_sh.box(X[sel]-.5,Y[sel]-.5,X[sel]+.5,Y[sel]+.5))
    n=0
    for i,q in enumerate(S):
        g=orig[i]
        if len(grow[i]): g=_uu2([g,*grow[i]])
        g=g.buffer(.8,join_style=2).buffer(-.8,join_style=2).intersection(fp)
        parts=[pp for pp in (g.geoms if hasattr(g,'geoms') else [g]) if pp.geom_type=='Polygon' and pp.area>=60]
        if not parts: continue
        pp=max(parts,key=lambda z:z.area)
        pp=_SP(pp.exterior,[h for h in pp.interiors if _SP(h).area>=120]).simplify(.9)
        if pp.is_empty or pp.geom_type!='Polygon': continue
        q['p']=[[round(x,1),round(y,1)] for x,y in list(pp.exterior.coords)[:-1]]
        q['a']=round(pp.area);c=pp.representative_point();q['lx'],q['ly']=round(c.x,1),round(c.y,1);n+=1
    return n
import re as _re
for _b in P['buildings']:
    for _q in _b.get('suites') or []:
        n=_q.get('n') or '';m=_re.fullmatch(r'(.+?)[ ,]+\1',n)
        if m:_q['n']=m.group(1)
_nc=sum(_clean_suites(b) for b in P['buildings'])
print('suites cleaned:',_nc)
B=P['buildings']
rv=[b for b in B if b['role']=='rv'];rva=[b for b in B if b['role']=='rva']
rvT=[t for b in rv for t in b['tenants']];rvaT=[t for b in rva for t in b['tenants']]
sf=sum(t['sf'] or 0 for t in rvT);vac=sum(1 for t in rvT+rvaT if t['c']=='Vacant')
nb=len([b for b in rv if b['use']!='Parking'])
SOURCES=[
 dict(id='s_wb',short='Tenant workbook',title='RV Tenant Profiles workbook: tenant canvass done for Rice, site plan, CoStar listings, Google Maps hours (11/10/26)',use='Tenants, suites, listed SF, categories, hours',url=None),
 dict(id='s_map',short='Tenant map',title='Rice Village ground floor tenant map (slide)',use='Suite outlines, suite numbers and tenant placement',url=None),
 dict(id='s_tm',short='Trademark, 2014',title='Trademark Property Company, "Trademark to Lead Transformation of Houston\'s Rice Village," September 17, 2014',use='2014 acquisition, 193,000 SF, three buildings',url='https://trademarkproperty.com/trademark-lead-transformation-houstons-rice-village/'),
 dict(id='s_thr14',short='Rice Thresher, 2014',title='Rice Thresher, "Rice to purchase Rice Village Arcade Shopping Center," February 2014',use='Ground lease purchase option, Weingarten joint venture',url='https://www.ricethresher.org/article/2014/02/news-in-brief-rice-to-purchase-rice-village-arcade-shopping-center'),
 dict(id='s_thr15',short='Rice Thresher, 2015',title='Rice Thresher, "Rice invests in more Village property," February 2015',use='Later purchases: 15,273 SF and 7,500 SF buildings',url='https://www.ricethresher.org/article/2015/02/rice-invests-in-more-village-property'),
 dict(id='s_houstonia',short='Houstonia, 2024',title='Houstonia, "The Funky Rice Village History You Didn\'t Know," November 11, 2024',use='1991 Village Arcade and its garage; Hanover Rice Village',url='https://www.houstoniamag.com/articles/rice-village-history'),
 dict(id='s_chron2015',short='Houston Chronicle, 2015',title='Houston Chronicle, "Parking updated, stores get new façades," November 19, 2015',use='Rebrand to Rice Village; rooftop deck at Kirby and University',url='https://www.pressreader.com/usa/houston-chronicle/20151119/283588104259050'),
 dict(id='s_ci',short='Community Impact',title='Community Impact, "Changes at Rice Village bring more upscale shops"',use='Founding year, 1938',url='https://communityimpact.com/bellaire-meyerland-west-university/business/changes-at-rice-village-bring-more-upscale-shops/'),
 dict(id='s_rv',short='rice-village.com',title='Rice Village, About',use='Since 1938; Rice Real Estate Company and the management district',url='https://rice-village.com/about/'),
 dict(id='s_lidar',short='USGS lidar, 2018',title='USGS 3D Elevation Program, TX Coastal B1 2018 point cloud',use='Roof heights, garage outline, trees',url='https://s3-us-west-2.amazonaws.com/usgs-lidar-public/TX_Coastal_B1_2018/ept.json'),
 dict(id='s_ov',short='Overture Maps',title='Overture Maps Foundation, release 2026-10-21 (OpenStreetMap and Microsoft footprints, places, roads)',use='Footprints, tenant points, street names',url='https://docs.overturemaps.org/'),
 dict(id='s_hcad',short='HCAD parcels',title='Harris Central Appraisal District, parcel layer',use='Parcels. The gold line follows parcels the county roll lists under Rice entities, found by Rice University\'s mailing address; owner names are not shown',url='https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0'),
 dict(id='s_yb',short='County year built',title='City of Houston GIS, HCAD Parcels 2024 layer (year built and remodel year only)',use='Year built for the timeline',url='https://geohwp.houstontx.gov/arcgis/rest/services/03_BaseData_External/Parcels_Historic/FeatureServer/39'),
 dict(id='s_census',short='Census geocoder',title='U.S. Census Bureau geocoder',use='Tenant addresses without a mapped point',url='https://geocoding.geo.census.gov/'),
]
NARR=[
 ['Overview','Rice Village is a retail district west of Rice University in Houston. It has traded since 1938.',['s_ci','s_rv']],
 ['Village Arcade, 1991','In 1991 the 1941 Village Theatre came down. Three blocks were rebuilt as the Village Arcade, with a multistory garage at its core.',['s_houstonia']],
 ['Joint venture and buyout, 2014','Rice and Weingarten Realty developed the Village Arcade in a joint venture from the 1990s. In 2014 Rice, as holder of the ground leases, exercised its purchase option.',['s_thr14']],
 ['Acquisition, September 2014','On September 17, 2014, Rice Management Company and Trademark Property closed on the three-building, 193,000 SF Village Arcade. Trademark took on management, leasing and repositioning.',['s_tm']],
 ['Added buildings, 2014 to 2015','Within a year Rice also bought a 15,273 SF building leased to Urban Outfitters and a 7,500 SF retail building.',['s_thr15']],
 ['Rebrand, 2015','Trademark renamed the Village Arcade buildings Rice Village. The work covered two garages: the multilevel garage and a one-level building with a rooftop deck at Kirby Drive and University Boulevard.',['s_chron2015']],
 ['Rice blocks today',f'The tenant workbook places {len(rvT)} Rice tenants on {nb} Rice-owned buildings and the garage, with {sf:,} SF listed. Rice Real Estate Company is working to set up a municipal management district for the streets and infrastructure.',['s_wb','s_rv']],
 ['Neighbors',f'Other owners hold {len(rvaT)} listings on {len(rva)} buildings in the district. Hanover Rice Village spans two blocks on both sides of Bolsover Street.',['s_wb','s_houstonia']],
]
arc=['1377','1378','1379','1381','garage']
STORY=[
 dict(k='Rice Village',t='Retail district west of Rice University, Houston. Trading since 1938.',x=-60,y=-150,m=1500,el=32,az=-30),
 dict(k='1991',t='The 1941 Village Theatre came down. Three blocks became the Village Arcade, built around a multistory garage.',ids=arc,el=26,az=-55),
 dict(k='September 2014',t='Rice Management Company and Trademark Property closed on the three-building, 193,000 SF Village Arcade.',ids=arc,el=20,az=20),
 dict(k='Rice blocks today',t=f'{nb} Rice-owned buildings and the garage. {len(rvT)} tenants on {sf:,} SF listed.',ids=[b['id'] for b in rv],el=30,az=-20),
 dict(k='Other owners',t=f'{len(rvaT)} listings on {len(rva)} buildings along Rice Blvd, Times Blvd, Kirby Dr and Morningside Dr. {vac} listings vacant.',ids=[b['id'] for b in rva],el=30,az=35),
]
s=open(ROOT+'src/template.html').read()
three=open(ROOT+'vendor/three.iife.js').read()
s=s.replace('/*THREE*/',three.replace('</script','<\\/script'))
s=s.replace('/*PACK*/',json.dumps(P,separators=(',',':')))
s=s.replace('/*SOURCES*/',json.dumps(SOURCES)).replace('/*NARR*/',json.dumps(NARR)).replace('/*STORY*/',json.dumps(STORY))
open(ROOT+'index.html','w').write(s)
print(len(s), nb, len(rvT), sf, len(rvaT), len(rva), vac)
