import math
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = "8960396864:AAG6hvz70PmVMk-ZrhoMH-21ZwiBBB-J-d0"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class BuildingStates(StatesGroup):
    wait_len = State()
    wait_wid = State()
    wait_hei = State()
    wait_roof = State()
    wait_annex = State()

class PavingStates(StatesGroup):
    wait_area = State()
    wait_perim = State()
    wait_curve = State()
    wait_depth = State()

class FenceStates(StatesGroup):
    wait_len = State()
    wait_hei = State()
    wait_gate = State()
    wait_wicket = State()

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Каркасник")],[KeyboardButton(text="🧱 Дорожки")],[KeyboardButton(text="🚧 Забор")]],
        resize_keyboard=True
    )

def yesno():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]],
        resize_keyboard=True
    )

def back():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Отмена")]],
        resize_keyboard=True
    )

class Building:
    def __init__(self, l, w, h, rs, ia=False, oa=10.0):
        self.L, self.W, self.H, self.rs, self.ia, self.oa = float(l), float(w), float(h), float(rs), ia, float(oa)
    def calc(self):
        p = self.L + (self.W*2) if self.ia else (self.L+self.W)*2
        wa = p*self.H; nwa = max(0, wa-self.oa); fa = self.L*self.W
        hw = self.W/2
        ga = 2*(0.5*self.W*math.sqrt(self.rs**2-hw**2)) if self.rs>hw else 0
        sc = math.ceil(p/0.59)+1; sv = sc*self.H*0.05*0.1
        jc = math.ceil(self.L/0.40)+1; jv = jc*self.W*0.04*0.15 + fa*0.04
        lc = math.ceil(self.H/0.30); lv = lc*p*0.025*0.15 + fa*0.025
        vc = math.ceil(p/0.40); vv = vc*self.H*0.05*0.04
        rv = 0
        if self.rs>0: rc = math.ceil(self.W/0.60)+1; rv = rc*self.rs*0.05*0.15
        ss = wa*1.1 + ga*1.2 - self.oa
        mv = (nwa+ga)*1.15
        return (f"📊 КАРКАСНИК\n{'─'*25}\n📐 Стены: {wa:.1f}м² | Чистые: {nwa:.1f}м²\n📐 Пол: {fa:.1f}м² | Фронтоны: {ga:.1f}м²\n\n🪵 Стойки 50×100: {sv:.3f}м³ ({sc}шт)\n🪵 Лаги 40×150: {jv:.3f}м³\n🪵 Обрешетка 25×150: {lv:.3f}м³\n🪵 Вентзазор 50×40: {vv:.3f}м³\n🪵 Стропила 50×150: {rv:.3f}м³\n\n📦 Сайдинг: {ss:.1f}м²\n📦 Пленки: {mv:.1f}м²\n\n🏷 {'ПРИСТРОЙ' if self.ia else 'ДОМ'}")

class Paving:
    def __init__(self, a, p, d=0.3, ic=False):
        self.S, self.P, self.d, self.ic = float(a), float(p), float(d), ic
    def calc(self):
        ev = self.S*self.d; gv = self.S*0.15*1.3; sv = self.S*0.1*1.2
        gt = self.S*1.1; tc = 1.12 if self.ic else 1.05; ta = self.S*tc
        bc = self.P*0.05
        return (f"🧱 МОЩЕНИЕ\n{'─'*25}\n🕳 Выемка: {ev:.2f}м³\n🧱 Щебень: {gv:.2f}м³\n🧱 Песок: {sv:.2f}м³\n📦 Геотекстиль: {gt:.1f}м²\n📦 Плитка: {ta:.1f}м²\n📦 Бетон М200: {bc:.2f}м³\n\n🏷 {'Радиусная' if self.ic else 'Прямая'}")

class Fence:
    def __init__(self, l, h, gl=4, wl=1):
        self.L, self.H, self.gl, self.wl = float(l), float(h), float(gl), float(wl)
    def calc(self):
        nl = max(0, self.L-self.gl-self.wl)
        pc = math.ceil(nl/2.5)+1; tl = pc*(self.H+1.2)
        hv = math.pi*0.01*1.2; tc = pc*hv; ll = nl*2
        sc = math.ceil(nl/1.15); sa = sc*self.H*1.05
        return (f"🚧 ЗАБОР\n{'─'*25}\n📏 Длина: {self.L:.1f}м | Высота: {self.H:.1f}м\n📏 Чистая: {nl:.1f}м | Ворота: {self.gl:.1f}м | Калитка: {self.wl:.1f}м\n\n🪵 Столбов: {pc}шт\n🪵 Трубы: {tl:.1f}м\n🪵 Прожилины: {ll:.1f}м\n📦 Бетон: {tc:.2f}м³\n📦 Профлист С8: {sc}л ({sa:.1f}м²)")

@dp.message(F.text=="/start")
async def start(m: Message):
    await m.answer("👋 Привет! Выбери что считаем:", reply_markup=menu())

@dp.message(F.text=="🔙 Отмена")
async def cancel(m: Message, s: FSMContext):
    await s.clear(); await m.answer("Главное меню:", reply_markup=menu())

@dp.message(F.text=="🏠 Каркасник")
async def b_start(m: Message, s: FSMContext):
    await s.set_state(BuildingStates.wait_len)
    await m.answer("🏠 КАРКАСНИК\nШаг 1/5\nДлина здания (м)?\nПример: 6", reply_markup=back())

@dp.message(BuildingStates.wait_len)
async def b_len(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 6", reply_markup=back()); return
    if v<=0 or v>50: await m.answer("От 1 до 50 метров", reply_markup=back()); return
    await s.update_data(l=v); await s.set_state(BuildingStates.wait_wid)
    await m.answer("Шаг 2/5\nШирина здания (м)?\nПример: 8", reply_markup=back())

@dp.message(BuildingStates.wait_wid)
async def b_wid(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 8", reply_markup=back()); return
    if v<=0 or v>50: await m.answer("От 1 до 50 метров", reply_markup=back()); return
    await s.update_data(w=v); await s.set_state(BuildingStates.wait_hei)
    await m.answer("Шаг 3/5\nВысота стен (м)?\nПример: 2.5", reply_markup=back())

@dp.message(BuildingStates.wait_hei)
async def b_hei(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 2.5", reply_markup=back()); return
    if v<=0 or v>10: await m.answer("От 1 до 10 метров", reply_markup=back()); return
    await s.update_data(h=v); await s.set_state(BuildingStates.wait_roof)
    await m.answer("Шаг 4/5\nДлина ската крыши (м)?\nЕсли крыши нет - введите 0\nПример: 3.5", reply_markup=back())

@dp.message(BuildingStates.wait_roof)
async def b_roof(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 3.5", reply_markup=back()); return
    if v<0 or v>20: await m.answer("От 0 до 20 метров", reply_markup=back()); return
    await s.update_data(rs=v); await s.set_state(BuildingStates.wait_annex)
    await m.answer("Шаг 5/5\nЭто пристрой к зданию?", reply_markup=yesno())

@dp.message(BuildingStates.wait_annex)
async def b_annex(m: Message, s: FSMContext):
    if m.text=="✅ Да": ia=True
    elif m.text=="❌ Нет": ia=False
    else: await m.answer("Нажмите кнопку", reply_markup=yesno()); return
    d=await s.get_data()
    c=Building(d["l"],d["w"],d["h"],d["rs"],ia)
    await m.answer(c.calc(), reply_markup=menu()); await s.clear()

@dp.message(F.text=="🧱 Дорожки")
async def p_start(m: Message, s: FSMContext):
    await s.set_state(PavingStates.wait_area)
    await m.answer("🧱 МОЩЕНИЕ\nШаг 1/4\nПлощадь мощения (м²)?\nПример: 30", reply_markup=back())

@dp.message(PavingStates.wait_area)
async def p_area(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 30", reply_markup=back()); return
    if v<=0 or v>1000: await m.answer("От 1 до 1000 м²", reply_markup=back()); return
    await s.update_data(a=v); await s.set_state(PavingStates.wait_perim)
    await m.answer("Шаг 2/4\nПериметр по бордюрам (м)?\nПример: 25", reply_markup=back())

@dp.message(PavingStates.wait_perim)
async def p_perim(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 25", reply_markup=back()); return
    if v<=0 or v>500: await m.answer("От 1 до 500 метров", reply_markup=back()); return
    await s.update_data(p=v); await s.set_state(PavingStates.wait_curve)
    await m.answer("Шаг 3/4\nДорожка криволинейная (радиусная)?", reply_markup=yesno())

@dp.message(PavingStates.wait_curve)
async def p_curve(m: Message, s: FSMContext):
    if m.text=="✅ Да": ic=True
    elif m.text=="❌ Нет": ic=False
    else: await m.answer("Нажмите кнопку", reply_markup=yesno()); return
    await s.update_data(ic=ic); await s.set_state(PavingStates.wait_depth)
    await m.answer("Шаг 4/4\nГлубина выемки грунта (м)?\nПо умолчанию 0.3\nВведите 0 если стандартная", reply_markup=back())

@dp.message(PavingStates.wait_depth)
async def p_depth(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",",".")); v=v if v>0 else 0.3
    except: v=0.3
    d=await s.get_data()
    c=Paving(d["a"],d["p"],v,d["ic"])
    await m.answer(c.calc(), reply_markup=menu()); await s.clear()

@dp.message(F.text=="🚧 Забор")
async def f_start(m: Message, s: FSMContext):
    await s.set_state(FenceStates.wait_len)
    await m.answer("🚧 ЗАБОР\nШаг 1/4\nОбщая длина забора (м)?\nПример: 50", reply_markup=back())

@dp.message(FenceStates.wait_len)
async def f_len(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 50", reply_markup=back()); return
    if v<=0 or v>500: await m.answer("От 1 до 500 метров", reply_markup=back()); return
    await s.update_data(l=v); await s.set_state(FenceStates.wait_hei)
    await m.answer("Шаг 2/4\nВысота забора (м)?\nСтандарт: 1.8 или 2.0\nПример: 1.8", reply_markup=back())

@dp.message(FenceStates.wait_hei)
async def f_hei(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 1.8", reply_markup=back()); return
    if v<=0 or v>5: await m.answer("От 0.5 до 5 метров", reply_markup=back()); return
    await s.update_data(h=v); await s.set_state(FenceStates.wait_gate)
    await m.answer("Шаг 3/4\nШирина ворот (м)?\nЕсли ворот нет - 0\nПример: 3", reply_markup=back())

@dp.message(FenceStates.wait_gate)
async def f_gate(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: await m.answer("Введите число. Пример: 3", reply_markup=back()); return
    if v<0 or v>20: await m.answer("От 0 до 20 метров", reply_markup=back()); return
    await s.update_data(g=v); await s.set_state(FenceStates.wait_wicket)
    await m.answer("Шаг 4/4\nШирина калитки (м)?\nЕсли калитки нет - 0\nПример: 1", reply_markup=back())

@dp.message(FenceStates.wait_wicket)
async def f_wicket(m: Message, s: FSMContext):
    try: v=float(m.text.replace(",","."));
    except: v=0
    if v<0 or v>5: await m.answer("От 0 до 5 метров", reply_markup=back()); return
    d=await s.get_data()
    c=Fence(d["l"],d["h"],d["g"],v)
    await m.answer(c.calc(), reply_markup=menu()); await s.clear()

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
