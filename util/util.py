import pandas as pd
import numpy as np
import torch
from typing import Tuple


class DataSet(torch.utils.data.Dataset):
    # load the dataset
    def __init__(self, X, y):
        self.X = X
        self.y = y

    # number of rows in the dataset
    def __len__(self):
        return len(self.X)

    # get a row at an index
    def __getitem__(self, idx):
        return [self.X[idx], self.y[idx]]


def data_process_records(data: pd.DataFrame) -> pd.DataFrame:
    """Preprocessing raw data to experiment data

    :param data: data to be cleaned
    :type data: pd.DataFrame
    :return: cleaned ddata
    :rtype: pd.DataFrame
    """

    # Make sure data is sorted
    data = data.sort_values(["optionid", "date"])

    # Create some features
    data["moneyness"] = data["spot"] - data["strike_price"]
    data["mid_price"] = (data["best_bid"] + data["best_offer"]) / 2
    data["spread"] = (data["best_offer"] - data["best_bid"]) / data["mid_price"]

    # Create features
    features = [
        "moneyness",
        "VIX",
        "spread",
        "impl_volatility",
        "impvol_chg",
        "delta",
        "gamma",
        "vega",
        "theta",
    ]

    # EMA of features
    for feature in features:
        for span in [5, 20]:
            data[f"{feature}_{str(span)}"] = (
                data.groupby("optionid")[feature]
                .ewm(span=span, adjust=False)
                .mean()
                .reset_index(drop=True)
            )

    # Save the prediction target, today's implied vol in a separate column
    data["iv"] = data["impl_volatility"]

    # Shift features
    feature_cols = []
    for feature in features:
        for span in ["", "_5", "_20"]:
            feature_cols.append(feature + span)
            data[feature + span] = data.groupby("optionid")[feature + span].shift(
                periods=1
            )

    # From the paper. This makes sense as the deep in/out-of-money option delta
    # are much less relevant to our model (movements in price do not meaningfully change
    # the delta)
    data = data[(data["delta"] >= 0.05) & (data["delta"] <= 0.95)]

    # Process needed columns
    data = data[["date", "optionid", "iv", "time_to_maturity"] + feature_cols]
    data = data.dropna()
    data = data.reset_index(drop=True)

    return data


def split_train_test(
    data: pd.DataFrame, train_pct: float, seed: int = 1
) -> Tuple[pd.DataFrame]:
    """Split data by optionid into training and testing sets

    :param data: full data set
    :type data: pd.DataFrame
    :param train_pct: percentage of data to be using in training set
    :type train_pct: float
    :param seed: seed for random sampling, defaults to 1
    :type seed: int, optional
    :return: Tuple(pd.DataFrame)
    :rtype: The traiing and testing dataset, stored in a tuple
    """

    # Choose the traninig set
    n = len(data["optionid"].unique())
    np.random.seed(seed)
    n_train = int(train_pct * n)
    train_id = np.random.choice(data["optionid"].unique(), n_train, replace=False)

    # Create output
    train_mask = data.optionid.isin(train_id)
    train = data[train_mask].reset_index(drop=True)
    test_mask = [mask is False for mask in train_mask]
    test = data[test_mask].reset_index(drop=True)

    return train, test


def prep_mlp(data: pd.DataFrame) -> DataSet:

    X = data.drop(columns=["date", "optionid", "iv"]).values
    y = data.iv.values
    dataset = DataSet(X, y)

    return dataset
