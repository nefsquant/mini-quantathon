from typing import Dict, List
from datamodel import Order, Symbol, TradingState


class Trader:
    def run(self, state: TradingState) -> Dict[Symbol, List[Order]]:
        return {}
