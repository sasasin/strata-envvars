# `strata-hy4-metal --prof3`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--prof3` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常のトークン生成経路で、9回目の decode step に積まれた GPU dispatch を個別に計測し、カーネル名ごとの所要時間を stderr に出します。初期プロンプト処理ではなく、生成時の1 step を構成する dispatch の計測です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1965`）。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 16 --prof3
```

`--prof3` は値を取らず、モデルとトークン入力を指定した生成実行に追加します。計測分岐に到達するには、EOS による早期終了がない状態で少なくとも9回の decode step が必要です。

## 値と既定値

フラグを指定すると内部の `prof3` が `true` になります。省略時は `false` です。別名、値の変換、数値範囲検証はありません。複数回指定しても真偽値を再設定するだけです（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1529`）。

## 実行時の動作

`--gen N` の通常生成ループは `s = 0` から始まり、各反復で次のトークンが EOS なら処理を終了します。EOS 判定を通過した反復で forward、head、argmax の dispatch を積み、`prof3 && s == 8` の場合に限って `kernel_profile(30)` を呼びます。したがって対象は0始まりの `s == 8`、すなわち9回目の decode です。`--prof3` 自体は `--gen` を設定せず、`--gen` 既定値は0なので、生成数を別途指定しなければ計測されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1512,1944-1964`）。

`kernel_profile` はその時点の pending dispatch を一件ずつ走査し、各 dispatch を30回実行して時間を集計します。カーネル名ごとに時間を合算し、合計時間の降順で「合計」「呼び出し数」「1呼び出しあたり」を stderr に出します。計測後も pending dispatch 一覧は残り、その後の `run_all()` で通常の dispatch graph も実行されるため、診断用に GPU 実行が追加されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1351-1366,1961-1965`）。

## 適用条件と副作用

この分岐は `gen > 0` の通常生成経路にあります。`--gen` が9未満なら `s == 8` に届かず、9以上でもその前に EOS が出れば計測しません。serve 経路、`--bench-m` 経路、speculative generation の経路など、通常生成の `else if (gen > 0)` に入らない実行では、この `--prof3` 分岐は使われません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1648,1887-1898,1900-1944,1951-1964`）。

各 pending dispatch は同じ dispatch 引数とバッファを用いて30回 GPU 上で実行されます。計測処理はdispatchを単独実行したあとにも通常の `run_all()` を実行します。バッファ内容への影響や特定 Metal device 上の計測精度はソースだけでは確定できず、実機では確認していません。

## 出力とエラー

計測時は stderr に `[prof3] one decode step, each dispatch alone x30 ...` の見出しと、カーネル名ごとの集計行を出力します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1365-1366`）。`--prof3` 固有の validation error や警告は確認できません。未知のオプションは別の一般処理で stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード2になりますが、`--prof3` は parser に登録されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1529,1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1504-1529` — フラグ状態の初期値と parser 登録。値を消費しない。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1351-1366` — pending dispatch を個別に30回実行し、名前別に集計して stderr に表示する処理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1965` — 通常生成経路での適用条件、EOS 判定、計測呼び出しとその後の通常実行。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609` — 未知のフラグの出力と終了コード。

調査は指定 commit のソースに基づきます。CLI の実行や Metal device 上での計測は行っていないため、実機での時間値・バッファへの影響は未確認です。
