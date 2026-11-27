# Daily crossover versus month-end timing

The paper strategy stays at 20/50. The eight-month candidate traded less in all three markets, but its improvement depended heavily on MSFT. AAPL had lower growth and a deeper drawdown. This sample is too narrow for changing the default.

## Experiment

The candidate targets stock when the last completed monthly close exceeds its trailing monthly average and cash otherwise. The ten-month reference comes from [Meb Faber's tactical asset allocation research](https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf). We also tested eight and twelve months. Selection used the mean annualized daily Sharpe across the three configured symbols during 2011-2018. Scores were 0.749, 0.745 and 0.726 for eight, ten and twelve months respectively. 2010 supplies warm-up history.

Each evaluation starts flat. The daily strategy waits for its first crossover. The monthly strategy can enter at the first monthly decision, and passive holding enters at the first close. Decisions execute at the next available close after observation. Returns use Yahoo adjusted daily closes for splits and distributions. Cash earns zero, and each position change costs 5 basis points of traded value. Metrics describe individual fully invested or flat sleeves; the paper desk uses one-share orders and its own risk limits. The final position is marked at the final close.

## Held-out results, 2019-2024

| Symbol | Rule | Annualized growth | Max drawdown | Sharpe | Position changes |
|---|---|---:|---:|---:|---:|
| AAPL | 20/50 | 22.68% | -24.16% | 1.03 | 31 |
| AAPL | 8 months | 20.25% | -31.43% | 0.85 | 15 |
| AAPL | Hold | 37.15% | -31.43% | 1.18 | 1 |
| MSFT | 20/50 | 10.44% | -35.73% | 0.55 | 35 |
| MSFT | 8 months | 28.29% | -28.04% | 1.13 | 5 |
| MSFT | Hold | 28.15% | -37.15% | 1.00 | 1 |
| SPY | 20/50 | 9.16% | -27.64% | 0.74 | 27 |
| SPY | 8 months | 11.03% | -27.65% | 0.87 | 11 |
| SPY | Hold | 17.09% | -33.72% | 0.90 | 1 |

At 20 basis points the candidate still had lower annualized growth on AAPL and higher growth on MSFT and SPY than the daily rule. These symbols overlap economically, and the data and fill assumptions differ from Alpaca IEX paper execution. Treat 2019-2024 as an examined period in future experiments.

## Reproduce

From PowerShell in the repository, fetch the public Yahoo Finance chart history into a local temporary directory and run the offline comparison. The end timestamp is exclusive. Vendor revisions can change subsequent results.

```powershell
foreach ($symbol in 'AAPL', 'MSFT', 'SPY') {
    $url = "https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?period1=1262304000&period2=1735689600&interval=1d"
    Invoke-WebRequest $url -OutFile (Join-Path $env:TEMP "marketpilot-$symbol.json")
}
python -m marketpilot.research $env:TEMP
```
