import time
import curses
import asyncio
import random
import itertools
import os

import curses_tools as ct
from curses_tools import draw_frame
from physics import update_speed
from obstacles import Obstacle, show_obstacles
from explosion import explode

DEBUG_MODE = 0

uid_garbage_name = 'garbage'
uid_shot_name = 'shot'
uid_spaceship_name = 'spaceship'

life_points = 1

TIC_TIMEOUT = 0.1
STAR_VIEW = '+*.:'
BORDER_WIDTH = 1

COROUTINES = []
OBSTACLES = []
OBSTACLES_IN_LAST_COLLISIONS = []

STAR_NUM = 150

TIC_SECOND = round(TIC_TIMEOUT * 10)
OFFSET_TICS = random.randint(0, TIC_SECOND * 3)

YEAR = 1957

PHRASES = {
    # Только на английском, Repl.it ломается на кириллице
    1957: "First Sputnik",
    1961: "Gagarin flew!",
    1969: "Armstrong got on the moon!",
    1971: "First orbital space station Salute-1",
    1981: "Flight of the Shuttle Columbia",
    1998: 'ISS start building',
    2011: 'Messenger launch to Mercury',
    2020: "Take the plasma gun! Shoot the garbage!",
}


async def show_phrase(canvas):
    prev_msg = None
    while True:
        if YEAR in PHRASES.keys():
            current_msg = f'Year - {YEAR}: {PHRASES[YEAR]}'
            if YEAR > 1957:
                draw_frame(canvas, 0, 0, prev_msg, negative=True)
            draw_frame(canvas, 0, 0, current_msg)
            prev_msg = current_msg
        else:
            current_msg = f'Year - {YEAR}'
            if YEAR > 1957:
                draw_frame(canvas, 0, 0, prev_msg, negative=True)
            draw_frame(canvas, 0, 0, current_msg)
            prev_msg = current_msg
        await sleep(1)


def get_garbage_delay_tics(year):
    if year < 1961:
        return 30
    elif year < 1969:
        return 20
    elif year < 1981:
        return 14
    elif year < 1995:
        return 10
    elif year < 2010:
        return 8
    elif year < 2020:
        return 6
    else:
        return 2


async def change_year():
    global YEAR
    while True:
        await sleep(15)
        YEAR += 1


async def show_game_over(canvas, row, column):
    rocket_frames = load_frames(path=os.path.join('frames', 'rocket'))
    draw_frame(canvas, row, column, rocket_frames[0], negative=True)
    draw_frame(canvas, row, column, rocket_frames[1], negative=True)

    max_rows, max_columns = canvas.getmaxyx()
    center_row, center_column = round(max_rows / 2), round(max_columns / 2)

    game_over_frame = load_frames(path=os.path.join('frames', 'game_over'))[0]
    game_over_row, game_over_column = ct.get_frame_size(game_over_frame)

    while True:
        ct.draw_frame(canvas=canvas, start_row=center_row-int(game_over_row/2),
                      start_column=center_column-int(game_over_column/2), text=game_over_frame)
        await sleep(1)


def create_frame_obstacles(row, column, frame, uid=None):
    frame_row_size, frame_column_size = ct.get_frame_size(frame)
    frame_obstacle = Obstacle(row=row, column=column,
                              rows_size=frame_row_size, columns_size=frame_column_size,
                              uid=uid)
    OBSTACLES.append(frame_obstacle)
    return frame_obstacle


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
    global life_points
    rows_number, columns_number = canvas.getmaxyx()

    column = max(column, 0)
    column = min(column, columns_number - 1)

    row = 0

    garbage_obstacle = create_frame_obstacles(row, column, garbage_frame, uid=uid_garbage_name)

    while row < rows_number:

        draw_frame(canvas, row, column, garbage_frame)
        await sleep(1)
        draw_frame(canvas, row, column, garbage_frame, negative=True)

        row += speed
        garbage_obstacle.row += speed

        for obstacle in OBSTACLES:
            if obstacle.uid == uid_spaceship_name and \
                    obstacle.has_collision(obj_corner_row=garbage_obstacle.row, obj_corner_column=garbage_obstacle.column,
                                           obj_size_rows=garbage_obstacle.rows_size,
                                           obj_size_columns=garbage_obstacle.columns_size):
                life_points -= 1
                OBSTACLES.remove(garbage_obstacle)
                return None

        if garbage_obstacle in OBSTACLES_IN_LAST_COLLISIONS:
            OBSTACLES.remove(garbage_obstacle)
            OBSTACLES_IN_LAST_COLLISIONS.remove(garbage_obstacle)
            await explode(canvas, row, column)
            return None

    if garbage_obstacle in OBSTACLES:
        OBSTACLES.remove(garbage_obstacle)
        return None


async def run_spaceship(canvas, row, column, frames):
    # start speed
    row_speed = column_speed = 0

    uid_name = 'spaceship'
    spaceship_obstacle = create_frame_obstacles(row, column, frames[0], uid=uid_name)

    while True:
        await animate_spaceship(canvas, row, column, frames, row_speed, column_speed, spaceship_obstacle)


async def animate_spaceship(canvas, row, column, frames, row_speed, column_speed, spaceship_obstacle):
    row_speed, column_speed = row_speed, column_speed
    for frame in itertools.cycle(frames):
        # getmaxyx() - возвращает ширину и высоту окна, которые всегда на единицу больше чем координаты крайних ячеек
        max_rows, max_columns = canvas.getmaxyx()

        rows_direction, columns_direction, space_pressed = ct.read_controls(canvas=canvas)

        row_speed, column_speed = update_speed(row_speed=row_speed, column_speed=column_speed,
                                               rows_direction=rows_direction, columns_direction=columns_direction)
        row += row_speed
        column += column_speed

        ct.draw_frame(canvas=canvas, start_row=row, start_column=column, text=frame)
        await sleep(1)
        # стираем предыдущий кадр, прежде чем рисовать новый
        ct.draw_frame(canvas=canvas, start_row=row, start_column=column, text=frame, negative=True)

        if space_pressed and YEAR > 2020:
            COROUTINES.append(fire(canvas, row - 1, column + 2))

        frame_rows, frame_columns = ct.get_frame_size(text=frame)
        # frame_rows и BORDER_WIDTH - учитываем размер модели и рамку на нижней рамке
        row = min(max_rows - frame_rows - BORDER_WIDTH, row)
        # frame_columns и BORDER_WIDTH - учитываем размер модели и рамку на правой рамке
        column = min(max_columns - frame_columns - BORDER_WIDTH, column)
        row = max(row, BORDER_WIDTH)  # BORDER_WIDTH отвечает за контроль от перехода выше верхней рамки
        column = max(column, BORDER_WIDTH)  # BORDER_WIDTH отвечает за контроль от перехода левее левой рамки

        spaceship_obstacle.row = row
        spaceship_obstacle.column = column

        if life_points <= 0:
            await explode(canvas, spaceship_obstacle.row, spaceship_obstacle.column)
            OBSTACLES.remove(spaceship_obstacle)
            await show_game_over(canvas=canvas, row=row, column=column)
            return None


async def fire(canvas, start_row, start_column, rows_speed=-0.3, columns_speed=0):
    """Display animation of gun shot, direction and speed can be specified."""
    row, column = start_row, start_column

    for symb in '*O ':
        await sleep(1)
        canvas.addstr(round(row), round(column), symb)

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'

    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1

    curses.beep()

    shot_obstacles = create_frame_obstacles(row, column, symbol, uid=uid_shot_name)

    while 0 < row < max_row and 0 < column < max_column:
        canvas.addstr(round(row), round(column), symbol)
        await sleep(1)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed
        shot_obstacles.row += rows_speed
        shot_obstacles.column += columns_speed

        for obstacle in OBSTACLES:
            if obstacle.uid == uid_garbage_name and \
                    obstacle.has_collision(obj_corner_row=shot_obstacles.row, obj_corner_column=shot_obstacles.column,
                                           obj_size_rows=shot_obstacles.rows_size,
                                           obj_size_columns=shot_obstacles.columns_size):
                OBSTACLES_IN_LAST_COLLISIONS.append(obstacle)
                OBSTACLES.remove(shot_obstacles)
                return None
    if shot_obstacles in OBSTACLES:
        OBSTACLES.remove(shot_obstacles)
        return None


async def blink(canvas, row, column, symbol='*', offset_tics=1):
    time_blink = [2, 0.3, 0.5, 0.3]
    time_blink = [round(i/TIC_TIMEOUT) for i in time_blink]
    await sleep(offset_tics)
    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await sleep(time_blink[0])

        canvas.addstr(row, column, symbol)
        await sleep(time_blink[1])

        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await sleep(time_blink[2])

        canvas.addstr(row, column, symbol)
        await sleep(time_blink[3])


def create_stars_params(canvas, star_num):
    # getmaxyx() - возвращает ширину и высоту окна, которые всегда на единицу больше чем координаты крайних ячеек
    max_rows, max_columns = canvas.getmaxyx()
    stars = [random.choice(STAR_VIEW) for _ in range(star_num)]
    row = [random.randint(BORDER_WIDTH, max_rows - BORDER_WIDTH*2) for _ in range(star_num)]
    column = [random.randint(BORDER_WIDTH, max_columns - BORDER_WIDTH*2) for _ in range(star_num)]
    return stars, row, column, max_rows, max_columns


async def fill_orbit_with_garbage(canvas, garbage_frames):
    max_columns = canvas.getmaxyx()[1]
    while True:
        column = random.randint(0, max_columns)
        random_frame = random.choice(garbage_frames)
        frame_rows, frame_columns = ct.get_frame_size(text=random_frame)

        # frame_columns и BORDER_WIDTH - учитываем размер модели и рамку на правой рамке
        column = min(max_columns - frame_columns - BORDER_WIDTH, column)
        column = max(column, BORDER_WIDTH)  # BORDER_WIDTH отвечает за контроль от перехода левее левой рамки

        random_pos = random.randint(0, column)

        random_delay = get_garbage_delay_tics(year=YEAR)
        await sleep(random_delay)

        COROUTINES.append(fly_garbage(canvas=canvas, column=random_pos, garbage_frame=random_frame))


def load_frames(path):
    files = os.listdir(path)
    frames = []
    if files:
        for filename in files:
            temp_path = os.path.join(path, filename)
            with open(temp_path, 'r') as temp_file:
                frames.append(temp_file.read())
    else:
        frames = None
    return frames.copy()


async def sleep(tics=1):
    for _ in range(tics):
        await asyncio.sleep(0)


def draw(canvas):
    canvas.border()
    canvas.nodelay(True)

    rocket_frames = load_frames(path=os.path.join('frames', 'rocket'))
    garbage_frames = load_frames(path=os.path.join('frames', 'garbage'))

    if DEBUG_MODE:
        COROUTINES.append(show_obstacles(canvas, OBSTACLES))

    coroutines_garbage = fill_orbit_with_garbage(canvas=canvas, garbage_frames=garbage_frames)

    stars, rows, columns, max_rows, max_columns = create_stars_params(canvas=canvas, star_num=STAR_NUM)
    center_row, center_column = round(max_rows / 2), round(max_columns / 2)

    coroutines_blink_stars = [blink(canvas=canvas, row=rows[i], column=columns[i],
                                    symbol=stars[i], offset_tics=OFFSET_TICS) for i in range(STAR_NUM)]

    coroutine_ship = run_spaceship(canvas=canvas, row=center_row, column=center_column,
                                   frames=[rocket_frames[0], rocket_frames[0],
                                           rocket_frames[1], rocket_frames[1]])

    canvas_for_phrase = canvas.derwin(max_rows - 2, 10)
    coroutine_year_phrase = show_phrase(canvas=canvas_for_phrase)

    temp_coroutines = [*coroutines_blink_stars, coroutine_ship, coroutines_garbage,
                       change_year(), coroutine_year_phrase]
    COROUTINES.extend(temp_coroutines)

    while COROUTINES:
        for coroutine in COROUTINES.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                COROUTINES.remove(coroutine)
        canvas.border()
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.initscr()
    curses.curs_set(False)
    curses.wrapper(draw)


