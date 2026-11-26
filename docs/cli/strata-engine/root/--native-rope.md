# `--native-rope`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、サブコマンドなし） |
| オプション | `--native-rope` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると有効 |

## 役割

QSA の RoPE（rotary positional embedding）処理で、通常の RoPE 経路に代えて実験的な native 算術カーネルを使います。CLI の説明文は「pinned text-only CUDA rotary arithmetic」としています。通常は無効で、モデル形状などがカーネルの対応条件を満たす必要があります。`--native SHARD1` プリセットを使う場合は、このフラグも自動で有効になります。

## 使い方

```sh
strata MODEL --native-rope
```

`MODEL` はエンジンが受け付けるモデル指定です。オプション自体は引数を取りません。ヘルプ文字列では実験的機能として案内されています（`engine/src/program/generate.cpp:1254`）。

## 値と既定値

`--native-rope` の parser はフラグを `true` にするだけで、値の読み取りや専用の CLI validation はありません。設定の初期値は `false` です（`engine/src/program/generate.cpp:802,3922`）。同じフラグを繰り返しても有効のままです。対応する `--no-native-rope` は parser にありません。

native kernel 側では、入力ポインタと stream が有効であること、行数が 1〜65535、head 幅が 128 または 256、回転次元が 64、RoPE scaling が有効、float32 バッファが 4-byte aligned であることを検証します。部分的に重なるバッファも拒否します。条件を満たさない場合は `std::invalid_argument`、起動時の CUDA エラーは `std::runtime_error` になります（`engine/src/kernels/cuda/native_rope.cu:194-223`）。これらは parser 時ではなく、native 経路が呼び出された時点の検証です。

## 実行時の動作

parser の設定は `native_rope_set_enabled` に渡され、カーネル側の有効状態になります（`engine/src/program/generate.cpp:6123`、`engine/src/kernels/cuda/native_rope.cu:178-179`）。有効時、QSA 層の正規化後のデータに native RoPE を適用し、無効時は `rope_neox_apply` を使います（`engine/src/core/layer.cpp:1154-1164`、`engine/src/core/verify.cpp:2028-2033`）。MTP の Q/K 処理にも同じ有効状態の分岐があります（`engine/src/core/mtp.cpp:1301-1306,2406-2419,2457-2477`）。native kernel は RoPE scaling から引数を作り、適合する場合は登録済みの cos/sin table を利用し、そうでない場合は native 算術経路で起動します（`engine/src/kernels/cuda/native_rope.cu:173-176,209-220`）。

`--native-qsa` と native RoPE がともに有効で、head 幅が 128/256 かつ回転次元が 64 などの条件を満たす場合、QSA の norm と RoPE をまとめた経路が選ばれます。通常の native RoPE 呼び出しへフォールバックする分岐もあります（`engine/src/core/verify.cpp:2030-2037`、usable 条件は `engine/src/kernels/cuda/native_rope.cu:180-191`）。また、`--native SHARD1` は `native_rope` を含む複数の native 設定をまとめて有効にします（`engine/src/program/generate.cpp:5160-5165`）。

## 適用条件と副作用

フラグを設定しただけでは全モデルで即時に native kernel が実行されるとは限らず、実際に対象の QSA/MTP RoPE 経路へ到達した時に使用されます。呼び出し時の形状・alignment・scaling 条件は上記の kernel validation に従い、不適合なら実行時エラーになります。QSA の呼び出し側は例外を捕捉してエラー文字列にし、処理失敗を返します（`engine/src/core/layer.cpp:1154-1164`）。MTP 側も例外を捕捉して `err` に設定し、失敗を返す経路があります（`engine/src/core/mtp.cpp:1293-1298,2438-2442`）。

このフラグ自体がファイルやネットワークを操作する処理は確認できません。native kernel は device stream に計算を投入し、直後に取得できる kernel launch error を例外にします（`engine/src/kernels/cuda/native_rope.cu:215-223`）。性能上の効果や特定モデルでの適合可否は、このソース調査だけでは保証できません。

## 出力とエラー

parser はこのフラグ固有の警告や validation error を出しません。native kernel の引数・バッファ条件を満たさない場合は `native RoPE requires aligned F32 rows, width 128/256, rotation 64, valid base/scaling and explicit stream`、バッファの部分重複では `native RoPE buffers partially overlap` の例外になります。kernel 起動エラーも例外になります（`engine/src/kernels/cuda/native_rope.cu:196-223`）。呼び出し元がそれを処理エラーへ変換する箇所は上記の通りです。CLI 全体での最終的な終了コードや標準出力・標準エラーへの表示形式は、ここで確認した呼び出し範囲だけからは特定できません。

## 根拠

- `engine/src/program/generate.cpp:802,1254,3922` — 既定値、help 表示、parser 登録。
- `engine/src/program/generate.cpp:5160-5165,6123` — `--native` プリセットとの関係と実行時有効化。
- `engine/src/core/layer.cpp:1154-1164`、`engine/src/core/verify.cpp:2028-2037` — QSA の通常/native 分岐、融合条件、例外処理。
- `engine/src/core/mtp.cpp:1301-1306,2406-2419,2438-2442,2457-2477` — MTP での適用箇所と例外処理。
- `engine/src/kernels/cuda/native_rope.cu:173-223` — 有効状態、対応条件、RoPE kernel 呼び出しとエラー。
