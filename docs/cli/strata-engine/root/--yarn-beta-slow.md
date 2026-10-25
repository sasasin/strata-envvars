# `--yarn-beta-slow`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の作業ツリーに未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（トップレベル。CMake で生成される推論エンジン） |
| オプション | `--yarn-beta-slow` |
| 別名 | なし |
| 値 | 数値（`double` として変換）。有限かつ `> 0` |

## 役割

YaRN の補正帯域の上端を決める beta 値です。RoPE のペア周波数ごとに補間と外挿を混ぜる境界計算に使われ、`--yarn-beta-fast` と組み合わせて補正区間を定めます。YaRN の回転設定が実際に有効なときに意味を持ちます。

## 使い方

```sh
strata --pack <pack-dir> --native <model.gguf> \
  --rope-scaling yarn --yarn-beta-slow 1.0
```

`--pack` と `--native` はエンジンのモデル入力例です。モデルやパックに必要な追加引数は環境に合わせて指定してください。

## 値と既定値

- 値は必須です。省略すると `--yarn-beta-slow needs a value` を標準エラーに出して終了コード 2 で終了します。
- 既定値は `1.0` です。オプションを複数回指定した場合、引数ループで後に処理された値が残ります。
- parser は `std::atof` で変換します。変換後の値が有限かつ正でなければ、起動時の rope knob 検証で拒否されます。したがって `0`、負数、`nan`、`inf` は無効です。正数への変換結果を持つ入力は受理されるため、厳密な数値文字列全体の検証ではありません。
- 値の上限や beta-fast との大小関係の検査はありません。

## 実行時の動作

`--yarn-beta-slow` は `Options::yarn_beta_slow` に保存され、モデルファイル由来の値ではなく CLI で指定した値（未指定時は既定値）が `RopeScaling::beta_slow` に設定されます。GGUF から読み出して優先順位を解決するのは scaling type、factor、frequency base、original context であり、beta-slow はそこから独立した CLI 値です。

`RopeScaling::corr_dims()` は beta-slow を使って補正区間の終端を計算し、その値は CUDA/SYCL の回転経路へ渡されます。補正が有効なら、区間終端より上のペアは補間側になり、区間内では外挿と補間を混ぜます。`--rope-scaling yarn` を指定した場合、ext-factor は既定で自動的に 1 となり、この境界が YaRN の角度に作用します。

## 適用条件と副作用

- `--rope-scaling none` では rope 設定を既定値に戻すため、beta-slow の指定は捨てられ、回転には作用しません。none 時に出る「knobs have no effect」の注記判定には beta-fast/beta-slow 自体が含まれないため、この値だけの指定では注記は出ません。
- `linear` では既定の ext-factor が 0 のため補正混合が無効で、beta-slow は角度に影響しません。`--yarn-ext-factor` を正に指定すると補正が有効になり、beta-slow が境界に使われます。
- 解決済み rope 設定は起動時に一度セットされ、セッション初期化で回転テーブルや kernel 設定を作ります。リクエスト単位で変更するオプションではありません。
- 設定はセッション構成にも含まれ、`rope.beta_slow` がセッション digest の入力になります。異なる値の回転設定は同じセッション構成として扱われません。
- YaRN / scaling の有効時には、起動時に解決済み scaling 情報を標準エラーへ出力します。beta 値単独の警告やファイル生成は確認できませんでした。

## 出力とエラー

- 値なし: 標準エラーに `--yarn-beta-slow needs a value`、終了コード 2。
- 数値変換結果が非有限または `<= 0`: 標準エラーに `invalid rope scaling knob ...`、終了コード 2。
- 値が有効でも、解決済み rope 設定全体が不正なら `invalid rope scaling configuration: ...` を標準エラーに出し、終了コード 2 で終了します。

## 根拠

- parser の既定値と利用説明: `src/program/generate.cpp:450-463`, `src/program/generate.cpp:875-877`
- parser と値の変換、欠落値の扱い: `src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2450-2454`
- 有限性・正数 validation: `src/program/generate.cpp:3312-3350`
- GGUF と CLI の解決、beta-slow の設定、none 時の無効化、出力と設定全体の検証: `src/program/generate.cpp:3681-3750`
- 補正境界への beta-slow の反映と kernel 引数: `include/strata/kernels/rope_scaling.hpp:92-116`
- 回転テーブルで補正帯域を角度に使う箇所: `src/kernels/cuda/rope.cu:61-84`
- セッション設定への値の受け渡し: `src/program/generate.cpp:9444-9448`
- セッション構成 digest への登録: `include/strata/core/conversation_file.hpp:61-67`, `src/core/conversation_file.cpp:887-895`

調査範囲は上記 commit のソースです。同一 revision の既存 CLI help、ビルド済みバイナリ、Release 配布物は補助資料として照合していません。実行例は parser と入力オプションを確認して記載しています。
