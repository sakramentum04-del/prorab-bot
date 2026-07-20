import math
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
# МАШИНА СОСТОЯНИЙ (FSM)
# ============================================================

class OrderStates(StatesGroup):
    waiting_for_building = State()
    waiting_for_paving = State()
    waiting_for_fence = State()

# ============================================================
# КЛАВИАТУРА ГЛАВНОГО МЕНЮ
# ============================================================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Каркасник/Пристрой")],
        [KeyboardButton(text="🧱 Дорожки и брусчатка")],
        [KeyboardButton(text="🚧 Забор из профлиста")]
    ],
    resize_keyboard=True
)

# ============================================================
# МОДУЛЬ 1: РАСЧЕТ КАРКАСНИКА / ПРИСТРОЯ
# ============================================================

class Building:
    """
    Расчет каркасного строения/пристроя.
    
    Вход: длина, ширина, высота стен, длина ската кровли,
          флаг пристроя (True/False), площадь проемов (по умолчанию 10 м²)
    
    Конструктивные требования:
    - Шаг стоек стен 50х100: 590 мм в свету
    - Шаг лаг пола 40х150: 400 мм
    - Обрешетка стен 25х150: шаг 300 мм
    - Вентзазор брусок 50х40: шаг 400 мм
    - Запас сайдинга: прямые стены 10%, фронтоны 20%
    - Нахлест мембран: 15%
    """
    
    def __init__(self, length, width, wall_height, roof_slope_len,
                 is_annex=False, openings_area=10.0):
        self.L = float(length)
        self.W = float(width)
        self.H = float(wall_height)
        self.roof_slope = float(roof_slope_len)
        self.is_annex = is_annex
        self.openings = float(openings_area)
    
    def calculate(self):
        # --- Геометрия стен ---
        # Если пристрой, одна длинная стена исключается
        if self.is_annex:
            perimeter = self.L + 2 * self.W
        else:
            perimeter = 2 * (self.L + self.W)
        
        wall_area = perimeter * self.H
        net_wall_area = max(0, wall_area - self.openings)
        
        # --- Площадь пола/потолка ---
        floor_area = self.L * self.W
        
        # --- Фронтоны (треугольные части кровли) ---
        half_width = self.W / 2
        if self.roof_slope > half_width:
            roof_height = math.sqrt(self.roof_slope**2 - half_width**2)
            gable_area = 2 * (0.5 * self.W * roof_height)
        else:
            gable_area = 0.0
        
        # --- Стойки стен 50х100 (шаг 590 мм) ---
        stud_count = math.ceil(perimeter / 0.59) + 1
        studs_volume = stud_count * self.H * 0.05 * 0.10
        
        # --- Лаги пола 40х150 (шаг 400 мм) ---
        joist_count = math.ceil(self.L / 0.40) + 1
        joists_volume = joist_count * self.W * 0.04 * 0.15
        # + запас на балки перекрытия (площадь пола * 0.04)
        joists_volume += floor_area * 0.04
        
        # --- Обрешетка стен 25х150 (шаг 300 мм) ---
        lath_count = math.ceil(self.H / 0.30)
        lath_volume = lath_count * perimeter * 0.025 * 0.15
        # + обрешетка потолка
        lath_volume += floor_area * 0.025
        
        # --- Вентзазор брусок 50х40 (шаг 400 мм) ---
        vent_count = math.ceil(perimeter / 0.40)
        vent_volume = vent_count * self.H * 0.05 * 0.04
        
        # --- Стропила (если есть кровля, шаг 600 мм) ---
        rafters_volume = 0.0
        if self.roof_slope > 0:
            rafter_count = math.ceil(self.W / 0.60) + 1
            rafters_volume = rafter_count * self.roof_slope * 0.05 * 0.15
        
        # --- Сайдинг с запасом на подрезку ---
        siding_straight = wall_area * 1.10
        siding_gable = gable_area * 1.20
        total_siding = siding_straight + siding_gable - self.openings
        
        # --- Мембраны (ветрозащита/пароизоляция) с нахлестом 15% ---
        membrane_area = (net_wall_area + gable_area) * 1.15
        
        # --- Формирование отчета ---
        result = (
            f"📊 <b>ОТЧЕТ ПО КАРКАСНИКУ/ПРИСТРОЮ</b>\n\n"
            f"📐 <b>Геометрия объекта:</b>\n"
            f"• Периметр стен: {perimeter:.1f} м\n"
            f"• Площадь стен (черная): {wall_area:.1f} м²\n"
            f"• Площадь стен (чистая): {net_wall_area:.1f} м²\n"
            f"• Площадь пола/потолка: {floor_area:.1f} м²\n"
            f"• Площадь фронтонов: {gable_area:.1f} м²\n\n"
            f"🪵 <b>Пиломатериалы:</b>\n"
            f"• Стойки стен 50х100 (шаг 590 мм): {studs_volume:.3f} м³ ({stud_count} шт)\n"
            f"• Лаги пола 40х150 (шаг 400 мм): {joists_volume:.3f} м³\n"
            f"• Обрешетка стен 25х150 (шаг 300 мм): {lath_volume:.3f} м³\n"
            f"• Брусок вентзазора 50х40 (шаг 400 мм): {vent_volume:.3f} м³\n"
            f"• Стропила 50х150 (шаг 600 мм): {rafters_volume:.3f} м³\n\n"
            f"📦 <b>Материалы с запасом:</b>\n"
            f"• Сайдинг (+10% стены, +20% фронтоны): {total_siding:.1f} м²\n"
            f"• Пленки/мембраны (+15% нахлест): {membrane_area:.1f} м²"
        )
        return result

# ============================================================
# МОДУЛЬ 2: РАСЧЕТ МОЩЕНИЯ / ДОРОЖЕК
# ============================================================

class Paving:
    """
    Расчет мощения: дорожки, отмостки, парковки, площадки.
    
    Вход: площадь мощения, периметр (для бордюров),
          глубина выемки, толщина песка, толщина щебня,
          флаг криволинейности (True/False)
    
    Коэффициенты:
    - Уплотнение щебня/ПГС: 1.3
    - Уплотнение песка/ПЩС: 1.2
    - Запас геотекстиля: 10%
    - Подрезка плитки: прямая 5%, радиусная 12%
    - Бетон на фиксацию бордюров: 0.05 м³/пог.м
    """
    
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
        # --- Выемка грунта ---
        excavation_volume = self.S * self.depth
        
        # --- Подушка из щебня/ПГС (коэф. уплотнения 1.3) ---
        gravel_volume = self.S * self.gravel * 1.3
        
        # --- Подушка из песка/ПЩС (коэф. уплотнения 1.2) ---
        sand_volume = self.S * self.sand * 1.2
        
        # --- Геотекстиль (запас 10% на нахлесты и подвороты) ---
        geotextile_area = self.S * 1.10
        
        # --- Брусчатка/плитка ---
        waste_coef = 1.12 if self.is_curved else 1.05
        tile_area = self.S * waste_coef
        
        # --- Бетон на фиксацию бордюров (0.05 м³ на пог.м) ---
        border_concrete = self.P * 0.05
        
        # --- Формирование отчета ---
        result = (
            f"🧱 <b>ОТЧЕТ ПО МОЩЕНИЮ</b>\n\n"
            f"🕳 <b>Земляные работы:</b>\n"
            f"• Выемка грунта (корыто): {excavation_volume:.2f} м³\n"
            f"• Периметр бордюров: {self.P:.1f} пог.м\n\n"
            f"🧱 <b>Подушка основания:</b>\n"
            f"• Щебень/ПГС (с уплотнением ×1.3): {gravel_volume:.2f} м³\n"
            f"• Песок/ПЩС (с уплотнением ×1.2): {sand_volume:.2f} м³\n\n"
            f"📦 <b>Материалы для закупа:</b>\n"
            f"• Геотекстиль (+10% нахлест): {geotextile_area:.1f} м²\n"
            f"• Брусчатка/плитка (подрезка {12 if self.is_curved else 5}%): {tile_area:.1f} м²\n"
            f"• Бетон М200 на замки бордюров: {border_concrete:.2f} м³"
        )
        return result

# ============================================================
# МОДУЛЬ 3: РАСЧЕТ ЗАБОРА ИЗ ПРОФЛИСТА
# ============================================================

class Fence:
    """
    Расчет забора из профлиста С8.
    
    Вход: общая длина забора, высота,
          шаг столбов (2.5 м), количество лаг (2),
          длина ворот, длина калитки
    
    Конструктивные требования:
    - Заглубление столбов: 1.2 м
    - Диаметр лунки: 200 мм (радиус 0.1 м)
    - Прожилины: профиль 40х20
    - Полезная ширина профлиста С8: 1.15 м
    - Нахлест: 1 волна
    """
    
    def __init__(self, total_length, height, step=2.5,
                 logs_count=2, gate_length=4.0,
                 wicket_length=1.0):
        self.L = float(total_length)
        self.H = float(height)
        self.step = float(step)
        self.logs = int(logs_count)
        self.gate_L = float(gate_length)
        self.wicket_L = float(wicket_length)
    
    def calculate(self):
        # Чистая длина забора без ворот и калитки
        net_length = self.L - self.gate_L - self.wicket_L
        if net_length < 0:
            net_length = 0
        
        # --- Количество и объем столбов ---
        posts_count = math.ceil(net_length / self.step) + 1
        total_posts_length = posts_count * (self.H + 1.2)  # +1.2 на заглубление
        
        # --- Объем бетона под лунки ---
        # Объем одной лунки: π * r² * h = 3.14 * 0.1² * 1.2
        hole_volume = math.pi * (0.1 ** 2) * 1.2
        total_concrete = posts_count * hole_volume
        
        # --- Прожилины (лаги 40х20) ---
        total_logs_length = net_length * self.logs
        
        # --- Профлист С8 ---
        # Полезная ширина листа 1.15 м
        sheets_count = math.ceil(net_length / 1.15)
        # Общая площадь профлиста с запасом 5%
        sheet_area = sheets_count * self.H * 1.05
        
        # --- Формирование отчета ---
        result = (
            f"🚧 <b>ОТЧЕТ ПО ЗАБОРУ ИЗ ПРОФЛИСТА</b>\n\n"
            f"📏 <b>Параметры ограждения:</b>\n"
            f"• Общая длина: {self.L:.1f} м\n"
            f"• Высота: {self.H:.1f} м\n"
            f"• Ворота: {self.gate_L:.1f} м\n"
            f"• Калитка: {self.wicket_L:.1f} м\n"
            f"• Чистая длина забора: {net_length:.1f} м\n\n"
            f"🪵 <b>Каркас и фундамент:</b>\n"
            f"• Столбов: {posts_count} шт\n"
            f"• Профиль на столбы (60×60): {total_posts_length:.1f} пог.м\n"
            f"• Бетон под лунки (Ø200 мм, глубина 1.2 м): {total_concrete:.2f} м³\n"
            f"• Прожилины 40×20 (2 ряда): {total_logs_length:.1f} пог.м\n\n"
            f"📦 <b>Зашивка:</b>\n"
            f"• Профлист С8 (полезная ширина 1.15 м): {sheets_count} листов\n"
            f"• Общая площадь профлиста (+5% запас): {sheet_area:.1f} м²"
        )
        return result

# ============================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    """Стартовое сообщение с главным меню."""
    await message.answer(
        "👋 <b>Здравствуйте, прораб!</b>\n\n"
        "Я помогу рассчитать материалы и объемы работ для:\n"
        "• 🏠 Каркасных домов и пристроев\n"
        "• 🧱 Дорожек, отмосток и площадок\n"
        "• 🚧 Заборов из профлиста\n\n"
        "<i>Выберите нужный раздел в меню ниже:</i>",
        reply_markup=main_kb
    )

# ----------------------------------------------------------
# ОБРАБОТКА КАРКАСНИКА / ПРИСТРОЯ
# ----------------------------------------------------------

@dp.message(F.text == "🏠 Каркасник/Пристрой")
async def start_building(message: Message, state: FSMContext):
    """Запрос размеров для каркасника."""
    await message.answer(
        "🏠 <b>Расчет каркасника / пристроя</b>\n\n"
        "Введите размеры через запятую <b>в одной строке</b>:\n"
        "<code>Длина, Ширина, Высота стен, Длина ската, Пристройка (0/1)</code>\n\n"
        "📌 <b>Пример для дома:</b> 6, 8, 2.5, 4, 0\n"
        "📌 <b>Пример для пристроя:</b> 4, 3, 2.5, 2.5, 1\n\n"
        "<i>Где 0 — отдельное здание, 1 — пристрой к существующему</i>",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(OrderStates.waiting_for_building)

@dp.message(OrderStates.waiting_for_building)
async def process_building(message: Message, state: FSMContext):
    """Обработка размеров и расчет каркасника."""
    try:
        parts = [x.strip() for x in message.text.split(",")]
        
        if len(parts) < 5:
            await message.answer(
                "❌ <b>Ошибка!</b> Нужно 5 параметров.\n"
                "Пример: <code>6, 8, 2.5, 4, 0</code>",
                reply_markup=main_kb
            )
            await state.clear()
            return
        
        length, width, height, slope = parts[0], parts[1], parts[2], parts[3]
        is_annex = bool(int(parts[4]))
        
        calculator = Building(
            length=length,
            width=width,
            wall_height=height,
            roof_slope_len=slope,
            is_annex=is_annex
        )
        
        result = calculator.calculate()
        
        await message.answer(result, parse_mode="HTML")
        await message.answer(
            "✅ <b>Расчет завершен!</b> Выберите следующий раздел:",
            reply_markup=main_kb
        )
        await state.clear()
        
    except (ValueError, IndexError) as e:
        await message.answer(
            f"❌ <b>Ошибка ввода!</b>\n"
            f"Проверьте формат данных.\n"
            f"Пример: <code>6, 8, 2.5, 4, 0</code>\n\n"
            f"<i>Детали: {str(e)}</i>",
            reply_markup=main_kb
        )
        await state.clear()

# ----------------------------------------------------------
# ОБРАБОТКА МОЩЕНИЯ / ДОРОЖЕК
# ----------------------------------------------------------

@dp.message(F.text == "🧱 Дорожки и брусчатка")
async def start_paving(message: Message, state: FSMContext):
    """Запрос параметров для мощения."""
    await message.answer(
        "🧱 <b>Расчет мощения и дорожек</b>\n\n"
        "Введите параметры через запятую <b>в одной строке</b>:\n"
        "<code>Площадь, Периметр, Глубина, Песок, Щебень, Кривая (0/1)</code>\n\n"
        "📌 <b>Пример для прямой дорожки:</b> 30, 25, 0.3, 0.1, 0.15, 0\n"
        "📌 <b>Пример для радиусной:</b> 40, 30, 0.3, 0.1, 0.15, 1\n\n"
        "<i>Где 0 — прямая дорожка, 1 — криволинейная/радиусная</i>",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(OrderStates.waiting_for_paving)

@dp.message(OrderStates.waiting_for_paving)
async def process_paving(message: Message, state: FSMContext):
    """Обработка параметров и расчет мощения."""
    try:
        parts = [float(x.strip()) for x in message.text.split(",")]
        
        if len(parts) < 6:
            await message.answer(
                "❌ <b>Ошибка!</b> Нужно 6 параметров.\n"
                "Пример: <code>30, 25, 0.3, 0.1, 0.15, 0</code>",
                reply_markup=main_kb
            )
            await state.clear()
            return
        
        calculator = Paving(
            area=parts[0],
            perimeter=parts[1],
            depth=parts[2],
            sand_thick=parts[3],
            gravel_thick=parts[4],
            is_curved=bool(int(parts[5]))
        )
        
        result = calculator.calculate()
        
        await message.answer(result, parse_mode="HTML")
        await message.answer(
            "✅ <b>Расчет завершен!</b> Выберите следующий раздел:",
            reply_markup=main_kb
        )
        await state.clear()
        
    except (ValueError, IndexError) as e:
        await message.answer(
            f"❌ <b>Ошибка ввода!</b>\n"
            f"Проверьте формат данных.\n"
            f"Пример: <code>30, 25, 0.3, 0.1, 0.15, 0</code>\n\n"
            f"<i>Детали: {str(e)}</i>",
            reply_markup=main_kb
        )
        await state.clear()

# ----------------------------------------------------------
# ОБРАБОТКА ЗАБОРА
# ----------------------------------------------------------

@dp.message(F.text == "🚧 Забор из профлиста")
async def start_fence(message: Message, state: FSMContext):
    """Запрос параметров для забора."""
    await message.answer(
        "🚧 <b>Расчет забора из профлиста С8</b>\n\n"
        "Введите параметры через запятую <b>в одной строке</b>:\n"
        "<code>Длина, Высота, Длина ворот, Длина калитки</code>\n\n"
        "📌 <b>Пример:</b> 50, 1.8, 3, 1\n"
        "📌 <b>Пример без ворот:</b> 30, 2.0, 0, 1\n\n"
        "<i>Ворота и калитка вычитаются из общей длины забора</i>",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(OrderStates.waiting_for_fence)

@dp.message(OrderStates.waiting_for_fence)
async def process_fence(message: Message, state: FSMContext):
    """Обработка параметров и расчет забора."""
    try:
        parts = [float(x.strip()) for x in message.text.split(",")]
        
        if len(parts) < 4:
            await message.answer(
                "❌ <b>Ошибка!</b> Нужно 4 параметра.\n"
                "Пример: <code>50, 1.8, 3, 1</code>",
                reply_markup=main_kb
            )
            await state.clear()
            return
        
        calculator = Fence(
            total_length=parts[0],
            height=parts[1],
            gate_length=parts[2],
            wicket_length=parts[3]
        )
        
        result = calculator.calculate()
        
        await message.answer(result, parse_mode="HTML")
        await message.answer(
            "✅ <b>Расчет завершен!</b> Выберите следующий раздел:",
            reply_markup=main_kb
        )
        await state.clear()
        
    except (ValueError, IndexError) as e:
        await message.answer(
            f"❌ <b>Ошибка ввода!</b>\n"
            f"Проверьте формат данных.\n"
            f"Пример: <code>50, 1.8, 3, 1</code>\n\n"
            f"<i>Детали: {str(e)}</i>",
            reply_markup=main_kb
        )
        await state.clear()

# ============================================================
# ЗАПУСК БОТА
# ============================================================

async def main():
    """Главная функция запуска бота."""
    print("✅ Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

