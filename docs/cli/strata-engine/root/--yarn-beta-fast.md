# `--yarn-beta-fast`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | CMake 生成の `strata` 推論エンジン（`generate` 実行経路） |
| オプション | `--yarn-beta-fast` |
| 別名 | なし |
| 値 | `F`。`atof` で double に変換し、有限かつ `F > 0` が必要 |

## 役割

YaRN の RoPE 補正窓を計算する fast 側の beta 値を指定します。YaRN が有効な場合、回転次元ごとの補正境界を決める計算に使われます。既定値は `32` です。

## 使い方

```sh
strata --pack MODEL.pack --yarn-beta-fast 32 --rope-scaling yarn --rope-scale 2
```

この例はエンジンの通常引数 parser を通る実行を示します。`--yarn-beta-fast` 単独では YaRN を有効にしません。

## 値と既定値

- 値は必須です。値を省略すると `next()` が `--yarn-beta-fast needs a value` を stderr に出して終了コード `2` で終了します。
- 既定値は `32.0` です。同じフラグを複数回指定した場合、parser は各出現を順に代入するため最後の値が残ります。
- 変換は `std::atof` です。値は parser 時点では厳密な数値文字列として検査されませんが、後段で全 RoPE knob の有限性と `yarn_beta_fast > 0` を検査します。`0`、負数、`nan`、`inf` は拒否され、数値に変換できない文字列は `atof` の結果 `0` となるため同じく拒否されます。正の値に上限はコード上で設けられていません。

## 実行時の動作

parser が値を `Options::yarn_beta_fast` に格納し、モデルの RoPE 設定を解決する際に `RopeScaling::beta_fast` へ渡します。`RopeScaling::corr_dims()` は `beta_fast` を使って補正窓の下端を計算し、上端には `--yarn-beta-slow` の値を使います。この窓は回転ペアの補間・外挿の混合範囲に関わります。

YaRN の場合、既定の `--yarn-ext-factor` は自動で `1` になり、この補正窓が回転計算で使用されます。`--rope-scaling` が未指定ならモデル GGUF の `rope.scaling.type` があればその種類を使い、明示した `none` はモデルの種類を無効化します。解決された種類が `none` の場合は scaling knob がリセットされ、beta 値は回転に影響しません。なお、この `none` 経路の注意メッセージ判定には beta fast/slow の変更自体は含まれないため、beta 値だけを変えても注意メッセージが出るとは限りません。

モデル GGUF から読み取る scaling metadata はコード上、type、factor、frequency base、original context です。beta fast/slow は CLI 側の値（それぞれ既定値 `32`、`1`）が設定されます。

## 適用条件と副作用

- 値の parser 検査は RoPE の種類にかかわらず行われるため、`none` を選んで効果がない場合も、不正な beta 値は拒否されます。
- 実際の値が回転に影響するのは補正を伴う scaling 構成です。標準的な YaRN では既定で補正が有効です。`none` では無効です。
- scaling は起動時に一度解決され、`session_init` より前にプロセス共通の設定としてセットされます。リクエストごとの切替はありません。
- このオプション固有のファイル書き込み、ネットワーク通信、子プロセス起動は確認できません。推論時の回転計算設定に作用します。

## 出力とエラー

- 非有限値または正でない値は `strata generate: a rope scaling knob is not a finite number (...)` または `strata generate: invalid rope scaling knob ...` を stderr に出し、終了コード `2` で終了します。
- scaling 設定の検証に失敗した場合は `invalid rope scaling configuration: ...` を stderr に出し、終了コード `2` で終了します。
- scaling が有効な場合、解決済みの種類・factor・周波数設定・context 情報を stderr に表示します。これは本フラグ値だけの専用表示ではありません。

## 根拠

- `src/program/generate.cpp:462` — parser オプション値の既定値 `32.0`。
- `src/program/generate.cpp:2418-2420,2453` — 値必須の処理と `atof` による parser 格納。
- `src/program/generate.cpp:3328-3350` — 有限性・正数の検証と失敗時の終了コード。
- `src/program/generate.cpp:3682-3707` — モデル metadata と CLI 値の解決、beta 値の設定。
- `src/program/generate.cpp:3708-3729` — `none` 時のリセット、注意表示条件、設定全体の検証。
- `src/program/generate.cpp:3731-3750` — 起動時設定の登録と stderr 出力。
- `include/strata/kernels/rope_scaling.hpp:66-75,92-100` — beta の既定値と補正窓境界の計算。
- `include/strata/kernels/rope_scaling.hpp:130-161` — 補正窓を使った角度の混合。
- `docs/DETAILS.md:1628-1638` — 利用者向け RoPE scaling 説明と固定適用に関する補足。値・実挙動の根拠は上記ソースを優先。

調査範囲は記載した checkout のソースです。同一 revision のビルド済みエンジンや Release artifact の help は照合していません。また、parser より前に別ファミリー実装へ振り分けられるモデル経路について、その実装が同じフラグを受理するかは確認していません。
