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

def menu_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Каркасник")],[KeyboardButton(text="🧱 Дорожки")],[KeyboardButton(text="🚧 Забор")]],resize_keyboard=True)
def yesno_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да"),KeyboardButton(text="❌ Нет")]],resize_keyboard=True)
def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Отмена")]],resize_keyboard=True)

class Building:
    def __init__(self,l,w,h,rs,ia=False,oa=10):
        self.L,self.W,self.H,self.rs,self.ia,self.oa=float(l),float(w),float(h),float(rs),ia,float(oa)
    def calc(self):
        p=self.L+(self.W*2) if self.ia else (self.L+self.W)*2
        wa=p*self.H;nwa=max(0,wa-self.oa);fa=self.L*self.W
        hw=self.W/2;ga=2*(0.5*self.W*((self.rs**2-hw**2)**0.5)) if self.rs>hw else 0
        sc=int(p/0.59)+2;sv=sc*self.H*0.05*0.1
        jc=int(self.L/0.4)+2;jv=jc*self.W*0.04*0.15+fa*0.04
        lc=int(self.H/0.3)+1;lv=lc*p*0.025*0.15+fa*0.025
        vc=int(p/0.4)+1;vv=vc*self.H*0.05*0.04
        rv=0
        if self.rs>0:rc=int(self.W/0.6)+2;rv=rc*self.rs*0.05*0.15
        ss=wa*1.1+ga*1.2-self.oa;mv=(nwa+ga)*1.15
        return f"📊 КАРКАСНИК\n{'─'*25}\n📐 Стены: {wa:.1f}м² (чистые: {nwa:.1f}м²)\n📐 Пол: {fa:.1f}м²\n📐 Фронтоны: {ga:.1f}м²\n\n🪵 Стойки 50×100: {sv:.3f}м³ ({sc}шт)\n🪵 Лаги 40×150: {jv:.3f}м³\n🪵 Обрешетка 25×150: {lv:.3f}м³\n🪵 Вентзазор 50×40: {vv:.3f}м³\n🪵 Стропила 50×150: {rv:.3f}м³\n\n📦 Сайдинг: {ss:.1f}м²\n📦 Пленки: {mv:.1f}м²\n\n🏷 {'ПРИСТРОЙ' if self.ia else 'ДОМ'}"

class Paving:
    def __init__(self,a,p,d=0.3,ic=False):
        self.S,self.P,self.d,self.ic=float(a),float(p),float(d),ic
    def calc(self):
        ev=self.S*self.d;gv=self.S*0.15*1.3;sv2=self.S*0.1*1.2
        gt=self.S*1.1;tc=1.12 if self.ic else 1.05;ta=self.S*tc
        bc=self.P*0.05
        return f"🧱 МОЩЕНИЕ\n{'─'*25}\n🕳 Выемка: {ev:.2f}м³\n🧱 Щебень: {gv:.2f}м³\n🧱 Песок: {sv2:.2f}м³\n📦 Геотекстиль: {gt:.1f}м²\n📦 Плитка: {ta:.1f}м²\n📦 Бетон М200: {bc:.2f}м³\n\n🏷 {'Радиусная' if self.ic else 'Прямая'}"

class Fence:
    def __init__(self,l,h,gl=4,wl=1):
        self.L,self.H,self.gl,self.wl=float(l),float(h),float(gl),float(wl)
    def calc(self):
        nl=max(0,self.L-self.gl-self.wl);pc=int(nl/2.5)+2;tl=pc*(self.H+1.2)
        hv=3.14*0.01*1.2;tc=pc*hv;ll=nl*2
        sc=int(nl/1.15)+1;sa=sc*self.H*1.05
        return f"🚧 ЗАБОР\n{'─'*25}\n📏 Длина: {self.L:.1f}м | Высота: {self.H:.1f}м\n📏 Чистая: {nl:.1f}м | Ворота: {self.gl:.1f}м | Калитка: {self.wl:.1f}м\n\n🪵 Столбов: {pc}шт\n🪵 Трубы: {tl:.1f}м\n🪵 Прожилины: {ll:.1f}м\n📦 Бетон: {tc:.2f}м³\n📦 Профлист С8: {sc}л ({sa:.1f}м²)"

@dp.message(F.text=="/start")
async def cmd_start(message:Message):
    await message.answer("👋 Привет! Выбери что считаем:",reply_markup=menu_kb())

@dp.message(F.text=="🔙 Отмена")
async def cmd_cancel(message:Message, state:FSMContext):
    await state.clear();await message.answer("Главное меню:",reply_markup=menu_kb())

@dp.message(F.text=="🏠 Каркасник")
async def building_start(message:Message, state:FSMContext):
    await state.set_state(BSt.l);await message.answer("🏠 КАРКАСНИК\nШаг 1/5\n\nВведите ДЛИНУ (м)\nПример: 6",reply_markup=back_kb())

@dp.message(BSt.l)
async def building_length(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 6",reply_markup=back_kb());return
    if v<=0 or v>50:await message.answer("❌ От 1 до 50 метров",reply_markup=back_kb());return
    await state.update_data(l=v);await state.set_state(BSt.w)
    await message.answer("Шаг 2/5\n\nВведите ШИРИНУ (м)\nПример: 8",reply_markup=back_kb())

@dp.message(BSt.w)
async def building_width(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 8",reply_markup=back_kb());return
    if v<=0 or v>50:await message.answer("❌ От 1 до 50 метров",reply_markup=back_kb());return
    await state.update_data(w=v);await state.set_state(BSt.h)
    await message.answer("Шаг 3/5\n\nВведите ВЫСОТУ СТЕН (м)\nПример: 2.5",reply_markup=back_kb())

@dp.message(BSt.h)
async def building_height(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 2.5",reply_markup=back_kb());return
    if v<=0 or v>10:await message.answer("❌ От 1 до 10 метров",reply_markup=back_kb());return
    await state.update_data(h=v);await state.set_state(BSt.r)
    await message.answer("Шаг 4/5\n\nВведите ДЛИНУ СКАТА (м)\nЕсли крыши нет - 0\nПример: 3.5",reply_markup=back_kb())

@dp.message(BSt.r)
async def building_roof(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 3.5",reply_markup=back_kb());return
    if v<0 or v>20:await message.answer("❌ От 0 до 20 метров",reply_markup=back_kb());return
    await state.update_data(r=v);await state.set_state(BSt.a)
    await message.answer("Шаг 5/5\n\nЭто ПРИСТРОЙ к зданию?",reply_markup=yesno_kb())

@dp.message(BSt.a)
async def building_annex(message:Message, state:FSMContext):
    if message.text=="✅ Да":ia=True
    elif message.text=="❌ Нет":ia=False
    else:await message.answer("Нажмите кнопку",reply_markup=yesno_kb());return
    d=await state.get_data()
    c=Building(d["l"],d["w"],d["h"],d["r"],ia)
    await message.answer(c.calc());await message.answer("✅ Готово! Выберите следующий раздел:",reply_markup=menu_kb());await state.clear()

@dp.message(F.text=="🧱 Дорожки")
async def paving_start(message:Message, state:FSMContext):
    await state.set_state(PSt.a);await message.answer("🧱 МОЩЕНИЕ\nШаг 1/4\n\nВведите ПЛОЩАДЬ (м²)\nПример: 30",reply_markup=back_kb())

@dp.message(PSt.a)
async def paving_area(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 30",reply_markup=back_kb());return
    if v<=0 or v>1000:await message.answer("❌ От 1 до 1000 м²",reply_markup=back_kb());return
    await state.update_data(a=v);await state.set_state(PSt.p)
    await message.answer("Шаг 2/4\n\nВведите ПЕРИМЕТР по бордюрам (м)\nПример: 25",reply_markup=back_kb())

@dp.message(PSt.p)
async def paving_perimeter(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 25",reply_markup=back_kb());return
    if v<=0 or v>500:await message.answer("❌ От 1 до 500 метров",reply_markup=back_kb());return
    await state.update_data(p=v);await state.set_state(PSt.c)
    await message.answer("Шаг 3/4\n\nДорожка КРИВОЛИНЕЙНАЯ?",reply_markup=yesno_kb())

@dp.message(PSt.c)
async def paving_curved(message:Message, state:FSMContext):
    if message.text=="✅ Да":ic=True
    elif message.text=="❌ Нет":ic=False
    else:await message.answer("Нажмите кнопку",reply_markup=yesno_kb());return
    await state.update_data(c=ic);await state.set_state(PSt.d)
    await message.answer("Шаг 4/4\n\nГлубина выемки грунта (м)?\nПо умолч. 0.3\nВведите 0 если стандарт",reply_markup=back_kb())

@dp.message(PSt.d)
async def paving_depth(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."));v=v if v>0 else 0.3
    except:v=0.3
    d=await state.get_data()
    c=Paving(d["a"],d["p"],v,d["c"])
    await message.answer(c.calc());await message.answer("✅ Готово!",reply_markup=menu_kb());await state.clear()

@dp.message(F.text=="🚧 Забор")
async def fence_start(message:Message, state:FSMContext):
    await state.set_state(FSt.l);await message.answer("🚧 ЗАБОР\nШаг 1/4\n\nВведите ОБЩУЮ ДЛИНУ (м)\nПример: 50",reply_markup=back_kb())

@dp.message(FSt.l)
async def fence_length(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 50",reply_markup=back_kb());return
    if v<=0 or v>500:await message.answer("❌ От 1 до 500 метров",reply_markup=back_kb());return
    await state.update_data(l=v);await state.set_state(FSt.h)
    await message.answer("Шаг 2/4\n\nВведите ВЫСОТУ ЗАБОРА (м)\nСтандарт: 1.8 или 2.0\nПример: 1.8",reply_markup=back_kb())

@dp.message(FSt.h)
async def fence_height(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 1.8",reply_markup=back_kb());return
    if v<=0 or v>5:await message.answer("❌ От 0.5 до 5 метров",reply_markup=back_kb());return
    await state.update_data(h=v);await state.set_state(FSt.g)
    await message.answer("Шаг 3/4\n\nВведите ШИРИНУ ВОРОТ (м)\nЕсли ворот нет - 0\nПример: 3",reply_markup=back_kb())

@dp.message(FSt.g)
async def fence_gate(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 3",reply_markup=back_kb());return
    if v<0 or v>20:await message.answer("❌ От 0 до 20 метров",reply_markup=back_kb());return
    await state.update_data(g=v);await state.set_state(FSt.wk)
    await message.answer("Шаг 4/4\n\nВведите ШИРИНУ КАЛИТКИ (м)\nЕсли калитки нет - 0\nПример: 1",reply_markup=back_kb())

@dp.message(FSt.wk)
async def fence_wicket(message:Message, state:FSMContext):
    try:v=float(message.text.replace(",","."))
    except:await message.answer("❌ Введите число. Пример: 1",reply_markup=back_kb());return
    if v<0 or v>5:await message.answer("❌ От 0 до 5 метров",reply_markup=back_kb());return
    d=await state.get_data()
    c=Fence(d["l"],d["h"],d["g"],v)
    await message.answer(c.calc());await message.answer("✅ Готово!",reply_markup=menu_kb());await state.clear()

async def main():
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
