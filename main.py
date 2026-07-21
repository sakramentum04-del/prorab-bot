import math, logging, asyncio, json, sqlite3, os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = "8960396864:AAG6hvz70PmVMk-ZrhoMH-21ZwiBBB-J-d0"
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ============================================================
# БАЗА ДАННЫХ SQLITE3
# ============================================================

DB_PATH = "/root/prorab-bot/prorab_experience.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS coefficients (
        key TEXT PRIMARY KEY, value REAL, description TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS objects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT, params TEXT, results TEXT,
        fakt TEXT, delta TEXT, created_at TEXT
    )""")
    
    defaults = [
        ("crush_compaction", 1.3, "Коэф уплотнения щебня"),
        ("sand_compaction", 1.2, "Коэф уплотнения песка"),
        ("geotextile_waste", 1.1, "Запас геотекстиля"),
        ("tile_waste_straight", 1.05, "Подрезка прямой плитки"),
        ("tile_waste_curved", 1.12, "Подрезка радиусной плитки"),
        ("siding_waste_wall", 1.10, "Запас сайдинга стены"),
        ("siding_waste_gable", 1.20, "Запас сайдинга фронтон"),
        ("membrane_overlap", 1.15, "Нахлест мембран"),
        ("border_concrete_rate", 0.05, "Бетон на замок бордюра м3/м"),
        ("post_depth", 1.2, "Заглубление столба м"),
        ("hole_radius", 0.1, "Радиус лунки м"),
        ("proflist_useful_width", 1.15, "Полезная ширина профлиста м"),
    ]
    for key, val, desc in defaults:
        c.execute("INSERT OR IGNORE INTO coefficients (key, value, description) VALUES (?, ?, ?)", (key, val, desc))
    conn.commit()
    conn.close()

def get_coef(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM coefficients WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 1.0

def update_coef(key, delta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM coefficients WHERE key = ?", (key,))
    row = c.fetchone()
    if row:
        new_val = max(0.5, row[0] + delta)
        c.execute("UPDATE coefficients SET value = ? WHERE key = ?", (new_val, key))
    conn.commit()
    conn.close()

def save_object(obj_type, params, results):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO objects (type, params, results, created_at) VALUES (?, ?, ?, ?)",
              (obj_type, json.dumps(params, ensure_ascii=False), json.dumps(results, ensure_ascii=False), datetime.now().isoformat()))
    conn.commit()
    obj_id = c.lastrowid
    conn.close()
    return obj_id

def get_last_objects(limit=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, type, params, created_at FROM objects ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_object_by_id(obj_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM objects WHERE id = ?", (obj_id,))
    row = c.fetchone()
    conn.close()
    return row

# Инициализация БД при старте
init_db()

# ============================================================
# МОДУЛЬ 1D РАСКРОЯ
# ============================================================

class CuttingOptimizer:
    """Линейный раскрой пиломатериалов (жадный алгоритм)."""
    
    COMMERCIAL_LENGTH = 6000  # мм
    
    @staticmethod
    def optimize(parts_mm, count_mm=6000):
        """
        parts_mm: список [(длина_мм, количество), ...]
        count_mm: коммерческая длина хлыста
        Возвращает: (количество_хлыстов, карта_распила, мусор, деловой_остаток)
        """
        # Разворачиваем в плоский список
        all_parts = []
        for length, qty in parts_mm:
            all_parts.extend([length] * qty)
        
        # Сортируем по убыванию (жадный алгоритм First-Fit Decreasing)
        all_parts.sort(reverse=True)
        
        bins = []  # список хлыстов: каждый хлыст = список остатков [свободно, ...]
        bin_details = []  # карта распила: [[(длина, количество), ...], ...]
        
        for part in all_parts:
            placed = False
            for i, free in enumerate(bins):
                if free >= part:
                    bins[i] -= part
                    bin_details[i].append(part)
                    placed = True
                    break
            if not placed:
                bins.append(count_mm - part)
                bin_details.append([part])
        
        waste_short = 0      # мусор < 300 мм
        waste_long = 0       # деловой остаток 300-1200 мм
        waste_very_long = 0  # > 1200 мм (считается в запас)
        
        for free in bins:
            if free < 300:
                waste_short += free
            elif free <= 1200:
                waste_long += free
            else:
                waste_very_long += free
        
        # Формируем карту распила
        cut_map = ""
        for i, details in enumerate(bin_details):
            parts_str = " + ".join([f"{p}мм" for p in details])
            remaining = bins[i]
            cut_map += f"Хлыст №{i+1}: {parts_str}. Остаток: {remaining}мм\n"
        
        total_parts_used = sum(len(d) for d in bin_details)
        
        result = {
            "total_sticks": len(bins),
            "cut_map": cut_map,
            "waste_short_mm": waste_short,
            "waste_long_mm": waste_long,
            "waste_very_long_mm": waste_very_long,
            "total_parts": total_parts_used
        }
        return result

# ============================================================
# МОДУЛЬ 1: КАРКАСНИК (Building)
# ============================================================

class Building:
    """
    Расчет каркасного строения/пристроя.
    """
    
    def __init__(self, length, width, wall_height, roof_slope_len,
                 is_annex=False, openings_area=10.0):
        self.L = float(length)
        self.W = float(width)
        self.H = float(wall_height)
        self.roof_slope = float(roof_slope_len)
        self.is_annex = is_annex
        self.openings = float(openings_area)
        
        # Коэффициенты из БД
        self.sw_wall = get_coef("siding_waste_wall")
        self.sw_gable = get_coef("siding_waste_gable")
        self.membrane = get_coef("membrane_overlap")
    
    def calculate(self):
        # Периметр
        if self.is_annex:
            perimeter = self.L + 2 * self.W
        else:
            perimeter = 2 * (self.L + self.W)
        
        wall_area = perimeter * self.H
        net_wall_area = max(0, wall_area - self.openings)
        floor_area = self.L * self.W
        
        # Фронтоны
        half_w = self.W / 2
        gable_area = 0
        if self.roof_slope > half_w:
            roof_height = math.sqrt(self.roof_slope**2 - half_w**2)
            gable_area = 2 * (0.5 * self.W * roof_height)
        
        # ========== ПИЛОМАТЕРИАЛЫ (1D раскрой) ==========
        
        # Стойки стен 50х100 (шаг 590 мм)
        stud_count = math.ceil(perimeter / 0.590) + 1
        # + угловые стойки (по 3 на угол)
        corner_count = 8 if not self.is_annex else 4
        stud_count += corner_count
        
        # Нижняя обвязка (1 доска по периметру)
        bottom_trim = math.ceil(perimeter * 1000 / 6000)
        # Верхняя обвязка (2 доски по периметру)
        top_trim = math.ceil(perimeter * 2 * 1000 / 6000)
        
        # Лаги пола 40х150 (шаг 400 мм)
        joist_count = math.ceil(self.L / 0.400) + 1
        
        # Балки перекрытия (шаг 400 мм по ширине)
        beam_count = math.ceil(self.W / 0.400) + 1
        
        # Обрешетка стен 25х150 (шаг 300 мм)
        wall_lath_count = math.ceil(self.H / 0.300)
        
        # Обрешетка потолка
        ceil_lath_count_x = math.ceil(self.L / 0.400)
        ceil_lath_count_y = math.ceil(self.W / 0.400)
        
        # Стропила 50х150 (шаг 600 мм)
        rafter_count = 0
        if self.roof_slope > 0:
            rafter_count = math.ceil(self.W / 0.600) + 1
        
        # Вентзазор 50х40 (шаг 400 мм)
        vent_count = math.ceil(self.H / 0.400)
        
        # Формируем данные для 1D раскроя
        stud_length_mm = int(self.H * 1000)
        joist_length_mm = int(self.W * 1000)
        beam_length_mm = int(self.L * 1000)
        lath_wall_length_mm = int(perimeter * 1000)
        lath_ceil_length_mm = int(self.L * 1000)
        rafter_length_mm = int(self.roof_slope * 1000) if self.roof_slope > 0 else 0
        vent_length_mm = int(perimeter * 1000)
        
        cutting_parts = []
        
        # Стойки 50х100
        cutting_parts.append((stud_length_mm, stud_count))
        # Обвязки передаются как отрезки
        cutting_parts.append((int(perimeter * 1000), 3))  # 1 нижняя + 2 верхних
        
        # Лаги пола 40х150
        cutting_parts.append((joist_length_mm, joist_count))
        # Балки перекрытия
        cutting_parts.append((beam_length_mm, beam_count))
        
        # Обрешетка стен 25х150
        cutting_parts.append((lath_wall_length_mm, wall_lath_count))
        # Обрешетка потолка
        cutting_parts.append((lath_ceil_length_mm, ceil_lath_count_x))
        
        # Стропила 50х150
        if rafter_count > 0:
            cutting_parts.append((rafter_length_mm, rafter_count))
        
        # Вентзазор 50х40
        cutting_parts.append((vent_length_mm, vent_count))
        
        # Оптимизация раскроя
        lumber_50x100_parts = [(stud_length_mm, stud_count)]
        lumber_50x100_parts.append((int(perimeter * 1000), 3))
        
        lumber_40x150_parts = [(joist_length_mm, joist_count), (beam_length_mm, beam_count)]
        
        lumber_25x150_parts = [(lath_wall_length_mm, wall_lath_count), (lath_ceil_length_mm, ceil_lath_count_x)]
        
        lumber_50x150_parts = []
        if rafter_count > 0:
            lumber_50x150_parts.append((rafter_length_mm, rafter_count))
        
        lumber_50x40_parts = [(vent_length_mm, vent_count)]
        
        cut_50x100 = CuttingOptimizer.optimize(lumber_50x100_parts)
        cut_40x150 = CuttingOptimizer.optimize(lumber_40x150_parts)
        cut_25x150 = CuttingOptimizer.optimize(lumber_25x150_parts)
        cut_50x150 = CuttingOptimizer.optimize(lumber_50x150_parts) if lumber_50x150_parts else {"total_sticks": 0, "cut_map": "Нет кровли\n", "waste_short_mm": 0, "waste_long_mm": 0, "waste_very_long_mm": 0}
        cut_50x40 = CuttingOptimizer.optimize(lumber_50x40_parts)
        
        # ========== 2D МАТЕРИАЛЫ ==========
        
        # Сайдинг (панели 3000х230 мм)
        siding_straight = wall_area * self.sw_wall
        siding_gable = gable_area * self.sw_gable
        total_siding_m2 = siding_straight + siding_gable - self.openings
        # Площадь одной панели: 3.0 * 0.23 = 0.69 м²
        panel_area = 3.0 * 0.23
        siding_panels = math.ceil(total_siding_m2 / panel_area)
        
        # Мембраны (рулоны по 70 м²)
        membrane_m2 = (net_wall_area + gable_area) * self.membrane
        membrane_rolls = math.ceil(membrane_m2 / 70)
        
        # ========== ФОРМИРУЕМ ОТВЕТ ==========
        
        tech = (
            f"📊 ТЕХНОЛОГИЧЕСКАЯ ВЕДОМОСТЬ\n"
            f"{'─'*40}\n"
            f"🏠 {('ПРИСТРОЙ' if self.is_annex else 'КАРКАСНИК')}\n"
            f"📐 Размеры: {self.L:.1f} x {self.W:.1f} x {self.H:.1f} м\n\n"
            f"Периметр стен: {perimeter:.1f} м\n"
            f"Площадь стен: {wall_area:.1f} м²\n"
            f"Площадь стен чистая: {net_wall_area:.1f} м²\n"
            f"Площадь пола: {floor_area:.1f} м²\n"
            f"Площадь фронтонов: {gable_area:.1f} м²\n"
            f"Площадь сайдинга: {total_siding_m2:.1f} м²\n"
            f"Площадь мембран: {membrane_m2:.1f} м²\n\n"
            f"Конструктив:\n"
            f"• Стоек 50×100: {stud_count} шт по {stud_length_mm} мм\n"
            f"• Лаг пола 40×150: {joist_count} шт по {joist_length_mm} мм\n"
            f"• Балок перекр. 40×150: {beam_count} шт по {beam_length_mm} мм\n"
            f"• Обреш. стен 25×150: {wall_lath_count} шт\n"
            f"• Стропил 50×150: {rafter_count} шт\n"
            f"• Вентзазор 50×40: {vent_count} шт"
        )
        
        spec = (
            f"📦 ТОРГОВО-ЗАКУПОЧНАЯ СПЕЦИФИКАЦИЯ\n"
            f"{'─'*40}\n\n"
            f"🪵 Доска 50×100×6000:\n"
            f"  Хлыстов: {cut_50x100['total_sticks']} шт\n"
            f"  Отход <300мм: {cut_50x100['waste_short_mm']} мм\n"
            f"  Остаток 300-1200мм: {cut_50x100['waste_long_mm']} мм\n"
            f"  Карта распила:\n{cut_50x100['cut_map']}\n"
            f"🪵 Доска 40×150×6000:\n"
            f"  Хлыстов: {cut_40x150['total_sticks']} шт\n"
            f"  Отход: {cut_40x150['waste_short_mm']} мм\n"
            f"  Остаток: {cut_40x150['waste_long_mm']} мм\n"
            f"  Карта распила:\n{cut_40x150['cut_map']}\n"
            f"🪵 Доска 25×150×6000:\n"
            f"  Хлыстов: {cut_25x150['total_sticks']} шт\n"
            f"  Карта распила:\n{cut_25x150['cut_map']}\n"
            f"🪵 Доска 50×150×6000 (стропила):\n"
            f"  Хлыстов: {cut_50x150['total_sticks']} шт\n"
            f"  Карта распила:\n{cut_50x150['cut_map']}\n"
            f"🪵 Брусок 50×40×6000 (вентзазор):\n"
            f"  Хлыстов: {cut_50x40['total_sticks']} шт\n\n"
            f"📦 Сайдинг (панели 3.0×0.23 м):\n"
            f"  {siding_panels} шт ({total_siding_m2:.1f} м²)\n\n"
            f"📦 Мембрана (рулоны 70 м²):\n"
            f"  {membrane_rolls} рул. ({membrane_m2:.1f} м²)"
        )
        
        # Данные для БД
        params = {
            "length": self.L, "width": self.W, "height": self.H,
            "roof_slope": self.roof_slope, "is_annex": self.is_annex,
            "openings": self.openings
        }
        results = {
            "tech": tech, "spec": spec,
            "materials": {
                "studs_50x100": cut_50x100['total_sticks'],
                "joists_40x150": cut_40x150['total_sticks'],
                "lath_25x150": cut_25x150['total_sticks'],
                "rafters_50x150": cut_50x150['total_sticks'],
                "vent_50x40": cut_50x40['total_sticks'],
                "siding_panels": siding_panels,
                "membrane_rolls": membrane_rolls,
            }
        }
        
        # Сохраняем в БД
        obj_id = save_object("building", params, results)
        
        return tech, spec, obj_id
    
    def generate_sketchup_meta(self):
        """Генерация JSON для SketchUp Ruby API."""
        if self.is_annex:
            perimeter = self.L + 2 * self.W
        else:
            perimeter = 2 * (self.L + self.W)
        
        stud_count = math.ceil(perimeter / 0.590) + 9
        
        meta = {
            "type": "building",
            "dimensions": {"length": self.L, "width": self.W, "height": self.H},
            "studs": {
                "count": stud_count,
                "section": "50x100",
                "spacing_m": 0.590,
                "positions": []  # Здесь будут координаты от Ruby
            },
            "joists": {
                "count": math.ceil(self.L / 0.400) + 1,
                "section": "40x150",
                "spacing_m": 0.400
            },
            "rafters": {
                "count": math.ceil(self.W / 0.600) + 1 if self.roof_slope > 0 else 0,
                "section": "50x150",
                "spacing_m": 0.600,
                "slope_length": self.roof_slope
            }
        }
        return json.dumps(meta, ensure_ascii=False, indent=2)
# ============================================================
# МОДУЛЬ 2: МОЩЕНИЕ (Paving)
# ============================================================

class Paving:
    """Расчет дорожек, отмосток, брусчатки."""
    
    def __init__(self, area, perimeter, depth=0.3, is_curved=False):
        self.S = float(area)
        self.P = float(perimeter)
        self.depth = float(depth)
        self.is_curved = is_curved
        
        # Коэффициенты из БД
        self.crush_comp = get_coef("crush_compaction")
        self.sand_comp = get_coef("sand_compaction")
        self.geo_waste = get_coef("geotextile_waste")
        self.tile_waste = get_coef("tile_waste_curved") if is_curved else get_coef("tile_waste_straight")
        self.border_rate = get_coef("border_concrete_rate")
    
    def calculate(self):
        # Выемка грунта
        excavation = self.S * self.depth
        
        # Щебень слой 150 мм (0.15 м)
        gravel_vol = self.S * 0.15 * self.crush_comp
        
        # Песок слой 100 мм (0.10 м)
        sand_vol = self.S * 0.10 * self.sand_comp
        
        # Геотекстиль
        geotextile = self.S * self.geo_waste
        
        # Плитка
        tile_area = self.S * self.tile_waste
        tile_pallets = math.ceil(tile_area / 10)  # 1 поддон = 10 м²
        
        # Бордюры
        border_pieces = math.ceil(self.P / 1.0)  # 1 м длина бордюра
        border_concrete = self.P * self.border_rate
        
        # Объём сыпучки для закупа
        gravel_buy = math.ceil(gravel_vol * 10) / 10  # с точностью до 0.1 м³
        sand_buy = math.ceil(sand_vol * 10) / 10
        
        tech = (
            f"📊 ТЕХНОЛОГИЧЕСКАЯ ВЕДОМОСТЬ\n"
            f"{'─'*40}\n"
            f"🧱 {'РАДИУСНОЕ' if self.is_curved else 'ПРЯМОЕ'} МОЩЕНИЕ\n"
            f"📐 Площадь: {self.S:.1f} м²\n"
            f"📐 Периметр: {self.P:.1f} м\n"
            f"📐 Глубина корыта: {self.depth:.2f} м\n\n"
            f"🕳 Выемка грунта: {excavation:.2f} м³\n"
            f"🧱 Слой щебня 150 мм: {gravel_vol:.2f} м³\n"
            f"🧱 Слой песка 100 мм: {sand_vol:.2f} м³\n"
            f"📦 Геотекстиль: {geotextile:.1f} м²\n"
            f"🧱 Плитка: {tile_area:.1f} м²\n"
            f"📏 Бордюр: {border_pieces} шт по 1.0 м\n"
            f"🧱 Бетон М200: {border_concrete:.2f} м³"
        )
        
        spec = (
            f"📦 ТОРГОВО-ЗАКУПОЧНАЯ СПЕЦИФИКАЦИЯ\n"
            f"{'─'*40}\n\n"
            f"🧱 Щебень фр. 20-40:\n"
            f"  {gravel_buy:.1f} м³ (с коэф. упл. {self.crush_comp})\n\n"
            f"🧱 Песок карьерный:\n"
            f"  {sand_buy:.1f} м³ (с коэф. упл. {self.sand_comp})\n\n"
            f"📦 Геотекстиль (рулоны 50 м²):\n"
            f"  {math.ceil(geotextile / 50)} рул.\n\n"
            f"🧱 Брусчатка/плитка:\n"
            f"  {tile_pallets} подд. по 10 м² ({tile_area:.1f} м²)\n"
            f"  Запас на подрезку: {self.tile_waste:.0%}\n\n"
            f"📏 Бордюр садовый 1000×200×50:\n"
            f"  {border_pieces} шт\n\n"
            f"🧱 Бетон М200:\n"
            f"  {border_concrete:.2f} м³ (на замки бордюров)"
        )
        
        params = {
            "area": self.S, "perimeter": self.P,
            "depth": self.depth, "is_curved": self.is_curved
        }
        results = {
            "tech": tech, "spec": spec,
            "materials": {
                "gravel": gravel_buy, "sand": sand_buy,
                "geotextile_rolls": math.ceil(geotextile / 50),
                "tile_pallets": tile_pallets,
                "border_pieces": border_pieces,
                "concrete": border_concrete
            }
        }
        
        obj_id = save_object("paving", params, results)
        return tech, spec, obj_id
    
    def generate_sketchup_meta(self):
        meta = {
            "type": "paving",
            "area_m2": self.S,
            "perimeter_m": self.P,
            "depth_m": self.depth,
            "is_curved": self.is_curved,
            "border_count": math.ceil(self.P / 1.0),
            "border_length_m": 1.0,
            "layers": [
                {"material": "Щебень", "thickness_m": 0.15},
                {"material": "Песок", "thickness_m": 0.10},
                {"material": "Плитка", "thickness_m": 0.06}
            ]
        }
        return json.dumps(meta, ensure_ascii=False, indent=2)

# ============================================================
# МОДУЛЬ 3: ЗАБОР (Fence)
# ============================================================

class Fence:
    """Расчет забора из профлиста С8."""
    
    def __init__(self, total_length, height, gate_length=4.0, wicket_length=1.0,
                 post_spacing=2.5, log_rows=2):
        self.L = float(total_length)
        self.H = float(height)
        self.gate_L = float(gate_length)
        self.wicket_L = float(wicket_length)
        self.post_step = float(post_spacing)
        self.logs = int(log_rows)
        
        # Коэффициенты из БД
        self.post_depth = get_coef("post_depth")
        self.hole_radius = get_coef("hole_radius")
        self.proflist_width = get_coef("proflist_useful_width")
    
    def calculate(self):
        net_length = max(0, self.L - self.gate_L - self.wicket_L)
        
        # Столбы из профтрубы 60×60×3
        post_count = math.ceil(net_length / self.post_step) + 1
        post_full_length = self.H + self.post_depth  # высота над землей + заглубление
        
        # Лунки и бетон
        hole_vol = math.pi * (self.hole_radius ** 2) * self.post_depth
        total_concrete = post_count * hole_vol
        
        # Прожилины 40×20×2 (1D раскрой)
        log_length_mm = int(net_length * 1000)
        
        # Зашивка профлистом С8
        sheets_count = math.ceil(net_length / self.proflist_width)
        sheet_area = sheets_count * self.H
        # Запас 5% на подрезку
        sheet_area_with_waste = sheet_area * 1.05
        
        # Оптимизация раскроя прожилин
        cutting_parts = [(log_length_mm, self.logs)]
        cut_logs = CuttingOptimizer.optimize(cutting_parts)
        
        # Оптимизация раскроя столбов
        post_parts = [(int(post_full_length * 1000), post_count)]
        cut_posts = CuttingOptimizer.optimize(post_parts)
        
        tech = (
            f"📊 ТЕХНОЛОГИЧЕСКАЯ ВЕДОМОСТЬ\n"
            f"{'─'*40}\n"
            f"🚧 ЗАБОР ИЗ ПРОФЛИСТА С8\n\n"
            f"📏 Общая длина: {self.L:.1f} м\n"
            f"📏 Высота: {self.H:.1f} м\n"
            f"📏 Ворота: {self.gate_L:.1f} м\n"
            f"📏 Калитка: {self.wicket_L:.1f} м\n"
            f"📏 Чистая длина: {net_length:.1f} м\n\n"
            f"🪵 Столбов 60×60×3: {post_count} шт\n"
            f"  Длина столба: {post_full_length:.2f} м (в т.ч. заглуб. {self.post_depth} м)\n"
            f"  Лунок Ø{int(self.hole_radius*2*1000)} мм: {post_count} шт\n"
            f"  Бетон под лунки: {total_concrete:.2f} м³\n\n"
            f"🪵 Прожилин 40×20×2: {self.logs} ряда\n"
            f"  Общий погонаж: {log_length_mm/1000:.1f} м\n\n"
            f"📦 Профлист С8 (полезная ширина {self.proflist_width:.2f} м):\n"
            f"  Листов: {sheets_count} шт × {self.H:.2f} м\n"
            f"  Общая площадь: {sheet_area_with_waste:.1f} м² (с запасом 5%)"
        )
        
        spec = (
            f"📦 ТОРГОВО-ЗАКУПОЧНАЯ СПЕЦИФИКАЦИЯ\n"
            f"{'─'*40}\n\n"
            f"🪵 Профтруба 60×60×3 мм (6 м):\n"
            f"  Хлыстов: {cut_posts['total_sticks']} шт\n"
            f"  Карта распила:\n{cut_posts['cut_map']}\n"
            f"🪵 Профтруба 40×20×2 мм (6 м):\n"
            f"  Хлыстов: {cut_logs['total_sticks']} шт\n"
            f"  Карта распила:\n{cut_logs['cut_map']}\n\n"
            f"🧱 Бетон М200:\n"
            f"  {total_concrete:.2f} м³ (на {post_count} лунок)\n\n"
            f"📦 Профлист С8 ({self.H:.2f} м):\n"
            f"  {sheets_count} листов\n\n"
            f"🔩 Саморезы кровельные (5.5×19):\n"
            f"  {sheets_count * 8} шт (по 8 на лист)\n\n"
            f"🔩 Саморезы по металлу (для лаг):\n"
            f"  {post_count * 4} шт"
        )
        
        params = {
            "length": self.L, "height": self.H,
            "gate": self.gate_L, "wicket": self.wicket_L,
            "post_spacing": self.post_step, "log_rows": self.logs
        }
        results = {
            "tech": tech, "spec": spec,
            "materials": {
                "posts_tubes": cut_posts['total_sticks'],
                "logs_tubes": cut_logs['total_sticks'],
                "concrete": total_concrete,
                "sheets": sheets_count,
                "screws": sheets_count * 8 + post_count * 4
            }
        }
        
        obj_id = save_object("fence", params, results)
        return tech, spec, obj_id
    
    def generate_sketchup_meta(self):
        net_length = max(0, self.L - self.gate_L - self.wicket_L)
        post_count = math.ceil(net_length / self.post_step) + 1
        
        post_positions = []
        for i in range(post_count):
            x = i * self.post_step
            post_positions.append({"x_m": x, "z_m": 0, "height_m": self.H + self.post_depth})
        
        meta = {
            "type": "fence",
            "total_length_m": self.L,
            "height_m": self.H,
            "post_count": post_count,
            "post_section": "60x60x3",
            "post_depth_m": self.post_depth,
            "post_positions": post_positions,
            "log_section": "40x20x2",
            "log_rows": self.logs,
            "sheeting": {
                "type": "Профлист С8",
                "useful_width_m": self.proflist_width,
                "sheets_count": math.ceil(net_length / self.proflist_width),
                "height_m": self.H
            },
            "gates": {
                "gate_width_m": self.gate_L,
                "wicket_width_m": self.wicket_L
            }
        }
        return json.dumps(meta, ensure_ascii=False, indent=2)

# ============================================================
# FSM СОСТОЯНИЯ
# ============================================================

class BSt(StatesGroup):
    l = State(); w = State(); h = State(); r = State(); a = State()

class PSt(StatesGroup):
    a = State(); p = State(); c = State(); d = State()

class FSt(StatesGroup):
    l = State(); h = State(); g = State(); wk = State()

class LearnSt(StatesGroup):
    waiting_id = State(); waiting_fakt_key = State(); waiting_fakt_val = State()

# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Каркасник"), KeyboardButton(text="🧱 Дорожки")],
            [KeyboardButton(text="🚧 Забор"), KeyboardButton(text="📂 История")],
            [KeyboardButton(text="🧠 Обучение")]
        ],
        resize_keyboard=True
    )

def yesno_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]],
        resize_keyboard=True
    )

def back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Отмена")]],
        resize_keyboard=True
    )

# ============================================================
# СТАРТ И ОБЩИЕ КОМАНДЫ
# ============================================================

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет, Прораб!\n\n"
        "Я помогу рассчитать материалы для стройки.\n"
        "Выбери раздел:",
        reply_markup=main_kb()
    )

@dp.message(F.text == "🔙 Отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_kb())

# ============================================================
# КАРКАСНИК - ОБРАБОТЧИКИ
# ============================================================

@dp.message(F.text == "🏠 Каркасник")
async def b_start(message: Message, state: FSMContext):
    await state.set_state(BSt.l)
    await message.answer(
        "🏠 КАРКАСНИК\nШаг 1/5\n\nВведите ДЛИНУ здания (м):\nПример: 6",
        reply_markup=back_kb()
    )

@dp.message(BSt.l)
async def b_len(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 50:
            raise ValueError
        await state.update_data(l=v)
        await state.set_state(BSt.w)
        await message.answer("Шаг 2/5\n\nВведите ШИРИНУ (м):\nПример: 8", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 1 до 50.\nПример: 6", reply_markup=back_kb())

@dp.message(BSt.w)
async def b_wid(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 50:
            raise ValueError
        await state.update_data(w=v)
        await state.set_state(BSt.h)
        await message.answer("Шаг 3/5\n\nВведите ВЫСОТУ СТЕН (м):\nПример: 2.5", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 1 до 10.\nПример: 2.5", reply_markup=back_kb())

@dp.message(BSt.h)
async def b_hei(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 10:
            raise ValueError
        await state.update_data(h=v)
        await state.set_state(BSt.r)
        await message.answer("Шаг 4/5\n\nВведите ДЛИНУ СКАТА кровли (м):\nЕсли крыши нет - введите 0\nПример: 3.5", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 0 до 20.\nПример: 3.5", reply_markup=back_kb())

@dp.message(BSt.r)
async def b_roof(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v < 0 or v > 20:
            raise ValueError
        await state.update_data(r=v)
        await state.set_state(BSt.a)
        await message.answer("Шаг 5/5\n\nЭто ПРИСТРОЙ к существующему зданию?", reply_markup=yesno_kb())
    except:
        await message.answer("❌ Введите число от 0 до 20.\nПример: 3.5", reply_markup=back_kb())

@dp.message(BSt.a)
async def b_annex(message: Message, state: FSMContext):
    if message.text == "✅ Да":
        ia = True
    elif message.text == "❌ Нет":
        ia = False
    else:
        await message.answer("Нажмите кнопку Да или Нет.", reply_markup=yesno_kb())
        return
    
    data = await state.get_data()
    
    await message.answer("⏳ Рассчитываю...")
    
    try:
        calc = Building(
            length=data["l"], width=data["w"],
            wall_height=data["h"], roof_slope_len=data["r"],
            is_annex=ia
        )
        tech, spec, obj_id = calc.calculate()
        
        await message.answer(tech)
        await message.answer(spec)
        await message.answer(
            f"✅ Расчет завершен! ID: #{obj_id}\n"
            f"Смета сохранена в историю.",
            reply_markup=main_kb()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка расчета: {str(e)}", reply_markup=main_kb())
    
    await state.clear()

# ============================================================
# МОЩЕНИЕ - ОБРАБОТЧИКИ
# ============================================================

@dp.message(F.text == "🧱 Дорожки")
async def p_start(message: Message, state: FSMContext):
    await state.set_state(PSt.a)
    await message.answer(
        "🧱 МОЩЕНИЕ\nШаг 1/4\n\nВведите ПЛОЩАДЬ мощения (м²):\nПример: 30",
        reply_markup=back_kb()
    )

@dp.message(PSt.a)
async def p_area(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 1000:
            raise ValueError
        await state.update_data(a=v)
        await state.set_state(PSt.p)
        await message.answer("Шаг 2/4\n\nВведите ПЕРИМЕТР по бордюрам (м):\nПример: 25", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 1 до 1000.\nПример: 30", reply_markup=back_kb())

@dp.message(PSt.p)
async def p_perim(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 500:
            raise ValueError
        await state.update_data(p=v)
        await state.set_state(PSt.c)
        await message.answer("Шаг 3/4\n\nДорожка КРИВОЛИНЕЙНАЯ (радиусная)?", reply_markup=yesno_kb())
    except:
        await message.answer("❌ Введите число от 1 до 500.\nПример: 25", reply_markup=back_kb())

@dp.message(PSt.c)
async def p_curve(message: Message, state: FSMContext):
    if message.text == "✅ Да":
        ic = True
    elif message.text == "❌ Нет":
        ic = False
    else:
        await message.answer("Нажмите кнопку.", reply_markup=yesno_kb())
        return
    await state.update_data(c=ic)
    await state.set_state(PSt.d)
    await message.answer(
        "Шаг 4/4\n\nВведите ГЛУБИНУ выемки грунта (м):\n"
        "По умолчанию 0.3 м. Если стандартная - введите 0",
        reply_markup=back_kb()
    )

@dp.message(PSt.d)
async def p_depth(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        v = v if v > 0 else 0.3
    except:
        v = 0.3
    
    data = await state.get_data()
    
    await message.answer("⏳ Рассчитываю...")
    
    try:
        calc = Paving(
            area=data["a"], perimeter=data["p"],
            depth=v, is_curved=data["c"]
        )
        tech, spec, obj_id = calc.calculate()
        
        await message.answer(tech)
        await message.answer(spec)
        await message.answer(
            f"✅ Расчет завершен! ID: #{obj_id}",
            reply_markup=main_kb()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=main_kb())
    
    await state.clear()

# ============================================================
# ЗАБОР - ОБРАБОТЧИКИ
# ============================================================

@dp.message(F.text == "🚧 Забор")
async def f_start(message: Message, state: FSMContext):
    await state.set_state(FSt.l)
    await message.answer(
        "🚧 ЗАБОР ИЗ ПРОФЛИСТА\nШаг 1/4\n\nВведите ОБЩУЮ ДЛИНУ забора (м):\nПример: 50",
        reply_markup=back_kb()
    )

@dp.message(FSt.l)
async def f_len(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 500:
            raise ValueError
        await state.update_data(l=v)
        await state.set_state(FSt.h)
        await message.answer("Шаг 2/4\n\nВведите ВЫСОТУ забора (м):\nСтандарт: 1.8 или 2.0\nПример: 1.8", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 1 до 500.\nПример: 50", reply_markup=back_kb())

@dp.message(FSt.h)
async def f_hei(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or v > 5:
            raise ValueError
        await state.update_data(h=v)
        await state.set_state(FSt.g)
        await message.answer("Шаг 3/4\n\nВведите ШИРИНУ ВОРОТ (м):\nЕсли ворот нет - 0\nПример: 3", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 0.5 до 5.\nПример: 1.8", reply_markup=back_kb())

@dp.message(FSt.g)
async def f_gate(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v < 0 or v > 20:
            raise ValueError
        await state.update_data(g=v)
        await state.set_state(FSt.wk)
        await message.answer("Шаг 4/4\n\nВведите ШИРИНУ КАЛИТКИ (м):\nЕсли калитки нет - 0\nПример: 1", reply_markup=back_kb())
    except:
        await message.answer("❌ Введите число от 0 до 20.\nПример: 3", reply_markup=back_kb())

@dp.message(FSt.wk)
async def f_wicket(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v < 0 or v > 5:
            raise ValueError
        await state.update_data(wk=v)
    except:
        await state.update_data(wk=0)
    
    data = await state.get_data()
    
    await message.answer("⏳ Рассчитываю...")
    
    try:
        calc = Fence(
            total_length=data["l"], height=data["h"],
            gate_length=data["g"], wicket_length=data.get("wk", 0)
        )
        tech, spec, obj_id = calc.calculate()
        
        await message.answer(tech)
        await message.answer(spec)
        await message.answer(
            f"✅ Расчет завершен! ID: #{obj_id}",
            reply_markup=main_kb()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=main_kb())
    
    await state.clear()

# ============================================================
# ИСТОРИЯ ОБЪЕКТОВ
# ============================================================

@dp.message(F.text == "📂 История")
async def show_history(message: Message):
    objects = get_last_objects(5)
    if not objects:
        await message.answer("📂 История пуста. Еще нет рассчитанных объектов.", reply_markup=main_kb())
        return
    
    text = "📂 ПОСЛЕДНИЕ 5 ОБЪЕКТОВ\n" + "─"*30 + "\n"
    for obj in objects:
        obj_id, obj_type, params_json, created = obj
        params = json.loads(params_json)
        
        type_names = {"building": "🏠 Каркасник", "paving": "🧱 Мощение", "fence": "🚧 Забор"}
        type_name = type_names.get(obj_type, obj_type)
        
        text += f"\n🆔 #{obj_id} | {type_name}\n"
        text += f"📅 {created[:19]}\n"
        if obj_type == "building":
            text += f"   {params.get('length',0)}×{params.get('width',0)}×{params.get('height',0)} м\n"
        elif obj_type == "paving":
            text += f"   {params.get('area',0)} м²\n"
        elif obj_type == "fence":
            text += f"   {params.get('length',0)} м × {params.get('height',0)} м\n"
    
    text += "\n🔍 Чтобы посмотреть детали - используйте /view ID"
    
    await message.answer(text, reply_markup=main_kb())

# ============================================================
# ОБУЧЕНИЕ ИИ (Корректировка коэффициентов)
# ============================================================

@dp.message(F.text == "🧠 Обучение")
async def learn_start(message: Message, state: FSMContext):
    objects = get_last_objects(10)
    if not objects:
        await message.answer("Нет объектов для обучения. Сначала сделайте расчет.", reply_markup=main_kb())
        return
    
    text = "🧠 ОБУЧЕНИЕ ИИ\n" + "─"*30 + "\n\n"
    text += "Выберите объект для корректировки.\n"
    text += "Напишите ID объекта (например: /learn 1)\n\n"
    text += "Последние объекты:\n"
    
    for obj in objects:
        obj_id, obj_type, params_json, created = obj
        params = json.loads(params_json)
        type_names = {"building": "🏠", "paving": "🧱", "fence": "🚧"}
        tn = type_names.get(obj_type, "❓")
        
        if obj_type == "building":
            desc = f"{params.get('length',0)}×{params.get('width',0)}м"
        elif obj_type == "paving":
            desc = f"{params.get('area',0)} м²"
        elif obj_type == "fence":
            desc = f"{params.get('length',0)}м × {params.get('height',0)}м"
        else:
            desc = ""
        
        text += f"  {tn} #{obj_id} | {desc} | {created[:10]}\n"
    
    await message.answer(text, reply_markup=back_kb())
    await state.set_state(LearnSt.waiting_id)

@dp.message(LearnSt.waiting_id)
async def learn_get_id(message: Message, state: FSMContext):
    try:
        obj_id = int(message.text.strip().replace("/learn ", ""))
    except:
        try:
            obj_id = int(message.text.strip())
        except:
            await message.answer("❌ Введите число - ID объекта.", reply_markup=back_kb())
            return
    
    obj = get_object_by_id(obj_id)
    if not obj:
        await message.answer(f"❌ Объект #{obj_id} не найден.", reply_markup=main_kb())
        await state.clear()
        return
    
    await state.update_data(learn_obj_id=obj_id)
    
    results = json.loads(obj[3])
    materials = results.get("materials", {})
    
    text = f"🆔 Объект #{obj_id}\n"
    text += f"📋 Тип: {obj[1]}\n\n"
    text += "Выберите материал для корректировки (напишите ключ):\n\n"
    
    key_names = {
        "studs_50x100": "Стойки 50×100 (шт)",
        "joists_40x150": "Лаги 40×150 (шт)",
        "lath_25x150": "Обрешетка 25×150 (шт)",
        "rafters_50x150": "Стропила 50×150 (шт)",
        "vent_50x40": "Вентзазор 50×40 (шт)",
        "siding_panels": "Сайдинг (панели)",
        "membrane_rolls": "Мембрана (рулоны)",
        "gravel": "Щебень (м³)",
        "sand": "Песок (м³)",
        "geotextile_rolls": "Геотекстиль (рулоны)",
        "tile_pallets": "Плитка (поддоны)",
        "border_pieces": "Бордюр (шт)",
        "concrete": "Бетон (м³)",
        "posts_tubes": "Столбы (трубы шт)",
        "logs_tubes": "Лаги (трубы шт)",
        "sheets": "Профлист (листы)",
        "screws": "Саморезы (шт)"
    }
    
    for key, val in materials.items():
        name = key_names.get(key, key)
        text += f"  • {name}: {val}\n"
    
    await message.answer(text, reply_markup=back_kb())
    await state.set_state(LearnSt.waiting_fakt_key)

@dp.message(LearnSt.waiting_fakt_key)
async def learn_get_key(message: Message, state: FSMContext):
    key = message.text.strip()
    
    # Маппинг ключей
    key_map = {
        "стойки": "studs_50x100", "лаги пола": "joists_40x150",
        "обрешетка": "lath_25x150", "стропила": "rafters_50x150",
        "вентзазор": "vent_50x40", "сайдинг": "siding_panels",
        "мембрана": "membrane_rolls", "щебень": "gravel",
        "песок": "sand", "геотекстиль": "geotextile_rolls",
        "плитка": "tile_pallets", "бордюр": "border_pieces",
        "бетон": "concrete", "столбы": "posts_tubes",
        "лаги": "logs_tubes", "профлист": "sheets",
        "саморезы": "screws"
    }
    
    db_key = key_map.get(key.lower(), key)
    await state.update_data(learn_key=db_key)
    await state.set_state(LearnSt.waiting_fakt_val)
    await message.answer(
        f"Введите ФАКТИЧЕСКИЙ расход для \"{key}\":\n"
        f"(сколько реально ушло материала)",
        reply_markup=back_kb()
    )

@dp.message(LearnSt.waiting_fakt_val)
async def learn_get_val(message: Message, state: FSMContext):
    try:
        fakt_val = float(message.text.replace(",", "."))
    except:
        await message.answer("❌ Введите число. Пример: 5.5", reply_markup=back_kb())
        return
    
    data = await state.get_data()
    obj_id = data.get("learn_obj_id")
    key = data.get("learn_key")
    
    obj = get_object_by_id(obj_id)
    if not obj:
        await message.answer("❌ Объект не найден.", reply_markup=main_kb())
        await state.clear()
        return
    
    results = json.loads(obj[3])
    materials = results.get("materials", {})
    
    if key not in materials:
        await message.answer(f"❌ Ключ '{key}' не найден в объекте.", reply_markup=main_kb())
        await state.clear()
        return
    
    calc_val = materials[key]
    if calc_val == 0:
        await message.answer("❌ Расчетное значение = 0. Корректировка невозможна.", reply_markup=main_kb())
        await state.clear()
        return
    
    # Вычисляем дельту погрешности (отклонение от расчетного)
    delta = (fakt_val - calc_val) / calc_val
    
    # Сохраняем фактический расход в объект
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE objects SET fakt = ?, delta = ? WHERE id = ?",
              (json.dumps({key: fakt_val}, ensure_ascii=False),
               json.dumps({key: delta}, ensure_ascii=False), obj_id))
    conn.commit()
    conn.close()
    
    # Корректируем коэффициент в БД
    # delta > 0 — материала ушло больше -> увеличиваем коэффициент
    # delta < 0 — материала ушло меньше -> уменьшаем коэффициент
    correction = delta * 0.5  # половинный шаг, чтобы не было резких скачков
    
    # Маппинг ключей материалов на коэффициенты
    coef_map = {
        "studs_50x100": None,  # нет прямого коэффициента
        "joists_40x150": None,
        "lath_25x150": None,
        "rafters_50x150": None,
        "vent_50x40": None,
        "siding_panels": "siding_waste_wall",
        "membrane_rolls": "membrane_overlap",
        "gravel": "crush_compaction",
        "sand": "sand_compaction",
        "geotextile_rolls": "geotextile_waste",
        "tile_pallets": "tile_waste_curved" if obj[1] == "paving" else None,
        "border_pieces": None,
        "concrete": "border_concrete_rate",
        "posts_tubes": None,
        "logs_tubes": None,
        "sheets": None,
        "screws": None
    }
    
    coef_key = coef_map.get(key)
    if coef_key:
        old_val = get_coef(coef_key)
        update_coef(coef_key, correction)
        new_val = get_coef(coef_key)
        
        await message.answer(
            f"🧠 ИИ ОБУЧЕН!\n\n"
            f"🆔 Объект #{obj_id}\n"
            f"📌 Материал: {key}\n"
            f"🧮 Расчет: {calc_val}\n"
            f"📐 Факт: {fakt_val}\n"
            f"📊 Погрешность: {delta*100:+.1f}%\n\n"
            f"⚙️ Скорректирован коэффициент:\n"
            f"  {coef_key}: {old_val:.3f} → {new_val:.3f}\n\n"
            f"✅ Система стала точнее!",
            reply_markup=main_kb()
        )
    else:
        await message.answer(
            f"🧠 Данные сохранены!\n\n"
            f"🆔 Объект #{obj_id}\n"
            f"📌 Материал: {key}\n"
            f"🧮 Расчет: {calc_val}\n"
            f"📐 Факт: {fakt_val}\n"
            f"📊 Погрешность: {delta*100:+.1f}%\n\n"
            f"ℹ️ Для этого материала нет прямого коэффициента,\n"
            f"но данные сохранены для будущих аналитик.",
            reply_markup=main_kb()
        )
    
    await state.clear()

# ============================================================
# КОМАНДА /view - ДЕТАЛИ ОБЪЕКТА
# ============================================================

@dp.message(F.text.startswith("/view"))
async def view_object(message: Message):
    try:
        parts = message.text.split()
        obj_id = int(parts[1])
    except:
        await message.answer("❌ Используйте: /view ID\nПример: /view 1", reply_markup=main_kb())
        return
    
    obj = get_object_by_id(obj_id)
    if not obj:
        await message.answer(f"❌ Объект #{obj_id} не найден.", reply_markup=main_kb())
        return
    
    obj_id, obj_type, params_json, results_json, fakt_json, delta_json, created = obj
    params = json.loads(params_json)
    results = json.loads(results_json)
    fakt = json.loads(fakt_json) if fakt_json else {}
    delta = json.loads(delta_json) if delta_json else {}
    
    type_names = {"building": "🏠 Каркасник", "paving": "🧱 Мощение", "fence": "🚧 Забор"}
    type_name = type_names.get(obj_type, obj_type)
    
    text = f"📋 ДЕТАЛИ ОБЪЕКТА #{obj_id}\n"
    text += f"{'─'*40}\n"
    text += f"📌 Тип: {type_name}\n"
    text += f"📅 Дата: {created[:19]}\n\n"
    
    text += "📐 Параметры:\n"
    for k, v in params.items():
        if isinstance(v, float):
            text += f"  {k}: {v:.2f}\n"
        else:
            text += f"  {k}: {v}\n"
    
    text += f"\n📦 Материалы:\n"
    materials = results.get("materials", {})
    for k, v in materials.items():
        fakt_v = fakt.get(k)
        if fakt_v:
            delta_v = delta.get(k, 0) * 100
            text += f"  {k}: {v} (факт: {fakt_v}, δ: {delta_v:+.1f}%)\n"
        else:
            text += f"  {k}: {v}\n"
    
    await message.answer(text, reply_markup=main_kb())

# ============================================================
# КОМАНДА /learn - ЗАПУСК ОБУЧЕНИЯ ПО ID
# ============================================================

@dp.message(F.text.startswith("/learn"))
async def learn_by_id(message: Message, state: FSMContext):
    try:
        parts = message.text.split()
        obj_id = int(parts[1])
    except:
        await message.answer("❌ Используйте: /learn ID\nПример: /learn 1", reply_markup=main_kb())
        return
    
    obj = get_object_by_id(obj_id)
    if not obj:
        await message.answer(f"❌ Объект #{obj_id} не найден.", reply_markup=main_kb())
        return
    
    await state.update_data(learn_obj_id=obj_id)
    
    results = json.loads(obj[3])
    materials = results.get("materials", {})
    
    text = f"🧠 ОБУЧЕНИЕ ПО ОБЪЕКТУ #{obj_id}\n"
    text += f"{'─'*40}\n\n"
    text += "Введите КЛЮЧ материала для корректировки:\n\n"
    
    key_names = {
        "studs_50x100": "Стойки 50×100", "joists_40x150": "Лаги 40×150",
        "lath_25x150": "Обрешетка 25×150", "rafters_50x150": "Стропила 50×150",
        "vent_50x40": "Вентзазор 50×40", "siding_panels": "Сайдинг (панели)",
        "membrane_rolls": "Мембрана (рулоны)", "gravel": "Щебень (м³)",
        "sand": "Песок (м³)", "geotextile_rolls": "Геотекстиль (рулоны)",
        "tile_pallets": "Плитка (поддоны)", "border_pieces": "Бордюр (шт)",
        "concrete": "Бетон (м³)", "posts_tubes": "Столбы (трубы шт)",
        "logs_tubes": "Лаги (трубы шт)", "sheets": "Профлист (листы)",
        "screws": "Саморезы (шт)"
    }
    
    for key, val in materials.items():
        name = key_names.get(key, key)
        text += f"  • {name} — {val}\n"
    
    text += "\nНапишите ключ (например: щебень, бетон, сайдинг)"
    
    await message.answer(text, reply_markup=back_kb())
    await state.set_state(LearnSt.waiting_fakt_key)

# ============================================================
# ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД
# ============================================================

@dp.message()
async def unknown_command(message: Message):
    """Обработка всего, что не подходит под другие хендлеры."""
    text = message.text.lower()
    
    if text in ["да", "нет", "✅ да", "❌ нет"]:
        # Если бот не ожидает ответа, но пользователь нажал кнопку
        await message.answer(
            "Сначала выберите раздел из меню:",
            reply_markup=main_kb()
        )
    elif text in ["каркасник", "дорожки", "забор", "история", "обучение"]:
        await message.answer("Используйте кнопки в меню ниже 👇", reply_markup=main_kb())
    else:
        await message.answer(
            "❓ Неизвестная команда.\n"
            "Используйте /start для главного меню.",
            reply_markup=main_kb()
        )

# ============================================================
# ТОЧКА ВХОДА
# ============================================================

async def main():
    print("✅ Prorab Bot v2.0 запущен!")
    print(f"📂 База данных: {DB_PATH}")
    print(f"🤖 Бот: @prorab_bot")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
