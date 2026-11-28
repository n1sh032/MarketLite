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

## Frozen-rule check on 2025

Using 2024 for warm-up, start each sleeve in cash and run the unchanged rules on the 250 sessions from January 2 through December 31, 2025. Apply the same delayed close execution and five basis points per position change. Returns below are cumulative for the calendar year.

| Symbol | 20/50 return | Eight-month return | Hold return | 20/50 max drawdown | Eight-month max drawdown |
|---|---:|---:|---:|---:|---:|
| AAPL | 11.72% | 8.38% | 11.93% | -17.01% | -15.14% |
| MSFT | 6.10% | 2.98% | 16.33% | -14.28% | -12.74% |
| SPY | 7.92% | 11.52% | 17.95% | -10.39% | -10.04% |

For reproduction, use the same chart endpoint with period1=1704067200 and period2=1767225600. Pass each series from load_prices to evaluate with start=end=2025 and cost_bps=5. Convert annualized growth to period return with (1 + growth) ** (250 / 252) - 1. The eight-month rule reduced drawdown across these three symbols, while its earlier MSFT return advantage reversed.

## One shared paper account in 2025

Start with $100,000 cash, zero interest, zero positions and the default RiskLimits.
Evaluate AAPL, MSFT and SPY in that order. Size every order at one share and
reserve position slots for approved buys. Signals use regular closes. Approved
orders fill at the next session open with five basis points of one-way costs.
Credit dividends on ex-date to shareholders entering the session. Mark open
positions at the closing price on December 31. The historical files include 2024
for warm-up. The first decision is made after the first 2025 close. The monthly
candidate acts at the end of each month and passive holding buys once.

| Rule | Net P&L | Worst account drawdown | Mean closing exposure | Fills | Rejected |
|---|---:|---:|---:|---:|---:|
| Daily 20/50 | $139.51 | -0.086% | 0.817% | 12 | 3 |
| Eight-month | $125.94 | -0.100% | 0.901% | 7 | 0 |
| Buy and hold one share each | $196.51 | -0.264% | 1.311% | 3 | 0 |

All three rejections were sells from a flat position. At 20 basis points the
respective profits were $132.36, $121.63 and $194.64. Closing exposure explains
why account returns and drawdowns are small. This already-examined year serves
as an execution comparison. Opening prints approximate fills and the simulation
assumes complete data, immediate acknowledgments and a single fill per order.
It accepts split-free files only. MarketPilot's connected paper account uses
Alpaca IEX data and can receive different prices.

To reproduce, use the download loop above with period1=1704067200,
period2=1767225600 and append &events=div%2Csplits to the URL. Run
`python -m marketpilot.desk_replay "$env:TEMP"`. Add `--cost-bps 20` for the
stress case.

## Prior-year exposure matching

Using 2023 for warm-up, replay each strategy in 2024 at one share per order and
$100,000 starting capital. Set the common target to the lowest mean invested
percentage among the three. Add idle cash to each higher-exposure account until
its 2024 mean matches that target. Freeze each starting balance before restarting
flat in January 2025. This compares account returns at a common historical
exposure target. The strategies still decide independently when to invest.

| Rule | Starting balance | 2024 mean exposure | 2025 mean exposure | 2025 return | Worst 2025 drawdown |
|---|---:|---:|---:|---:|---:|
| Daily 20/50 | $100,000 | 0.5880% | 0.8172% | 0.1395% | -0.0861% |
| Eight-month | $167,944 | 0.5880% | 0.5367% | 0.0750% | -0.0596% |
| Buy and hold | $197,935 | 0.5880% | 0.6624% | 0.0993% | -0.1332% |

The daily crossover led in account return while the monthly rule had the smallest
drawdown. Realized exposure diverged in 2025. The ordering therefore combines
timing and exposure effects. These results apply to the already examined 2025
sample, fixed one-share orders and zero interest on idle cash.

To reproduce, use the preceding three-symbol download with period1=1672531200
and period2=1767225600, including dividends and splits. Run
`python -m marketpilot.exposure_study "$env:TEMP" --year 2025`.

## Timing contribution in the one-share replay

For each symbol, compare actual gross profit with the profit from holding its
realized average share count throughout the evaluation. Measure intervals from
the first eligible opening fill to the final close. Shares carried overnight
receive the next session's dividend. The benchmark uses hindsight to explain
P&L and is independent of signal generation. Timing is the difference in gross
profit. Subtract simulated costs separately to recover net account P&L.

| 2025 rule | Average holdings contribution | Timing contribution | Costs | Net profit |
|---|---:|---:|---:|---:|
| Daily 20/50 | $119.17 | $22.72 | $2.38 | $139.51 |
| Eight-month | $130.78 | -$3.40 | $1.44 | $125.94 |
| One share each | $197.14 | $0.00 | $0.63 | $196.51 |

Daily crossover timing contributed $18.54 on AAPL, $11.36 on MSFT and
-$7.18 on SPY. This measures one previously examined period. The desk replay
command above includes per-symbol attribution in its output.
