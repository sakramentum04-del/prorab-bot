import math,logging,asyncio
from aiogram import Bot,Dispatcher,F
from aiogram.types import Message,ReplyKeyboardMarkup,KeyboardButton,ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State

BOT_TOKEN="8960396864:AAG6hvz70PmVMk-ZrhoMH-21ZwiBBB-J-d0"
logging.basicConfig(level=logging.INFO)
bot=Bot(token=BOT_TOKEN);dp=Dispatcher()

class BSt(StatesGroup): l=State();w=State();h=State();r=State();a=State()
class PSt(StatesGroup): a=State();p=State();c=State();d=State()
class FSt(StatesGroup): l=State();h=State();g=State();wk=State()

def m():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Каркасник")],[KeyboardButton(text="🧱 Дорожки")],[KeyboardButton(text="🚧 Забор")]],resize_keyboard=True)
def yn():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да"),KeyboardButton(text="❌ Нет")]],resize_keyboard=True)
def b():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Отмена")]],resize_keyboard=True)

class Building:
    def __init__(s,l,w,h,rs,ia=False,oa=10):
        s.L,l2,w2,h2,rs2=float(l),float(w),float(h),float(rs)
        s.L,s.W,s.H,s.rs,s.ia,s.oa=l2,w2,h2,rs2,ia,float(oa)
    def calc(s):
        p=s.L+(s.W*2) if s.ia else (s.L+s.W)*2
        wa=p*s.H;nwa=max(0,wa-s.oa);fa=s.L*s.W
        hw=s.W/2;ga=2*(0.5*s.W*((s.rs**2-hw**2)**0.5)) if s.rs>hw else 0
        sc=int(p/0.59)+2;sv=sc*s.H*0.05*0.1
        jc=int(s.L/0.4)+2;jv=jc*s.W*0.04*0.15+fa*0.04
        lc=int(s.H/0.3)+1;lv=lc*p*0.025*0.15+fa*0.025
        vc=int(p/0.4)+1;vv=vc*s.H*0.05*0.04
        rv=0
        if s.rs>0:rc=int(s.W/0.6)+2;rv=rc*s.rs*0.05*0.15
        ss=wa*1.1+ga*1.2-s.oa;mv=(nwa+ga)*1.15
        return f"📊 КАРКАСНИК\n{'─'*25}\n📐 Стены: {wa:.1f}м² (чистые: {nwa:.1f}м²)\n📐 Пол: {fa:.1f}м²\n📐 Фронтоны: {ga:.1f}м²\n\n🪵 Стойки 50×100: {sv:.3f}м³ ({sc}шт)\n🪵 Лаги 40×150: {jv:.3f}м³\n🪵 Обрешетка 25×150: {lv:.3f}м³\n🪵 Вентзазор 50×40: {vv:.3f}м³\n🪵 Стропила 50×150: {rv:.3f}м³\n\n📦 Сайдинг: {ss:.1f}м²\n📦 Пленки: {mv:.1f}м²\n\n🏷 {'ПРИСТРОЙ' if s.ia else 'ДОМ'}"

class Paving:
    def __init__(s,a,p,d=0.3,ic=False):
        s.S,s.P,s.d,s.ic=float(a),float(p),float(d),ic
    def calc(s):
        ev=s.S*s.d;gv=s.S*0.15*1.3;sv2=s.S*0.1*1.2
        gt=s.S*1.1;tc=1.12 if s.ic else 1.05;ta=s.S*tc
        bc=s.P*0.05
        return f"🧱 МОЩЕНИЕ\n{'─'*25}\n🕳 Выемка: {ev:.2f}м³\n🧱 Щебень: {gv:.2f}м³\n🧱 Песок: {sv2:.2f}м³\n📦 Геотекстиль: {gt:.1f}м²\n📦 Плитка: {ta:.1f}м²\n📦 Бетон М200: {bc:.2f}м³\n\n🏷 {'Радиусная' if s.ic else 'Прямая'}"

class Fence:
    def __init__(s,l,h,gl=4,wl=1):
        s.L,s.H,s.gl,s.wl=float(l),float(h),float(gl),float(wl)
    def calc(s):
        nl=max(0,s.L-s.gl-s.wl);pc=int(nl/2.5)+2;tl=pc*(s.H+1.2)
        hv=3.14*0.01*1.2;tc=pc*hv;ll=nl*2
        sc=int(nl/1.15)+1;sa=sc*s.H*1.05
        return f"🚧 ЗАБОР\n{'─'*25}\n📏 Длина: {s.L:.1f}м | Высота: {s.H:.1f}м\n📏 Чистая: {nl:.1f}м | Ворота: {s.gl:.1f}м | Калитка: {s.wl:.1f}м\n\n🪵 Столбов: {pc}шт\n🪵 Трубы: {tl:.1f}м\n🪵 Прожилины: {ll:.1f}м\n📦 Бетон: {tc:.2f}м³\n📦 Профлист С8: {sc}л ({sa:.1f}м²)"

@dp.message(F.text=="/start")
async def start(m:Message):
    await m.answer("👋 Привет! Выбери что считаем:",reply_markup=m())

@dp.message(F.text=="🔙 Отмена")
async def cancel(m:Message,s:FSMContext):
    await s.clear();await m.answer("Главное меню:",reply_markup=m())

@dp.message(F.text=="🏠 Каркасник")
async def bs(m:Message,s:FSMContext):
    await s.set_state(BSt.l);await m.answer("🏠 КАРКАСНИК\nШаг 1/5\n\nВведите ДЛИНУ (м)\nПример: 6",reply_markup=b())

@dp.message(BSt.l)
async def bl(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 6",reply_markup=b());return
    if v<=0 or v>50:await m.answer("❌ От 1 до 50 метров",reply_markup=b());return
    await s.update_data(l=v);await s.set_state(BSt.w)
    await m.answer("Шаг 2/5\n\nВведите ШИРИНУ (м)\nПример: 8",reply_markup=b())

@dp.message(BSt.w)
async def bw(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 8",reply_markup=b());return
    if v<=0 or v>50:await m.answer("❌ От 1 до 50 метров",reply_markup=b());return
    await s.update_data(w=v);await s.set_state(BSt.h)
    await m.answer("Шаг 3/5\n\nВведите ВЫСОТУ СТЕН (м)\nПример: 2.5",reply_markup=b())

@dp.message(BSt.h)
async def bh(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 2.5",reply_markup=b());return
    if v<=0 or v>10:await m.answer("❌ От 1 до 10 метров",reply_markup=b());return
    await s.update_data(h=v);await s.set_state(BSt.r)
    await m.answer("Шаг 4/5\n\nВведите ДЛИНУ СКАТА (м)\nЕсли крыши нет - 0\nПример: 3.5",reply_markup=b())

@dp.message(BSt.r)
async def br(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 3.5",reply_markup=b());return
    if v<0 or v>20:await m.answer("❌ От 0 до 20 метров",reply_markup=b());return
    await s.update_data(r=v);await s.set_state(BSt.a)
    await m.answer("Шаг 5/5\n\nЭто ПРИСТРОЙ к зданию?",reply_markup=yn())

@dp.message(BSt.a)
async def ba(m:Message,s:FSMContext):
    if m.text=="✅ Да":ia=True
    elif m.text=="❌ Нет":ia=False
    else:await m.answer("Нажмите кнопку",reply_markup=yn());return
    d=await s.get_data()
    c=Building(d["l"],d["w"],d["h"],d["r"],ia)
    await m.answer(c.calc());await m.answer("✅ Готово! Выберите следующий раздел:",reply_markup=m());await s.clear()

@dp.message(F.text=="🧱 Дорожки")
async def ps(m:Message,s:FSMContext):
    await s.set_state(PSt.a);await m.answer("🧱 МОЩЕНИЕ\nШаг 1/4\n\nВведите ПЛОЩАДЬ (м²)\nПример: 30",reply_markup=b())

@dp.message(PSt.a)
async def pa(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 30",reply_markup=b());return
    if v<=0 or v>1000:await m.answer("❌ От 1 до 1000 м²",reply_markup=b());return
    await s.update_data(a=v);await s.set_state(PSt.p)
    await m.answer("Шаг 2/4\n\nВведите ПЕРИМЕТР по бордюрам (м)\nПример: 25",reply_markup=b())

@dp.message(PSt.p)
async def pp(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 25",reply_markup=b());return
    if v<=0 or v>500:await m.answer("❌ От 1 до 500 метров",reply_markup=b());return
    await s.update_data(p=v);await s.set_state(PSt.c)
    await m.answer("Шаг 3/4\n\nДорожка КРИВОЛИНЕЙНАЯ?",reply_markup=yn())

@dp.message(PSt.c)
async def pc(m:Message,s:FSMContext):
    if m.text=="✅ Да":ic=True
    elif m.text=="❌ Нет":ic=False
    else:await m.answer("Нажмите кнопку",reply_markup=yn());return
    await s.update_data(c=ic);await s.set_state(PSt.d)
    await m.answer("Шаг 4/4\n\nГлубина выемки грунта (м)?\nПо умолч. 0.3\nВведите 0 если стандарт",reply_markup=b())

@dp.message(PSt.d)
async def pd(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."));v=v if v>0 else 0.3
    except:v=0.3
    d=await s.get_data()
    c=Paving(d["a"],d["p"],v,d["c"])
    await m.answer(c.calc());await m.answer("✅ Готово!",reply_markup=m());await s.clear()

@dp.message(F.text=="🚧 Забор")
async def fs(m:Message,s:FSMContext):
    await s.set_state(FSt.l);await m.answer("🚧 ЗАБОР\nШаг 1/4\n\nВведите ОБЩУЮ ДЛИНУ (м)\nПример: 50",reply_markup=b())

@dp.message(FSt.l)
async def fl(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 50",reply_markup=b());return
    if v<=0 or v>500:await m.answer("❌ От 1 до 500 метров",reply_markup=b());return
    await s.update_data(l=v);await s.set_state(FSt.h)
    await m.answer("Шаг 2/4\n\nВведите ВЫСОТУ ЗАБОРА (м)\nСтандарт: 1.8 или 2.0\nПример: 1.8",reply_markup=b())

@dp.message(FSt.h)
async def fh(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 1.8",reply_markup=b());return
    if v<=0 or v>5:await m.answer("❌ От 0.5 до 5 метров",reply_markup=b());return
    await s.update_data(h=v);await s.set_state(FSt.g)
    await m.answer("Шаг 3/4\n\nВведите ШИРИНУ ВОРОТ (м)\nЕсли ворот нет - 0\nПример: 3",reply_markup=b())

@dp.message(FSt.g)
async def fg(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 3",reply_markup=b());return
    if v<0 or v>20:await m.answer("❌ От 0 до 20 метров",reply_markup=b());return
    await s.update_data(g=v);await s.set_state(FSt.wk)
    await m.answer("Шаг 4/4\n\nВведите ШИРИНУ КАЛИТКИ (м)\nЕсли калитки нет - 0\nПример: 1",reply_markup=b())

@dp.message(FSt.wk)
async def fwk(m:Message,s:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:await m.answer("❌ Введите число. Пример: 1",reply_markup=b());return
    if v<0 or v>5:await m.answer("❌ От 0 до 5 метров",reply_markup=b());return
    d=await s.get_data()
    c=Fence(d["l"],d["h"],d["g"],v)
    await m.answer(c.calc());await m.answer("✅ Готово!",reply_markup=m());await s.clear()

async def main():
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
