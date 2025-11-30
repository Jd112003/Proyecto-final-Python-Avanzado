"""
Break Bricks (Breakout) in Python using Pygame
------------------------------------------------
How to run:
  1) pip install pygame
  2) python breakout.py

Controls:
  - Move paddle: Left/Right arrows or A/D
  - Launch ball: Space (when stuck to paddle)
  - Pause/Resume: P
  - Back to Menu: M or ESC
  - Quit: ESC (in menu) or window close

Features:
  - 5 levels with different brick patterns
  - Level selection menu with unlock system
  - Smooth paddle movement with acceleration and friction
  - Angle-based ball reflection depending on impact point on paddle
  - Score + Lives + Level HUD with FPS counter
  - Basic sound effects (generated programmatically; no asset files needed)
  - Window-scale safe area (fixed logical resolution rendered to screen)

Tested with Pygame 2.5+
"""
from __future__ import annotations
import math
import random
import sys
import asyncio
import json
from dataclasses import dataclass

import pygame as pg

# ----------------------------
# Configuration
# ----------------------------
LOGICAL_W, LOGICAL_H = 800, 600
FPS = 120

PADDLE_W = 110
PADDLE_H = 16
PADDLE_Y = LOGICAL_H - 60
PADDLE_ACCEL = 2200.0
PADDLE_MAX_SPEED = 650.0
PADDLE_FRICTION = 0.000001  # scaled by dt

BALL_RADIUS = 8
BALL_SPEED = 370.0
BALL_SPEED_INC_ON_HIT = 4.0  # each brick bounce adds a tiny speed bump
BALL_MAX_SPEED = 820.0

BRICK_ROWS = 7
BRICK_COLS = 12
BRICK_W = 56
BRICK_H = 24
BRICK_GAP = 4
TOP_MARGIN = 80

LIVES_START = 3

# Colors
WHITE = (240, 240, 240)
BLACK = (10, 10, 20)
GREY = (70, 80, 95)
CYAN = (80, 235, 255)
GREEN = (100, 240, 140)
MAGENTA = (230, 120, 255)
YELLOW = (255, 230, 120)
ORANGE = (255, 170, 80)
RED = (255, 95, 95)

# Background Colors for Worlds
BG_WORLD_1 = (10, 10, 20)
BG_WORLD_2 = (30, 5, 5)
BG_WORLD_3 = (20, 5, 30)
BG_MENU = (15, 15, 25)

# ----------------------------
# Utility: render to logical surface then scale to window
# ----------------------------
class Screen:
    def __init__(self):
        self.window = pg.display.set_mode((LOGICAL_W, LOGICAL_H), pg.RESIZABLE)
        pg.display.set_caption("Break Bricks - Python/Pygame (Nativo)")
        self.surface = pg.Surface((LOGICAL_W, LOGICAL_H))

    def begin(self, bg_color=BLACK):
        self.surface.fill(bg_color)

    def end(self):
        win_w, win_h = self.window.get_size()
        scale = min(win_w / LOGICAL_W, win_h / LOGICAL_H)
        sw, sh = int(LOGICAL_W * scale), int(LOGICAL_H * scale)
        x = (win_w - sw) // 2
        y = (win_h - sh) // 2
        scaled = pg.transform.smoothscale(self.surface, (sw, sh))
        self.window.fill((0, 0, 0))
        self.window.blit(scaled, (x, y))
        pg.display.flip()
    
    def get_mouse_pos(self):
        """Convierte posición del mouse de ventana a coordenadas lógicas"""
        win_w, win_h = self.window.get_size()
        scale = min(win_w / LOGICAL_W, win_h / LOGICAL_H)
        sw, sh = int(LOGICAL_W * scale), int(LOGICAL_H * scale)
        x_offset = (win_w - sw) // 2
        y_offset = (win_h - sh) // 2
        
        mx, my = pg.mouse.get_pos()
        logical_x = (mx - x_offset) / scale
        logical_y = (my - y_offset) / scale
        return (int(logical_x), int(logical_y))

# ----------------------------
# Simple sound synth (no files needed)
# ----------------------------
class SFX:
    def __init__(self):
        if not pg.mixer.get_init():
            pg.mixer.init(frequency=44100, size=-16, channels=1)
        self.hit = self._tone(740, 0.04)
        self.brick = self._tone(1240, 0.05)
        self.lose = self._tone(140, 0.2)
        self.win = self._tone(520, 0.25)

    def _tone(self, freq, dur):
        rate = 44100
        n = int(rate * dur)
        buf = bytearray()
        for i in range(n):
            # Simple decayed sine wave
            t = i / rate
            amp = int(32000 * (1 - i / n) * math.sin(2 * math.pi * freq * t))
            buf += amp.to_bytes(2, byteorder="little", signed=True)
        return pg.mixer.Sound(buffer=buf)

# ----------------------------
# Entities
# ----------------------------
@dataclass
class Paddle:
    x: float = LOGICAL_W / 2
    y: float = PADDLE_Y
    w: float = PADDLE_W
    h: float = PADDLE_H
    vx: float = 0.0

    def rect(self) -> pg.Rect:
        return pg.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), int(self.w), int(self.h))

    def update(self, dt: float, left: bool, right: bool):
        ax = 0.0
        if left:
            ax -= PADDLE_ACCEL
        if right:
            ax += PADDLE_ACCEL
        self.vx += ax * dt
        # friction
        self.vx *= (1.0 - PADDLE_FRICTION * max(0.0, dt * FPS))
        # clamp speed
        self.vx = max(-PADDLE_MAX_SPEED, min(PADDLE_MAX_SPEED, self.vx))
        self.x += self.vx * dt
        # walls
        half = self.w / 2
        if self.x - half < 0:
            self.x = half
            self.vx = 0
        if self.x + half > LOGICAL_W:
            self.x = LOGICAL_W - half
            self.vx = 0

    def draw(self, surf: pg.Surface):
        pg.draw.rect(surf, GREY, self.rect(), border_radius=10)
        inner = self.rect().inflate(-int(self.w*0.3), -6)
        pg.draw.rect(surf, CYAN, inner, border_radius=8)

@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    r: int = BALL_RADIUS
    stuck: bool = True

    def update(self, dt: float):
        if self.stuck:
            return
        self.x += self.vx * dt
        self.y += self.vy * dt

        # walls
        if self.x - self.r < 0:
            self.x = self.r
            self.vx = abs(self.vx)
        if self.x + self.r > LOGICAL_W:
            self.x = LOGICAL_W - self.r
            self.vx = -abs(self.vx)
        if self.y - self.r < 0:
            self.y = self.r
            self.vy = abs(self.vy)

    def draw(self, surf: pg.Surface):
        pg.draw.circle(surf, WHITE, (int(self.x), int(self.y)), self.r)

@dataclass
class Brick:
    rect: pg.Rect
    color: tuple
    alive: bool = True

    def draw(self, surf: pg.Surface):
        if not self.alive:
            return
        pg.draw.rect(surf, self.color, self.rect, border_radius=6)
        pg.draw.rect(surf, (0,0,0), self.rect, width=1, border_radius=6)

# ----------------------------
# Level builder
# ----------------------------

def build_level(level: int) -> list[Brick]:
    bricks: list[Brick] = []
    palette = [MAGENTA, ORANGE, YELLOW, GREEN, CYAN, WHITE, RED]
    
    total_w = BRICK_COLS * BRICK_W + (BRICK_COLS - 1) * BRICK_GAP
    left = (LOGICAL_W - total_w) // 2
    
    # LEVEL 1: Standard Block
    if level == 1:
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                x = left + col * (BRICK_W + BRICK_GAP)
                y = TOP_MARGIN + row * (BRICK_H + BRICK_GAP)
                rect = pg.Rect(x, y, BRICK_W, BRICK_H)
                bricks.append(Brick(rect, palette[row % len(palette)], True))
                
    # LEVEL 2: Checkerboard
    elif level == 2:
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                if (row + col) % 2 == 0:
                    x = left + col * (BRICK_W + BRICK_GAP)
                    y = TOP_MARGIN + row * (BRICK_H + BRICK_GAP)
                    rect = pg.Rect(x, y, BRICK_W, BRICK_H)
                    bricks.append(Brick(rect, palette[(col) % len(palette)], True))

    # LEVEL 3: Pyramid
    elif level == 3:
        for row in range(BRICK_ROWS + 2):
            # Center the row
            cols_in_row = BRICK_COLS - (row * 2)
            if cols_in_row <= 0: break
            row_w = cols_in_row * BRICK_W + (cols_in_row - 1) * BRICK_GAP
            row_left = (LOGICAL_W - row_w) // 2
            for col in range(cols_in_row):
                x = row_left + col * (BRICK_W + BRICK_GAP)
                y = TOP_MARGIN + row * (BRICK_H + BRICK_GAP)
                rect = pg.Rect(x, y, BRICK_W, BRICK_H)
                bricks.append(Brick(rect, palette[row % len(palette)], True))
    
    # LEVEL 4: Columns / Towers (Sparse)
    elif level == 4:
        for col in range(0, BRICK_COLS, 2):
            for row in range(BRICK_ROWS + 2):
                x = left + col * (BRICK_W + BRICK_GAP)
                y = TOP_MARGIN + row * (BRICK_H + BRICK_GAP)
                rect = pg.Rect(x, y, BRICK_W, BRICK_H)
                bricks.append(Brick(rect, RED if row % 2 == 0 else WHITE, True))

    # LEVEL 5+: Random / Dense
    else:
        for row in range(BRICK_ROWS + 1):
            for col in range(BRICK_COLS):
                if random.random() > 0.2:
                    x = left + col * (BRICK_W + BRICK_GAP)
                    y = TOP_MARGIN + row * (BRICK_H + BRICK_GAP)
                    rect = pg.Rect(x, y, BRICK_W, BRICK_H)
                    bricks.append(Brick(rect, random.choice(palette), True))

    return bricks

def get_bg_color(level: int) -> tuple:
    if level <= 2: return BG_WORLD_1
    if level <= 4: return BG_WORLD_2
    return BG_WORLD_3

# ----------------------------
# Collision helpers
# ----------------------------

def reflect_ball_off_paddle(ball: Ball, paddle: Paddle, sfx: SFX | None):
    prect = paddle.rect()
    if ball.vy > 0 and prect.collidepoint(ball.x, ball.y + ball.r):
        # place ball just above the paddle
        ball.y = prect.top - ball.r
        # compute hit position (-1 left .. 1 right)
        rel = (ball.x - prect.centerx) / (paddle.w / 2)
        rel = max(-1.0, min(1.0, rel))
        angle = math.radians(150 * rel + 90)  # 15°..165° upward
        speed = min(BALL_MAX_SPEED, math.hypot(ball.vx, ball.vy) + 6)
        ball.vx = speed * math.cos(angle)
        ball.vy = -abs(speed * math.sin(angle))
        if sfx: sfx.hit.play()


def ball_brick_collision(ball: Ball, bricks: list[Brick], sfx: SFX | None) -> int:
    # sweep circle vs AABBs; simple resolution via last axis of min overlap
    hit_count = 0
    for b in bricks:
        if not b.alive:
            continue
        # expand brick by radius and treat ball center as point
        expanded = b.rect.inflate(ball.r*2, ball.r*2)
        if expanded.collidepoint(ball.x, ball.y):
            # compute overlaps
            dx_left = abs(ball.x - b.rect.left)
            dx_right = abs(b.rect.right - ball.x)
            dy_top = abs(ball.y - b.rect.top)
            dy_bottom = abs(b.rect.bottom - ball.y)
            minx = min(dx_left, dx_right)
            miny = min(dy_top, dy_bottom)
            if minx < miny:
                # horizontal impact
                if dx_left < dx_right:
                    ball.x = b.rect.left - ball.r
                    ball.vx = -abs(ball.vx)
                else:
                    ball.x = b.rect.right + ball.r
                    ball.vx = abs(ball.vx)
            else:
                # vertical impact
                if dy_top < dy_bottom:
                    ball.y = b.rect.top - ball.r
                    ball.vy = -abs(ball.vy)
                else:
                    ball.y = b.rect.bottom + ball.r
                    ball.vy = abs(ball.vy)
            b.alive = False
            # tiny speed up each brick
            speed = min(BALL_MAX_SPEED, math.hypot(ball.vx, ball.vy) + BALL_SPEED_INC_ON_HIT)
            ang = math.atan2(ball.vy, ball.vx)
            ball.vx = math.cos(ang) * speed
            ball.vy = math.sin(ang) * speed
            hit_count += 1
            if sfx: sfx.brick.play()
    return hit_count

# ----------------------------
# Network Helper
# ----------------------------
def send_score_to_server(username, score):
    """Envía el puntaje al backend usando JavaScript fetch si estamos en web"""
    if sys.platform == "emscripten":
        from platform import window
        import json
        
        try:
            window.console.log(f"Python: Preparing to send score for {username}: {score}")
            json_data = json.dumps({"username": username, "score": score})
            
            js_code = f"""
                fetch('/api/scores', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: '{json_data}'
                }})
                .then(response => response.json())
                .then(data => console.log('Success:', data))
                .catch((error) => console.error('Error:', error));
            """
            window.eval(js_code)
            
        except Exception as e:
            print(f"Error in send_score_to_server: {e}")
            try:
                window.console.error(f"Python Error: {str(e)}")
            except:
                pass

    else:
        print(f"Simulando envío de score: {score} para {username} (No estamos en web)")

# ----------------------------
# Game state
# ----------------------------

# Estados del juego
STATE_MENU = 0
STATE_PLAYING = 1
STATE_INPUT_NAME = 2
STATE_GAME_OVER = 3

class Game:
    def __init__(self):
        self.screen = Screen()
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont("consolas", 24)
        self.bigfont = pg.font.SysFont("consolas", 52, bold=True)
        self.input_font = pg.font.SysFont("consolas", 36)
        
        self.sfx: SFX | None = None
        try:
            self.sfx = SFX()
        except Exception:
            self.sfx = None 
            
        self.unlocked_level = 1
        self.init_menu()
        # Start at menu
        self.state = STATE_MENU
        self.bg_color = BG_MENU

    def init_menu(self):
        # Definir botones para niveles
        self.level_buttons = []
        start_x = 150
        start_y = 200
        padding = 20
        btn_w = 100
        btn_h = 100
        
        # 5 niveles
        for i in range(5):
            x = start_x + (i % 3) * (btn_w + padding)
            y = start_y + (i // 3) * (btn_h + padding)
            rect = pg.Rect(x, y, btn_w, btn_h)
            self.level_buttons.append(rect)

    def start_level(self, level_num):
        self.level = level_num
        self.lives = LIVES_START
        self.score = 0
        self.bricks = build_level(self.level)
        self.paddle = Paddle()
        self.ball = Ball(self.paddle.x, self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1, 0, 0, BALL_RADIUS, True)
        self.state = STATE_PLAYING
        self.bg_color = get_bg_color(self.level)
        self.paused = False
        self.player_name = ""
        self.final_message = ""

    def launch_ball(self):
        if not self.ball.stuck:
            return
        angle = math.radians(random.uniform(45, 135))
        self.ball.vx = BALL_SPEED * math.cos(angle)
        self.ball.vy = -abs(BALL_SPEED * math.sin(angle))
        self.ball.stuck = False

    def lose_life(self):
        self.lives -= 1
        if self.sfx: self.sfx.lose.play()
        if self.lives == 0:
            self.state = STATE_INPUT_NAME
            self.ball.vx = 0
            self.ball.vy = 0
            self.ball.stuck = True
            self.final_message = "GAME OVER"
        else:
            self.ball = Ball(self.paddle.x, self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1, 0, 0, BALL_RADIUS, True)

    def update(self, dt):
        if self.state == STATE_MENU:
            return

        if self.state != STATE_PLAYING:
            return
            
        if self.paused:
            return

        keys = pg.key.get_pressed()
        left = keys[pg.K_LEFT] or keys[pg.K_a]
        right = keys[pg.K_RIGHT] or keys[pg.K_d]
        self.paddle.update(dt, left, right)

        if self.ball.stuck:
            self.ball.x = self.paddle.x
            self.ball.y = self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1
        else:
            self.ball.update(dt)

        reflect_ball_off_paddle(self.ball, self.paddle, self.sfx)
        got = ball_brick_collision(self.ball, self.bricks, self.sfx)
        self.score += got * 10

        if not self.ball.stuck and self.ball.y - self.ball.r > LOGICAL_H:
            self.lose_life()

        if all(not b.alive for b in self.bricks):
            # Level Complete
            if self.sfx: self.sfx.win.play()
            
            # Unlock next level
            next_lvl = self.level + 1
            if next_lvl > self.unlocked_level:
                self.unlocked_level = next_lvl
            
            if next_lvl <= 5:
                # Auto-advance to next level
                self.level = next_lvl
                self.lives += 1
                self.bricks = build_level(self.level)
                self.bg_color = get_bg_color(self.level)
                # Reset ball
                self.ball = Ball(self.paddle.x, self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1, 0, 0, BALL_RADIUS, True)
                self.ball.stuck = True
            else:
                # Victory after Level 5
                self.state = STATE_INPUT_NAME
                self.final_message = "VICTORY!"
                self.ball.vx = 0
                self.ball.vy = 0
                self.ball.stuck = True

    def draw_menu(self, surf: pg.Surface):
        # Draw Title
        title = self.bigfont.render("SELECT LEVEL", True, CYAN)
        surf.blit(title, (LOGICAL_W//2 - title.get_width()//2, 80))
        
        mouse_pos = self.screen.get_mouse_pos()
        
        for i, rect in enumerate(self.level_buttons):
            lvl_num = i + 1
            is_locked = lvl_num > self.unlocked_level
            
            color = GREY if is_locked else GREEN
            
            # Hover effect
            if not is_locked and rect.collidepoint(mouse_pos):
                color = WHITE
                
            pg.draw.rect(surf, color, rect, border_radius=8)
            pg.draw.rect(surf, BLACK, rect, width=2, border_radius=8)
            
            if is_locked:
                txt = self.font.render("LOCKED", True, BLACK)
                surf.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery - txt.get_height()//2))
            else:
                txt = self.bigfont.render(str(lvl_num), True, BLACK)
                surf.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery - txt.get_height()//2))
        
        # Instructions
        instr = self.font.render("Click a level to start | ESC to quit", True, GREY)
        surf.blit(instr, (LOGICAL_W//2 - instr.get_width()//2, LOGICAL_H - 60))

    def draw_hud(self, surf: pg.Surface):
        # FPS counter en la esquina superior izquierda
        fps = self.clock.get_fps()
        fps_txt = self.font.render(f"FPS: {fps:.1f} (Nativo)", True, GREEN)
        surf.blit(fps_txt, (16, 16))
        
        # Score, Lives y Level debajo del FPS
        txt = f"Score: {self.score:06d}   Lives: {max(0, self.lives)}   Level: {self.level}"
        img = self.font.render(txt, True, WHITE)
        surf.blit(img, (16, 46))

    def draw_input_name(self, surf: pg.Surface):
        overlay = pg.Surface((LOGICAL_W, LOGICAL_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surf.blit(overlay, (0,0))
        
        title = self.bigfont.render(self.final_message, True, YELLOW)
        surf.blit(title, (LOGICAL_W//2 - title.get_width()//2, LOGICAL_H//3))
        
        instr = self.font.render("Enter your name:", True, WHITE)
        surf.blit(instr, (LOGICAL_W//2 - instr.get_width()//2, LOGICAL_H//2 - 20))
        
        input_box = pg.Rect(LOGICAL_W//2 - 100, LOGICAL_H//2 + 10, 200, 40)
        pg.draw.rect(surf, WHITE, input_box, 2)
        
        name_txt = self.input_font.render(self.player_name + "_", True, CYAN)
        surf.blit(name_txt, (input_box.x + 10, input_box.y + 8))
        
        help_txt = self.font.render("Press ENTER to submit", True, GREY)
        surf.blit(help_txt, (LOGICAL_W//2 - help_txt.get_width()//2, LOGICAL_H//2 + 60))

    def draw_game_over(self, surf: pg.Surface):
        overlay = pg.Surface((LOGICAL_W, LOGICAL_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surf.blit(overlay, (0,0))

        title = self.bigfont.render(self.final_message, True, YELLOW)
        surf.blit(title, (LOGICAL_W//2 - title.get_width()//2, LOGICAL_H//3))
        
        score_txt = self.bigfont.render(f"Final Score: {self.score}", True, WHITE)
        surf.blit(score_txt, (LOGICAL_W//2 - score_txt.get_width()//2, LOGICAL_H//2))

        sub = self.font.render("Press M for Menu", True, CYAN)
        surf.blit(sub, (LOGICAL_W//2 - sub.get_width()//2, LOGICAL_H//2 + 60))

    def draw(self):
        s = self.screen.surface
        
        if self.state == STATE_MENU:
            self.draw_menu(s)
        else:
            # Game rendering - background grid
            line_col = (min(255, self.bg_color[0]+20), min(255, self.bg_color[1]+20), min(255, self.bg_color[2]+20))
            for i in range(0, LOGICAL_W, 40):
                pg.draw.line(s, line_col, (i, 0), (i, LOGICAL_H))
            for i in range(0, LOGICAL_H, 40):
                pg.draw.line(s, line_col, (0, i), (LOGICAL_W, i))

            for b in self.bricks:
                b.draw(s)
            self.paddle.draw(s)
            self.ball.draw(s)
            self.draw_hud(s)

            if self.paused:
                self._center_text("PAUSED", CYAN)
                
            if self.state == STATE_INPUT_NAME:
                self.draw_input_name(s)
            elif self.state == STATE_GAME_OVER:
                self.draw_game_over(s)

    def _center_text(self, text, color):
        img = self.bigfont.render(text, True, color)
        self.screen.surface.blit(img, (LOGICAL_W//2 - img.get_width()//2, LOGICAL_H//2 - img.get_height()//2))

    def handle_event(self, e: pg.event.Event):
        if e.type == pg.QUIT:
            pg.quit(); sys.exit(0)
            
        if self.state == STATE_MENU:
            if e.type == pg.MOUSEBUTTONDOWN:
                if e.button == 1:  # Left click
                    mouse_pos = self.screen.get_mouse_pos()
                    for i, rect in enumerate(self.level_buttons):
                        if rect.collidepoint(mouse_pos):
                            lvl = i + 1
                            if lvl <= self.unlocked_level:
                                self.start_level(lvl)
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    pg.quit(); sys.exit(0)

        elif self.state == STATE_PLAYING:
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE or e.key == pg.K_m:
                    self.state = STATE_MENU
                    self.bg_color = BG_MENU
                if e.key == pg.K_SPACE:
                    self.launch_ball()
                if e.key == pg.K_p:
                    self.paused = not self.paused
                # --- CHEAT CODE: F10 to leave 1 brick ---
                if e.key == pg.K_F10:
                    if self.bricks:
                        survivor = self.bricks[0]
                        survivor.rect.centerx = int(self.paddle.x)
                        survivor.rect.bottom = int(self.paddle.y - 100)
                        self.bricks = [survivor]
                        print("CHEAT ACTIVATED: Only 1 brick remains!")

        elif self.state == STATE_INPUT_NAME:
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_RETURN:
                    if not self.player_name:
                        self.player_name = "Anonymous"
                    send_score_to_server(self.player_name, self.score)
                    self.state = STATE_GAME_OVER
                elif e.key == pg.K_BACKSPACE:
                    self.player_name = self.player_name[:-1]
                else:
                    if len(self.player_name) < 12 and e.unicode.isprintable():
                        self.player_name += e.unicode
        
        elif self.state == STATE_GAME_OVER:
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_m:
                    self.state = STATE_MENU
                    self.bg_color = BG_MENU
                if e.key == pg.K_ESCAPE:
                    pg.quit(); sys.exit(0)

# ----------------------------
# Main loop
# ----------------------------

async def main():
    pg.init()
    game = Game()
    while True:
        dt = game.clock.tick(FPS) / 1000.0
        for e in pg.event.get():
            game.handle_event(e)
        game.screen.begin(game.bg_color)
        game.update(dt)
        game.draw()
        game.screen.end()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
