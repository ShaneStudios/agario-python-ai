from flask import Flask, jsonify, request
from flask_cors import CORS
import random
import uuid
import time
import math

app = Flask(__name__)
CORS(app)

WORLD_WIDTH = 3000
WORLD_HEIGHT = 3000
BOT_MAX_CELLS = 4 
BOT_INITIAL_MASS = math.pi * 15 * 15 
BOT_BASE_SPEED = 2.5 

bots_data = {}

def generate_bot_id():
    return "pybot_" + str(uuid.uuid4())[:8]

def mass_to_radius(mass):
    return (mass / math.pi)**0.5

def radius_to_mass(radius):
    return math.pi * radius * radius

class PyBotCell:
    def __init__(self, x, y, mass, cell_id=None):
        self.id = cell_id or str(uuid.uuid4())[:6]
        self.x = x
        self.y = y
        self.mass = mass
        self.radius = mass_to_radius(self.mass)

    def update_mass(self, new_mass):
        self.mass = new_mass
        self.radius = mass_to_radius(self.mass)

    def to_dict(self):
        return {"id": self.id, "x": self.x, "y": self.y, "mass": self.mass, "radius": self.radius}


class PyBot:
    def __init__(self, bot_id=None, name=None, color=None):
        self.id = bot_id or generate_bot_id()
        self.name = name or f"PyBot {self.id[-3:]}"
        self.color = color or f"#{random.randint(0, 0xFFFFFF):06x}"
        self.cells = []
        self.target_x = random.uniform(0, WORLD_WIDTH)
        self.target_y = random.uniform(0, WORLD_HEIGHT)
        self.last_update_time = time.time()
        self.total_mass = 0
        self.add_initial_cell()

    def add_initial_cell(self):
        initial_x = random.uniform(100, WORLD_WIDTH - 100)
        initial_y = random.uniform(100, WORLD_HEIGHT - 100)
        self.cells.append(PyBotCell(initial_x, initial_y, BOT_INITIAL_MASS))
        self.recalculate_total_mass()

    def recalculate_total_mass(self):
        self.total_mass = sum(cell.mass for cell in self.cells)
        if not self.cells and self.id in bots_data:
            app.logger.info(f"Bot {self.id} has no cells, removing.")
            del bots_data[self.id]

    def get_center_of_mass(self):
        if not self.cells:
            return self.target_x, self.target_y
        
        com_x = sum(c.x * c.mass for c in self.cells) / self.total_mass if self.total_mass else self.cells[0].x
        com_y = sum(c.y * c.mass for c in self.cells) / self.total_mass if self.total_mass else self.cells[0].y
        return com_x, com_y
        
    def update_position(self, delta_time):
        if not self.cells:
            return

        com_x, com_y = self.get_center_of_mass()

        dist_to_target = ((self.target_x - com_x)**2 + (self.target_y - com_y)**2)**0.5
        
        if dist_to_target < 50 or random.random() < 0.01:
            self.target_x = random.uniform(0, WORLD_WIDTH)
            self.target_y = random.uniform(0, WORLD_HEIGHT)

        angle = math.atan2(self.target_y - com_y, self.target_x - com_x)
        
        speed = BOT_BASE_SPEED / (1 + self.total_mass / (BOT_INITIAL_MASS * 20)) 
        speed = max(0.5, speed)

        move_x = math.cos(angle) * speed * delta_time * 60
        move_y = math.sin(angle) * speed * delta_time * 60
        
        for cell in self.cells:
            cell.x += move_x
            cell.y += move_y
            cell.x = max(cell.radius, min(WORLD_WIDTH - cell.radius, cell.x))
            cell.y = max(cell.radius, min(WORLD_HEIGHT - cell.radius, cell.y))
            
        self.last_update_time = time.time()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "cells": [cell.to_dict() for cell in self.cells],
            "target": {"x": self.target_x, "y": self.target_y},
            "totalMass": self.total_mass,
            "isPythonBot": True
        }

def create_bot_instance():
    return PyBot()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "bot_count": len(bots_data)}), 200

@app.route('/bots', methods=['GET'])
def get_bots_data():
    current_time = time.time()
    active_bots = []
    for bot_id, bot_instance in list(bots_data.items()):
        delta_time = current_time - bot_instance.last_update_time
        bot_instance.update_position(delta_time)
        if bot_instance.cells:
            active_bots.append(bot_instance.to_dict())
        else:
            if bot_id in bots_data:
                del bots_data[bot_id]
    return jsonify(active_bots)

@app.route('/bots/reset', methods=['POST'])
def reset_all_bots():
    global bots_data
    bots_data.clear()
    count = request.args.get('count', default=10, type=int)
    for _ in range(count):
        bot = create_bot_instance()
        bots_data[bot.id] = bot
    app.logger.info(f"Reset and created {len(bots_data)} bots.")
    return jsonify([b.to_dict() for b in bots_data.values() if b.cells]), 200

@app.route('/bots/eaten/<bot_id>', methods=['POST'])
def bot_was_eaten(bot_id):
    if bot_id in bots_data:
        app.logger.info(f"Bot {bot_id} reported as eaten by client.")
        del bots_data[bot_id]
        new_bot = create_bot_instance()
        bots_data[new_bot.id] = new_bot
        app.logger.info(f"Bot {bot_id} removed, new bot {new_bot.id} spawned.")
        return jsonify({"message": f"Bot {bot_id} acknowledged as eaten, new bot {new_bot.id} spawned."}), 200
    return jsonify({"message": f"Bot {bot_id} not found."}), 404

if __name__ == '__main__':
    for _ in range(10):
        bot = create_bot_instance()
        bots_data[bot.id] = bot
    app.run(host='0.0.0.0', port=int(random.uniform(5000,5999)), debug=False)
