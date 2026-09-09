import sys, os, json, math, random, statistics
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"]="1"
import pinsize as ps

def cell(taumax):
    ps.TAU_MAX = taumax
    closes,_ = ps.eligible(verbose=False)
    buys,_,_ = ps.replay(closes,"improve",ps._one,2,unit=1)
    firsts={}
    for b in buys:
        firsts.setdefault(b.close, b.price)
    return closes, buys, firsts

def ev(p):
    return ps.ev_per_contract(p, ps.MEASURED_FLIP) - ps.billed_fee(p,1)

for tm in (30,20):
    closes, buys, firsts = cell(tm)
    bl=[b.price for b in buys]; fb=list(firsts.values())
    evb=[ev(p) for p in bl]; evf=[ev(p) for p in fb]
    print(f"tau3-{tm}: blended EV/contract {100*sum(evb)/len(evb):.3f}c  per CLOSE {100*sum(evb)/len(closes):.3f}c")
    print(f"        first-buy EV/contract {100*sum(evf)/len(evf):.3f}c  per CLOSE {100*sum(evf)/len(fb):.3f}c   n={len(fb)}")
    sd=statistics.stdev(fb)
    se=sd/math.sqrt(10)
    print(f"        first-buy price mean {100*sum(fb)/len(fb):.3f}c sd {100*sd:.3f}c ; se at n=10 = {100*se:.3f}c")
    print(f"        MDE(80% power, 1-sided 5%) at n=10 = {100*(1.645+0.8416)*se:.3f}c ; at n=17 = {100*(1.645+0.8416)*sd/math.sqrt(17):.3f}c")
    # EV sd for the profit comparison
    sde=statistics.stdev(evf)
    print(f"        first-buy EV sd {100*sde:.3f}c ; MDE on EV at n=10 = {100*(1.645+0.8416)*sde/math.sqrt(10):.3f}c")

# live numbers
live=[0.979,0.947,0.950,0.950,0.977,0.972,0.963,0.987,0.935,0.975]
all17=[0.992,0.979,0.947,0.992,0.996,0.992,0.995,0.996,0.995,0.950,0.950,0.977,0.972,0.963,0.987,0.935,0.975]
print("\nlive accepted n=%d mean %.3fc  EV/contract %.3fc" % (len(live),100*sum(live)/len(live),100*sum(ev(p) for p in live)/len(live)))
print("live ALL 17    mean %.3fc  EV/contract %.3fc" % (100*sum(all17)/len(all17),100*sum(ev(p) for p in all17)/len(all17)))
# what if the 7 refused closes had traded at the replay's first gated price where one existed
extra=[0.982,0.982,0.987,0.977]
mix=live+extra
print("live accepted + 4 replayed-refused closes at their first gated price: n=%d mean %.3fc EV %.3fc"
      % (len(mix),100*sum(mix)/len(mix),100*sum(ev(p) for p in mix)/len(mix)))
