from aiogram.fsm.state import StatesGroup, State

class GenerateState(StatesGroup):
    choosing_model = State()
    choosing_quality = State()
    choosing_ratio = State()
    waiting_prompt = State()