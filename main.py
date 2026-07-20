import math
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

BOT_TOKEN = "8960396864:AAG6hvz70PmVMk-ZrhoMH-21ZwiBBB-J-d0"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ============================================================
# МАШИНА СОСТОЯНИЙ
# ============================================================

class BuildingStates(StatesGroup):
    waiting_length = State()
    waiting_width = State()
    waiting_height = State()
    waiting_roof_slope = State()
    waiting_roof_type = State()
    waiting_is_annex = State()
    waiting_openings = State()

class PavingStates(StatesGroup):
    waiting_area = State()
    waiting_perimeter = State()
    waiting_depth = State()
    waiting_sand = State()
    waiting_gravel = State()
    waiting_is_curved = State()

class FenceStates(StatesGroup):
    waiting_length = State()
    waiting_height = State()
    waiting_gate = State()
    waiting_wicket = State()

# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Каркасник")],
            [KeyboardButton(text="🧱 Дорожки")],
            [KeyboardButton(text="🚧 Забор")]
        ],
        resize_keyboard=True
    )

def yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )

def roof_type_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Двускатная")],
            [KeyboardButton(text="📐 Односкатная")],
            [KeyboardButton(text="🚫 Нет крыши")]
        ],
        resize_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔙 Отмена")]
        ],
        resize_keyboard=True
    )

# ============================================================
# МОДУЛЬ 1: РАСЧЕТ КАРКАСНИКА
# ============================================================

class Building:
    def __init__(self, length, width, wall_height, roof_slope_len,
                 is_annex=False, openings_area=10.0):
        self.L = float(length)
        self.W = float(width)
        self.H = float(wall_height)
        self.roof_slope = float(roof_slope_len)
        self.is_annex = is_annex
        self.openings = float(openings_area)
    
    def calculate(self):
        if self.is_annex:
            perimeter = self.L + 2 * self.W
        else:
            perimeter = 2 * (self.L + self.W)
        
        wall_area = perimeter * self.H
        net_wall_area = max(0, wall_area - self.openings)
        floor_area = self.L * self.W
        
        half_width = self.W / 2
        if self.roof_slope > half_width:
            roof_height = math.sqrt(self.roof_slope**2 - half_width**2)
            gable_area = 2 * (0.5 * self.W * roof_height)
        else:
            gable_area = 0.0
        
        stud_count = math.ceil(perimeter / 0.59) + 1
        studs_volume = stud_count * self.H * 0.05 * 0.10
        
        joist_count = math.ceil(self.L / 0.40) + 1
        joists_volume = joist_count * self.W * 0.04 * 0.15
        joists_volume += floor_area * 0.04
        
        lath_count = math.ceil(self.H / 0.30)
        lath_volume = lath_count * perimeter * 0.025 * 0.15
        lath_volume += floor_area * 0.025
        
        vent_count = math.ceil(perimeter / 0.40)
        vent_volume = vent_count * self.H * 0.05 * 0.04
        
        rafters_volume = 0.0
        if self.roof_slope > 0:
            rafter_count = math.ceil(self.W / 0.60) + 1
            rafters_volume = rafter_count * self.roof_slope * 0.05 * 0.15
        
        siding_straight = wall_area * 1.10
        siding_gable = gable_area * 1.20
        total_siding = siding_straight + siding_gable - self.openings
        
        membrane_area = (net_wall_area + gable_area) * 1.15
        
        result = (
            f"📊 ОТЧЕТ ПО КАРКАСНИКУ\n"
            f"{'='*30}\n\n"
            f"📐 Геометрия:\n"
            f"  Периметр стен: {perimeter:.1f} м\n"
            f"  Площадь стен: {wall_area:.1f} м²\n"
            f"  Чистая площадь: {net_wall_area:.1f} м²\n"
            f"  Площадь пола: {floor_area:.1f} м²\n"
            f"  Фронтоны: {gable_area:.1f} м²\n\n"
            f"🪵 Пиломатериалы:\n"
            f"  Стойки 50х100: {studs_volume:.3f} м³ ({stud_count} шт)\n"
            f"  Лаги пола 40х150: {joists_volume:.3f} м³\n"
            f"  Обрешетка 25х150: {lath_volume:.3f} м³\n"
            f"  Вентзазор 50х40: {vent_volume:.3f} м³\n"
            f"  Стропила 50х150: {rafters_volume:.3f} м³\n\n"
            f"📦 Материалы:\n"
            f"  Сайдинг: {total_siding:.1f} м²\n"
            f"  Пленки/мембраны: {membrane_area:.1f} м²\n\n"
            f"Тип: {'Пристрой' if self.is_annex else 'Отдельное здание'}"
        )
        return result

# ============================================================
# МОДУЛЬ 2: РАСЧЕТ МОЩЕНИЯ
# ============================================================

class Paving:
    def __init__(self, area, perimeter, depth=0.3,
                 sand_thick=0.1, gravel_thick=0.15,
                 is_curved=False):
        self.S = float(area)
        self.P = float(perimeter)
        self.depth = float(depth)
        self.sand = float(sand_thick)
        self.gravel = float(gravel_thick)
        self.is_curved = is_curved
    
    def calculate(self):
        excavation_volume = self.S * self.depth
        gravel_volume = self.S * self.gravel * 1.3
        sand_volume = self.S * self.sand * 1.2
        geotextile_area = self.S * 1.10
        waste_coef = 1.12 if self.is_curved else 1.05
        tile_area = self.S * waste_coef
        border_concrete = self.P * 0.05
        
        result = (
            f"🧱 ОТЧЕТ ПО МОЩЕНИЮ\n"
            f"{'='*30}\n\n"
            f"🕳 Земляные работы:\n"
            f"  Выемка грунта: {excavation_volume:.2f} м³\n"
            f"  Периметр бордюров: {self.P:.1f} м\n\n"
            f"🧱 Подушка:\n"
            f"  Щебень: {gravel_volume:.2f} м³\n"
            f"  Песок: {sand_volume:.2f} м³\n\n"
            f"📦 Материалы:\n"
            f"  Геотекстиль: {geotextile_area:.1f} м²\n"
            f"  Плитка: {tile_area:.1f} м²\n"
            f"  Бетон М200: {border_concrete:.2f} м³\n\n"
            f"Тип: {'Криволинейная' if self.is_curved else 'Прямая'}"
        )
        return result

# ============================================================
# МОДУЛЬ 3: РАСЧЕТ ЗАБОРА
# ============================================================

class Fence:
    def __init__(self, total_length, height, gate_length=4.0, wicket_length=1.0):
        self.L = float(total_length)
        self.H = float(height)
        self.gate_L = float(gate_length)
        self.wicket_L = float(wicket_length)
    
    def calculate(self):
        net_length = self.L - self.gate_L - self.wicket_L
        if net_length < 0:
            net_length = 0
        
        posts_count = math.ceil(net_length / 2.5) + 1
        total_posts_length = posts_count * (self.H + 1.2)
        hole_volume = math.pi * (0.1 ** 2) * 1.2
        total_concrete = posts_count * hole_volume
        total_logs_length = net_length * 2
        sheets_count = math.ceil(net_length / 1.15)
        sheet_area = sheets_count * self.H * 1.05
        
        result = (
            f"🚧 ОТЧЕТ ПО ЗАБОРУ\n"
            f"{'='*30}\n\n"
            f"📏 Параметры:\n"
            f"  Длина: {self.L:.1f} м\n"
            f"  Высота: {self.H:.1f} м\n"
            f"  Ворота: {self.gate_L:.1f} м\n"
            f"  Калитка: {self.wicket_L:.1f} м\n"
            f"  Чистая длина: {net_length:.1f} м\n\n"
            f"🪵 Каркас:\n"
            f"  Столбов: {posts_count} шт\n"
            f"  Труба на столбы: {total_posts_length:.1f} м\n"
            f"  Бетон: {total_concrete:.2f} м³\n"
            f"  Прожилины: {total_logs_length:.1f} м\n\n"
            f"📦 Зашивка:\n"
            f"  Профлист С8: {sheets_count} листов\n"
            f"  Площадь: {sheet_area:.1f} м²"
        )
        return result

# ============================================================
# СТАРТ
# ============================================================

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет, Прораб!\n\n"
        "Помогу рассчитать материалы для стройки.\n"
        "Выбери что считаем:",
        reply_markup=main_menu()
    )

@dp.message(F.text == "🔙 Отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Возвращаюсь в главное меню.", reply_markup=main_menu())

# ============================================================
# КАРКАСНИК - ПОШАГОВЫЙ ВВОД
# ============================================================

@dp.message(F.text == "🏠 Каркасник")
async def building_start(message: Message, state: FSMContext):
    await state.set_state(BuildingStates.waiting_length)
    await message.answer(
        "🏠 КАРКАСНИК\n\n"
        "Шаг 1 из 6\n\n"
        "Введите ДЛИНУ здания в метрах.\n"
        "Пример: 6",
        reply_markup=cancel_kb()
    )

@dp.message(BuildingStates.waiting_length)
async def building_length(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 50:
            raise ValueError
        await state.update_data(length=val)
        await state.set_state(BuildingStates.waiting_width)
        await message.answer(
            "Шаг 2 из 6\n\n"
            "Введите ШИРИНУ здания в метрах.\n"
            "Пример: 8",
            reply_markup=cancel_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 1 до 50.\nПример: 6", reply_markup=cancel_kb())

@dp.message(BuildingStates.waiting_width)
async def building_width(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 50:
            raise ValueError
        await state.update_data(width=val)
        await state.set_state(BuildingStates.waiting_height)
        await message.answer(
            "Шаг 3 из 6\n\n"
            "Введите ВЫСОТУ стен в метрах.\n"
            "Пример: 2.5",
            reply_markup=cancel_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 1 до 10.\nПример: 2.5", reply_markup=cancel_kb())

@dp.message(BuildingStates.waiting_height)
async def building_height(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 10:
            raise ValueError
        await state.update_data(height=val)
        await state.set_state(BuildingStates.waiting_roof_type)
        await message.answer(
            "Шаг 4 из 6\n\n"
            "Выберите тип крыши:",
            reply_markup=roof_type_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 1 до 10.\nПример: 2.5", reply_markup=cancel_kb())

@dp.message(BuildingStates.waiting_roof_type)
async def building_roof_type(message: Message, state: FSMContext):
    text = message.text
    if text == "🏠 Двускатная":
        await state.update_data(roof_type="gable")
        await state.set_state(BuildingStates.waiting_roof_slope)
        await message.answer(
            "Шаг 5 из 6\n\n"
            "Введите ДЛИНУ СКАТА кровли в метрах.\n"
            "Пример: 4",
            reply_markup=cancel_kb()
        )
    elif text == "📐 Односкатная":
        await state.update_data(roof_type="shed")
        await state.set_state(BuildingStates.waiting_roof_slope)
        await message.answer(
            "Шаг 5 из 6\n\n"
            "Введите ДЛИНУ СКАТА кровли в метрах.\n"
            "Пример: 3",
            reply_markup=cancel_kb()
        )
    elif text == "🚫 Нет крыши":
        await state.update_data(roof_type="none", roof_slope=0)
        await state.set_state(BuildingStates.waiting_is_annex)
        await message.answer(
            "Шаг 5 из 6\n\n"
            "Это ПРИСТРОЙ к существующему зданию?",
            reply_markup=yes_no_kb()
        )
    else:
        await message.answer("Нажмите на одну из кнопок.", reply_markup=roof_type_kb())

@dp.message(BuildingStates.waiting_roof_slope)
async def building_roof_slope(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 20:
            raise ValueError
        await state.update_data(roof_slope=val)
        await state.set_state(BuildingStates.waiting_is_annex)
        await message.answer(
            "Шаг 6 из 6\n\n"
            "Это ПРИСТРОЙ к существующему зданию?",
            reply_markup=yes_no_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 0.5 до 20.\nПример: 4", reply_markup=cancel_kb())

@dp.message(BuildingStates.waiting_is_annex)
async def building_annex(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text == "✅ Да":
        data["is_annex"] = True
    elif message.text == "❌ Нет":
        data["is_annex"] = False
    else:
        await message.answer("Нажмите Да или Нет.", reply_markup=yes_no_kb())
        return
    
    await state.set_state(BuildingStates.waiting_openings)
    await message.answer(
        "Введите площадь окон и дверей в м².\n"
        "По умолчанию: 10 м²\n"
        "Если не знаете - просто отправьте 0",
        reply_markup=cancel_kb()
    )

@dp.message(BuildingStates.waiting_openings)
async def building_openings(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val == 0:
            val = 10.0
        await state.update_data(openings=val)
    except:
        await state.update_data(openings=10.0)
    
    data = await state.get_data()
    calc = Building(
        length=data["length"],
        width=data["width"],
        wall_height=data["height"],
        roof_slope_len=data.get("roof_slope", 0),
        is_annex=data.get("is_annex", False),
        openings_area=data.get("openings", 10.0)
    )
    
    await message.answer(calc.calculate(), reply_markup=main_menu())
    await state.clear()

# ============================================================
# МОЩЕНИЕ - ПОШАГОВЫЙ ВВОД
# ============================================================

@dp.message(F.text == "🧱 Дорожки")
async def paving_start(message: Message, state: FSMContext):
    await state.set_state(PavingStates.waiting_area)
    await message.answer(
        "🧱 МОЩЕНИЕ\n\n"
        "Шаг 1 из 4\n\n"
        "Введите ПЛОЩАДЬ мощения в м².\n"
        "Пример: 30",
        reply_markup=cancel_kb()
    )

@dp.message(PavingStates.waiting_area)
async def paving_area(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 1000:
            raise ValueError
        await state.update_data(area=val)
        await state.set_state(PavingStates.waiting_perimeter)
        await message.answer(
            "Шаг 2 из 4\n\n"
            "Введите ПЕРИМЕТР по бордюрам в метрах.\n"
            "Пример: 25",
            reply_markup=cancel_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 1 до 1000.\nПример: 30", reply_markup=cancel_kb())

@dp.message(PavingStates.waiting_perimeter)
async def paving_perimeter(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 500:
            raise ValueError
        await state.update_data(perimeter=val)
        await state.set_state(PavingStates.waiting_is_curved)
        await message.answer(
            "Шаг 3 из 4\n\n"
            "Дорожка КРИВОЛИНЕЙНАЯ (радиусная)?\n"
            "Для прямой выберите Нет",
            reply_markup=yes_no_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 1 до 500.\nПример: 25", reply_markup=cancel_kb())

@dp.message(PavingStates.waiting_is_curved)
async def paving_curved(message: Message, state: FSMContext):
    if message.text == "✅ Да":
        await state.update_data(is_curved=True)
    elif message.text == "❌ Нет":
        await state.update_data(is_curved=False)
    else:
        await message.answer("Нажмите Да или Нет.", reply_markup=yes_no_kb())
        return
    
    await state.set_state(PavingStates.waiting_depth)
    await message.answer(
        "Шаг 4 из 4\n\n"
        "Введите ГЛУБИНУ выемки грунта (корыто) в метрах.\n"
        "По умолчанию: 0.3 м\n"
        "Просто отправьте 0 если стандартная",
        reply_markup=cancel_kb()
    )

@dp.message(PavingStates.waiting_depth)
async def paving_depth(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            val = 0.3
        await state.update_data(depth=val)
    except:
        await state.update_data(depth=0.3)
    
    await state.update_data(sand=0.1, gravel=0.15)
    
    data = await state.get_data()
    calc = Paving(
        area=data["area"],
        perimeter=data["perimeter"],
        depth=data["depth"],
        is_curved=data.get("is_curved", False)
    )
    
    await message.answer(calc.calculate(), reply_markup=main_menu())
    await state.clear()

# ============================================================
# ЗАБОР - ПОШАГОВЫЙ ВВОД
# ============================================================

@dp.message(F.text == "🚧 Забор")
async def fence_start(message: Message, state: FSMContext):
    await state.set_state(FenceStates.waiting_length)
    await message.answer(
        "🚧 ЗАБОР ИЗ ПРОФЛИСТА\n\n"
        "Шаг 1 из 4\n\n"
        "Введите ОБЩУЮ ДЛИНУ забора в метрах.\n"
        "Пример: 50",
        reply_markup=cancel_kb()
    )

@dp.message(FenceStates.waiting_length)
async def fence_length(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 500:
            raise ValueError
        await state.update_data(length=val)
        await state.set_state(FenceStates.waiting_height)
        await message.answer(
            "Шаг 2 из 4\n\n"
            "Введите ВЫСОТУ забора в метрах.\n"
            "Стандарт: 1.8 м или 2.0 м\n"
            "Пример: 1.8",
            reply_markup=cancel_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 1 до 500.\nПример: 50", reply_markup=cancel_kb())

@dp.message(FenceStates.waiting_height)
async def fence_height(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0 or val > 5:
            raise ValueError
        await state.update_data(height=val)
        await state.set_state(FenceStates.waiting_gate)
        await message.answer(
            "Шаг 3 из 4\n\n"
            "Введите ШИРИНУ ВОРОТ в метрах.\n"
            "Если ворот нет - введите 0\n"
            "Стандарт: 3-4 метра",
            reply_markup=cancel_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 0 до 5.\nПример: 1.8", reply_markup=cancel_kb())

@dp.message(FenceStates.waiting_gate)
async def fence_gate(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val < 0 or val > 20:
            raise ValueError
        await state.update_data(gate=val)
        await state.set_state(FenceStates.waiting_wicket)
        await message.answer(
            "Шаг 4 из 4\n\n"
            "Введите ШИРИНУ КАЛИТКИ в метрах.\n"
            "Если калитки нет - введите 0\n"
            "Стандарт: 0.8-1.2 метра",
            reply_markup=cancel_kb()
        )
    except:
        await message.answer("❌ Ошибка! Введите число от 0 до 20.\nПример: 3", reply_markup=cancel_kb())

@dp.message(FenceStates.waiting_wicket)
async def fence_wicket(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val < 0 or val > 5:
            raise ValueError
        await state.update_data(wicket=val)
    except:
        await state.update_data(wicket=0)
    
    data = await state.get_data()
    calc = Fence(
        total_length=data["length"],
        height=data["height"],
        gate_length=data.get("gate", 0),
        wicket_length=data.get("wicket", 0)
    )
    
    await message.answer(calc.calculate(), reply_markup=main_menu())
    await state.clear()

# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
