
"""
SchemBoard — GUI Layer (Pygame)
- Canvas rendering, toolbar, dragging, port snapping, and wire drawing
- Reads visual/config options from config.txt (JSON format)

Public API:
    run(config_path: str = "config.txt") -> None
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import pygame


def _load_config(path: str) -> Dict:
    defaults = {
        "WIDTH": 1280,
        "HEIGHT": 720,
        "FPS": 90,
        "GRID": 16,
        "SNAP_RADIUS": 14,
        "PORT_RADIUS": 6,
        "SIGNAL_FAMILIES": {
            "red": {"on": [230, 70, 70], "off": [110, 35, 35]},
            "green": {"on": [70, 210, 120], "off": [30, 80, 55]},
            "blue": {"on": [100, 160, 250], "off": [40, 65, 95]},
            "purple": {"on": [170, 100, 220], "off": [70, 45, 95]},
            "amber": {"on": [255, 200, 80], "off": [120, 90, 40]},
        },
        "DEFAULT_FAMILY": "red",
        "COLORS": {
            "BLACK": [15, 17, 20],
            "PANEL_BG": [30, 34, 40],
            "PANEL_BORDER": [60, 68, 80],
            "WHITE": [230, 235, 240],
            "MUTED": [150, 156, 165],
            "SELECT": [255, 204, 102],
        },
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        # shallow merge (sufficient here)
        for k, v in user.items():
            if isinstance(v, dict) and k in defaults:
                defaults[k].update(v)
            else:
                defaults[k] = v
    except FileNotFoundError:
        pass
    return defaults


def _snap(v: int, g: int) -> int:
    return g * round(v / g)


def _draw_text(surface, text, pos, size=16, color=(255, 255, 255), center=False):
    font = pygame.font.SysFont("SF Mono, Menlo, Consolas, monospace", size)
    s = font.render(text, True, color)
    r = s.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    surface.blit(s, r)


@dataclass
class Port:
    owner: "Block"
    name: str
    direction: str  # "in" | "out"
    offset: Tuple[int, int]
    family: str
    state: bool = False

    def world(self) -> Tuple[int, int]:
        bx, by = self.owner.pos
        ox, oy = self.offset
        return (bx + ox, by + oy)

    def color(self, fam_palette: Dict[str, Dict[str, Tuple[int, int, int]]]):
        pal = fam_palette.get(self.family, fam_palette[self.owner.world_ref.DEFAULT_FAMILY])
        return pal["on"] if self.state else pal["off"]

    def hit(self, mx, my, port_radius: int) -> bool:
        x, y = self.world()
        return (mx - x) ** 2 + (my - y) ** 2 <= (port_radius + 3) ** 2


@dataclass
class Wire:
    src: Port
    dst: Port

    def color(self, fam_palette, default_family):
        pal = fam_palette.get(self.src.family, fam_palette[default_family])
        return pal["on"] if self.src.state else pal["off"]

    def draw(self, surface, fam_palette, default_family, port_radius: int):
        sx, sy = self.src.world()
        dx, dy = self.dst.world()
        midx = (sx + dx) // 2
        points = [(sx, sy), (midx, sy), (midx, dy), (dx, dy)]
        col = self.color(fam_palette, default_family)
        pygame.draw.lines(surface, col, False, points, 4)
        pygame.draw.circle(surface, col, (sx, sy), max(2, port_radius // 2))
        pygame.draw.circle(surface, col, (dx, dy), max(2, port_radius // 2))


class Block:
    def __init__(self, world_ref: "World", pos: Tuple[int, int]):
        self.world_ref = world_ref
        self.pos = [_snap(pos[0], world_ref.GRID), _snap(pos[1], world_ref.GRID)]
        self.w, self.h = 96, 64
        self.title = self.__class__.__name__
        self.ports: List[Port] = []
        self.selected: bool = False
        self.family = world_ref.DEFAULT_FAMILY

    def rect(self) -> pygame.Rect:
        x, y = self.pos
        return pygame.Rect(x - self.w // 2, y - self.h // 2, self.w, self.h)

    def draw(self, surface):
        r = self.rect()
        pygame.draw.rect(surface, (52, 84, 110), r, border_radius=10)
        pygame.draw.rect(surface, (20, 25, 30), r, 2, border_radius=10)
        _draw_text(surface, self.title, (r.x + 8, r.y + 6), 14, self.world_ref.WHITE)
        if self.selected:
            pygame.draw.rect(surface, self.world_ref.SELECT, r.inflate(6, 6), 2, border_radius=12)
        # ports
        for p in self.ports:
            wx, wy = p.world()
            pygame.draw.circle(surface, (0, 0, 0), (wx, wy), self.world_ref.PORT_RADIUS + 2)
            pygame.draw.circle(surface, p.color(self.world_ref.SIGNAL_FAMILIES), (wx, wy), self.world_ref.PORT_RADIUS)

    def move_to(self, x, y):
        self.pos[0], self.pos[1] = _snap(x, self.world_ref.GRID), _snap(y, self.world_ref.GRID)

    def hit(self, mx, my) -> bool:
        return self.rect().collidepoint(mx, my)

    def hit_port(self, mx, my) -> Optional[Port]:
        for p in self.ports:
            if p.hit(mx, my, self.world_ref.PORT_RADIUS):
                return p
        return None

    def add_port(self, name, direction, offset, family=None) -> Port:
        fam = family or self.family
        p = Port(self, name, direction, offset, fam)
        self.ports.append(p)
        return p


class InputBlock(Block):
    def __init__(self, world_ref: "World", pos):
        super().__init__(world_ref, pos)
        self.title = "INPUT"
        self.w, self.h = 84, 50
        self.out = self.add_port("out", "out", (self.w // 2, 0), family="red")
        self.state = False

    def toggle(self):
        self.state = not self.state
        self.out.state = self.state

    def draw(self, surface):
        r = self.rect()
        bg = (60, 30, 30) if self.state else (35, 20, 20)
        pygame.draw.rect(surface, bg, r, border_radius=10)
        pygame.draw.rect(surface, (20, 25, 30), r, 2, border_radius=10)
        _draw_text(surface, f"INPUT: {'ON' if self.state else 'OFF'}", (r.x + 8, r.y + 6), 14, self.world_ref.WHITE)
        if self.selected:
            pygame.draw.rect(surface, self.world_ref.SELECT, r.inflate(6, 6), 2, border_radius=12)
        for p in self.ports:
            wx, wy = p.world()
            pygame.draw.circle(surface, (0, 0, 0), (wx, wy), self.world_ref.PORT_RADIUS + 2)
            pygame.draw.circle(surface, p.color(self.world_ref.SIGNAL_FAMILIES), (wx, wy), self.world_ref.PORT_RADIUS)

    def on_click(self):
        self.toggle()


class LampBlock(Block):
    def __init__(self, world_ref: "World", pos):
        super().__init__(world_ref, pos)
        self.title = "LAMP"
        self.w, self.h = 64, 64
        self.inp = self.add_port("in", "in", (-self.w // 2, 0), family="red")

    def draw(self, surface):
        r = self.rect()
        pygame.draw.rect(surface, (30, 30, 30), r, border_radius=12)
        pygame.draw.rect(surface, (20, 25, 30), r, 2, border_radius=12)
        cx, cy = r.center
        on = self.inp.state
        pal = self.world_ref.SIGNAL_FAMILIES[self.inp.family]
        col = pal["on" if on else "off"]
        pygame.draw.circle(surface, col, (cx, cy + 6), 16)
        _draw_text(surface, "LAMP", (r.x + 8, r.y + 6), 14, self.world_ref.WHITE)
        if self.selected:
            pygame.draw.rect(surface, self.world_ref.SELECT, r.inflate(6, 6), 2, border_radius=14)
        for p in self.ports:
            wx, wy = p.world()
            pygame.draw.circle(surface, (0, 0, 0), (wx, wy), self.world_ref.PORT_RADIUS + 2)
            pygame.draw.circle(surface, p.color(self.world_ref.SIGNAL_FAMILIES), (wx, wy), self.world_ref.PORT_RADIUS)


class OutputBlock(Block):
    """A generic OUTPUT sink (visual like a right-facing jack).
    - One input on the left; shows ON/OFF text and color block.
    """
    def __init__(self, world_ref: "World", pos):
        super().__init__(world_ref, pos)
        self.title = "OUTPUT"
        self.w, self.h = 84, 50
        self.inp = self.add_port("in", "in", (-self.w // 2, 0), family="amber")

    def draw(self, surface):
        r = self.rect()
        pal = self.world_ref.SIGNAL_FAMILIES[self.inp.family]
        col = pal["on" if self.inp.state else "off"]
        pygame.draw.rect(surface, (34, 34, 24), r, border_radius=10)
        pygame.draw.rect(surface, (20, 25, 30), r, 2, border_radius=10)
        _draw_text(surface, f"OUTPUT: {'ON' if self.inp.state else 'OFF'}", (r.x + 8, r.y + 6), 14, self.world_ref.WHITE)
        # indicator bar on right
        bar = pygame.Rect(r.right - 18, r.y + 10, 10, r.height - 20)
        pygame.draw.rect(surface, col, bar, border_radius=4)
        if self.selected:
            pygame.draw.rect(surface, self.world_ref.SELECT, r.inflate(6, 6), 2, border_radius=12)
        for p in self.ports:
            wx, wy = p.world()
            pygame.draw.circle(surface, (0, 0, 0), (wx, wy), self.world_ref.PORT_RADIUS + 2)
            pygame.draw.circle(surface, p.color(self.world_ref.SIGNAL_FAMILIES), (wx, wy), self.world_ref.PORT_RADIUS)


class AndBlock(Block):
    def __init__(self, world_ref: "World", pos, n_inputs=2):
        super().__init__(world_ref, pos)
        self.title = f"AND{n_inputs}"
        self.w, self.h = 100, 64
        gap = self.h // (n_inputs + 1)
        for i in range(n_inputs):
            oy = -self.h // 2 + gap * (i + 1)
            self.add_port(f"in{i}", "in", (-self.w // 2, oy), family="green")
        self.add_port("out", "out", (self.w // 2, 0), family="green")


class OrBlock(Block):
    def __init__(self, world_ref: "World", pos, n_inputs=2):
        super().__init__(world_ref, pos)
        self.title = f"OR{n_inputs}"
        self.w, self.h = 100, 64
        gap = self.h // (n_inputs + 1)
        for i in range(n_inputs):
            oy = -self.h // 2 + gap * (i + 1)
            self.add_port(f"in{i}", "in", (-self.w // 2, oy), family="blue")
        self.add_port("out", "out", (self.w // 2, 0), family="blue")


class NotBlock(Block):
    def __init__(self, world_ref: "World", pos):
        super().__init__(world_ref, pos)
        self.title = "NOT"
        self.w, self.h = 84, 50
        self.add_port("in", "in", (-self.w // 2, 0), family="purple")
        self.add_port("out", "out", (self.w // 2, 0), family="purple")



@dataclass
class Button:
    label: str
    rect: pygame.Rect
    payload: Dict

    def draw(self, surface, colors, hovered=False):
        pygame.draw.rect(surface, colors["PANEL_BG"], self.rect, border_radius=8)
        pygame.draw.rect(surface, colors["PANEL_BORDER"], self.rect, 1, border_radius=8)
        _draw_text(surface, self.label, (self.rect.centerx, self.rect.centery - 8), 16, colors["WHITE"], center=True)
        if hovered:
            pygame.draw.rect(surface, colors["SELECT"], self.rect, 2, border_radius=10)


class Toolbar:
    def __init__(self, world_ref: "World"):
        self.world_ref = world_ref
        self.rect = pygame.Rect(0, world_ref.HEIGHT - 84, world_ref.WIDTH, 84)
        self.buttons: List[Button] = []
        self.active_payload: Optional[Dict] = None
        self._layout()

    def _layout(self):
        labels = [
            ("Select", {"tool": "select"}),
            ("Input", {"tool": "place", "type": "input"}),
            ("Lamp", {"tool": "place", "type": "lamp"}),
            ("Output", {"tool": "place", "type": "output"}),
            ("AND", {"tool": "place", "type": "and", "n": 2}),
            ("OR", {"tool": "place", "type": "or", "n": 2}),
            ("NOT", {"tool": "place", "type": "not"}),
        ]
        x = 12
        for text, payload in labels:
            r = pygame.Rect(x, self.rect.y + 12, 120, 60)
            self.buttons.append(Button(text, r, payload))
            x += 130

    def draw(self, surface):
        colors = self.world_ref.COLORS
        pygame.draw.rect(surface, colors["PANEL_BG"], self.rect)
        pygame.draw.line(surface, colors["PANEL_BORDER"], (0, self.rect.y), (self.rect.right, self.rect.y), 2)
        mx, my = pygame.mouse.get_pos()
        for b in self.buttons:
            b.draw(surface, colors, b.rect.collidepoint(mx, my))
        if self.active_payload:
            label = self.active_payload.get("type", self.active_payload.get("tool", ""))
            _draw_text(surface, f"Active: {label}", (self.rect.right - 200, self.rect.y + 8), 14, self.world_ref.COLORS["MUTED"])

    def handle_click(self, pos):
        for b in self.buttons:
            if b.rect.collidepoint(*pos):
                self.active_payload = b.payload
                return b.payload
        return None



class World:
    def __init__(self, cfg: Dict):
        # Config
        self.WIDTH = cfg["WIDTH"]
        self.HEIGHT = cfg["HEIGHT"]
        self.FPS = cfg["FPS"]
        self.GRID = cfg["GRID"]
        self.SNAP_RADIUS = cfg["SNAP_RADIUS"]
        self.PORT_RADIUS = cfg["PORT_RADIUS"]
        self.SIGNAL_FAMILIES = {k: {s: tuple(v2) for s, v2 in v.items()} for k, v in cfg["SIGNAL_FAMILIES"].items()}
        self.DEFAULT_FAMILY = cfg["DEFAULT_FAMILY"]
        self.COLORS = {k: tuple(v) for k, v in cfg["COLORS"].items()}
        self.BLACK = self.COLORS["BLACK"]
        self.PANEL_BG = self.COLORS["PANEL_BG"]
        self.PANEL_BORDER = self.COLORS["PANEL_BORDER"]
        self.WHITE = self.COLORS["WHITE"]
        self.MUTED = self.COLORS["MUTED"]
        self.SELECT = self.COLORS["SELECT"]
        self.WIRE_WIDTH = int(cfg.get("WIRE_WIDTH", 4))

        # World state
        self.blocks: List[Block] = []
        self.wires: List[Wire] = []
        self.selected: Optional[Block] = None
        self.drag_offset = (0, 0)
        self.wiring_from: Optional[Port] = None
        self.toolbar = Toolbar(self)
        self.tool = "select"
        self.place_spec: Optional[Dict] = None

    # Block factory
    def create_block(self, kind: str, pos: Tuple[int, int], **kw) -> Block:
        if kind == "input":
            b = InputBlock(self, pos)
        elif kind == "lamp":
            b = LampBlock(self, pos)
        elif kind == "output":
            b = OutputBlock(self, pos)
        elif kind == "and":
            b = AndBlock(self, pos, kw.get("n", 2))
        elif kind == "or":
            b = OrBlock(self, pos, kw.get("n", 2))
        elif kind == "not":
            b = NotBlock(self, pos)
        else:
            raise ValueError("Unknown block type")
        self.blocks.append(b)
        return b

    def remove_block(self, b: Block):
        self.wires = [w for w in self.wires if (w.src.owner is not b and w.dst.owner is not b)]
        self.blocks.remove(b)
        if self.selected is b:
            self.selected = None

    # Interaction
    def on_mouse_down(self, pos, button):
        # 1) Toolbar interaction
        if self.toolbar.rect.collidepoint(*pos):
            payload = self.toolbar.handle_click(pos)
            if payload:
                self.tool = payload.get("tool", "select")
                self.place_spec = payload if self.tool == "place" else None
            return

        # 2) Place mode — only allow placing, no selecting/dragging
        if self.tool == "place" and self.place_spec:
            kind = self.place_spec["type"]
            n = self.place_spec.get("n", 2)
            self.create_block(kind, pos, n=n)
            # After placing, automatically return to select mode
            self.tool = "select"
            self.place_spec = None
            self.toolbar.active_payload = {"tool": "select"}
            return

        # 3) Selection/wiring
        clicked_block = self.find_block_at(*pos)
        if clicked_block:
            port = clicked_block.hit_port(*pos)
            if port:
                # Start wiring from any port (input or output)
                self.wiring_from = port
                # Do not change selection while wiring
                return
            # Select for dragging
            self.selected = clicked_block
            for b in self.blocks:
                b.selected = (b is clicked_block)
            rx, ry = clicked_block.rect().topleft
            self.drag_offset = (pos[0] - rx, pos[1] - ry)
            # Toggle input only in select mode when clicking the body
            if isinstance(clicked_block, InputBlock):
                clicked_block.on_click()
        else:
            if self.selected:
                self.selected.selected = False
            self.selected = None

    def on_mouse_up(self, pos, button):
        if self.wiring_from:
            expected = "in" if self.wiring_from.direction == "out" else "out"
            target_port = self.find_near_port(*pos, expect_direction=expected)
            if target_port and target_port is not self.wiring_from:
                if self.wiring_from.direction == "out":
                    self.wires.append(Wire(self.wiring_from, target_port))
                else:
                    self.wires.append(Wire(target_port, self.wiring_from))
                self.propagate_demo()
            self.wiring_from = None

    def on_mouse_motion(self, pos, rel, buttons):
        if self.selected and buttons[0]:
            new_x = pos[0] - self.drag_offset[0] + self.selected.w // 2
            new_y = pos[1] - self.drag_offset[1] + self.selected.h // 2
            self.selected.move_to(new_x, new_y)

    def on_key_down(self, key):
        if key in (pygame.K_DELETE, pygame.K_BACKSPACE) and self.selected:
            self.remove_block(self.selected)

    # Queries
    def find_block_at(self, mx, my) -> Optional[Block]:
        for b in reversed(self.blocks):
            if b.hit(mx, my):
                return b
        return None

    def find_near_port(self, mx, my, expect_direction: Optional[str] = None) -> Optional[Port]:
        best = None
        best_d2 = self.SNAP_RADIUS ** 2
        for b in self.blocks:
            for p in b.ports:
                if expect_direction and p.direction != expect_direction:
                    continue
                x, y = p.world()
                d2 = (mx - x) ** 2 + (my - y) ** 2
                if d2 <= best_d2:
                    best = p
                    best_d2 = d2
        return best

    # Demo signal propagation
    def propagate_demo(self):
        for w in self.wires:
            w.dst.state = w.src.state

    # Rendering
    def draw_grid(self, surface):
        for x in range(0, self.WIDTH, self.GRID):
            pygame.draw.line(surface, (26, 28, 32), (x, 0), (x, self.toolbar.rect.y))
        for y in range(0, self.toolbar.rect.y, self.GRID):
            pygame.draw.line(surface, (26, 28, 32), (0, y), (self.WIDTH, y))

    def draw(self, surface):
        surface.fill(self.BLACK)
        self.draw_grid(surface)
        for w in self.wires:
            w.draw(surface, self.SIGNAL_FAMILIES, self.DEFAULT_FAMILY, self.PORT_RADIUS)
        if self.wiring_from:
            mx, my = pygame.mouse.get_pos()
            expected = "in" if self.wiring_from.direction == "out" else "out"
            target = self.find_near_port(mx, my, expect_direction=expected)
            if target:
                mx, my = target.world()
            sx, sy = self.wiring_from.world()
            midx = (sx + mx) // 2
            points = [(sx, sy), (midx, sy), (midx, my), (mx, my)]
            pal = self.SIGNAL_FAMILIES[self.wiring_from.family]
            col = pal["on"] if self.wiring_from.state else pal["off"]
            pygame.draw.lines(surface, col, False, points, self.WIRE_WIDTH)  # 두께 적용
            if target:
                pygame.draw.circle(surface, self.SELECT, target.world(), self.PORT_RADIUS + 3, 2)

        for b in self.blocks:
            b.draw(surface)
        self.toolbar.draw(surface)



def run(config_path: str = "config.txt") -> None:
    cfg = _load_config(config_path)
    pygame.init()
    pygame.display.set_caption("SchemBoard — GUI Prototype")
    screen = pygame.display.set_mode((cfg["WIDTH"], cfg["HEIGHT"]))
    clock = pygame.time.Clock()

    world = World(cfg)

    running = True
    while running:
        clock.tick(cfg["FPS"])
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                world.on_mouse_down(event.pos, event.button)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                world.on_mouse_up(event.pos, event.button)
            elif event.type == pygame.MOUSEMOTION:
                world.on_mouse_motion(event.pos, event.rel, event.buttons)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    world.tool = "select"
                    world.place_spec = None
                    world.toolbar.active_payload = {"tool": "select"}
                else:
                    world.on_key_down(event.key)

        world.draw(screen)
        pygame.display.flip()

    pygame.quit()
