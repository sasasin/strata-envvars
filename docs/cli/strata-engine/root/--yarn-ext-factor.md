# `--yarn-ext-factor`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数。`strata generate` として処理） |
| オプション | `--yarn-ext-factor` |
| 別名 | なし |
| 値 | 有限の浮動小数点数 `F`。`F >= -1` |

## 役割

YaRN の RoPE 補正深度を指定します。負値（既定値 `-1` を含む）は自動選択で、解決された RoPE scaling type が `yarn` なら `1`、それ以外なら `0` になります。`yarn` とともに `0` を明示すると補正を無効化し、`0` より大きい値はそのまま補正係数になります。これはエンジン起動時に一度解決され、リクエスト単位では変更できません。

## 使い方

```sh
strata --rope-scaling yarn --rope-scale 1.5 --yarn-ext-factor 1 MODEL.gguf
```

`MODEL.gguf` と併せて YaRN scaling を指定し、補正係数を `1.5` に設定する例です。通常は `--yarn-ext-factor` を省略して自動値を使えます。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。既定値は `-1.0` です（parser 定義: `engine/src/program/generate.cpp:798`、変換: `engine/src/program/generate.cpp:3877`。SYCL parser も同じ既定値・変換: `engine/sycl/src/program/generate.cpp:482,1916`）。
- `F < -1` は不正値として拒否されます。NaN や無限大も有限値検査で拒否されます。`-1 <= F < 0` はいずれも自動選択、`F = 0` は明示的な補正なし、`F > 0` は明示した補正係数です（`engine/src/program/generate.cpp:5243-5264`、SYCL: `engine/sycl/src/program/generate.cpp:2657-2679`）。
- parser は同じ option を複数回指定した場合に値を順次代入するため、最後の指定が残ります（`engine/src/program/generate.cpp:3877`）。
- 数値文字列の厳密な書式検査は `atof` の呼び出し前にはありません。変換後の有限性と下限が検査されます。

## 実行時の動作

- 自動値は、最終的に選ばれた scaling type に応じて決まります。`--rope-scaling` を指定すればその type がモデルファイルの type より優先され、省略時はモデルファイルの `rope.scaling.type` が使われます。従って `--rope-scaling none` では auto は `0`、`--rope-scaling yarn` では auto は `1` です（`engine/src/program/generate.cpp:5235-5241,5700-5723`）。
- `F >= 0` を明示した場合、その値が auto 判定に優先します。モデルファイルから読み込む RoPE metadata に ext factor は含まれず、この option の既定値 `-1` はモデルの ext-factor metadata を引き継ぐ指定ではありません。モデルの type・factor・original context の読み込み箇所は `engine/src/program/generate.cpp:5650-5674`、ext factor の解決は `engine/src/program/generate.cpp:5721-5725` です。
- type が `none` の場合、RoPE scaling 設定全体が既定値に戻され、補正係数は適用されません。`F > 0` など scaling knob が指定されていれば「scaling は有効でなく、`--yarn-*` は効果なし」という note が stderr に出ます（`engine/src/program/generate.cpp:5727-5739`）。
- YaRN type で scaling が有効な場合、係数は `RopeScaling` から kernel 引数へ渡されます。`0` は補正なし、`1` は full YaRN と定義され、補正ウィンドウ内の回転角補正の混合に使われます（`engine/include/strata/kernels/rope_scaling.hpp:66-75,105-116,149-157`）。係数が異なる場合の品質・性能の推奨値は、この実装調査からは判断できません。
- 解決済み設定はプロセスで一つだけ、startup 時に設定され、session 初期化の RoPE table 構築や kernel 実行時に参照されます（`engine/include/strata/kernels/rope_scaling.hpp:186-190`）。CUDA/HIP 系と SYCL 系の両 parser が同様に解決します（`engine/src/program/generate.cpp:5721-5759`、`engine/sycl/src/program/generate.cpp:2995-3024`）。

## 適用条件と副作用

- `none` では補正係数を含む scaling knobs は inert になり、明示値は note の対象になります（`engine/src/program/generate.cpp:5727-5739`）。scaling が有効な場合、補正係数は RoPE 補正ウィンドウ内の角度ブレンドに使われます（`engine/include/strata/kernels/rope_scaling.hpp:149-157`）。
- 他の関連値（`--rope-scaling`、`--rope-scale`、`--rope-freq-scale`、`--yarn-attn-factor` など）と一緒に最終 RoPE 設定として検証されます。個別 option 文書は [`docs/cli/README.md`](../../README.md) の `strata-engine` 節を参照してください。
- 起動時に一度設定し、キャッシュ内の key は RoPE 適用後に保存されるため、実行中に係数を切り替える CLI 経路はありません（`engine/src/program/generate.cpp:788-792`、`engine/include/strata/kernels/rope_scaling.hpp:186-190`）。

## 出力とエラー

- `F` が有限値でない場合は stderr に `a rope scaling knob is not a finite number` を出し、終了コード `2` で終了します。`F < -1` は `invalid rope scaling knob` を stderr に出し、終了コード `2` です（CUDA/HIP: `engine/src/program/generate.cpp:5243-5264`、SYCL: `engine/sycl/src/program/generate.cpp:2657-2679`）。
- 解決済み設定が無効な場合も stderr に `invalid rope scaling configuration` と理由を出して終了コード `2` になります（`engine/src/program/generate.cpp:5749-5759`）。
- scaling が有効なら stderr に scaling type、factor、frequency scale、base、mscale、context 情報が出ます。係数を含む YaRN magnitude correction が実際に有効な場合は、追加の note も出ます（`engine/src/program/generate.cpp:5760-5778`）。

## 根拠

- `engine/src/program/generate.cpp:798,3877` — CUDA/HIP 系 parser の既定値と値の取り込み。
- `engine/sycl/src/program/generate.cpp:482,1916` — SYCL parser の既定値と値の取り込み。
- `engine/src/program/generate.cpp:5235-5264,5700-5759` — CLI 値の検証、type による auto 解決、`none` 時の無効化、設定の登録と失敗経路。
- `engine/sycl/src/program/generate.cpp:2657-2679,2974-3024` — SYCL 系での検証と同等の設定解決。
- `engine/include/strata/kernels/rope_scaling.hpp:66-90,105-116,149-157,165-190` — 係数の意味、kernel への受け渡し、設定検証と起動時適用。
- 索引照合: `docs/cli/README.md:1036-1041,1234-1238` — `strata-engine` の root scope と当該 option のリンク。

調査範囲は上記 revision の Strata 所有 parser・設定解決・RoPE scaling 実装です。help は実行せず、外部 ggml/CUDA/HIP/SYCL 実装の挙動や実測性能は根拠にしていません。
