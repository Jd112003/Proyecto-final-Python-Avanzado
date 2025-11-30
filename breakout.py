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
  - Restart round after Game Over / Win: R
  - Quit: ESC or window close

Features:
  - Smooth paddle movement with acceleration and friction
  - Angle-based ball reflection depending on impact point on paddle
  - Solid brick grid with simple level layout
  - Score + Lives HUD
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

WHITE = (240, 240, 240)
BLACK = (10, 10, 20)
GREY = (70, 80, 95)
CYAN = (80, 235, 255)
GREEN = (100, 240, 140)
MAGENTA = (230, 120, 255)
YELLOW = (255, 230, 120)
ORANGE = (255, 170, 80)
RED = (255, 95, 95)

# ----------------------------
# Utility: render to logical surface then scale to window
# ----------------------------
class Screen:
    def __init__(self):
        self.window = pg.display.set_mode((LOGICAL_W, LOGICAL_H), pg.RESIZABLE)
        pg.display.set_caption("Break Bricks - Python/Pygame")
        self.surface = pg.Surface((LOGICAL_W, LOGICAL_H))

    def begin(self):
        self.surface.fill(BLACK)

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

# ----------------------------
# Simple sound synth (no files needed)
# ----------------------------
class SFX:
    def __init__(self):
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

def build_level() -> list[Brick]:
    bricks: list[Brick] = []
    palette = [MAGENTA, ORANGE, YELLOW, GREEN, CYAN, WHITE, RED]
    total_w = BRICK_COLS * BRICK_W + (BRICK_COLS - 1) * BRICK_GAP
    left = (LOGICAL_W - total_w) // 2
    for row in range(BRICK_ROWS):
        for col in range(BRICK_COLS):
            x = left + col * (BRICK_W + BRICK_GAP)
            y = TOP_MARGIN + row * (BRICK_H + BRICK_GAP)
            rect = pg.Rect(x, y, BRICK_W, BRICK_H)
            bricks.append(Brick(rect, palette[row % len(palette)], True))
    return bricks

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
def send_score_to_server(score):
    """Envía el puntaje al backend usando JavaScript fetch si estamos en web"""
    if sys.platform == "emscripten":
        from platform import window
        import json
        
        # Preparamos los datos
        data = json.dumps({"username": "Player1", "score": score})
        
        # Usamos fetch de JS nativo
        headers = window.Object.new()
        headers.set("Content-Type", "application/json")
        
        options = window.Object.new()
        options.set("method", "POST")
        options.set("headers", headers)
        options.set("body", data)
        
        window.fetch("/api/scores", options)
        print(f"Score {score} sent to server.")
    else:
        print(f"Simulando envío de score: {score} (No estamos en web)")

# ----------------------------
# Game state
# ----------------------------
class Game:
    def __init__(self):
        self.screen = Screen()
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont("consolas", 24)
        self.bigfont = pg.font.SysFont("consolas", 52, bold=True)
        self.sfx: SFX | None = None
        try:
            self.sfx = SFX()
        except Exception:
            self.sfx = None  # allow running without sound device
        self.reset(hard=True)

    def reset(self, hard=False):
        self.paddle = Paddle()
        self.ball = Ball(self.paddle.x, self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1, 0, 0, BALL_RADIUS, True)
        self.bricks = build_level()
        if hard:
            self.score = 0
            self.lives = LIVES_START
        self.paused = False
        self.round_over_text = None
        self.score_sent = False

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
        if self.lives < 0:
            self.round_over_text = "GAME OVER"
            # Detener la bola completamente y enviar score
            self.ball.vx = 0
            self.ball.vy = 0
            self.ball.stuck = True
            if not self.score_sent:
                send_score_to_server(self.score)
                self.score_sent = True
        else:
            # reset ball to paddle
            self.ball = Ball(self.paddle.x, self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1, 0, 0, BALL_RADIUS, True)

    def update(self, dt):
        # No actualizar nada si el juego terminó
        if self.round_over_text:
            return
            
        if self.paused:
            return

        keys = pg.key.get_pressed()
        left = keys[pg.K_LEFT] or keys[pg.K_a]
        right = keys[pg.K_RIGHT] or keys[pg.K_d]
        self.paddle.update(dt, left, right)

        if self.ball.stuck:
            # keep ball glued to paddle
            self.ball.x = self.paddle.x
            self.ball.y = self.paddle.y - PADDLE_H//2 - BALL_RADIUS - 1
        else:
            self.ball.update(dt)

        reflect_ball_off_paddle(self.ball, self.paddle, self.sfx)
        got = ball_brick_collision(self.ball, self.bricks, self.sfx)
        self.score += got * 10

        # check bottom
        if not self.ball.stuck and self.ball.y - self.ball.r > LOGICAL_H:
            self.lose_life()

        # win condition
        if all(not b.alive for b in self.bricks):
            self.round_over_text = "YOU WIN!"
            if self.sfx: self.sfx.win.play()

            if not self.score_sent:
                send_score_to_server(self.score)
                self.score_sent = True

    def draw_hud(self, surf: pg.Surface):
        txt = f"Score: {self.score:06d}   Lives: {max(0, self.lives)}"
        img = self.font.render(txt, True, WHITE)
        surf.blit(img, (16, 16))

    def draw(self):
        s = self.screen.surface
        # background grid glow
        for i in range(0, LOGICAL_W, 40):
            pg.draw.line(s, (15, 25, 40), (i, 0), (i, LOGICAL_H))
        for i in range(0, LOGICAL_H, 40):
            pg.draw.line(s, (15, 25, 40), (0, i), (LOGICAL_W, i))

        # entities
        for b in self.bricks:
            b.draw(s)
        self.paddle.draw(s)
        self.ball.draw(s)
        self.draw_hud(s)

        if self.paused:
            self._center_text("PAUSED", CYAN)
        if self.round_over_text:
            self._center_text(self.round_over_text, YELLOW)
            sub = self.font.render("Press R to restart", True, WHITE)
            s.blit(sub, (LOGICAL_W//2 - sub.get_width()//2, LOGICAL_H//2 + 40))

    def _center_text(self, text, color):
        img = self.bigfont.render(text, True, color)
        self.screen.surface.blit(img, (LOGICAL_W//2 - img.get_width()//2, LOGICAL_H//2 - img.get_height()//2))

    def handle_event(self, e: pg.event.Event):
        if e.type == pg.QUIT:
            pg.quit(); sys.exit(0)
        elif e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                pg.quit(); sys.exit(0)
            if e.key == pg.K_SPACE and not self.round_over_text:
                self.launch_ball()
            if e.key == pg.K_p:
                self.paused = not self.paused
            if e.key == pg.K_r and self.round_over_text:
                self.reset(hard=True)

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
        game.screen.begin()
        game.update(dt)
        game.draw()
        game.screen.end()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
