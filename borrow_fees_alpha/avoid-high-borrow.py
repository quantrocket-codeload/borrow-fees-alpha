# Copyright 2024 QuantRocket LLC - All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import zipline.api as algo
from zipline.pipeline import Pipeline, ibkr, master
from zipline.pipeline.factors import AverageDollarVolume
from zipline.finance.execution import MarketOrder

BUNDLE = "usstock-1d-bundle"
MAX_BORROW_FEE = 0.3

def initialize(context: algo.Context):
    """
    Called once at the start of a backtest, and once per day in
    live trading.
    """
    # Attach the pipeline to the algo
    algo.attach_pipeline(make_pipeline(), 'pipeline')

    # Rebalance monthly
    algo.schedule_function(
        rebalance,
        algo.date_rules.month_start(),
    )

def make_pipeline():
    """
    Create a pipeline that filters by dollar volume and borrow fee.
    """
    # limit initial universe to common stocks
    universe = master.SecuritiesMaster.usstock_SecurityType2.latest.eq("Common Stock")

    screen = AverageDollarVolume(window_length=90).percentile_between(50, 75)
    
    if MAX_BORROW_FEE:
        screen &= (ibkr.BorrowFees.FeeRate.latest <= MAX_BORROW_FEE)
    
    pipeline = Pipeline(
        initial_universe=universe,
        screen=screen
    )
    return pipeline

def rebalance(context: algo.Context, data: algo.BarData):
    """
    Execute orders according to our schedule_function() timing.
    """
    desired_stocks = algo.pipeline_output('pipeline').index
    
    positions = context.portfolio.positions

    # Exit positions we no longer want to hold
    for asset, position in positions.items():
        if asset not in desired_stocks and data.can_trade(asset):
            algo.order_target_value(asset, 0, style=MarketOrder())

    # Enter long positions
    for asset in desired_stocks:

        # allocate 1/Nth of capital per asset
        algo.order_target_percent(asset, 1/len(desired_stocks), style=MarketOrder())
        