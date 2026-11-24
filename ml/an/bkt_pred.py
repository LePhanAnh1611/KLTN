import sys; from pathlib import Path
ML=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ML))
import numpy as np
from src.bkt import load_full, build_train_skill_seqs, fit_all_skills
data=load_full(); params,gp=fit_all_skills(build_train_skill_seqs(data))
U=[];P=[];Pp=[]
for ui,seq in enumerate(data.values()):
    belief={}
    for pos,(it,c,sp) in enumerate(zip(seq["items"],seq["corrects"],seq["splits"])):
        it=int(it); p=params.get(it,gp)
        pi,pl,ps,pg=p["p_init"],p["p_learn"],p["p_slip"],p["p_guess"]
        prior=belief.get(it,pi); pc=prior*(1-ps)+(1-prior)*pg
        if pos>=1: U.append(ui);P.append(pos);Pp.append(pc)
        if c==1: num=prior*(1-ps); den=num+(1-prior)*pg
        else: num=prior*ps; den=num+(1-prior)*(1-pg)
        post=num/den if den>0 else prior
        belief[it]=post+(1-post)*pl
np.savez_compressed(ML/'an/out/pred_bkt.npz',u=np.array(U),pos=np.array(P),p=np.array(Pp))
print(len(Pp))
