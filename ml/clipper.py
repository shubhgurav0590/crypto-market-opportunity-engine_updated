import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

class QuantileClipper(BaseEstimator, TransformerMixin):
    def __init__(self, low=0.01, high=0.99):
        self.low = low
        self.high = high

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.bounds_ = {}
        for col in X.columns:
            self.bounds_[col] = (
                X[col].quantile(self.low),
                X[col].quantile(self.high)
            )
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        for col, (low, high) in self.bounds_.items():
            if col in X.columns:
                X[col] = X[col].clip(low, high)
        return X
