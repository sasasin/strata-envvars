# `STRATA_ROUTE_STATS`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

speculative verification の各 window で router が選んだ expert ID を集計する診断用スイッチです。window 幅ごとに、layer あたりの異なる expert 数と、各 row がそれ以前の row にない expert を何個選んだかを表示します。生成方法、expert 選択、token 出力を変える制御ではありません。

## 値と判定

`Verifier::init()` が `std::getenv("STRATA_ROUTE_STATS")` を読み、値が存在し先頭文字が `1` の場合だけ有効にします。文字列全体の parse はしません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効（値は存在するが先頭文字は `\0`） |
| `1`、`10`、`1anything` | 有効 |
| `0`、`true`、その他、先頭文字が `1` でない値 | 無効 |

有効時は `9 * n_layers * 8` 個の 64 bit カウンターを GPU に確保してゼロ初期化します。確保に失敗すると統計は無効のままになり、エラーは表示されません（CUDA エラー状態は読み捨てられます）。

## 有効になる条件

- verifier が初期化され、その初期化時点で環境変数の先頭文字が `1` であること。既存の `Verifier` では初期化後に環境を書き換えても設定は変わりません。新しい `Verifier` の再初期化は改めて値を読みます。
- `record_window()` の router 処理で `rs_on_` が真、group 数 `G` が 1、row 数 `n` が 8 以下、window 幅 `T` が 8 以下であること。これを満たさない経路ではカーネルを起動しません。
- 結果を標準出力に表示するには、別変数 `STRATA_SPEC_T_CYCLE` から有効な窓幅リストが作られ、window 幅計測の終了処理に入る必要があります。統計カーネル自体はこのリストの有無に関係なく、上記条件を満たす window を集計します。

## 実行時の詳細

CUDA カーネルは各 row の expert ID を調べ、同じ row 内の重複と先行 row に現れた ID を除いた個数を、その row のカウンターへ加算します。したがって row 0 はその row 内の異なる expert 数、後続 row は window の先行 row にはない expert 数です。カーネル呼び出し箇所は各 layer の router 処理後です。

`route_stats_report()` はカウンターをホストへコピーし、`T1` から `T8` について集計済み window がある幅だけ、次の形式で返します。

```text
T%d (n=%lld): distinct experts per layer %.2f; new per row: ...
```

ここで `n` はその幅の集計 window 数、`distinct experts per layer` は window 内の全 row を通じた異なる expert 数を window 数と layer 数で割った平均、`new per row` の各値は対応する row の新規 expert 数を同じ分母で割った平均です。レポート呼び出し後、device カウンターと幅別 window 数はゼロに戻ります。

生成処理は `STRATA_SPEC_T_CYCLE` による窓幅計測ブロックでのみこのレポートを `stdout` に出します。先頭行は `routed experts per window width:` です。環境変数が有効でもこのブロックを通らなければ、統計を内部で集計するだけで表示しません。初期化、集計、表示いずれもこの変数に関する専用ログや警告はありません。

## 根拠

- 値の読み取り、カウンター確保、確保失敗時の処理: `src/core/verify.cpp:935-945`。
- router 後に統計カーネルを呼ぶ条件: `src/core/verify.cpp:1982-1983`。
- row ごとの重複排除と先行 row との比較、カウンター加算: `src/kernels/cuda/verify_kernels.cu:591-604`。
- 幅別 window 数の加算: `src/core/verify.cpp:2717-2745`（特に 2742 行）。
- GPU からの集計、出力形式、レポート後の reset: `src/core/verify.cpp:2381-2406`。
- 計測ブロックと stdout 出力: `src/program/generate.cpp:16746-16756`。ブロックに入る `t_cycle` は `STRATA_SPEC_T_CYCLE` の値から組み立てられます（`src/program/generate.cpp:16386-16397`）。
- 宣言上の集計説明: `include/strata/core/verify.hpp:368-369`、`include/strata/kernels/verify_kernels.hpp:129-131`。
- `docs/DETAILS.md` に `STRATA_ROUTE_STATS` の説明や測定値は見当たりません。性能効果や追加負荷の測定値は記載していません。
