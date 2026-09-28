from common import *
print("## apostrophes")
for p in ["meera iyer's loan","Meera Iyer’s loan","meera iyers' loans","meera iyer' s","iyer'","'meera iyer'","‘meera iyer’","meera o'iyer","naveen rao's's","rao's holdings","rao holdings'","rao holdings's","o'brien","D'souza owes 5000","deepak menon’ll pay","anil sharma'd lend","meera iyer`s loan","meera iyer´s loan","meera iyerʼs loan"]: run(p)
print("## digits glued")
for p in ["b1,b2","b1,b2,b3","bg10/bg13","bg1 vs bg13","bg13","bg 13","bg-13","bg_13","b1_b2","b1-b2","b1.b2","b1&b2","b1/b2 owe","d1b1","b1b2","bg1's","show b10","b 10","B-10","dg1,dg2","b1:b2","b1;b2","b12345","meera_iyer","anil_sharma_loans","anil_sharma's","naveen_rao_holdings","iyer_chem_bg1"]: run(p)
print("## ref ids")
for p in ["ref 2026_03_004 of b1","2026_03_004's status","2026_03_004,2026_03_005","loans 2026_01_001-2026_01_009","ref#2026_03_004","2026_03_004/b1","2026-03-004","2026 03 004","ref 2026_03_004 lent 45000"]: run(p)
print("## emails urls")
for p in ["mail meera.iyer@finhive.in","meera_iyer@x.com","anil.sharma@gmail.com about 45000","https://finhive.in/loans/anil-sharma","www.sharma-group.com","naveenrao@x.com","ping @meera.iyer","https://x.io/?amt=45000&who=b1","file:///C:/iyer_chem/2026.csv"]: run(p)
print("## mixed scripts")
for p in ["मीरा iyer","meera अय्यर","Меера Иyer","meera iyer का लोन","meera iyerजी","anil sharmaजी","ａｎｉｌ　ｓｈａｒｍａ","anil\u200bsharma","anil\u00a0sharma","ANİL SHARMA","anil\u0301 sharma","meera iyer\u200d","sharma\u2019s group","anil sharma\u2014₹45,000","₹४५,०००","45000 रुपये","५० हजार"]: run(p)
print("## empty/ws")
for p in [""," ","\n\t  ","   \u3000 ","\u200b","..."]:
    out,_=run(p)
