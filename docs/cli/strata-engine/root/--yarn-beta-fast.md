# `--yarn-beta-fast`

調査対象: Strata commit `e17975c3bd27b75386f2fcc262485ff334282232`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--yarn-beta-fast` |
| 別名 | なし |
| 値 | 正の有限浮動小数点数 `F` |

## 役割

YaRN の RoPE 周波数補正ウィンドウの下端を決める beta 値です。`--rope-scaling yarn` で YaRN を有効にしたとき、回転次元のどの位置から補正を始めるかの計算に使われます。

## 使い方

```sh
strata generate --pack model.gguf --tokens 1,2,3 --max-new 1 --rope-scaling yarn --yarn-beta-fast 32
```

モデルと入力 token 列を指定して生成する例です。`--yarn-beta-fast` は単独では RoPE scaling の種類を有効にしません。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。既定値は `32.0` です。文字列全体が数値として厳密に解析されたかの確認はなく、先頭部分が数値なら後続文字があってもその数値部分が使われます。
- 変換後の値は有限で、かつ `0` より大きい必要があります。上限はこの parser の validation では設けられていません。
- `nan` / `inf` など有限でない値、および 0 以下の値は起動時 validation で拒否されます。数値として解釈できない文字列は `atof` により 0 となり、同じく拒否されます。
- 同じオプションを複数回指定すると、引数走査で後から読まれた値が設定を上書きします。

## 実行時の動作

parser は値を `Options::yarn_beta_fast` に格納し、RoPE 設定解決時に `RopeScaling::beta_fast` へ渡します。YaRN 補正窓の開始側は `floor(rope_yarn_corr_dim(..., beta_fast, ...))` で算出され、上端側は対応する `--yarn-beta-slow` の値から算出されます。このため、実際の位置は beta 値だけでなく回転次元数、元の context、周波数 base との組み合わせで決まります。

値の既定は 32 です。モデルの GGUF RoPE beta metadata をこの CLI 値に取り込む処理は、確認した engine の設定解決箇所にはありません。`--rope-scaling none`（または model metadata も scaling を指定しない場合）には補正ノブが使われず、同時にこの値自体の有限性・正値 validation は行われます。RoPE 設定は起動時に解決・設定されるもので、リクエスト単位の切り替えではありません。

engine の通常 parser と SYCL parser は同じ既定値、引数変換、validation、RoPE 設定反映を持ちます。

## 適用条件と副作用

- 有効な補正として使うには YaRN scaling を選ぶ必要があります。YaRN の設定をしない場合、この値を変えても回転設定への効果はありません。
- `--yarn-beta-slow` は補正窓の上端側を決める対になる値です。`--rope-scaling`、`--rope-scale`、`--yarn-orig-ctx` など、他の RoPE 設定と合わせて一つの起動時設定に解決されます。
- 直接のファイル変更やネットワーク処理はありません。非既定の RoPE scaling が有効な場合、起動時に解決した scaling 情報を標準エラーへ出力します。

## 出力とエラー

- 値がない場合は `--yarn-beta-fast needs a value` を標準エラーに出して終了コード 2 で終了します。
- 非有限値または 0 以下の場合は `invalid rope scaling knob` 系の診断を標準エラーに出し、終了コード 2 を返します。
- 指定値が正しくても、他の RoPE ノブを含む解決済み設定が不正なら `invalid rope scaling configuration` を標準エラーに出し、終了コード 2 で終了します。
- 未知の引数は `unknown argument: ...` と usage を標準エラーに出し、終了コード 2 を返します。

## 根拠

- `engine/src/program/generate.cpp:800` — option の保存先と既定値。
- `engine/src/program/generate.cpp:1278-1279` — usage 表示と既定値の説明。
- `engine/src/program/generate.cpp:3844-3847, 3879` — 必須値の取得と `std::atof` 変換。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数をエラーとして扱う経路。
- `engine/src/program/generate.cpp:5243-5248, 5260-5264` — 有限値・正値 validation と失敗時の終了コード。
- `engine/src/program/generate.cpp:5724-5726, 5749-5759` — YaRN beta を含む設定への反映と解決済み設定の validation。
- `engine/include/strata/kernels/rope_scaling.hpp:74-75, 92-100` — beta の既定値と beta fast/slow から補正窓を計算する処理。
- `engine/src/program/generate.cpp:5727-5738` — scaling type が `None` の場合に scaling ノブを無効化する処理。
- `engine/sycl/src/program/generate.cpp:484, 866-867, 1918, 2657-2679, 2998-3000`、`engine/sycl/include/strata/kernels/rope_scaling.hpp:74-75, 95-103` — SYCL parser と補正設定の対応実装。
- `docs/cli/README.md:1235`、`docs/cli/000_cli_tools.md:10` — 索引リンク、`strata-engine` の parser と root scope。
