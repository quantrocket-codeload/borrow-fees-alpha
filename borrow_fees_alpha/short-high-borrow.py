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

import pandas as pd
from moonshot import Moonshot
from moonshot.slippage.borrowfee import IBKRBorrowFees
from quantrocket.fundamental import get_ibkr_borrow_fees_reindexed_like
from quantrocket.master import get_securities_reindexed_like

class ShortHighBorrow(Moonshot):
    """
    Strategy that shorts stocks with the highest borrow fees.
    """

    CODE = "short-high-borrow"
    DB = "usstock-1d-bundle"
    DB_FIELDS = ["Open", "Close", "Volume"]
    BORROW_FEE_TOP_N_PCT = 10
    DOLLAR_VOLUME_TOP_N_PCT = 75
    SLIPPAGE_CLASSES = IBKRBorrowFees

    def prices_to_signals(self, prices: pd.DataFrame):
        closes = prices.loc["Close"]
        volumes = prices.loc["Volume"]

        # limit to common stocks...
        sec_types = get_securities_reindexed_like(closes, "usstock_SecurityType2").loc["usstock_SecurityType2"]
        are_common_stocks = sec_types == "Common Stock"

        # ...in the top 75% by dollar volume
        avg_dollar_volumes = (closes * volumes).rolling(30).mean()
        dollar_volume_pct_ranks = avg_dollar_volumes.where(are_common_stocks).rank(axis=1, ascending=False, pct=True)
        have_adequate_dollar_volumes = dollar_volume_pct_ranks <= (self.DOLLAR_VOLUME_TOP_N_PCT / 100)

        # rank by borrow fee and short the 10% with the highest fees
        borrow_fees = get_ibkr_borrow_fees_reindexed_like(closes)
        borrow_fee_ranks = borrow_fees.where(have_adequate_dollar_volumes).rank(axis=1, ascending=False, pct=True)
        short_signals = borrow_fee_ranks <= (self.BORROW_FEE_TOP_N_PCT / 100)
        
        return -short_signals.astype(int)

    def signals_to_target_weights(self, signals: pd.DataFrame, prices: pd.DataFrame):
        weights = self.allocate_equal_weights(signals)
        return weights

    def target_weights_to_positions(self, weights: pd.DataFrame, prices: pd.DataFrame):
        # Enter the position the day after the signal
        return weights.shift()

    def positions_to_gross_returns(self, positions: pd.DataFrame, prices: pd.DataFrame):
        # We'll enter on the open, so our return is today's open to
        # tomorrow's open
        opens = prices.loc["Open"]
        # The return is the security's percent change over the period,
        # multiplied by the position.
        gross_returns = opens.pct_change() * positions.shift()
        return gross_returns
