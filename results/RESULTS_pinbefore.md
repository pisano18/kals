  ok: at 60 seconds the whole window is ahead and nothing has drifted yet
  ok: risk falls monotonically as the close approaches
  ok: past 60 seconds each extra second adds a full second of drift -- which is exactly why the model degrades out there
  ok: NULL: at the close there is nothing left to learn
  ok: thirty seconds carries 24.6x the risk of ten
  ok: at the strike it is a coin flip whatever the volatility
  ok: a dollar clear with small vol is near certain (1.00000)
  ok: and with 59 of 60 prints locked far above the strike it is settled -- the whole reason the pin works
  ok: the two sides sum to exactly one
  ok: THE BOUNDARY THAT MATTERS: 30 is inside today's window, 31 is outside
  ok: NULL: outside the measured range belongs to no band
pinbefore selftest: OK

16258 settled markets, 9 indices loaded
scored 14261 closes

=== the model must be at least 99.50% sure (claims 0.50% risk) ===
  seconds left    moments    wrong  real risk overconfident
  3-10             113003       31     0.027%        0.1x
  11-20            137472       31     0.023%        0.0x
  21-30            131752       28     0.021%        0.0x
  31-45            183936      107     0.058%        0.1x
  46-60            164994      153     0.093%        0.2x

=== the model must be at least 99.90% sure (claims 0.10% risk) ===
  seconds left    moments    wrong  real risk overconfident
  3-10             112755       23     0.020%        0.2x
  11-20            136426       17     0.012%        0.1x
  21-30            129471       20     0.015%        0.2x
  31-45            178010       78     0.044%        0.4x
  46-60            155891       73     0.047%        0.5x

=== the model must be at least 99.87% sure (claims 0.13% risk) ===
  seconds left    moments    wrong  real risk overconfident
  3-10             112803       25     0.022%        0.2x
  11-20            136591       19     0.014%        0.1x
  21-30            129831       20     0.015%        0.1x
  31-45            178914       82     0.046%        0.4x
  46-60            157229       80     0.051%        0.4x

=== the model must be at least 99.99% sure (claims 0.01% risk) ===
  seconds left    moments    wrong  real risk overconfident
  3-10             112463       20     0.018%        1.8x
  11-20            135095        9     0.007%        0.7x
  21-30            126670       16     0.013%        1.3x
  31-45            170933       51     0.030%        3.0x
  46-60            145119       24     0.017%        1.7x

A band is usable if its real risk is no worse than what we accept
today (the 21-30 row at 99.5%). More moments there is the prize;
a worse real risk at any bar is the thing that would invert the P&L.
