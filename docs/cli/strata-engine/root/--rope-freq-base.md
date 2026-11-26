# `strata generate --rope-freq-base`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--rope-freq-base` |
| 別名 | なし |
| 値 | 数値 `N`。明示値は有限かつ `1` より大きい必要がある。`0` はモデルの値を使う指定。 |

## 役割

RoPE の周波数基底 `freq_base` を上書きする。これは RoPE の回転角の周波数列を定める値で、位置拡張の方式・倍率を選ぶ `--rope-scaling` / `--rope-scale` とは別の raw 設定値である。既定では GGUF モデルメタデータに `rope.freq_base` があればそれを使い、なければ `1e7` を使う。`--rope-scaling none` の場合も基底値自体は RoPE 回転に適用される。

## 使い方

```sh
strata generate --pack MODEL.gguf --tokens 1,2,3 --rope-freq-base 10000000
```

この例では `MODEL.gguf` と入力 token 列を指定し、RoPE 基底を `10000000` に固定する。モデルファイルの値を使う場合は `--rope-freq-base 0` とするか、このオプションを省略する。

## 値と既定値

- parser は次の引数を `std::atof` で `double` に変換し、オプション値として保存する。短縮別名はなく、同じオプションを複数回指定するとループ内で後に読まれた値が残る（`engine/sycl/src/program/generate.cpp:1882-1887,1913`）。
- 初期値は `0`。`0` は明示的な基底値ではなく未指定相当で、モデルメタデータへのフォールバックを許す（`engine/sycl/src/program/generate.cpp:479,2991-2992`）。
- 非有限値は拒否される。非ゼロ値が `1` 以下の場合も拒否される。したがって有効な明示値は有限な `N > 1`（`engine/sycl/src/program/generate.cpp:2657-2673`）。
- 引数自体が省略されていると `--rope-freq-base needs a value` を stderr に出して終了コード `2` で終了する（`engine/sycl/src/program/generate.cpp:1884-1886`）。数値として解釈できない文字列は `atof` により `0` となり、モデル値または既定値へフォールバックする。`nan` / `inf` など非有限数は別途拒否される。

## 実行時の動作

parser で受理した値は、RoPE 設定をモデルから解決する段階で適用される。明示値が `0` より大きければそれを採用し、そうでなければ GGUF のアーキテクチャ接頭辞付き `rope.freq_base` が `1` より大きい場合に採用し、いずれもなければ `RopeScaling` の既定 `1e7` が残る。明示した正値はモデルメタデータに優先する（`engine/sycl/src/program/generate.cpp:2915-2923,2942-2947,2991-2992`; `engine/include/strata/kernels/rope_scaling.hpp:66-75`）。

解決済み設定は `rope_scaling_set` によりプロセス設定へ一度だけ登録され、後続の RoPE テーブル構築と解析的 RoPE kernel に使われる。テーブル生成では `freq_base` を周波数列の指数計算に使い、解析 kernel でも同じ設定を参照する（`engine/sycl/src/program/generate.cpp:3014-3024`; `engine/include/strata/kernels/rope_scaling.hpp:30-35,186-191`; `engine/sycl/src/core/layer.cpp:952-962`; `engine/sycl/src/kernels/cuda/rope.dp.cpp:64-78`; `engine/sycl/src/kernels/cuda/native_rope.dp.cpp:258-262`）。

## 適用条件と副作用

- 値はモデル設定との統合後、セッション初期化前に確定する。実行中に変更する CLI 経路はなく、RoPE 後の key cache に異なる設定が混ざらないようプロセス内で固定される（`engine/sycl/src/program/generate.cpp:472-476,2915-2920`; `engine/include/strata/kernels/rope_scaling.hpp:30-35`）。
- 周波数基底は RoPE scaling type が `none` でも有効である。`none` の場合に他のスケーリング knob はリセットされるが、基底だけは保存される（`engine/sycl/src/program/generate.cpp:3001-3012`）。
- 起動時の RoPE 設定検証に失敗した場合は stderr にエラーを出し、終了コード `2` となる（`engine/sycl/src/program/generate.cpp:2670-2678,3014-3022`）。有効値の場合、このオプション固有のファイル書き換えやネットワーク操作は確認できない。

## 根拠

- `engine/sycl/src/program/generate.cpp:479,1913` — 初期値と parser の型変換。
- `engine/sycl/src/program/generate.cpp:1884-1886,2657-2678` — 値不足時の終了、および有限性・範囲の検証。
- `engine/sycl/src/program/generate.cpp:2915-2923,2942-2947,2991-2992` — モデルメタデータとの優先順位と設定への反映。
- `engine/sycl/src/program/generate.cpp:3001-3024` — scaling type `none` での基底保持、検証、設定の登録。
- `engine/include/strata/kernels/rope_scaling.hpp:30-35,61-75,164-190` — 基底の既定値、設定の妥当性、プロセス定数としての適用条件。
- `engine/sycl/src/core/layer.cpp:952-962`、`engine/sycl/src/kernels/cuda/rope.dp.cpp:64-78`、`engine/sycl/src/kernels/cuda/native_rope.dp.cpp:258-262` — テーブル生成と解析 RoPE 経路で設定を使う箇所。
